from reho.model.postprocessing.sensitivity_analysis import *
from reho.model.preprocessing.mobility_generator import *
import datetime
from scripts.solene.functions import *

def remove_nan_QBuilding(buildings_data):
    for bui in buildings_data["buildings_data"]:
        bui_class = buildings_data["buildings_data"][bui]["id_class"]
        buildings_data["buildings_data"][bui]["id_class"] = buildings_data["buildings_data"][bui]["id_class"].replace("nan", "II")
        buildings_data["buildings_data"][bui]["id_class"] = buildings_data["buildings_data"][bui]["id_class"].replace("VIII", "III")
        buildings_data["buildings_data"][bui]["ratio"] = buildings_data["buildings_data"][bui]["ratio"].replace("nan", "0.0")
        if bui_class != buildings_data["buildings_data"][bui]["id_class"]:
            print(bui, "had nan class and was", bui_class)
        if math.isnan(buildings_data["buildings_data"][bui]["U_h"]):
            buildings_data["buildings_data"][bui]["U_h"] = 0.00181
        if math.isnan(buildings_data["buildings_data"][bui]["HeatCapacity"]):
            buildings_data["buildings_data"][bui]["HeatCapacity"] = 120
        if math.isnan(buildings_data["buildings_data"][bui]["T_comfort_min_0"]):
            buildings_data["buildings_data"][bui]["T_comfort_min_0"] = 20
    return buildings_data

def filter_data(reho, s):
    for i in reho.results[f'S{s + 1}']:
        df_Unit_t_local = reho.results[f'S{s + 1}'][i]["df_Unit_t"]
        reho.results[f'S{s + 1}'][i]["df_Unit_t"] = df_Unit_t_local[df_Unit_t_local.index.get_level_values("Unit").str.contains("district")]
        df_Grid_t_local = reho.results[f'S{s + 1}'][i]["df_Grid_t"]
        reho.results[f'S{s + 1}'][i]["df_Grid_t"] = df_Grid_t_local[["Grid_demand", "Grid_supply"]]
        reho.results[f'S{s + 1}'][i]["df_Grid_t_net"] = df_Grid_t_local.xs("Network", level="Hub")
    return reho


