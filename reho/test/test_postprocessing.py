"""Tests for the post-processing of the results: indicators."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from reho.model.postprocessing.KPIs import postcompute_annual_COP


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
