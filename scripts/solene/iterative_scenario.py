import pandas as pd

from reho.model.reho import *
import datetime

def rho_param(ext_districts,S,activities = ["work","leisure","travel"]):
    """
    This function is used to calculate the parameter rho from the share of activities S(a) in each districts.
    To be updated when I have the values S.
    """
    rho = pd.DataFrame(index=ext_districts,columns=activities).fillna(1/len(ext_districts))
    rho = rho.stack().to_frame(name= "share_district_activity").reorder_levels([1,0])
    rho.loc['travel'] = 0 # additionnal precaution
    return rho




def compute_iterative_parameters(variables,parameters):
    df_load = pd.DataFrame()
    df_prices = pd.DataFrame()
    for d in variables.keys():
        df_load = pd.concat([df_load,variables[d]['externaldemand']])
        price = variables[d]['pi'].to_frame().copy()
        price['district'] = d
        price = price.set_index('district',append = True).reorder_levels([2,0,1])
        df_prices = pd.concat([df_prices,price])

    df_load = df_load.groupby(["district" ,"Period", "Time"]).agg('sum').stack()
    df_load = df_load.unstack(level='district').reorder_levels([2,0,1])
    
    for d in variables.keys():
            parameters[d] = {   "charging_externalload"     : df_load[[str(d)]].rename(columns={str(d) :"charging_externalload"}),
                                "outside_charging_price"    : df_prices[df_prices.index.get_level_values(level="district") != d].rename(columns = {'pi' : 'outside_charging_price'}),
                                "externalload_sellingprice" : variables[d]['pi'].to_frame(name = "externalload_sellingprice")}


    # # for 2 districts:
    # if len(variables.keys()) == 2:
    #     for d1,d2 in zip(variables.keys(),reversed(variables.keys())):
    #         parameters[d1] = {  "outside_charging_price"    : variables[d2]['pi'].to_frame(name=d2).stack().to_frame(name='outside_charging_price').reorder_levels([2,0,1]),
    #                             "charging_externalload"     : variables[d2]["externaldemand"].reset_index(level="district",drop=True).stack().to_frame(name = "charging_externalload").reorder_levels([2,0,1]),
    #                             "externalload_sellingprice" : variables[d1]['pi'].rename("externalload_sellingprice")
    #                     }
    # else:
    #     # temporary weights (for loads => loads should be replaced by district activity index, prices proxy to be found)
    #     # weights = pd.DataFrame(index=variables.keys(),columns=['leisure','work','travel']).fillna(1/len(variables.keys()))
    #     # df_load = pd.DataFrame(columns = variables.keys(),index=    variables[list(variables.keys())[0]]['externalload'].stack().to_frame().reorder_levels([2,0,1]).index).fillna(0)
    #     # df_prices = pd.DataFrame(columns = variables.keys(),index=  variables[list(variables.keys())[0]]['pi'].index).fillna(0)
        


    #     # for d in variables.keys(): # TODO : a refaire avec pas des boucles un jour :/
    #     #     for i in variables.keys():
    #     #         if i != d:
    #     #             w = weights.loc[i]/(1-weights.loc[d])
    #     #             #loads
    #     #             l = variables[d]['externaldemand'].mul(w)
    #     #             l.columns.name = 'Activity'
    #     #             l = l.stack().to_frame(name = i).reorder_levels([2,0,1])
    #     #             df_load[[i]] = df_load[[i]]  + l

    #     #             #prices
    #     #             wp = 1/(len(variables.keys()) - 1) # temporary weight
    #     #             p = variables[d]['pi'].mul(wp)
    #     #             p.name = i
    #     #             df_prices[i] = df_prices[i].add(p)
    #     for d in variables.keys():
    #         parameters[d] = {   "charging_externalload"     : df_load[[d]].rename(columns={d :"charging_externalload"}),
    #                             "outside_charging_price"    : df_prices[[d]].rename(columns={d :"outside_charging_price"}),
    #                             "externalload_sellingprice" : variables[d]['pi'].rename("externalload_sellingprice")}



def check_convergence(deltas,df_delta,variables):
    termination_threshold = 0.1 # 10% TODO : mettre ces tuning parametres somewhere else
    termination_iter = 3
    
    # Compute Delta
    df_demand = pd.DataFrame()
    df_load = pd.DataFrame()
    for k in variables.keys():
        df = variables[k]['externaldemand'].groupby(["Period","Time"]).agg("sum")
        df.columns.name = "Activity"
        df_demand[k] = df.stack()
       
        df = variables[k]['externalload']
        df.columns.name = "Activity"
        df_load[k] = df.stack()
    
    df_delta[f"demand{i}"] = df_demand.sum(axis=1)
    df_delta[f"load{i}"] = df_load.sum(axis=1)

    df_delta[f"delta{i}"] = df_delta[f"demand{i}"] - df_delta[f"load{i}"]
    delta = df_delta[f"delta{i}"].apply(lambda x : x*x).sum()
    deltas.append(delta)

    # Check no_improvement criteria
    count = 0
    convergence_reached = False
    if len(deltas) > 1:
        if deltas[-1] < 0.01:
            convergence_reached = True
    else:
        for n in range(len(deltas) - 1, -1, -1):
            t = abs((deltas[n] - deltas[n-1])/deltas[n])
            if t < termination_threshold:
                count += 1
            else:
                break
        if count >= termination_iter:
            convergence_reached = True
        else:
            convergence_reached = False

    return df_delta,convergence_reached



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

        df_delta,c = check_convergence(deltas,df_delta,variables)
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