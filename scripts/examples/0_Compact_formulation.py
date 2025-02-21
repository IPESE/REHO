from reho.model.reho import *
from reho.plotting import plotting


if __name__ == '__main__': 

    # Set building parameters
    reader = QBuildingsReader()  # load QBuildingsReader class
    reader.establish_connection('Geneva')  # connect to QBuildings database
    qbuildings_data = reader.read_db(district_id=5, egid=['2034144/2034143/2749579/2034146/2034145'])  # read data

    # Select clustering options for weather data
    #  - I refers to Irradiance, T to Temperature, and W to Weekday
    #  - specify the desired number of typical days
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'  # select an objective function as defined in ampl_model/scenario.mod
    scenario['EMOO'] = {}  # remain empty for now
    scenario['specific'] = []  # remain empty for now
    scenario['name'] = 'totex'  # any name is possible here
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']  # specify some units to be excluded
    scenario['enforce_units'] = []  # specify some units to be enforced

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()  # grids parameters are based on data/infrastructure/layers.csv
    units = infrastructure.initialize_units(scenario, grids)  # units are based on data/infrastructure/building_units.csv

    # Set method options (as defined in sub_problem.py > initialize_default_methods)
    # By default a district-scale design is performed with a compact formulation.
    # Watch out the maximum number of buildings is around 10 due to exponential complexity.
    method = {}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='0')

    # Plot results
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()
    plotting.plot_performance(reho.results, plot='gwp', indexed_on='Scn_ID', label='EN_long', title="Environmental performance").show()
    plotting.plot_sankey(reho.results['totex'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()
