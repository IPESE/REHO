from reho.model.postprocessing.sensitivity_analysis import *
from reho.model.preprocessing.mobility_generator import *
import datetime
from scripts.solene.functions import *


if __name__ == '__main__':
    date = datetime.datetime.now().strftime("%d_%H%M")

    district_parameters = pd.read_csv(os.path.join(path_to_mobility, 'leman.csv'), index_col=0)
    districts = list(district_parameters.index.values)
    districts = [int(x) for x in districts]
    n_buildings = 3

    reader = QBuildingsReader(load_roofs=True)
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
    method = {'use_pv_orientation': True, 'use_dynamic_emission_profiles': True, 'building-scale': True,
              "print_logs": False, "save_timeseries": False, "save_data_input": False, "include_all_solutions": True}
    DW_params = {"max_iter": 2}

    # SA object used to generate the sampled values
    reho = REHO(qbuildings_data=qbuildings_data[districts[0]], units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobiasl", DW_params=DW_params)
    SA = SensitivityAnalysis(reho, SA_type="Monte_Carlo", sampling_parameters=2)
    SA_parameters = {'Elec_retail': [0.15, 0.4], "Elec_feedin": [0.0, 0.149], "NG_retail": [0.1, 0.3],
                     'DailyDist': [15, 45], "share_cars": [0.0, 1.0], "share_EV_infleet": [0.0, 1.0]}
    SA.build_SA(SA_parameters=SA_parameters, unit_parameter=[])
    df_sampling = pd.DataFrame(SA.sampling.T, index=SA.problem['names'])

    # Initialization of reho objects - one per district
    reho_models = {}
    for tr in districts:
        ext_districts = [d for d in districts if d != tr]
        set_indexed = {"Districts": ext_districts}
        parameters = {'Population': district_parameters[tr]['Population'], 'Transformer_Ext': np.array([tr_capacity[tr], 1e6, 1e6, 1e6]),
                      "CostTransformer_inv1": np.array([14000, 0, 0, 0]), "CostTransformer_inv2": np.array([8, 0, 0, 0])}
        reho_models[tr] = REHO(qbuildings_data=qbuildings_data[tr], units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, parameters=parameters, set_indexed=set_indexed, solver="gurobiasl", DW_params=DW_params)
        district_parameters[tr]['f'] = district_parameters[tr]['Scluster'] * 10**6/ reho_models[tr].ERA

        # Compute the share activity parameter
        df_rho = pd.DataFrame()
        for k in district_parameters.keys():
            df_rho[k] = district_parameters[k]['rho']
            df_rho[k] *= district_parameters[k]['Scluster']
        df_rho = df_rho.T.rename(columns={'industry': 'work', 'service': 'leisure'})

    pi_results = {}
    # RUN the different samples
    for s in range(len(SA.sampling)):
        
        pi_results[f'S{s+1}'] = {}
        print("Co-optimization number", str(s + 1) + "/" + str(len(SA.sampling)))

        scenario['name'] = f'S{s+1}'
        sample = SA.sampling[s]
        DailyDist, modal_split = SA.format_mobilitySA(sample)

        # Initialization RUN
        i = 0
        for tr in districts:
            print(f"S{s+1} - iteration {i} (uncoordinated): district {tr}")

            # Parameters update
            reho_models[tr].scenario = scenario
            reho_models[tr].parameters['DailyDist'] = DailyDist
            reho_models[tr].modal_split = modal_split
            for k, value in enumerate(sample):
                parameter = list(SA.parameter.keys())[k]
                if parameter == 'Elec_retail':
                    grids["Electricity"]["Cost_supply_cst"] = value
                elif parameter == 'Elec_feedin':
                    grids["Electricity"]["Cost_demand_cst"] = value
                elif parameter == 'NG_retail':
                    grids["NaturalGas"]["Cost_supply_cst"] = value

            qbuildings_data[tr] = {'buildings_data': reho_models[tr].buildings_data}
            reho_models[tr].infrastructure = infrastructure.Infrastructure(qbuildings_data[tr], units, grids)
            reho_models[tr].single_optimization(Pareto_ID = i)

        # Compute the share activity parameter
        parameters = compute_iterative_parameters(reho_models, Scn_ID=f'S{s+1}', iter=i, district_parameters=district_parameters, only_prices=True)

        # Iterations for co-optimization
        for i in range(1, 4):
            for tr in districts:
                print(f"S{s+1} - iteration {i} : district {tr}")
                reho_models[tr].method['external_district'] = True
                ext_districts = [d for d in districts if d != tr]
                reho_models[tr].parameters["share_activity"] = rho_param(ext_districts, df_rho)
                for p in parameters[tr].keys():
                    reho_models[tr].parameters[p] = parameters[tr][p]
                reho_models[tr].single_optimization(Pareto_ID=i)

            parameters = compute_iterative_parameters(reho_models, Scn_ID=f'S{s+1}', iter=i, district_parameters=district_parameters)

        # Store pi results
        for tr in districts:
            pi_results[f'S{s+1}'][tr] = {}
            for i in reho_models[tr].results_MP[f"S{s+1}"]:
                pi_results[f'S{s+1}'][tr][i] = {}
                for j in reho_models[tr].results_MP[f"S{s+1}"][i]:
                    pi_results[f'S{s+1}'][tr][i][j] = reho_models[tr].results_MP[f"S{s+1}"][i][j]["df_Dual_t"]["pi"]
                pi_results[f'S{s+1}'][tr][i] = pd.DataFrame.from_dict(pi_results[f'S{s+1}'][tr][i])

        # Delete intermediate results
        for tr in districts:
            reho_models[tr].initialize_optimization_tracking_attributes()
            reho_models[tr] = filter_data(reho_models[tr], s)

 

    # Save results
    print("End")
    results = {}
    for tr in districts:
        results[tr] = reho_models[tr].results
    reho_models[districts[0]].results = results
    reho_models[districts[0]].save_results(format=['pickle'], filename=f'SA_{date}')

    df_sampling.to_csv(f"results/SA_samples_{date}.csv")

    f = open(f"results/SA_pi_{date}.pickle", 'wb')
    pickle.dump(pi_results, f)
    f.close()