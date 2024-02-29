from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters with roof orientations and facades loaded from csv files
    reader = QBuildingsReader(load_facades=True, load_roofs=True)
    qbuildings_data = reader.read_csv(buildings_filename='../template/data/buildings.csv', nb_buildings=2,
                                      facades_filename='../template/data/facades.csv', roofs_filename='../template/data/roofs.csv')

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
    reho.save_results(format=['xlsx', 'pickle'], filename='5b')
