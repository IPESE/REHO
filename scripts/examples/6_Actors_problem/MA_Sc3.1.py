from reho.model.actors_problem import *

def filter_nan(qbuildings_data):
    for bui in qbuildings_data["buildings_data"]:
        bui_class = qbuildings_data["buildings_data"][bui]["id_class"]
        qbuildings_data["buildings_data"][bui]["id_class"] = qbuildings_data["buildings_data"][bui]["id_class"].replace("nan", "II")
        qbuildings_data["buildings_data"][bui]["id_class"] = qbuildings_data["buildings_data"][bui]["id_class"].replace("VIII", "III")
        qbuildings_data["buildings_data"][bui]["ratio"] = qbuildings_data["buildings_data"][bui]["ratio"].replace("nan","0.0")
        if bui_class != qbuildings_data["buildings_data"][bui]["id_class"]:
            print(bui, "had nan class and was", bui_class)
        if math.isnan(qbuildings_data["buildings_data"][bui]["U_h"]):
            qbuildings_data["buildings_data"][bui]["U_h"] = 0.00181
        if math.isnan(qbuildings_data["buildings_data"][bui]["HeatCapacity"]):
            qbuildings_data["buildings_data"][bui]["HeatCapacity"] = 120
        if math.isnan(qbuildings_data["buildings_data"][bui]["T_comfort_min_0"]):
            qbuildings_data["buildings_data"][bui]["T_comfort_min_0"] = 20
        if math.isnan(qbuildings_data["buildings_data"][bui]["count_floor"]):
            qbuildings_data["buildings_data"][bui]["count_floor"] = 2
        if qbuildings_data["buildings_data"][bui]["n_p"] < 1:
            qbuildings_data["buildings_data"][bui]["n_p"] = 1
    return qbuildings_data

if __name__ == '__main__':

    cluster_num = 6
    location = 'Zurich'
    nb_buildings = 6
    risk_factor = 0.277933
    n_samples = 5
    Owner_portfolio = True
    Utility_portfolio = False
    Owner_PIR = False
    clusters_data = pd.read_csv("./clusters_data.csv")

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['EMOO'] = {}
    # TEST for what happens if there is no subsidies for renters
    scenario['specific'] = ['Renter_noSub', 'Owner_Sub_bigM_ub', 'Renovation_Improvement'] #
    # Set building parameters
    reader = QBuildingsReader(load_roofs=True)
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(9529, nb_buildings=nb_buildings)
    qbuildings_data = filter_nan(qbuildings_data)
    # Set specific parameters
    parameters = {"TransformerCapacity": np.array([2466, 1e8])}

    # Select clustering options for weather data
    cluster = {'Location': location, 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Choose energy system structure options
    scenario['exclude_units'] = ['ThermalSolar', 'NG_Cogeneration','Battery']
    scenario['enforce_units'] = []

    # Set method options
    method = {'actors_problem': True, "print_logs": True, "refurbishment": True, "include_all_solutions": False,
              'use_pv_orientation': True, 'use_facades': False, "use_dynamic_emission_profiles": True,
              "save_streams": False, "save_timeseries": False, "save_data_input": False, "parallel_computation": True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {"Cost_demand_cst": 0.1, "Cost_supply_cst": 0.3346},  'NaturalGas': {"Cost_supply_cst": 0.14}})
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
        bound_d = [0, -np.array([reho.results[i][0]["df_Actors"].loc["Utility"][0] for i in reho.results]).max() / 2]
    else:
        print("Calculate boundary for Utility: DEFAULT 0")
        bound_d = [0, 0.000001]

    # Define owner boundaries
    if Owner_portfolio:
        reho.scenario["name"] = "Owners"
        print("Calculate boundary for Owners")
        reho.execute_actors_problem(n_sample=n_samples, bounds=None, actor="Owners")
        bound_o = [0, 0.29]
    else:
        print("Calculate boundary for Owners: DEFAULT 0")
        bound_o = [0, 0.000001]
        if Utility_portfolio == False:
            reho.parameters["renter_expense_max"] = [1e7] * nb_buildings

    if Owner_PIR:
        print("Calculate PIR boundary for Owners")
        bound_pir = [0, 1]
    else:
        print("Calculate PIR boundary for Owners: DEFAULT 1")
        bound_pir = [0.99, 1]

    bounds = {"Utility": bound_d, "Owners": bound_o, "PIR": bound_pir}

    # Run actor-based optimization
    reho.scenario["name"] = "MOO_actors"
    reho.set_actors_boundary(bounds=bounds, n_sample=n_samples, risk_factor=risk_factor)
    #reho.set_actors_boundary(bounds=bounds, mode='CH',start=0 ,step=0.01, risk_factor=risk_factor)
    reho.actor_decomposition_optimization(scenario)

    # print(reho.results["Renters"][0]["df_Actors_tariff"].xs("Electricity").mean(), "\n")
    # print(reho.results["Renters"][0]["df_Actors"])
    # Save results
    reho.save_results(format=["pickle"], filename='Test_9529')