if __name__ == '__main__':
    date = datetime.datetime.now().strftime("%d_%H%M")

    district_parameters = pd.read_csv(os.path.join(path_to_mobility, 'leman.csv'), index_col=0)
    districts = list(district_parameters.index.values)
    districts = [int(x) for x in districts]
    n_buildings = 600

    reader = QBuildingsReader()
    qbuildings_data = {}
    for tr in districts:
        path = 'data/' + str(tr) + '_'
        qbuildings_data[tr] = reader.read_csv(buildings_filename=path+'buildings.gpkg', nb_buildings=n_buildings,
                                      roofs_filename=path+'roofs.gpkg', facades_filename=path+'facades.gpkg')
        qbuildings_data[tr] = remove_nan_QBuilding(qbuildings_data[tr])
        district_parameters.at[tr, "Scluster"] = np.sum([qbuildings_data[tr]["buildings_data"][bui]["ERA"] for bui in qbuildings_data[tr]["buildings_data"]])

    district_parameters = compute_district_parameters(district_parameters)
    for k in district_parameters.keys():
        district_parameters[k]['Population'] = len(qbuildings_data[k]["buildings_data"]) * district_parameters[k]['PopHouse']

    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = [ 'NG_Cogeneration', 'Battery']
    scenario['enforce_units'] = ['EV_district']
    scenario['specific'] = []
    scenario['EMOO'] = {}
    grids = infrastructure.initialize_grids({'Electricity': {}, 'NaturalGas': {}, 'FossilFuel': {}, 'Mobility': {}})
    grids["Electricity"]["ReinforcementTrOfLayer"] = np.array([200.0, 1000.0])
    tr_capacity = {9678: 200.0, 9697: 1000.0, 2534: 200.0, 10260: 200.0, 10312: 1000.0}

    units = infrastructure.initialize_units(scenario, grids,district_data=True)
    method = {'use_pv_orientation': True, 'use_dynamic_emission_profiles': True, 'district-scale': True,
              "print_logs": False, "save_timeseries": False, "save_data_input": False, "include_all_solutions": True}
    DW_params = {"max_iter": 3}

    # SA object used to generate the sampled values
    reho = REHO(qbuildings_data=qbuildings_data[districts[0]], units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobiasl", DW_params=DW_params)
    SA = SensitivityAnalysis(reho, SA_type="Monte_Carlo", sampling_parameters=2)
    SA_parameters = {'Elec_retail': [0.15, 0.4], "Elec_feedin": [0.0, 0.149], "NG_retail": [0.1, 0.3],
                     'DailyDist': [15, 45], "share_cars": [0.0, 1.0], "share_EV_infleet": [0.0, 1.0]}
    SA.build_SA(SA_parameters=SA_parameters, unit_parameter=[])
    df_sampling = pd.DataFrame(SA.sampling.T, index=SA.problem['names'])

    # Initialization of reho objects - one per district
    for tr in districts:
        ext_districts = [d for d in districts if d != tr]
        set_indexed = {"Districts": ext_districts}
        parameters = {'Population': district_parameters[tr]['Population'], 'Transformer_Ext': np.array([tr_capacity[tr], 1e6, 1e6, 1e6]),
                      "CostTransformer_inv1": np.array([10000, 0, 0, 0]), "CostTransformer_inv2": np.array([10000, 0, 0, 0])}
        vars()[f'reho_{tr}'] = REHO(qbuildings_data=qbuildings_data[tr], units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, parameters=parameters, set_indexed=set_indexed, solver="gurobiasl", DW_params=DW_params)
        district_parameters[tr]['f'] = district_parameters[tr]['Scluster'] * 10**6/ vars()['reho_' + str(tr)].ERA

        # Compute the share activity parameter
        df_rho = pd.DataFrame()
        for k in district_parameters.keys():
            df_rho[k] = district_parameters[k]['rho']
            df_rho[k] *= district_parameters[k]['Scluster']
        df_rho = df_rho.T.rename(columns={'industry': 'work', 'service': 'leisure'})

    pi_results = {}
    # RUN the different samples
    for s in range(len(SA.sampling)):
        try:
            pi_results[f'S{s+1}'] = {}
            print("Co-optimization number", str(s + 1) + "/" + str(len(SA.sampling)))

            scenario['name'] = f'S{s+1}'
            sample = SA.sampling[s]
            mob_param = SA.format_mobilitySA(sample)

            # variables for co-optimisation
            variables = dict()

            # Initialization RUN
            i = 0
            for tr in districts:
                print(f"S{s+1} - iteration {i} (uncoordinated): district {tr}")

                # Parameters update
                vars()[f"reho_{tr}"].scenario = scenario
                for p in mob_param.keys():
                    vars()[f"reho_{tr}"].parameters[p] = mob_param[p]
                for k, value in enumerate(sample):
                    parameter = list(SA.parameter.keys())[k]
                    if parameter == 'Elec_retail':
                        grids["Electricity"]["Cost_supply_cst"] = value
                    elif parameter == 'Elec_feedin':
                        grids["Electricity"]["Cost_demand_cst"] = value
                    elif parameter == 'NG_retail':
                        grids["NaturalGas"]["Cost_supply_cst"] = value

                qbuildings_data[tr] = {'buildings_data': vars()[f"reho_{tr}"].buildings_data}
                vars()[f"reho_{tr}"].infrastructure = infrastructure.Infrastructure(qbuildings_data[tr], units, grids)

                vars()[f"reho_{tr}"].single_optimization(Pareto_ID = i)

                pi = vars()[f"reho_{tr}"].results_MP[f'S{s+1}'][i][0]["df_Dual_t"]["pi"].xs("Electricity")
                variables[tr] = {"pi": pi}

            # Compute the share activity parameter
            parameters, variables = compute_iterative_parameters(variables, district_parameters,only_prices=True)

            # Iterations for co-optimization
            for i in range(1, 4):
                for tr in districts:
                    print(f"S{s+1} - iteration {i} : district {tr}")
                    vars()[f"reho_{tr}"].method['external_district'] = True
                    ext_districts = [d for d in districts if d != tr]
                    vars()[f"reho_{tr}"].parameters["share_activity"] = rho_param(ext_districts, df_rho)
                    for p in parameters[tr].keys():
                        vars()[f"reho_{tr}"].parameters[p] = parameters[tr][p]
                    vars()[f"reho_{tr}"].single_optimization(Pareto_ID = i)

                    pi = vars()[f"reho_{tr}"].results_MP[f'S{s+1}'][i][0]["df_Dual_t"]["pi"].xs("Electricity")
                    df_Unit_t = vars()[f"reho_{tr}"].results[f'S{s+1}'][i]['df_Unit_t']
                    df_Grid_t = vars()[f"reho_{tr}"].results[f'S{s+1}'][i]['df_Grid_t']
                    variables[tr] = {"pi": pi, "df_Unit_t" : df_Unit_t, "df_Grid_t" : df_Grid_t}

                parameters, variables = compute_iterative_parameters(variables,district_parameters)

            # Delete intermediate results
            for tr in districts:
                pi_results[f'S{s+1}'][tr] = {}
                for i in vars()[f"reho_{tr}"].results_MP[f"S{s+1}"]:
                    pi_results[f'S{s+1}'][tr][i] = {}
                    for j in vars()[f"reho_{tr}"].results_MP[f"S{s+1}"][i]:
                        pi_results[f'S{s+1}'][tr][i][j] = vars()[f"reho_{tr}"].results_MP[f"S{s+1}"][i][j]["df_Dual_t"]["pi"]
                    pi_results[f'S{s+1}'][tr][i] = pd.DataFrame.from_dict(pi_results[f'S{s+1}'][tr][i])
            for tr in districts:
                vars()[f"reho_{tr}"].initialize_optimization_tracking_attributes()
                vars()[f"reho_{tr}"] = filter_data(vars()[f"reho_{tr}"], s)
        except:
            vars()[f"reho_{tr}"].results[f'S{s+1}'] = None

    # Save results
    print("End")
    results = {}
    for tr in districts:
        results[tr] = vars()[f"reho_{tr}"].results
    vars()[f"reho_{districts[0]}"].results = results
    vars()[f"reho_{districts[0]}"].save_results(format=['pickle'], filename=f'SA_{date}')

    df_sampling.to_csv(f"results/SA_samples_{date}.csv")

    f = open(f"results/SA_pi_{date}.pickle", 'wb')
    pickle.dump(pi_results, f)
    f.close()