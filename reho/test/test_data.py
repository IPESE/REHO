"""Integrity checks on the data files shipped with REHO.

These files are inputs of every optimization: a missing column, a stray decimal
comma or a technology referring to an undeclared energy layer produces a model
that either fails deep inside AMPL or, worse, solves a subtly different problem.
Checking them here is cheap and needs neither a solver nor a database.
"""

import os

import pytest

from reho.model.infrastructure import initialize_grids, initialize_units, prepare_units_df
from reho.paths import file_reader, path_to_infrastructure, path_to_mobility, path_to_sia, path_to_skydome

#: Columns every units file must declare, and which :func:`prepare_units_df` reads.
UNIT_COLUMNS = [
    "Unit", "ref_unit", "Units_Fmin", "Units_Fmax", "Cost_inv1", "Cost_inv2",
    "GWP_unit1", "GWP_unit2", "lifetime", "UnitOfType", "UnitOfLayer",
    "UnitOfService", "StreamsOfUnit", "Units_flowrate_in", "Units_flowrate_out",
    "stream_Tin", "stream_Tout",
]

UNIT_FILES = ["building_units.csv", "building_units_IP.csv", "district_units.csv", "district_units_IP.csv"]

#: Services a unit may declare. Must stay in sync with ``Infrastructure.Services``.
KNOWN_SERVICES = {"DHW", "SH", "Cooling", "rSOC_heat"}


@pytest.fixture(scope="module")
def layers():
    return file_reader(os.path.join(path_to_infrastructure, "layers.csv"))


class TestLayers:
    def test_required_columns(self, layers):
        required = {"Grid", "ref_unit", "Cost_demand_cst", "Cost_supply_cst",
                    "GWP_demand_cst", "GWP_supply_cst", "Network_ext", "Network_lifetime"}
        assert required <= set(layers.columns)

    def test_grid_names_are_unique(self, layers):
        assert layers["Grid"].is_unique

    def test_costs_and_emissions_are_non_negative(self, layers):
        for column in ["Cost_demand_cst", "Cost_supply_cst", "GWP_demand_cst", "GWP_supply_cst"]:
            assert (layers[column] >= 0).all(), f"{column} holds a negative value"

    def test_supply_is_not_cheaper_than_demand(self, layers):
        # Buying energy must cost at least as much as selling it back, otherwise the
        # model can make money by cycling energy through the grid.
        cheaper = layers[layers["Cost_supply_cst"] < layers["Cost_demand_cst"]]["Grid"].tolist()
        assert not cheaper, f"These layers pay more for exports than they charge for imports: {cheaper}"

    def test_reinforcement_steps_are_increasing(self, layers):
        for _, row in layers.iterrows():
            steps = [float(v) for v in str(row["ReinforcementOfNetwork"]).split("/")]
            assert steps == sorted(steps), f"ReinforcementOfNetwork of {row['Grid']} is not increasing: {steps}"


class TestUnits:
    @pytest.mark.parametrize("file_name", UNIT_FILES)
    def test_required_columns(self, file_name):
        units = file_reader(os.path.join(path_to_infrastructure, file_name))
        missing = [column for column in UNIT_COLUMNS if column not in units.columns]
        assert not missing, f"{file_name} is missing the columns {missing}"

    @pytest.mark.parametrize("file_name", UNIT_FILES)
    def test_unit_names_are_unique(self, file_name):
        units = file_reader(os.path.join(path_to_infrastructure, file_name))
        duplicates = units["Unit"][units["Unit"].duplicated()].tolist()
        assert not duplicates, f"{file_name} declares these units twice: {duplicates}"

    @pytest.mark.parametrize("file_name", UNIT_FILES)
    def test_sizes_and_costs_are_consistent(self, file_name):
        units = file_reader(os.path.join(path_to_infrastructure, file_name))
        for _, row in units.iterrows():
            assert row["Units_Fmin"] <= row["Units_Fmax"], f"{row['Unit']}: Units_Fmin exceeds Units_Fmax"
            assert row["lifetime"] > 0, f"{row['Unit']}: lifetime must be positive"
            for column in ["Cost_inv1", "Cost_inv2", "GWP_unit1", "GWP_unit2"]:
                assert row[column] >= 0, f"{row['Unit']}: {column} is negative"

    @pytest.mark.parametrize("file_name", UNIT_FILES)
    def test_layers_are_declared(self, file_name, layers):
        known = set(layers["Grid"]) | {"HeatCascade"}
        units = prepare_units_df(os.path.join(path_to_infrastructure, file_name), grids=None)
        for _, row in units.iterrows():
            unknown = [layer for layer in row["UnitOfLayer"] if layer and layer not in known]
            assert not unknown, f"{row['Unit']} uses the undeclared layers {unknown}"

    @pytest.mark.parametrize("file_name", UNIT_FILES)
    def test_services_are_known(self, file_name):
        units = prepare_units_df(os.path.join(path_to_infrastructure, file_name), grids=None)
        for _, row in units.iterrows():
            unknown = [s for s in row["UnitOfService"] if s and s not in KNOWN_SERVICES]
            assert not unknown, f"{row['Unit']} declares the unknown services {unknown}"

    @pytest.mark.parametrize("file_name", UNIT_FILES)
    def test_stream_temperatures_match_the_streams(self, file_name):
        units = prepare_units_df(os.path.join(path_to_infrastructure, file_name), grids=None)
        for _, row in units.iterrows():
            streams = [s for s in row["StreamsOfUnit"] if s]
            if not streams:
                continue
            for column in ["stream_Tin", "stream_Tout"]:
                values = [v for v in row[column] if v != ""]
                assert len(values) == len(streams), \
                    f"{row['Unit']}: {len(streams)} stream(s) but {len(values)} value(s) in {column}"

    @pytest.mark.parametrize("file_name", UNIT_FILES)
    def test_hot_streams_cool_down_and_cold_streams_heat_up(self, file_name):
        units = prepare_units_df(os.path.join(path_to_infrastructure, file_name), grids=None)
        for _, row in units.iterrows():
            for stream, t_in, t_out in zip(row["StreamsOfUnit"], row["stream_Tin"], row["stream_Tout"]):
                if not stream or t_in == "" or t_out == "":
                    continue
                if stream.startswith("h_"):
                    assert t_in >= t_out, f"{row['Unit']}: hot stream {stream} heats up ({t_in} -> {t_out})"
                elif stream.startswith("c_"):
                    assert t_in <= t_out, f"{row['Unit']}: cold stream {stream} cools down ({t_in} -> {t_out})"


