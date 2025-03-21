from reho.plotting import plotting
from reho.model.reho import *

if __name__ == '__main__':
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, egid=['1017073/1017074', '1017109', '1017079', '1030377/1030380'])

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'Bike_district', 'ICE_district', 'ElectricBike_district']
    scenario['enforce_units'] = []

    parameters = dict()

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'Gasoline': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    # Set method options
    method = {'building-scale': True}

    # Set specific parameters
    parameters = {}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, parameters=parameters, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='3d')

    # Plot results
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()
