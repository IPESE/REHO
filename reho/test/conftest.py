"""Shared pytest configuration for the REHO test-suite.

The suite is split in two tiers:

``fast``
    Tests that need neither an AMPL license, nor a solver, nor network access:
    imports, option handling, path resolution, data-file integrity and the AMPL
    technology registries. These run on every push.

``slow`` / ``needs_ampl`` / ``needs_network``
    Tests that solve a real problem or reach out to a database. Run them with
    ``pytest -m slow`` once a license and a solver are available.
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: solves an optimization problem; takes minutes")
    config.addinivalue_line("markers", "needs_ampl: requires a working AMPL license and solver")
    config.addinivalue_line("markers", "needs_network: requires internet access (QBuildings, PVGIS, ELCOM)")


@pytest.fixture(scope="session")
def sample_buildings_data():
    """Two buildings, as :class:`~reho.model.preprocessing.QBuildings.QBuildingsReader` returns them.

    Lets the infrastructure and option layers be tested without a database.
    """
    return {
        "buildings_data": {
            "Building1": {
                "ERA": 192, "HeatCapacity": 119, "SolarRoofArea": 140, "T_comfort_min_0": 20,
                "Tc_return_0": 17, "Tc_supply_0": 12, "Th_return_0": 50, "Th_supply_0": 65,
                "U_h": 0.002, "area_facade_m2": 144, "class": "Residential", "count_floor": 2,
                "egid": "1009515", "energy_cooling_signature_kWh_y": 0, "energy_el_kWh_y": 4007,
                "energy_heating_signature_kWh_y": 20400, "energy_hotwater_signature_kWh_y": 1692,
                "facade_annual_irr_kWh_y": 67952, "geometry": "", "height_m": 6, "id_building": "8320",
                "id_class": "II", "n_p": 10, "period": "1961-1970", "ratio": "1",
                "roof_annual_irr_kWh_y": 154769, "source_heating": "Oil", "source_hotwater": "Oil",
                "status": "['existing', 'existing']", "transformer": 71,
                "x": 2496193, "y": 1114279, "z": 402,
            },
            "Building2": {
                "ERA": 117, "HeatCapacity": 119, "SolarRoofArea": 101, "T_comfort_min_0": 20,
                "Tc_return_0": 17, "Tc_supply_0": 12, "Th_return_0": 50, "Th_supply_0": 65,
                "U_h": 0.002, "area_facade_m2": 121, "class": "Residential", "count_floor": 2,
                "egid": "2036614", "energy_cooling_signature_kWh_y": 0, "energy_el_kWh_y": 2451,
                "energy_heating_signature_kWh_y": 12478, "energy_hotwater_signature_kWh_y": 1035,
                "facade_annual_irr_kWh_y": 76152, "geometry": "", "height_m": 6, "id_building": "8330",
                "id_class": "II", "n_p": 6, "period": "1919-1945", "ratio": "1",
                "roof_annual_irr_kWh_y": 118639, "source_heating": "Oil", "source_hotwater": "Electricity",
                "status": "['existing', 'existing']", "transformer": 71,
                "x": 2496238, "y": 1114527, "z": 405,
            },
        }
    }
