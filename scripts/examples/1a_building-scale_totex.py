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

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Set method options
    method = {'building-scale': True}


    # Run optimization
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")

    # Scenarios
    scn={'capex':'CAPEX'}

    for name, obj in scn.items():
        reho.scenario['Objective'] = obj
        reho.scenario['name'] = name
        reho.scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
        reho.scenario['enforce_units'] = []
        units = infrastructure.initialize_units(reho.scenario, grids)
        reho.infrastructure = infrastructure.infrastructure(qbuildings_data, units, grids)
        h=reho.single_optimization()
        print(h)

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='1a')
    #
    # plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long').show()
    # plotting.plot_performance(reho.results, plot='gwp', indexed_on='Scn_ID', label='EN_long').show()
    # plotting.plot_sankey(reho.results['human_toxicity'][0], label='EN_long', color='ColorPastel').show()
