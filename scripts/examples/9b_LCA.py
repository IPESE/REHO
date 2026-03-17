from reho.model.reho import *
from reho.plotting import plotting


if __name__ == '__main__':
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, nb_buildings=5)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}
    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'LCA'
    scenario['exclude_units'] = []
    scenario['enforce_units'] = []

    # scenario['EMOO'] = {"EMOO_lca": {"Impact": 1}} # set an upper bound to

    # Set method options
    method = {'building-scale': True, "save_lca": True, "print_logs": False}
    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Load per-indicator LCA impacts from CSV.
    indicators = infrastructure.initialize_lca_impacts("data/lca/LCA_impacts.csv", units, grids, threshold=1e-3)


    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobiasl")
    reho.single_optimization()


    print("\nTOTEX: ", reho.results["LCA"][0]["df_Performance"].xs("Network")[["Costs_op", "Costs_inv"]].sum())
    # print("Construction & Operational impact [per indicator]:\n", np.round(reho.results["LCA"][0]["df_lca_Units"].sum() , 2))
    # print("Resources impact [per indicator]:\n", np.round(reho.results["LCA"][0]["df_lca_resources"].sum() , 2))
    print("Total impact [per indicator]:\n", np.round(reho.results["LCA"][0]["df_lca_Performance"].xs("Network") , 2))


    plotting.plot_sankey(reho.results['LCA'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()

    # Save results
    reho.save_results(format=['pickle'], filename='9a')
