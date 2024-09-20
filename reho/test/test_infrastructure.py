import pytest
import numpy as np
from reho.model.infrastructure import Infrastructure, initialize_grids, initialize_units


@pytest.fixture(scope="module")
def qbuildings_data():
    return {'buildings_data': {
        'Building1': {'ERA': 192, 'HeatCapacity': 119, 'SolarRoofArea': 140, 'T_comfort_min_0': 20, 'Tc_return_0': 17, 'Tc_supply_0': 12, 'Th_return_0': 50,
                      'Th_supply_0': 65, 'U_h': 0.002, 'area_facade_m2': 144, 'class': 'Residential', 'count_floor': 2, 'egid': '1009515',
                      'energy_cooling_signature_kWh_y': 0, 'energy_el_kWh_y': 4007, 'energy_heating_signature_kWh_y': 20400,
                      'energy_hotwater_signature_kWh_y': 1692, 'facade_annual_irr_kWh_y': 67952, 'geometry': "", 'height_m': 6, 'id_building': '8320',
                      'id_class': 'II', 'n_p': 10, 'period': '1961-1970', 'ratio': '1', 'roof_annual_irr_kWh_y': 154769, 'source_heating': 'Oil',
                      'source_hotwater': 'Oil', 'status': "['existing', 'existing']", 'transformer': 71, 'x': 2496193, 'y': 1114279, 'z': 402},
        'Building2': {'ERA': 117, 'HeatCapacity': 119, 'SolarRoofArea': 101, 'T_comfort_min_0': 20, 'Tc_return_0': 17, 'Tc_supply_0': 12, 'Th_return_0': 50,
                      'Th_supply_0': 65, 'U_h': 0.002, 'area_facade_m2': 121, 'class': 'Residential', 'count_floor': 2, 'egid': '2036614',
                      'energy_cooling_signature_kWh_y': 0, 'energy_el_kWh_y': 2451, 'energy_heating_signature_kWh_y': 12478,
                      'energy_hotwater_signature_kWh_y': 1035, 'facade_annual_irr_kWh_y': 76152, 'geometry': "", 'height_m': 6, 'id_building': '8330',
                      'id_class': 'II', 'n_p': 6, 'period': '1919-1945', 'ratio': '1', 'roof_annual_irr_kWh_y': 118639, 'source_heating': 'Oil',
                      'source_hotwater': 'Electricity', 'status': "['existing', 'existing']", 'transformer': 71, 'x': 2496238, 'y': 1114527, 'z': 405},
    }
    }


@pytest.fixture(scope="module")
def scenario():
    return {'exclude_units': ['NG_Cogeneration'], 'enforce_units': []}


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
    assert not infrastructure.Grids_flowrate.empty
    assert not infrastructure.Grids_Parameters.empty
    assert not infrastructure.Units_Parameters.empty


def test_infrastructure_initialization(infrastructure):
    assert 'HeatCascade' in infrastructure.Layers
    assert 'Electricity' in infrastructure.Layers
    assert 'Building1' in infrastructure.House
    assert 'Building2' in infrastructure.House

    assert set(infrastructure.grids.keys()) == {'Electricity', 'NaturalGas'}
    assert 'NG_Cogeneration' not in infrastructure.UnitTypes
    assert np.array_equal(infrastructure.LayersOfType['HeatCascade'], np.array(['HeatCascade']))
    assert not infrastructure.UnitsOfDistrict


def test_infrastructure_edge_cases(infrastructure):
    with pytest.raises(KeyError):
        Infrastructure({}, {}, {})

    with pytest.raises(KeyError):
        infrastructure.grids['NonExistentGrid']