class TestInitialization:
    def test_default_grids(self):
        grids = initialize_grids()
        assert set(grids) == {"Electricity", "NaturalGas"}

    def test_units_are_filtered_by_the_available_layers(self):
        # A unit burning natural gas cannot be offered when the layer is absent.
        electricity_only = initialize_grids({"Electricity": {}})
        units = initialize_units({"exclude_units": []}, electricity_only)
        types = {unit["UnitOfType"] for unit in units["building_units"]}
        assert "NG_Boiler" not in types
        assert "ElectricalHeater" in types

    def test_district_units_are_opt_in(self):
        grids = initialize_grids()
        assert len(initialize_units({"exclude_units": []}, grids)["district_units"]) == 0
        assert len(initialize_units({"exclude_units": []}, grids, district_data=True)["district_units"]) > 0


class TestOtherDataFiles:
    @pytest.mark.parametrize(
        "path",
        [
            os.path.join(path_to_infrastructure, "U_values.csv"),
            os.path.join(path_to_infrastructure, "renovation.csv"),
            os.path.join(path_to_infrastructure, "HP_parameters.csv"),
            os.path.join(path_to_infrastructure, "AC_parameters.csv"),
            os.path.join(path_to_mobility, "dailyprofiles.csv"),
            os.path.join(path_to_mobility, "dailyprofiles_metadata.csv"),
            os.path.join(path_to_sia, "sia2024_rooms_sia380_1.csv"),
            os.path.join(path_to_skydome, "skydome.csv"),
            os.path.join(path_to_skydome, "total_irradiation.csv"),
        ],
    )
    def test_file_is_readable_and_not_empty(self, path):
        df = file_reader(path)
        assert not df.empty, f"{path} is empty"

    def test_u_values_are_positive_and_periods_unique(self):
        u_values = file_reader(os.path.join(path_to_infrastructure, "U_values.csv"))
        assert u_values["period"].is_unique
        numeric = u_values.drop(columns="period")
        assert (numeric > 0).all().all(), "U_values.csv holds a non-positive U-value"

    def test_renovation_targets_improve_on_the_existing_envelope(self):
        u_values = file_reader(os.path.join(path_to_infrastructure, "U_values.csv")).set_index("period")
        offenders = []
        for element in ["facade", "footprint", "roof", "window"]:
            worse = u_values[u_values[f"U_required_{element}"] > u_values[f"U_{element}"]]
            offenders += [f"{element} ({period})" for period in worse.index]
        assert not offenders, f"Renovation target worse than the existing envelope for: {offenders}"

    def test_skydome_patches_are_consistent(self):
        skydome = file_reader(os.path.join(path_to_skydome, "skydome.csv"))
        irradiation = file_reader(os.path.join(path_to_skydome, "total_irradiation.csv"))
        assert len(irradiation.columns) - 1 == len(skydome), \
            "total_irradiation.csv must hold one column per sky patch, plus the time column"
