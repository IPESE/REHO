from reho.model.reho import *
from reho.model.preprocessing.mobility_generator import *


if __name__ == '__main__':

    # GENERAL DESCRIPTION =========================================================================================================
    # This script provides an example of multiple districts co-optimization regarding electric vehicles usage.
    # EVs can be charged both in their district of residence as well as the other optimized districts. 
    # To quantify the various charging exchanges, each district is optimized iteratively until convergence. 


    # DISTRICT PARAMETERS =========================================================================================================
    districts = [13219 ,13569,13228]
    district_parameters  = {        
        13569 : {"PopHouse" : 7.71, "rho" : pd.Series([96,3,1],index=['household','industry','service']), "f" : 1 , "Scluster" : 3552764}  ,
        13219 : {"PopHouse" : 9.59, "rho" : pd.Series([62,19,19],index=['household','industry','service']), "f" : 1 , "Scluster" : 3003409},
        13228 : {"PopHouse" : 11.29, "rho" : pd.Series([53,22,25],index=['household','industry','service']), "f" : 1 , "Scluster" : 3301366}
        }
    # rho describes typologies of districts (% of building respectively in the categories housing, industry and services)
    # f and Scluster are used to scale up the result of one district's optimisation to the cluster of district it is representative of.  
    # (see Methodo 2.2.3.2 in PDM solene)

    n_buildings = 2
    for k in district_parameters.keys():
        district_parameters[k]['Population'] = n_buildings * district_parameters[k]['PopHouse'] 

    # SET UP ======================================================================================================================
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')

    # Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['EMOO'] = {}
    scenario['specific'] = []
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids,district_data=True)

    # Set method options
    method = {'building-scale': True,
              }
    
    # Initialisation of REHO objects =======================================================================
    reho_models = {}
    for tr in districts:
        qbuildings_data = reader.read_db(district_id=tr, nb_buildings=n_buildings)

        ext_districts = [d for d in districts if d != tr]
        set_indexed = {"Districts": ext_districts}
        parameters = {"Population": district_parameters[tr]['Population'],
                      "DailyDist" : {'D0': 25, 'D1': 10}
                      }
        modal_split = pd.DataFrame({"min_D0" : [0,0,0.4,0.4], "max_D0" : [0.1,0.3,0.7,0.7],"min_D1" : [0,0.2,0.4,0.4], "max_D1" : [0,0.4,0.7,0.7]}, index = ['MD','PT','cars','EV_district'])
        
        reho_models[tr] = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario,
                    method=method, parameters=parameters, set_indexed=set_indexed, solver="gurobiasl")
        reho_models[tr].modal_split = modal_split

        # Compute f and share_activity parameters
        district_parameters[tr]['f'] = district_parameters[tr]['Scluster'] / reho_models[tr].ERA
        df_rho = pd.DataFrame()
        for k in district_parameters.keys():
            df_rho[k] = district_parameters[k]['rho']
            df_rho[k] *= district_parameters[k]['Scluster']
        df_rho = df_rho.T.rename(columns={'industry': 'work', 'service': 'leisure'})
    

    # ITERATION INIT ====================================================================================================================
    # Iteration 0 is computed to initialize the selling and retail prices. 

    i = 0 
    for tr in districts:
        print(f"Iteration {i} : district {tr}")
        reho_models[tr].single_optimization(Pareto_ID = i)

    parameters = compute_iterative_parameters(reho_models, Scn_ID='totex', iter=i, district_parameters=district_parameters, only_prices=True)


    # ITERATIONS =========================================================================================================================
    for i in range(1,3):
        for tr in districts:
            print(f"Iteration {i} : district {tr}")

            reho_models[tr].method['external_district'] = True
            ext_districts = [d for d in districts if d != tr]
            reho_models[tr].parameters["share_activity"] = rho_param(ext_districts, df_rho)
            for p in parameters[tr].keys():
                reho_models[tr].parameters[p] = parameters[tr][p]

            reho_models[tr].single_optimization(Pareto_ID = i)

        parameters = compute_iterative_parameters(reho_models, Scn_ID=f'totex', iter=i, district_parameters=district_parameters)

    print('End')
    results = {}
    for tr in districts:
        results[tr] = reho_models[tr].results
    reho_models[districts[0]].results = results
    reho_models[districts[0]].save_results(format=['pickle'], filename=f'6c')