from reho import QBuildingsReader, REHO, initialize_grids, initialize_units

if __name__ == '__main__':
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db({'transformers': 234}, nb_buildings=6)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = []
    scenario['enforce_units'] = []

    # Initialize available units and grids, with the capacity of the electricity network [kW]:
    # its existing capacity, and the larger capacities it can be reinforced to
    grids = initialize_grids({'Electricity': {'Network_capacity_existing': 100, 'Network_capacity_options': [150, 200, 250]},
                              'NaturalGas': {}})
    units = initialize_units(scenario, grids, district_data=True)

    # Set method options
    method = {'district-scale': True}
    DW_params = {'max_iter': 4}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, DW_params=DW_params, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='3j')
