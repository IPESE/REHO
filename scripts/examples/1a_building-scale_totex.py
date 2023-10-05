from model.reho import *
from model.preprocessing.QBuildings import QBuildingsReader


if __name__ == '__main__':

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'         # select an objective function as defined in ampl_model/scenario.mod
    scenario['EMOO'] = {}                   # remain empty for now
    scenario['specific'] = []               # remain empty for now
    scenario['name'] = 'totex'              # any name is possible here

    # Set building parameters
    reader = QBuildingsReader()             # load python class
    reader.establish_connection('Suisse')   # connect to QBuildings database
    qbuildings_data = reader.read_db(3658, nb_buildings=2)      # read data

    # Set specific parameters
    parameters = {}                         # remain empty for now

    # Select clustering file
    # Location can be chosen among the files available in preprocessing > weatherData > data > hour
    # I refers to Irradiance, T to Temperature, and W to Weekday
    # Select the desired number of typical days
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Choose superinfrastructure. Units are defined in the function return_building_units in infrastructure.py. Units characteristics are in preprocessing/units/building_units.csv
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration', 'DataHeat_DHW', 'OIL_Boiler', 'DHN_hex', 'HeatPump_DHN']      # specify some units we want toe exclude
    scenario['enforce_units'] = []

    # select some methods as defined in compact_optimization.py (function initialize_default_methods).
    method = {'building-scale': True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()    # initialize grid parameters such as energy tariffs. More information is available in example 2b
    units = infrastructure.initialize_units(scenario, grids, district_units=True)

    # Run optimization
    reho_model = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method)
    reho_model.single_optimization()

    # Save results
    SR.save_results(reho_model, save=['xlsx', 'pickle'], filename='1a')
