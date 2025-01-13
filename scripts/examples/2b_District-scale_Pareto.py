from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, nb_buildings=2)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = ['OPEX', 'CAPEX']
    scenario['nPareto'] = 2
    scenario['name'] = 'pareto'
    scenario['exclude_units'] = ['NG_Cogeneration', 'OIL_Boiler']
    scenario['enforce_units'] = []

    # Set method options
    method = {'district-scale': True}
    DW_params = {'max_iter': 2}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, DW_params=DW_params, solver="gurobi")
    reho.generate_pareto_curve()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='2b')
