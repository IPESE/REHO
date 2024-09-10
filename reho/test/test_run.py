import pytest
from reho.model.reho import *
from reho.plotting import plotting


def test_run():

    try:
        # Set building parameters
        reader = QBuildingsReader()
        reader.establish_connection('Geneva')
        qbuildings_data = reader.read_db(71, egid=['1009515'])

        # Select clustering options for weather data
        cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

        # Set scenario
        scenario = dict()
        scenario['Objective'] = 'TOTEX'
        scenario['EMOO'] = {}
        scenario['specific'] = []
        scenario['name'] = 'totex'
        scenario['exclude_units'] = ['ThermalSolar', 'NG_Cogeneration']
        scenario['enforce_units'] = []

        # Initialize available units and grids
        grids = infrastructure.initialize_grids()
        units = infrastructure.initialize_units(scenario, grids)

        # Set method options
        method = {'building-scale': True}

        # Run optimization
        reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="highs")
        reho.single_optimization()

        # Plot results
        plotting.plot_sankey(reho.results['totex'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()

    except ImportError as e:
        pytest.fail(f"Running REHO failed: {e}")
