from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(transformer=10889, nb_buildings=4)

    # Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = ['HeatPump_DHN']

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'Heat': {"Cost_demand_cst": 0.001, "Cost_supply_cst": 0.005}})
    units = infrastructure.initialize_units(scenario, grids)

    # Set method options
    # you can specify if the DHN is based on CO2. If not, a water DHN is assumed
    method = {'building-scale': True, 'DHN_CO2': True}

    # Set specific parameters
    # specify the temperature of the DHN
    parameters = {'T_DHN_supply_cst': np.repeat(20.0, 4), "T_DHN_return_cst": np.repeat(15.0, 4)}

    # Run optimization
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    reho.get_DHN_costs()  # run one optimization forcing DHN to find costs DHN connection per house
    reho.single_optimization()  # run optimization with DHN costs

    # Save results
    SR.save_results(reho, save=['xlsx', 'pickle'], filename='3g')
