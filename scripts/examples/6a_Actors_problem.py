from reho.model.actors_problem import *

if __name__ == '__main__':

    cluster_num = 7
    location = 'Geneva'
    nb_buildings = 5
    risk_factor = 0.0314571380856351
    n_samples = 5
    Owner_portfolio = True
    Utility_portfolio = False

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['EMOO'] = {}
    scenario['specific'] = []

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(9522, nb_buildings=nb_buildings)

    # Set specific parameters
    parameters = {}

    # Select clustering options for weather data
    cluster = {'Location': location, 'Attributes': ['I', 'T'], 'Periods': 10, 'PeriodDuration': 24}

    # Choose energy system structure options
    scenario['exclude_units'] = ['ThermalSolar', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    # Set method options
    method = {'actors_problem': True, "print_logs": True, "refurbishment": True, "include_all_solutions": True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    DW_params={}
    DW_params['max_iter'] = 6
    # Initiate the actor-based problem formulation
    reho = ActorsProblem(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobiasl", DW_params=DW_params)
    #, DW_params=DW_params
    #gurobiasl
    # Generate configurations
    tariffs_ranges = {'Electricity': {"Cost_supply_cst": [0.15, 0.45]},
                      'NaturalGas': {"Cost_supply_cst": [0.10, 0.30]}}
    try:
        reho.read_configurations()  # if configurations were already generated, simply import them
    except FileNotFoundError:
        reho.generate_configurations(n_sample=n_samples, tariffs_ranges=tariffs_ranges)

    # Define boundaries
    if Utility_portfolio:
        reho.scenario["name"] = "Utility"
        print("Calculate boundary for Utility")
        reho.execute_actors_problem(n_sample=n_samples, bounds=None, actor="Utility")
        bound_d = -np.array([reho.results[i][0]["df_Actors"].loc["Utility"][0] for i in reho.results])
    else:
        print("Calculate boundary for Utility: DEFAULT 0")
        bound_d = np.array(0.00001)

    # Define boundaries
    if Owner_portfolio:
        reho.scenario["name"] = "Owners"
        print("Calculate boundary for Owners")
        reho.execute_actors_problem(n_sample=n_samples, bounds=None, actor="Owners")
        bound_o = np.array([reho.get_portfolio_ratio()])
        #bound_o = -np.array([reho.results[i][0]["df_Actors"].loc["Owners"][0] for i in reho.results])
    else:
        print("Calculate boundary for Owners: DEFAULT 0")
        bound_o = np.array(100)
        if Utility_portfolio == False:
            reho.parameters["renter_expense_max"] = [1e6] * nb_buildings

    bounds = {"Utility": [0, bound_d.max()/2], "Owners": [0, bound_o.max()], "Renters": [2.0, 3.0]}

    # Run actor-based optimization
    reho.scenario["name"] = "MOO_actors"
    reho.set_actors_boundary(bounds=bounds, n_sample=n_samples, risk_factor=risk_factor)

    reho.actor_decomposition_optimization(scenario)

    # print(reho.results["Renters"][0]["df_Actors_tariff"].xs("Electricity").mean(), "\n")
    # print(reho.results["Renters"][0]["df_Actors"])
    # Save results
    reho.save_results(format=["pickle"], filename='0_actors_cluster{}_{}_{}_0'.format(cluster_num,risk_factor, Owner_portfolio))
