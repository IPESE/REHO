from reho.model.postprocessing.sensitivity_analysis import *
from reho.plotting import plotting
from reho.model.preprocessing.mobility_generator import *
import datetime

from scripts.solene.functions import *

if __name__ == '__main__':
    date = datetime.datetime.now().strftime("%d_%H%M")

    districts = [234,3112,837]
    n_buildings = 2
    district_parameters = { # DUMMY VALUES FOR NOW
        234 : {"N_house" : 129,"rho" : pd.Series([95,3,2],index=['household','industry','service']), "f" : 1 , "Scluster" : 94322 },
        3112 : {"N_house" : 200,"rho" : pd.Series([89,2,6],index=['household','industry','service']), "f" : 1 , "Scluster" : 110399 },
        837 : {"N_house" : 56,"rho" : pd.Series([70,10,20],index=['household','industry','service']), "f" : 1 , "Scluster" : 56540 }
    }

    district_parameters = compute_district_parameters(district_parameters)

    for k in district_parameters.keys():
        district_parameters[k]['Population'] = n_buildings * district_parameters[k]['PopHouse']


    # GETTING THE SAMPLED PARAMETERS ================================================================================

    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(transformer=234, nb_buildings=2)
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = [ 'NG_Cogeneration','Battery']
    scenario['enforce_units'] = ['EV_district']
    scenario['specific'] = []
    scenario['EMOO'] = {}
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids,district_data = True)
    method = {'building-scale': True} #coordination entre batiments ou non 

    # SA object used to generate the sampled values
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    SA  = SensitivityAnalysis(reho, SA_type="Monte_Carlo", sampling_parameters=8)
    SA_parameters = {'Elec_retail': [0.2, 0.45],"share_cars" : [0,0.6], 'DailyDist' : [15,30], "share_EV_infleet" : [0.5,1]}
    SA.build_SA( SA_parameters=SA_parameters,unit_parameter = [])

    df_sampling = pd.DataFrame(SA.sampling.T, index = SA.problem['names'])

    # Initialization of reho objects - one per district =====================================================================================================
    for tr in districts:
        qbuildings_data = reader.read_db(transformer=tr, nb_buildings=n_buildings)
        
        ## District parameters and sets
        ext_districts = [d for d in districts if d != tr]
        set_indexed = {"Districts": ext_districts}
        parameters = {'Population': district_parameters[tr]['Population']}
        
        vars()[f'reho_{tr}'] = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, parameters=parameters, set_indexed=set_indexed, solver="gurobiasl")

        # Compute the f parameter
        district_parameters[tr]['f'] = district_parameters[tr]['Scluster'] / vars()['reho_' + str(tr)].ERA

        # Compute the share activity parameter
        df_rho = pd.DataFrame()
        for k in district_parameters.keys():
            df_rho[k] = district_parameters[k]['rho']
            df_rho[k] *= district_parameters[k]['Scluster']
        df_rho = df_rho.T.rename(columns={'industry': 'work', 'service': 'leisure'})
    

    # RUN the different samples
    for s in range(len(SA.sampling)):
        print("Co-optimization number", str(s + 1) + "/" + str(len(SA.sampling)))

        # scenario
        scenario['name'] = f'S{s+1}'

        # parameters
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
            
            qbuildings_data = {'buildings_data': vars()[f"reho_{tr}"].buildings_data}
            vars()[f"reho_{tr}"].infrastructure = infrastructure.Infrastructure(qbuildings_data, units, grids)

            vars()[f"reho_{tr}"].single_optimization(Pareto_ID = i)

            pi = vars()[f"reho_{tr}"].results_MP[f'S{s+1}'][i][0]["df_Dual_t"]["pi"].xs("Electricity")
            variables[tr] = {  "pi": pi
                                    }
            
        # Compute the share activity parameter
        parameters, variables  = compute_iterative_parameters(variables,district_parameters,only_prices=True)

        # Iterations for co-optimization
        for i in range(1,5):
            for tr in districts:
                print(f"S{s+1} - iteration {i} : district {tr}")

                vars()[f"reho_{tr}"].method['external_district'] = True
                ext_districts = [d for d in districts if d != tr]
                vars()[f"reho_{tr}"].parameters["share_activity"] = rho_param(ext_districts,df_rho)
                for p in parameters[tr].keys():
                    vars()[f"reho_{tr}"].parameters[p] = parameters[tr][p]
                
                vars()[f"reho_{tr}"].single_optimization(Pareto_ID = i)

                pi = vars()[f"reho_{tr}"].results_MP[f'S{s+1}'][i][0]["df_Dual_t"]["pi"].xs("Electricity")
                df_Unit_t = vars()[f"reho_{tr}"].results[f'S{s+1}'][i]['df_Unit_t']
                df_Grid_t = vars()[f"reho_{tr}"].results[f'S{s+1}'][i]['df_Grid_t']


                variables[tr] = {  "pi": pi,
                                    "df_Unit_t" : df_Unit_t,
                                    "df_Grid_t" : df_Grid_t
                                    }
            
            parameters, variables  = compute_iterative_parameters(variables,district_parameters)

        # Delete intermediate results
        for tr in districts:
            # TODO : add something to save pi
            vars()[f"reho_{tr}"].results_MP = {}
            vars()[f"reho_{tr}"].results_SP = {}

    # # Save results
    for tr in districts:
        vars()[f"reho_{tr}"].save_results(format=[ 'pickle',"save_all"], filename=f'SAcooptimization_{tr}_{date}')
    df_sampling.to_csv(f"SAcooptimization_samples_{date}.csv")
    # plotting.plot_performance(reho.results, plot='costs', indexed_on='Pareto_ID', label='EN_long', title="Economical performance").show()
    # reho.save_results(format=['xlsx', 'pickle'], filename='4b')
