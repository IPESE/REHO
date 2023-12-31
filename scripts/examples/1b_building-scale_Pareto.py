from reho.model.reho import *
from reho.model.preprocessing.QBuildings import QBuildingsReader


if __name__ == '__main__':

    # Set scenario
    scenario = dict()
    scenario['Objective'] = ['OPEX', 'CAPEX']   # for multi-objective optimization we need two objectives
    scenario['nPareto'] = 1     # the number of points we want per objective (number of optimizations = nPareto * 2 + 2)
    scenario['name'] = 'pareto'

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(3658, nb_buildings=1)

    # Set specific parameters
    parameters = {}

    # Select clustering file
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Choose energy system structure options
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration', 'DataHeat_DHW', 'OIL_Boiler', 'DHN_hex', 'HeatPump_DHN']
    scenario['enforce_units'] = []

    method = {'building-scale': True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Run optimization
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.generate_pareto_curve()  # instead of single_optimization() we run a multi-objective optimization

    # Save results
    SR.save_results(reho, save=['pickle'], filename='1b')
