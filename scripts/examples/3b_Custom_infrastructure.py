from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, egid=['1017073/1017074', '1017109', '1017079', '1030377/1030380'])

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    # Initialize available units and grids
    # You can add more resources layers besides electricity and natural gas, and adapt their prices
    # - directly within the script
    # - or through a custom csv file based on the default values from data/infrastructure/layers.csv
    grids = infrastructure.initialize_grids({'Electricity': {"Cost_supply_cst": 0.30, "Cost_demand_cst": 0.16},
                                             'NaturalGas': {"Cost_supply_cst": 0.15},
                                             'Wood': {},
                                             'Oil': {},
                                             })

    # Units specifications can also be adapted through a custom csv file based on the default values from data/infrastructure/building_units.csv
    path_to_custom_units = str(Path(__file__).parent / 'data' / 'building_units.csv')
    units = infrastructure.initialize_units(scenario, grids, building_data=path_to_custom_units)

    # Set method options
    method = {'building-scale': True}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='3b')
