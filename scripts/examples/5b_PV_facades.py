from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    # PV on facades can be considered
    reader = QBuildingsReader(load_facades=True, load_roofs=True)

    # # Warning: to connect to QBuildings-Suisse (database including facades data), you need to be within EPFL intranet.
    # reader.establish_connection('Suisse')
    # qbuildings_data = reader.read_db(district_id=3658, nb_buildings=2)

    # Alternatively, roof orientations and facades can be loaded from csv files
    buildings_filename = str(Path(__file__).parent / 'data' / 'buildings.csv')
    facades_filename = str(Path(__file__).parent / 'data' / 'facades.csv')
    roofs_filename = str(Path(__file__).parent / 'data' / 'roofs.csv')
    qbuildings_data = reader.read_csv(buildings_filename=buildings_filename, nb_buildings=2,
                                      facades_filename=facades_filename, roofs_filename=roofs_filename)

    # Select clustering options for weather data
    cluster = {'Location': 'Sion', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

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
    method = {'use_pv_orientation': True, 'use_facades': True, 'building-scale': True}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='5b')
