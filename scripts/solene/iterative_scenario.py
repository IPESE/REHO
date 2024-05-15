import pandas as pd

from reho.model.reho import *
from reho.model.preprocessing.EV_profile_generator import *
import datetime


if __name__ == '__main__':

    districts = [3658,3112,277]

    # Initialization of scenarios - Generic parameters
    ## Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')

    ## Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    ## Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['EMOO'] = {}
    scenario['specific'] = []
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']

    ## Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    ## Set method options
    method = {'building-scale': True}

    # Initialization of scenarios - District parameters
    for transformer in districts:
        ## Set building parameters
        qbuildings_data = reader.read_db(transformer=transformer, nb_buildings=2)
        
        ## District parameters
        ext_districts = [d for d in districts if d != transformer]
        parameters = {'Population': 9,
                      "Districts" : ext_districts,
                      "share_district_activity": rho_param(ext_districts,1) } # other districts 

        vars()['reho_' + str(transformer)] = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario,
                    method=method, parameters=parameters, solver="baron")

    # if you want to add non-zero params  ["outside_charging_price","charging_externalload"] for the init scenario
    PARAM_INIT = False
    with open('data/mobility/parameters_iteration.pickle', 'rb') as handle:
        parameters_init = pickle.load(handle)


    # Run optimization
    df_pi = pd.DataFrame()
    df_externalcharging = pd.DataFrame()
    variables = dict()
    parameters = dict()
    deltas = list()
    df_delta = pd.DataFrame()

    # Iterations
    for i in range(10):
        for transformer in districts:
            print(f"iteration {i} : district {transformer}")
            # Add iterative parameters (only after init run i=0)
            if i > 0 :
                for param in parameters[transformer].keys():
                    vars()['reho_' + str(transformer)].parameters[param] = parameters[transformer][param]
            elif PARAM_INIT:
                for param in parameters_init[transformer].keys():
                    vars()['reho_' + str(transformer)].parameters[param] = parameters_init[transformer][param]
            

            # Run
            vars()['reho_' + str(transformer)].single_optimization(Pareto_ID = i)

            # getting variables for iteration
            pi = vars()['reho_' + str(transformer)].results_MP["totex"][i][0]["df_Dual_t"]["pi"].xs("Electricity")
            df_Unit_t = vars()['reho_' + str(transformer)].results['totex'][i]['df_Unit_t']
            df_Grid_t = vars()['reho_' + str(transformer)].results['totex'][i]['df_Grid_t']

            EV_E_charged_outside = df_Unit_t.loc[:,df_Unit_t.columns.str.startswith("EV_E_charged_outside")][df_Unit_t.index.get_level_values('Layer') == 'Electricity']
            externaldemand = EV_E_charged_outside.reset_index().groupby(['Period','Time']).agg('sum',numeric_only = True)
            externaldemand.columns = [x.split('[')[1].split(']')[0] for x in externaldemand.columns]
            externaldemand.columns = pd.MultiIndex.from_tuples([(x.split(',')[0],x.split(',')[1]) for x in externaldemand.columns])
            externaldemand.columns.names = ('activity','district')
            externaldemand = externaldemand.stack(level=1).reorder_levels([2,0,1])

            externalload = df_Grid_t.loc[:,df_Grid_t.columns.str.startswith("charging_externalload")][(df_Grid_t.index.get_level_values('Layer') == 'Electricity') & (df_Grid_t.index.get_level_values('Hub') == 'Network')]
            externalload = externalload.droplevel(['Layer','Hub'])
            externalload.columns = [x.split('[')[1].split(']')[0] for x in externalload.columns]

            print(pi, EV_E_charged_outside)
            variables[transformer] = {  "pi": pi,
                                        "EV_E_charged_outside" : EV_E_charged_outside,
                                        "externaldemand" : externaldemand,
                                        "externalload" : externalload
                                        }
            
            # results formatting
            pi = pd.DataFrame(pi).rename(columns = {"pi" : f"{i}_{transformer}"})
            df_pi = pd.concat([df_pi,pi],axis = 1)
            EV_E_charged_outside.columns = [col.replace("EV_E_charged_outside",f"{i}_{transformer}") for col in EV_E_charged_outside.columns] 
            df_externalcharging = pd.concat([df_externalcharging,EV_E_charged_outside],axis = 1)
        
        # Computing parameters for next iteration 
        compute_iterative_parameters(variables,parameters)

        df_delta,c = check_convergence(deltas,df_delta,variables,i)
        if c:
            print("Convergence criteria is reached")
            break

    date = datetime.datetime.now().strftime("%d_%H%M")
    for transformer in districts:
        vars()['reho_' + str(transformer)].save_results(format=['xlsx', 'pickle'], filename='Iterative')
        vars()['reho_' + str(transformer)].save_mobility_results(filename=f"iter_{date}")
    print(df_pi)
    print(df_externalcharging)

    with open('data/mobility/parameters_iteration.pickle', 'wb') as handle:
        pickle.dump(parameters, handle, protocol=pickle.HIGHEST_PROTOCOL)