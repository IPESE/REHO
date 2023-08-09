from model.reho import *
from model.preprocessing.QBuildings import *


if __name__ == '__main__':

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse-old')
    qbuildings_data = reader.read_db(3658, nb_buildings=2)

    # Set specific parameters
    parameters = {}

    # Select clustering file
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Choose energy system structure options
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration', 'DataHeat_DHW', 'OIL_Boiler', 'DHN_hex', 'HeatPump_DHN']
    scenario['enforce_units'] = []

    # to obtain a district scale design with many buildings, a decomposition of the problem is needed
    method = {'decomposed': True}

    # Initialize available units and grids
    grids = structure.initialize_grids()
    units = structure.initialize_units(scenario, grids)

    # Run optimization
    DW_params = {'max_iter': 2}
    reho_model = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters,
                    cluster=cluster, scenario=scenario, method=method, DW_params=DW_params)
    reho_model.single_optimization()

    # Save results
    SR.save_results(reho_model, save=['xlsx', 'pickle'], filename='3a')