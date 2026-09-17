"""Tests for the Dantzig-Wolfe decomposition logic that does not need a solver."""

from types import SimpleNamespace

import pandas as pd
import pytest

from reho.model.master_problem import MasterProblem, fix_unit_sizes
from reho.model.reho import REHO


@pytest.fixture
def master():
    """A master problem reduced to the attributes the objective weighting reads."""
    mp = MasterProblem.__new__(MasterProblem)
    mp.flags = {"TOTEX": 0, "CAPEX": 0, "OPEX": 0, "GWP": 0}
    mp.method = {"building-scale": False}
    return mp


class TestObjectiveWeights:
    def test_objective_gets_a_weight_of_one(self, master):
        scenario, beta = master.get_beta_values({"Objective": "GWP", "EMOO": {}})
        assert scenario["Objective"] == "SP_obj_fct"
        assert beta["GWP"] == 1
        assert beta[["TOTEX", "CAPEX", "OPEX"]].tolist() == [1e-6] * 3

    def test_initiation_weights_opex_when_minimizing_totex(self, master):
        _, beta = master.get_beta_values({"Objective": "TOTEX", "EMOO": {}}, beta=1000.0)
        assert (beta["CAPEX"], beta["OPEX"]) == (1, 1000.0)

    def test_initiation_weights_capex_when_minimizing_opex(self, master):
        # Weighting OPEX by beta would only rescale the objective, and the three initiations
        # would propose the same configuration.
        _, beta = master.get_beta_values({"Objective": "OPEX", "EMOO": {}}, beta=1000.0)
        assert (beta["OPEX"], beta["CAPEX"]) == (1, 1000.0)

    def test_initiation_weights_the_constrained_objective(self, master):
        _, beta = master.get_beta_values({"Objective": "TOTEX", "EMOO": {"EMOO_GWP": 5.0, "EMOO_grid": 0.0}}, beta=0.001)
        assert beta["GWP"] == 0.001

    def test_the_scenario_given_is_left_unchanged(self, master):
        # The buildings of a sequential run share the scenario: removing the epsilon constraints
        # from it changed the weights of every building but the first.
        scenario = {"Objective": "TOTEX", "EMOO": {"EMOO_GWP": 5.0, "EMOO_grid": 0.0}}
        returned, _ = master.get_beta_values(scenario, beta=1.0)

        assert scenario == {"Objective": "TOTEX", "EMOO": {"EMOO_GWP": 5.0, "EMOO_grid": 0.0}}
        assert returned["EMOO"] == {"EMOO_grid": 0.0}

    def test_several_constrained_objectives_raise(self, master):
        with pytest.raises(ValueError):
            master.get_beta_values({"Objective": "TOTEX", "EMOO": {"EMOO_GWP": 5.0, "EMOO_CAPEX": 1.0}}, beta=1.0)


class TestWorkerPool:
    @staticmethod
    def _master(**method):
        mp = MasterProblem.__new__(MasterProblem)
        mp.method = {"district-scale": True, "building-scale": False, "parallel_computation": True, **method}
        mp.pool = None
        mp.cpu_use = 1
        return mp

    def test_no_pool_without_parallel_computation(self):
        with self._master(parallel_computation=False).worker_pool() as pool:
            assert pool is None

    def test_no_pool_for_the_compact_formulation(self):
        with self._master(**{"district-scale": False}).worker_pool() as pool:
            assert pool is None

    def test_the_block_that_opens_the_pool_closes_it(self):
        master = self._master()
        with master.worker_pool() as pool:
            with master.worker_pool() as nested:
                assert nested is pool
            assert master.pool is pool  # the nested block left it open
            assert pool.apply_async(abs, (-3,)).get(timeout=120) == 3
        assert master.pool is None
        with pytest.raises(ValueError):  # "Pool not running"
            pool.apply_async(abs, (-3,))

    def test_an_exception_terminates_the_pool(self):
        master = self._master()
        with pytest.raises(KeyError):
            with master.worker_pool():
                raise KeyError("stop")
        assert master.pool is None


