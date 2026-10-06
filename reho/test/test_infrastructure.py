import os
import re

import numpy as np
import pandas as pd
import pytest
from reho.model.infrastructure import (
    PERFORMANCE_MAP_FILES,
    Infrastructure,
    _interperiod_unit_files,
    initialize_grids,
    initialize_units,
    network_capacity_options,
    parse_capacity_options,
    read_performance_map,
)
from reho.model.master_problem import MasterProblem, check_parameters
from reho.paths import path_to_infrastructure, path_to_units


@pytest.fixture(scope="module")
def qbuildings_data(sample_buildings_data):
    return sample_buildings_data


@pytest.fixture(scope="module")
def scenario():
    return {'exclude_units': ['ThermalSolar'], 'enforce_units': []}


@pytest.fixture(scope="module")
def grids():
    return initialize_grids()


@pytest.fixture(scope="module")
def units(scenario, grids):
    return initialize_units(scenario, grids)


@pytest.fixture(scope="module")
def infrastructure(qbuildings_data, units, grids):
    return Infrastructure(qbuildings_data, units, grids)


def test_infrastructure_not_empty(infrastructure):
    assert not infrastructure.Units_flowrate.empty
    assert not infrastructure.Grids_Parameters.empty
    assert not infrastructure.Units_Parameters.empty


def test_infrastructure_initialization(infrastructure):
    assert 'HeatCascade' in infrastructure.Layers
    assert 'Electricity' in infrastructure.Layers
    assert 'Building1' in infrastructure.House
    assert 'Building2' in infrastructure.House

    assert set(infrastructure.grids.keys()) == {'Electricity', 'NaturalGas'}
    # ThermalSolar is listed in `units_to_keep` in prepare_units_df, so it is always retained
    # even when the scenario excludes it (alongside PV, Battery, WaterTankSH/DHW).
    assert 'ThermalSolar' in infrastructure.UnitTypes
    assert np.array_equal(infrastructure.LayersOfType['HeatCascade'], np.array(['HeatCascade']))
    assert infrastructure.UnitsOfDistrict.size == 0


def test_infrastructure_edge_cases(infrastructure):
    with pytest.raises(KeyError):
        Infrastructure({}, {}, {})

    with pytest.raises(KeyError):
        infrastructure.grids['NonExistentGrid']


def test_units_are_named_after_their_building(infrastructure):
    for house in infrastructure.House:
        for unit in infrastructure.UnitsOfHouse[house]:
            assert unit.endswith("_" + house)


def test_every_unit_belongs_to_a_type_and_a_layer(infrastructure):
    all_of_type = {unit for units in infrastructure.UnitsOfType.values() for unit in units}
    all_of_layer = {unit for units in infrastructure.UnitsOfLayer.values() for unit in units}
    assert set(infrastructure.Units) == all_of_type
    assert set(infrastructure.Units) <= all_of_layer


def test_unit_parameters_cover_every_unit(infrastructure):
    assert set(infrastructure.Units_Parameters.index) == set(infrastructure.Units)


def test_streams_are_classified_as_hot_or_cold(infrastructure):
    # Streams_Hin / Streams_Hout are complementary flags driving the heat cascade.
    streams_h = infrastructure.Streams_H
    assert ((streams_h["Streams_Hin"] + streams_h["Streams_Hout"]) == 1).all()


def test_excluding_a_heating_unit_removes_it(grids):
    from reho.model.infrastructure import initialize_units
    units = initialize_units({"exclude_units": ["NG_Boiler"]}, grids)
    assert "NG_Boiler" not in {unit["Unit"] for unit in units["building_units"]}


@pytest.mark.parametrize("unit_type, model_file", [("HeatPump", "heatpump.mod"), ("AirConditioner", "air_conditioner.mod"),
                                                     ("HeatPump_WH", "heatpump_waste_heat.mod")])
