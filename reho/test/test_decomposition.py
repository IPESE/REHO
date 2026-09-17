"""Tests for the Dantzig-Wolfe decomposition logic that does not need a solver."""

import pytest

from reho.model.master_problem import MasterProblem


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
