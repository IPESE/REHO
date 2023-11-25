from reho.model.reho import *
from reho.model.preprocessing.QBuildings import *


if __name__ == '__main__':

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(3658, nb_buildings=2)

    # Set specific parameters
    parameters = {}

    # Select clustering file
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Choose energy system structure options
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration', 'DataHeat_DHW', 'OIL_Boiler', 'DHN_hex', 'HeatPump_DHN']
    scenario['enforce_units'] = []

    # add stochasticity in the demand profiles given by the SIA standards, tunable with:
    # standard deviation on the peak demand
    # and/or standard deviation on the time-shift
    method = {'building-scale': True, 'include_stochasticity': True, 'sd_stochasticity': [0.1, 2]}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Run optimization
    DW_params = {'max_iter': 2}
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters,
                    cluster=cluster, scenario=scenario, method=method, DW_params=DW_params)
    reho.single_optimization()

    # Save results
    SR.save_results(reho, save=['xlsx', 'pickle'], filename='3b')