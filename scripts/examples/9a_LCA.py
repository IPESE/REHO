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
    scenario['name'] = 'totex'
    scenario['exclude_units'] = []
    scenario['enforce_units'] = []
    scenario['EMOO'] = {"EMOO_lca": {"Impact": 1}} # set an upper bound to

    # Set method options
    method = {'building-scale': True, "save_lca": True, "print_logs": False}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    for layers in grids:
        grids[layers]["Impact_demand_cst"] = 0.02
        grids[layers]["Impact_supply_cst"] = 0.10

    for i in range(len(units["building_units"])):
        units["building_units"][i]["Impact_1"] = 10.0
        units["building_units"][i]["Impact_2"] = 5.0

    for i in range(len(units["district_units"])):
        units["district_units"][i]["Impact_1"] = 10.0
        units["district_units"][i]["Impact_2"] = 5.0

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobiasl")
    reho.single_optimization()

    print("\nTOTEX: ", reho.results["totex"][0]["df_Performance"].xs("Network")[["Costs_op", "Costs_inv"]].sum())
    print("Embodied impact: ", np.round(reho.results["totex"][0]["df_lca_Units"].sum()[0]/reho.ERA, 2))
    print("Operational impact: ", np.round(reho.results["totex"][0]["df_lca_operation"].sum()[0]/reho.ERA, 2))
    print("Total impact: ", np.round(reho.results["totex"][0]["df_lca_Performance"].xs("Network")[0]/reho.ERA, 2))

    plotting.plot_sankey(reho.results['totex'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='1a')
