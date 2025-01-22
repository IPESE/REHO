from reho.model.actors_problem import *

if __name__ == '__main__':

    cluster_num = 6
    location = 'Zurich'
    nb_buildings = 6
    risk_factor = 0.278
    n_samples = 2
    Owner_portfolio = True
    Utility_portfolio = False
    #for Sc2 PIR = 1
    Owner_PIR = False

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['EMOO'] = {}
    scenario['specific'] = []

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(15154, nb_buildings=nb_buildings)

    # Set specific parameters
    parameters = {"TransformerCapacity": np.array([24.66, 1e8])}

    # Select clustering options for weather data
    cluster = {'Location': location, 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Choose energy system structure options
    scenario['exclude_units'] = ['ThermalSolar', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    # Set method options
    method = {'actors_problem': True, "print_logs": True, "refurbishment": True, "include_all_solutions": False}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    DW_params={}
    DW_params['max_iter'] = 5
    # Initiate the actor-based problem formulation
    reho = ActorsProblem(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobiasl", DW_params=DW_params)

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

    # Define owner boundaries
    if Owner_portfolio:
        reho.scenario["name"] = "Owners"
        print("Calculate boundary for Owners")
        reho.execute_actors_problem(n_sample=n_samples, bounds=None, actor="Owners")
        bound_o = np.array(1) # Percentage of maximal achievable revenue
    else:
        print("Calculate boundary for Owners: DEFAULT 0")
        bound_o = np.array(0.00001)
        if Utility_portfolio == False:
            reho.parameters["renter_expense_max"] = [1e6] * nb_buildings

    if Owner_PIR:
        print("Calculate PIR boundary for Owners")
        bound_pir = np.array([reho.get_portfolio_ratio()])
    else:
        print("Calculate PIR boundary for Owners: DEFAULT 1")
        bound_pir = np.array(1)

    bounds = {"Utility": [0, bound_d.max()/2], "Owners": [0, bound_o.max()], "PIR": [0.99, bound_pir]}

    # Run actor-based optimization
    reho.scenario["name"] = "MOO_actors"
    reho.set_actors_boundary(bounds=bounds, n_sample=n_samples, risk_factor=risk_factor)

    reho.actor_decomposition_optimization(scenario)

    # print(reho.results["Renters"][0]["df_Actors_tariff"].xs("Electricity").mean(), "\n")
    # print(reho.results["Renters"][0]["df_Actors"])
    # Save results
    reho.save_results(format=["pickle","save_all"], filename='Scenario2_{}_{}'.format(cluster_num,risk_factor))