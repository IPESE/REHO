from reho.model.reho import *
from reho.plotting import plotting

if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, nb_buildings=6, correct_Uh=True)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = []
    scenario['enforce_units'] = []

    # The "renovation" method consists in a list of renovation options.
    # Each option contains building elements to renovate. The order does not matter.
    method = {'building-scale': True, "renovation": ["window/facade/roof/footprint", "window/facade", "roof"]}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    additional_data = {"renovation": reho.results["totex"][0]["df_Performance"].xs("Network")["Costs_ins"]}
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Pareto_ID', label='EN_long', title="Economical performance", additional_costs=additional_data).show()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='3k')
