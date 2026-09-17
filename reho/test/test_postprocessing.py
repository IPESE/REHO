"""Tests for the post-processing of the results: indicators, sensitivity analysis."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from reho.model.postprocessing.KPIs import postcompute_annual_COP
from reho.model.postprocessing.sensitivity_analysis import SensitivityAnalysis


class TestAnnualCOP:
    @pytest.fixture
    def infrastructure(self):
        heat_pumps = ["HeatPump_Air_Building1", "HeatPump_Geothermal_Building1",
                      "HeatPump_Air_Building2", "HeatPump_Geothermal_Building2"]
        return SimpleNamespace(
            UnitsOfType={"HeatPump": np.array(heat_pumps)},
            UnitsOfHouse={"Building1": np.array(heat_pumps[:2] + ["PV_Building1"]),
                          "Building2": np.array(heat_pumps[2:])},
        )

    @pytest.fixture
    def df_annuals(self):
        rows = {
            # Building1 only uses its second heat pump
            ("Electricity", "HeatPump_Air_Building1"): (0.0, 0.0),
            ("SH", "HeatPump_Air_Building1"): (0.0, 0.0),
            ("Electricity", "HeatPump_Geothermal_Building1"): (10.0, 0.0),
            ("SH", "HeatPump_Geothermal_Building1"): (0.0, 30.0),
            ("DHW", "HeatPump_Geothermal_Building1"): (0.0, 10.0),
            # Building2 uses both
            ("Electricity", "HeatPump_Air_Building2"): (5.0, 0.0),
            ("SH", "HeatPump_Air_Building2"): (0.0, 15.0),
            ("Electricity", "HeatPump_Geothermal_Building2"): (5.0, 0.0),
            ("SH", "HeatPump_Geothermal_Building2"): (0.0, 25.0),
        }
        index = pd.MultiIndex.from_tuples(rows, names=["Layer", "Hub"])
        return pd.DataFrame(list(rows.values()), index=index, columns=["Demand_MWh", "Supply_MWh"])

    def test_heat_pumps_of_a_building_are_combined(self, df_annuals, infrastructure):
        cop = postcompute_annual_COP(df_annuals, infrastructure)["COP"]
        assert cop["Building1"] == pytest.approx(4.0)
        assert cop["Building2"] == pytest.approx(4.0)
        assert cop["Network"] == pytest.approx(80 / 20)

    def test_no_electricity_gives_nan(self, df_annuals, infrastructure):
        df_annuals["Demand_MWh"] = 0.0
        assert postcompute_annual_COP(df_annuals, infrastructure)["COP"].isna().all()


class TestSensitivityAnalysis:
    @pytest.fixture
    def reho(self):
        periods = pd.MultiIndex.from_product([[1, 2], [1, 2]], names=["Period", "Time"])
        annuals = pd.DataFrame(
            {"Demand_MWh": [1.0, 2.0, 0.0, 0.0, 5.0], "Supply_MWh": [3.0, 4.0, 6.0, 7.0, 0.0]},
            index=pd.MultiIndex.from_tuples([("Electricity", "Network"), ("NaturalGas", "Network"), ("Electricity", "PV_Building1"),
                                             ("SH", "NG_Boiler_Building1"), ("Electricity", "Building1")], names=["Layer", "Hub"]),
        )
        grid_t = pd.DataFrame({"Grid_demand": 1.0, "Grid_supply": 2.0}, index=pd.MultiIndex.from_tuples(
            [(layer, hub, p, t) for layer in ["Electricity", "NaturalGas"] for hub in ["Building1", "Network"] for p, t in periods],
            names=["Layer", "Hub", "Period", "Time"]))
        unit_t = pd.DataFrame({"Units_demand": 0.0, "Units_supply": 1.0}, index=pd.MultiIndex.from_tuples(
            [("Electricity", unit, p, t) for unit in ["PV_Building1", "NG_Boiler_Building1"] for p, t in periods],
            names=["Layer", "Unit", "Period", "Time"]))
        results = {
            "df_Annuals": annuals,
            "df_Grid_t": grid_t,
            "df_Unit": pd.DataFrame({"Units_Mult": [10.0, 5.0]}, index=pd.Index(["PV_Building1", "NG_Boiler_Building1"], name="Unit")),
            "df_Performance": pd.DataFrame({"Costs_inv": [100.0, 100.0], "Costs_op": [50.0, 50.0], "Costs_rep": [10.0, 10.0]},
                                           index=pd.Index(["Building1", "Network"], name="Hub")),
            "df_Unit_t": unit_t,
        }
        return SimpleNamespace(scenario={"name": "totex", "exclude_units": []},
                               infrastructure=SimpleNamespace(UnitTypes=np.array(["PV", "NG_Boiler"])),
                               results={"totex": {"Elec_retail_0.3": results}})

    def test_results_of_an_optimization_are_recorded(self, reho):
        sa = SensitivityAnalysis(reho, SA_type="Morris")
        sa.extract_results(reho, 0, Pareto_ID="Elec_retail_0.3")

        assert sa.objective_values == [pytest.approx(160.0)]
        assert sa.SA_results["num_optimizations"] == [0]
        energy = sa.SA_results["dict_res_ES"][0]
        assert energy["E_unit"] == {"PV": 6.0, "NG_Boiler": 7.0}
        assert energy["E_unit_PV"].tolist() == [2.0, 2.0]
        assert sa.SA_results["dict_df_results"][0]["NG_Network_t"] is not None
