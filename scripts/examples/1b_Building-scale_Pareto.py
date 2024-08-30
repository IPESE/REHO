from reho.model.reho import *
from reho.plotting import plotting


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(transformer=234, nb_buildings=1)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = ['OPEX', 'CAPEX']  # for multi-objective optimization two objectives are needed
    scenario['nPareto'] = 2  # number of points per objective (total number of optimizations = nPareto * 2 + 2)
    scenario['name'] = 'pareto'
    scenario['exclude_units'] = ['NG_Cogeneration', 'OIL_Boiler', 'ThermalSolar']
    scenario['enforce_units'] = []

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Set method options
    method = {'building-scale': True}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.generate_pareto_curve()  # multi-objective optimization

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='1b')

    # Performance plot : costs and gwp
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Pareto_ID', label='EN_long', title="Economical performance").show()
    plotting.plot_performance(reho.results, plot='gwp', indexed_on='Pareto_ID', label='EN_long', title="Environmental performance").show()

    # Sankey diagram
    for key in reho.results['pareto'].keys():
        plotting.plot_sankey(reho.results['pareto'][key], label='EN_long', color='ColorPastel', title="Sankey diagram").show()