def test_performance_maps_fill_sets_of_the_model(unit_type, model_file):
    """The index columns of a performance map are named after sets of the model of the unit."""
    with open(os.path.join(path_to_units, model_file)) as model:
        declarations = model.read()
    performance = read_performance_map(unit_type)
    assert len(performance.index.names) == 2
    for temperatures in performance.index.names:
        assert re.search(rf"\bset {temperatures}\b", declarations), f"{temperatures} is not a set of {model_file}"


def test_performance_maps_cover_the_unit_types():
    assert set(PERFORMANCE_MAP_FILES) == {"HeatPump", "AirConditioner", "HeatPump_WH"}


def test_waste_heat_heat_pumps_share_the_map_of_the_heat_pumps():
    heat_pumps, waste_heat = read_performance_map("HeatPump"), read_performance_map("HeatPump_WH")
    assert list(waste_heat.columns) == [column + "_WH" for column in heat_pumps.columns]
    assert list(waste_heat.index.names) == [name + "_WH" for name in heat_pumps.index.names]
    assert (waste_heat.to_numpy() == heat_pumps.to_numpy()).all()


def test_a_unit_excluded_by_default_is_available_when_enforced(grids):
    def units(scenario):
        return {unit["Unit"] for unit in initialize_units(scenario, grids)["building_units"]}

    assert "HeatPump_Waste_heat" not in units({"exclude_units": [], "enforce_units": []})
    assert "HeatPump_Waste_heat" in units({"exclude_units": [], "enforce_units": ["HeatPump_Waste_heat"]})


_BUILDING_IP = os.path.join(path_to_infrastructure, "building_units_IP.csv")
_DISTRICT_IP = os.path.join(path_to_infrastructure, "district_units_IP.csv")


@pytest.mark.parametrize("interperiod_data, expected", [
    (None, (None, None)),
    (True, (_BUILDING_IP, _DISTRICT_IP)),
    ("building", (_BUILDING_IP, None)),
    ("district", (None, _DISTRICT_IP)),
    ({"building": True}, (_BUILDING_IP, None)),
    ({"district": "my_district_units_IP.csv"}, (None, "my_district_units_IP.csv")),
    ({"building": "my_units_IP.csv", "district": True}, ("my_units_IP.csv", _DISTRICT_IP)),
    ({"district_units_IP": "my_district_units_IP.csv"}, (None, "my_district_units_IP.csv")),
])
def test_interperiod_unit_files(interperiod_data, expected):
    assert _interperiod_unit_files(interperiod_data) == expected


@pytest.mark.parametrize("interperiod_data, error", [
    ("both", TypeError),
    ({"buildings": True}, KeyError),
    ({"building": 1}, TypeError),
])
def test_invalid_interperiod_data_is_rejected(interperiod_data, error):
    with pytest.raises(error):
        _interperiod_unit_files(interperiod_data)


def test_temperature_sets_come_from_the_performance_maps(infrastructure):
    heat_pumps = read_performance_map("HeatPump")
    assert list(infrastructure.Set["HP_Tsink"]) == list(heat_pumps.index.get_level_values("HP_Tsink").unique())
    assert list(infrastructure.Set["HP_Tsource"]) == list(heat_pumps.index.get_level_values("HP_Tsource").unique())


@pytest.mark.parametrize("value, expected", [
    ("600/1000/2000", [600, 1000, 2000]),
    ("600", [600]),
    (600, [600]),
    ([150, 200], [150, 200]),
    (np.array([150.0]), [150]),
    ("", []),
    (None, []),
    (np.nan, []),
])
def test_capacity_options_are_parsed(value, expected):
    assert list(parse_capacity_options(value)) == expected


def test_default_network_capacities(grids):
    assert grids["Electricity"]["Network_capacity_existing"] == 400
    assert list(grids["Electricity"]["Network_capacity_options"]) == [600, 1000, 2000]
    assert grids["NaturalGas"]["Network_capacity_options"].size == 0


def test_network_capacity_is_set_through_initialize_grids():
    grids = initialize_grids({"Electricity": {"Network_capacity_existing": 100, "Network_capacity_options": [150, 200]}})
    assert grids["Electricity"]["Network_capacity_existing"] == 100
    assert list(grids["Electricity"]["Network_capacity_options"]) == [150, 200]


