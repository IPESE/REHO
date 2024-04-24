from reho.model.reho import *
import datetime

def compute_iterative_parameters(variables,parameters):
    # for 2 districts:
    if len(variables.keys()) == 2:
        for d1,d2 in zip(variables.keys(),reversed(variables.keys())):
            parameters[d1] = {    "outside_charging_price" : variables[d2]['pi'].rename("outside_charging_price"),
                            "charging_externalload"  : variables[d2]["externaldemand"].stack().to_frame(name = "charging_externalload")
                        }

def check_convergence(deltas,df_delta,variables):
    
    # Compute Delta
    df_demand = pd.DataFrame()
    df_load = pd.DataFrame()
    for k in variables.keys():
        df = variables[k]['externaldemand']
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
    return df_delta



if __name__ == '__main__':

    districts = [3658,3112]

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
        parameters = {'Population': 9}

        vars()['reho_' + str(transformer)] = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario,
                    method=method, parameters=parameters, solver="baron")




    # Run optimization
    df_pi = pd.DataFrame()
    df_externalcharging = pd.DataFrame()
    variables = dict()
    parameters = dict()
    deltas = list()
    df_delta = pd.DataFrame()

    # Iterations
    for i in range(5):
        for transformer in districts:
            # Add iterative parameters (only after init run i=0)
            if i > 0:
                for param in ["outside_charging_price","charging_externalload"]:
                    vars()['reho_' + str(transformer)].parameters[param] = parameters[transformer][param]

            # Run
            vars()['reho_' + str(transformer)].single_optimization(Pareto_ID = i)

            # getting variables for iteration
            pi = vars()['reho_' + str(transformer)].results_MP["totex"][0][0]["df_Dual_t"]["pi"].xs("Electricity")
            df_Unit_t = vars()['reho_' + str(transformer)].results['totex'][0]['df_Unit_t']
            df_Grid_t = vars()['reho_' + str(transformer)].results['totex'][0]['df_Grid_t']

            EV_E_charged_outside = df_Unit_t.loc[:,df_Unit_t.columns.str.startswith("EV_E_charged_outside")][df_Unit_t.index.get_level_values('Layer') == 'Electricity']
            externaldemand = EV_E_charged_outside.reset_index().groupby(['Period','Time']).agg('sum',numeric_only = True)
            externaldemand.columns = [x.split('[')[1].split(']')[0] for x in externaldemand.columns]

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

        df_delta = check_convergence(deltas,df_delta,variables)

    print(df_pi)
    print(df_externalcharging)