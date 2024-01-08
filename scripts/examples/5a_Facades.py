from reho.model.reho import *
from reho.model.preprocessing.QBuildings import QBuildingsReader


if __name__ == '__main__':

    # Set building parameters
    # roof orientations and PV on facades can be considered
    reader = QBuildingsReader(load_facades=True, load_roofs=True)
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(3658, nb_buildings=2)

    # Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Set method options
    # select PV orientation and/or facades methods
    method = {'use_pv_orientation': True, 'use_facades': True, 'building-scale': True}

    # Run optimization
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    SR.save_results(reho, save=['xlsx', 'pickle'], filename='5a')