class _FixingAMPL:
    """Stand-in for an AMPL session that records the values its variables are fixed to."""

    def __init__(self):
        self.fixed = {}

    def getVariable(self, variable):
        fixed = self.fixed

        class Instances:
            def get(self, unit):
                class Instance:
                    def fix(self, value):
                        fixed[variable, unit] = value
                return Instance()
        return Instances()


class TestFixUnitSizes:
    df_fix_Units = pd.DataFrame({"Units_Mult": [10.0, 4.0, 2.0], "Units_Use": [1, 1, 1]},
                                index=["PV_Building1", "rSOC_Building1", "PV_Building10"])

    def test_the_units_of_the_problem_that_are_sized_are_fixed(self):
        ampl = _FixingAMPL()
        fix_unit_sizes(ampl, self.df_fix_Units, ["PV_Building1", "rSOC_Building1", "Battery_Building1"])
        assert ampl.fixed == {("Units_Mult", "PV_Building1"): 10.0 * (1 - 1e-9), ("Units_Use", "PV_Building1"): 1.0,
                              ("Units_Mult", "rSOC_Building1"): 4.0, ("Units_Use", "rSOC_Building1"): 1.0}

    def test_the_listed_technologies_not_sized_are_not_installed(self):
        ampl = _FixingAMPL()
        fix_unit_sizes(ampl, self.df_fix_Units, ["PV_Building1", "rSOC_Building1", "MTR_Building1"],
                       targets=["rSOC_Building1", "MTR_Building1", "ETZ_Building1"])
        assert ampl.fixed == {("Units_Mult", "rSOC_Building1"): 4.0, ("Units_Use", "rSOC_Building1"): 1.0,
                              ("Units_Mult", "MTR_Building1"): 0, ("Units_Use", "MTR_Building1"): 0}


class TestFixUnitSizesOfTheCompactFormulation:
    """``REHO.fix_unit_sizes`` fixes the units of the buildings and, in the compact formulation, those of the district."""

    @staticmethod
    def reho(fix_units_list=()):
        infrastructure = SimpleNamespace(
            houses={"Building1": {}, "Building2": {}},
            UnitsOfHouse={"Building1": ["PV_Building1", "rSOC_Building1"], "Building2": ["PV_Building2"]},
            UnitsOfDistrict=["rSOC_district"])
        df_fix_Units = pd.DataFrame({"Units_Mult": [10.0, 4.0, 6.0, 50.0], "Units_Use": [1, 1, 1, 1]},
                                    index=["PV_Building1", "rSOC_Building1", "PV_Building2", "rSOC_district"])
        return SimpleNamespace(infrastructure=infrastructure, df_fix_Units=df_fix_Units, fix_units_list=list(fix_units_list))

    def test_every_unit_sized_is_fixed(self):
        ampl = _FixingAMPL()
        REHO.fix_unit_sizes(self.reho(), ampl)
        assert {unit for _, unit in ampl.fixed} == {"PV_Building1", "rSOC_Building1", "PV_Building2", "rSOC_district"}
        assert ampl.fixed["Units_Mult", "rSOC_district"] == 50.0

    def test_a_building_is_fixed_alone(self):
        ampl = _FixingAMPL()
        REHO.fix_unit_sizes(self.reho(), ampl, house="Building2")
        assert ampl.fixed == {("Units_Mult", "PV_Building2"): 6.0 * (1 - 1e-9), ("Units_Use", "PV_Building2"): 1.0}

    def test_the_listed_technologies_are_fixed_in_the_buildings_and_the_district(self):
        ampl = _FixingAMPL()
        REHO.fix_unit_sizes(self.reho(fix_units_list=["rSOC", "rSOC_district"]), ampl)
        assert ampl.fixed == {("Units_Mult", "rSOC_Building1"): 4.0, ("Units_Use", "rSOC_Building1"): 1.0,
                              ("Units_Mult", "rSOC_district"): 50.0, ("Units_Use", "rSOC_district"): 1.0}
