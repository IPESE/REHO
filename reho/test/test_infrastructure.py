import pytest
from reho.model.infrastructure import *


def test_infrastructure_initialization():
    qbuildings_data = {'buildings_data': {'Building1': {}, 'Building2': {}}}

    scenario = dict()
    scenario['exclude_units'] = ['NG_Cogeneration']
    scenario['enforce_units'] = []

    grids = initialize_grids()
    units = initialize_units(scenario, grids)

    infrastructure = Infrastructure(qbuildings_data, units, grids)

    assert infrastructure.grids.keys() == {'Electricity', 'NaturalGas'}
    assert len(infrastructure.House) == 2
    assert 'NG_Cogeneration' not in infrastructure.UnitTypes
    assert infrastructure.LayersOfType['HeatCascade'] == np.array(['HeatCascade'])
    assert not infrastructure.UnitsOfDistrict

    with pytest.raises(KeyError):
        Infrastructure({}, {}, {})
