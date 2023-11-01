from model.reho import *
from model.preprocessing.QBuildings import QBuildingsReader


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

    method = {}

    # Initialize available units and grids. You can add more resources layer than simply electricity and gas
    grids = infrastructure.initialize_grids({'Electricity': {"Cost_demand_cst": 0.10, "Cost_supply_cst": 0.26},
                                        'Wood': {}, 'Oil': {},
                                        'NaturalGas': {'NaturalGas': {"Cost_demand_cst": 0.06, "Cost_supply_cst": 0.20}}})


    units = infrastructure.initialize_units(scenario, grids)

    # Run optimization
    reho_model = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method)
    reho_model.single_optimization()

    # Save results
    SR.save_results(reho_model, save=['xlsx', 'pickle'], filename='4b')
