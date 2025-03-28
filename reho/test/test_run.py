import pytest
from reho.model.reho import *
from reho.plotting import plotting


def test_run(save_results=True):

    try:
        # Set building parameters
        reader = QBuildingsReader()
        reader.establish_connection('Geneva')
        qbuildings_data = reader.read_db(district_id=71, egid=['1009515'])

        # Select clustering options for weather data
        cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

        # Set scenario
        scenario = dict()
        scenario['Objective'] = 'TOTEX'
        scenario['EMOO'] = {}
        scenario['specific'] = []
        scenario['name'] = 'totex'
        scenario['exclude_units'] = ['ThermalSolar']
        scenario['enforce_units'] = []

        # Set method options
        method = {'building-scale': True}

        # Initialize available units and grids
        grids = infrastructure.initialize_grids()
        units = infrastructure.initialize_units(scenario, grids)

        # Run optimization
        reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="highs")
        reho.single_optimization()

        if save_results:
            reho.save_results(format=['xlsx', 'pickle'], filename='test_results')

        # Plot results
        plotting.plot_sankey(reho.results['totex'][0], label='EN_long', color='ColorPastel', title="Sankey diagram", filename="figures/Sankey").show()

    except ImportError as e:
        pytest.fail(f"Running REHO failed: {e}")
