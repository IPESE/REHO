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

    cluster_num = 1
    location = 'Zurich'
    nb_buildings = 5
    renter_expense_ub = 100000
    n_samples = 3

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['EMOO'] = {}
    scenario['specific'] = ['Renter_noSub', 'Owner_Link_Subsidy_to_Insulation'] # activating constraints

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
    scenario['exclude_units'] = ['ThermalSolar', 'NG_Cogeneration', 'Battery']
    scenario['enforce_units'] = []

    # Set method options
    method = {'actors_problem': True, "print_logs": True, "refurbishment": True,
              'use_pv_orientation': True, 'use_facades': False, "use_dynamic_emission_profiles": True,
              "save_streams": False, "save_timeseries": False, "save_data_input": False, "parallel_computation": True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {"Cost_demand_cst": 0.1, "Cost_supply_cst": 0.3346},  'NaturalGas': {"Cost_supply_cst": 0.14}})
    units = infrastructure.initialize_units(scenario, grids)
    DW_params={}
    DW_params['max_iter'] = 3
    # Initiate the actor-based problem formulation
    reho = ActorsProblem(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobiasl", DW_params=DW_params)

    # Generate configurations
    tariffs_ranges = {'Electricity': {"Cost_supply_cst": [0.15, 0.45]},
                      'NaturalGas': {"Cost_supply_cst": [0.10, 0.30]}}
    try:
        reho.read_configurations()  # if configurations were already generated, simply import them
    except FileNotFoundError:
        reho.generate_configurations(n_sample=n_samples, tariffs_ranges=tariffs_ranges)

    # Set value / sampling range for actors epsilon
    actors_epsilon = {"renter_expense_max": renter_expense_ub,
                      #"utility_profit_min": [0, 200],
                      "owner_PIR_min": [0, 0.1],
                      }

    bounds = reho.set_actors_epsilon(actors_epsilon)
    reho.sample_actors_epsilon(bounds=bounds, n_samples= n_samples, linear=False)

    #Run actor-based optimization
    reho.scenario["name"] = "MOO_actors"
    reho.actor_decomposition_optimization(scenario)
    # Save results
    reho.save_results(format=["pickle"], filename='Test_9529')