def test_reinforcements_not_above_the_existing_capacity_are_ignored():
    grid = {"Grid": "Electricity", "Network_capacity_existing": 100, "Network_capacity_options": [250, 100, 50, 150]}
    assert list(network_capacity_options(grid)) == [150, 250]


def test_reinforcements_need_an_existing_capacity():
    with pytest.raises(ValueError, match="Network_capacity_existing"):
        network_capacity_options({"Grid": "Electricity", "Network_capacity_options": [150]})


def test_the_capacity_options_are_sets_of_the_model(infrastructure):
    assert list(infrastructure.Set["Network_capacity_options"]["Electricity"]) == [600, 1000, 2000]
    assert infrastructure.Set["Network_capacity_options"]["NaturalGas"].size == 0
    assert infrastructure.Set["Line_capacity_options"]["Electricity"].size == 0
    assert "Network_capacity_options" not in infrastructure.Grids_Parameters.columns
    assert infrastructure.Grids_Parameters.loc["Electricity", "Network_capacity_existing"] == 400


def test_line_capacity_options_are_set_on_one_grid(qbuildings_data, scenario):
    # The options are a set of the model, not a parameter: one grid may hold them alone
    grids = initialize_grids({"Electricity": {"Line_capacity_options": "40/20"}, "NaturalGas": {}})
    infrastructure = Infrastructure(qbuildings_data, initialize_units(scenario, grids), grids)
    assert list(infrastructure.Set["Line_capacity_options"]["Electricity"]) == [20, 40]
    assert infrastructure.Set["Line_capacity_options"]["NaturalGas"].size == 0
    assert "Line_capacity_options" not in infrastructure.Grids_Parameters.columns


@pytest.mark.parametrize("old, new", [("Network_ext", "Network_capacity_existing"), ("ReinforcementOfNetwork", "Network_capacity_options"),
                                      ("Network_capacity", "Network_capacity_existing"), ("ReinforcementOfLine", "Line_capacity_options")])
def test_the_forbidden_grid_keys_are_rejected(qbuildings_data, scenario, old, new):
    with pytest.raises(ValueError, match=new):
        initialize_grids({"Electricity": {old: 100}})

    grids = initialize_grids()
    grids["Electricity"][old] = 100
    with pytest.raises(ValueError, match=new):
        Infrastructure(qbuildings_data, initialize_units(scenario, grids), grids)


@pytest.mark.parametrize("key", ["Network_ext", "Network_capacity_existing", "Network_capacity_options", "Network_capacity"])
def test_the_network_capacity_is_not_a_parameter(qbuildings_data, units, grids, key):
    with pytest.raises(ValueError, match="grids\\['Electricity'\\]\\['Network_capacity_existing'\\]"):
        MasterProblem(qbuildings_data, units, grids, parameters={key: np.array([100, 1000])})


@pytest.mark.parametrize("parameters, new", [
    ({"Units_Ext": pd.DataFrame({"Units_Ext": [15.0]}, index=["PV_Building1"])}, "Units_Existing"),
    ({"Units_Existing": pd.DataFrame({"Units_Ext": [15.0]}, index=["PV_Building1"])}, "Units_Existing"),
    ({"Units_Ext_district": pd.DataFrame({"Units_Existing": [15.0]}, index=["Battery_district"])}, "Units_Existing_district"),
    ({"Line_ext": pd.DataFrame({"Line_ext": [10.0]}, index=pd.MultiIndex.from_tuples([("Building1", "Electricity")]))},
     "Line_capacity_existing"),
])
def test_the_former_parameters_are_rejected(parameters, new):
    with pytest.raises(ValueError, match=f"renamed {new}"):
        check_parameters(parameters)


def test_the_parameters_are_accepted():
    check_parameters({"Units_Existing": pd.DataFrame({"Units_Existing": [15.0]}, index=["PV_Building1"])})
    check_parameters(None)
