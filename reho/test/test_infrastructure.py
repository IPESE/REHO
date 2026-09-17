import os
import re

import numpy as np
import pytest
from reho.model.infrastructure import (
    PERFORMANCE_MAP_FILES,
    Infrastructure,
    _interperiod_unit_files,
    initialize_grids,
    initialize_units,
    read_performance_map,
)
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
