from reho.model.reho import *
from reho.plotting import plotting


if __name__ == '__main__':
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(transformer=3658, nb_buildings=2)

    # Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    # Initialize available units and grids
    # You can add more resources layers besides electricity and natural gas, and adapt their prices
    # or keep the default values from data/parameters/grids.csv
    grids = infrastructure.initialize_grids({'Electricity': {"Cost_supply_cst": 0.90, "Cost_demand_cst": 0.16},
                                             'NaturalGas': {"Cost_supply_cst": 0.45},
                                             'Chakra': {},
                                             })
    path_to_custom_units = os.path.join(path_to_reho,'data/infrastructure/building_units.csv')
    units = infrastructure.initialize_units(scenario, grids, building_data=path_to_custom_units)

    # Set method options
    method = {'building-scale': True}

    # Run optimization
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='3e')

    # Plotting

    plotting.plot_performance(reho.results, plot='costs', indexed_on='Pareto_ID', label='EN_long').show()
    plotting.plot_sankey(reho.results['totex'][0], label='EN_long', color='ColorPastel').show()
