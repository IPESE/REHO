from reho.model.reho import *
from reho.model.preprocessing.QBuildings import QBuildingsReader


if __name__ == '__main__':

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'

    # Set building parameters. We can consider the roofs orientations and add PV on facades.
    reader = QBuildingsReader(load_facades=True, load_roofs=True)       # specify to import as well buildings' roofs and facades data
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(3658, nb_buildings=2)

    # Set specific parameters
    parameters = {}

    # Select clustering file
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Choose energy system structure options
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration', 'DataHeat_DHW', 'OIL_Boiler', 'DHN_hex', 'HeatPump_DHN']
    scenario['enforce_units'] = []

    method = {'use_pv_orientation': True, 'use_facades': False, 'building-scale': False}     # select PV orientation and/or facades methods

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Run optimization
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    SR.save_results(reho, save=['xlsx', 'pickle'], filename='5a')