from reho.model.actors_problem import *
import time

def build_district(transformer, nb_buildings):
    reader = QBuildingsReader(load_roofs=True)
    path = ""#'scripts/examples/6_Actors_problem/'
    qbuildings_data = reader.read_csv(buildings_filename=path+'case_study/buildings_'+str(transformer)+'.gpkg',
                                      roofs_filename=path+'case_study/roofs_'+str(transformer)+'.gpkg', nb_buildings=nb_buildings)
    qbuildings_data = filter_nan(qbuildings_data)
    return qbuildings_data


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

    clusters_data = pd.read_csv("./clusters_data.csv")
    run_id = 1
    runs = [[0, 1, 2], [3], [4], [5], [6], [7]][run_id]

    for i in runs:
        try:
            transformer = int(clusters_data.loc[i, 'transformer'])
            cluster_num = clusters_data.loc[i, 'cluster_num']
            location = clusters_data.loc[i, 'location']
            nb_buildings = 1000
            risk_factor = float(clusters_data.loc[i, 'risk_factor'])
            TransformerCapacity = float(clusters_data.loc[i, 'TransformerCapacity'])
            n_samples = 2

            Owner_portfolio = True
            Utility_portfolio = False
            Owner_PIR = False

            # Set scenario
            scenario = dict()
            scenario['Objective'] = 'TOTEX'
            scenario['EMOO'] = {}
            scenario['specific'] = ['Renter_noSub', 'Owner_Sub_bigM_ub']

            # Set building parameters
            #reader = QBuildingsReader(load_roofs=True)
            #reader.establish_connection('Suisse')
            #qbuildings_data = reader.read_db(15154, nb_buildings=nb_buildings)
            qbuildings_data = build_district(transformer, nb_buildings)

            # Set specific parameters
            parameters = {"TransformerCapacity": np.array([TransformerCapacity*3, 1e8])}

            # Select clustering options for weather data
            cluster = {'Location': location, 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

            # Choose energy system structure options
            scenario['exclude_units'] = ['ThermalSolar', 'NG_Cogeneration','Battery']
            scenario['enforce_units'] = []

            # Set method options
            method = {'actors_problem': True, "print_logs": False, "refurbishment": True, "include_all_solutions": False,
                      'use_pv_orientation': True, 'use_facades': False,  "use_dynamic_emission_profiles": True,
                      "save_streams": False, "save_timeseries": False, "save_data_input": False}

            # Initialize available units and grids
            grids = infrastructure.initialize_grids({'Electricity': {"Cost_demand_cst": 0.1, "Cost_supply_cst": 0.3346},
                                                     'NaturalGas': {"Cost_supply_cst": 0.14}})
            units = infrastructure.initialize_units(scenario, grids)

            DW_params={}
            DW_params['max_iter'] = 6

            # Initiate the actor-based problem formulation
            reho = ActorsProblem(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobiasl", DW_params=DW_params)

            # Generate configurations
            tariffs_ranges = {'Electricity': {"Cost_supply_cst": [0.15, 0.45]},
                              'NaturalGas': {"Cost_supply_cst": [0.10, 0.30]}}
            try:
                reho.read_configurations()  # if configurations were already generated, simply import them
            except FileNotFoundError:
                reho.generate_configurations(n_sample=2, tariffs_ranges=tariffs_ranges)

            # Define boundaries
            if Utility_portfolio:
                reho.scenario["name"] = "Utility"
                print("Calculate boundary for Utility")
                reho.execute_actors_problem(n_sample=n_samples, bounds=None, actor="Utility")
                bound_d = [0, -np.array(
                    [reho.results[i][0]["df_Actors"].loc["Utility"][0] for i in reho.results]).max() / 2]
            else:
                print("Calculate boundary for Utility: DEFAULT 0")
                bound_d = [0, 0.000001]

            # Define owner boundaries
            # TODO: Adjust the bound_o depending on the first results
            if Owner_portfolio:
                reho.scenario["name"] = "Owners"
                print("Calculate boundary for Owners")
                reho.execute_actors_problem(n_sample=n_samples, bounds=None, actor="Owners")
                bound_o = [0, 0.5]
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
            #reho.save_samples_parameters(df_name='samples', file_name='samples_{}'.format(transformer))

            reho.actor_decomposition_optimization(scenario)

            time_now = time.strftime("%d_%Hh%M")
            # Save results
            reho.save_results(format=["pickle"], filename='Sc3.1_CH_{}_{}'.format(transformer, time_now))
            del reho

        except:
            pass