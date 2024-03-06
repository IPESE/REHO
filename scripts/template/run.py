from reho.model.reho import *


# Set building parameters
reader = QBuildingsReader()
qbuildings_data = reader.read_csv(buildings_filename='data/buildings.csv', nb_buildings=1)

# Select weather data
cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

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
method = {}

# Run optimization
reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
reho.single_optimization()

# Save results
reho.save_results(format=['pickle'], filename='my_case_study')