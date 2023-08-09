from model.reho import *
from model.preprocessing.QBuildings import QBuildingsReader


if __name__ == '__main__':

    # Set scenario
    scenario = dict()
    scenario['Objective'] = ['OPEX', 'CAPEX']
    scenario['nPareto'] = 2
    scenario['name'] = 'pareto'

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

    method = {}

    # Initialize available units and grids. You can specify the energy tariffs you want. Demand = feed-in and supply = retail
    grids = structure.initialize_grids({'Electricity': {"Cost_demand_cst": 0.14, "Cost_supply_cst": 0.26},
                                        'NaturalGas': {"Cost_supply_cst": 0.18}})
    units = structure.initialize_units(scenario, grids)

    # Run optimization
    reho_model = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster,
                  scenario=scenario, method=method)

    reho_model.generate_pareto_curve()

    # Save results
    SR.save_results(reho_model, save=['xlsx', 'pickle'], filename='2b')