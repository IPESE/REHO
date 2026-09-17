import numpy as np
import pytest
from reho.model.infrastructure import Infrastructure, initialize_grids, initialize_units


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
