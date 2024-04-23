from reho.model.reho import *
import datetime


def run_district(transformer,price = pd.DataFrame(),externalload = pd.DataFrame()):
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(transformer=transformer, nb_buildings=2)

    # Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['EMOO'] = {}
    scenario['specific'] = []
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    parameters = {'Population': 9}

    # Set method options
    method = {'building-scale': True}
    rehorun = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario,
                method=method, parameters=parameters, solver="gurobi")

    # Set specific parameters
    # reho.parameters['TransformerCapacity'] = np.array([1e6, 1e6, 0, 1e6])  # TODO : robustesse of mobility Network
    rehorun.parameters['Mode_Speed'] = {'Bike2_district': 20}
    # rehorun.parameters['DailyDist'] = 9
    if not price.empty :
        rehorun.parameters['outside_charging_price'] = price
    if not externalload.empty :
        rehorun.parameters['charging_externalload'] = externalload

    # Other params
    # Mobility demand profile can be changed in the csv file data/mobility/dailyprofiles.csv
    # (imported through the function generate_mobility_profiles)

    # Run optimization
    rehorun.single_optimization()

    # Save results
    rehorun.save_results(format=['xlsx', 'pickle'], filename='Mob')

    # Mobility Formatting of results
    date = datetime.datetime.now().strftime("%d_%H%M")
    result_file_path = 'results/Mob_totex.xlsx'
    df_Unit_t = pd.read_excel(result_file_path, sheet_name="df_Unit_t",
                              index_col=[0, 1, 2, 3])  # refaire sans passer par le xlsx
    df_Grid_t = pd.read_excel(result_file_path, sheet_name="df_Grid_t",
                              index_col=[0, 1, 2, 3])
    # df_Unit_t.index.name = ['Layer','Unit','Period','Time']
    df_Unit_t = df_Unit_t[df_Unit_t.index.get_level_values("Layer") == "Mobility"]
    df_Grid_t = df_Grid_t[df_Grid_t.index.get_level_values("Layer") == "Mobility"]
    df_dd = df_Grid_t[df_Grid_t.index.get_level_values("Hub") == "Network"]
    # df_dd.index = df_dd.index.droplevel('Hub')
    df_dd.reset_index("Hub", inplace=True)

    df_mobility = df_Unit_t[['Units_demand', 'Units_supply']].unstack(level='Unit')
    df_mobility['Domestic_energy'] = df_dd['Domestic_energy']
    df_mobility.sort_index(inplace=True)
    df_mobility.to_excel(f"results/3f_mobility{date}.xlsx")
    print(f"Results are saved in 3f_mobility{date}")

    # getting parameters for iteration
    pi = rehorun.results_MP["totex"][0][0]["df_Dual_t"]["pi"].xs("Electricity")
    EV_E_charged_outside = rehorun.results['totex'][0]['df_Unit_t'].reset_index()
    EV_E_charged_outside = EV_E_charged_outside[EV_E_charged_outside.Layer.isin(['work', 'leisure', 'travel'])].set_index(['Layer','Unit','Period','Time'])[['EV_E_charged_outside']]

    print(pi, EV_E_charged_outside)
    return pi,EV_E_charged_outside



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
                    method=method, parameters=parameters, solver="gurobi")


    # Run optimization
    df_pi = pd.DataFrame()
    df_externalcharging = pd.DataFrame()
    variables = dict()
    parameters = dict()

    # Init iteration 
    i = 0
    for transformer in districts:
        vars()['reho_' + str(transformer)].single_optimization(Pareto_ID = i)

        # getting variables for iteration
        pi = vars()['reho_' + str(transformer)].results_MP["totex"][0][0]["df_Dual_t"]["pi"].xs("Electricity")

        EV_E_charged_outside = vars()['reho_' + str(transformer)].results['totex'][0]['df_Unit_t'].reset_index()
        EV_E_charged_outside = EV_E_charged_outside[EV_E_charged_outside.Layer.isin(['work', 'leisure', 'travel'])].set_index(['Layer','Unit','Period','Time'])[['EV_E_charged_outside']]
        externaldemand = EV_E_charged_outside.reset_index().groupby(['Layer','Period','Time']).agg({"EV_E_charged_outside":'sum'})

        print(pi, EV_E_charged_outside)
        variables[transformer] = {  "pi": pi,
                                    "EV_E_charged_outside" : EV_E_charged_outside,
                                    "externaldemand" : externaldemand
                                     }
        
        # results formatting
        pi = pd.DataFrame(pi).rename(columns = {"pi" : f"{i}_{transformer}"})
        df_pi = pd.concat([df_pi,pi],axis = 1)
        EV_E_charged_outside = EV_E_charged_outside.rename(columns = {"EV_E_charged_outside" : f"{i}_{transformer}"})
        df_externalcharging = pd.concat([df_externalcharging,EV_E_charged_outside],axis = 1)
    
    # Computing parameters for next iteration 
    parameters[3658] = {    "outside_charging_price" : variables[3112]['pi'].rename("outside_charging_price"),
                            "charging_externalload"  : variables[3112]["externaldemand"].rename(columns = {"EV_E_charged_outside" : "charging_externalload" })
                        }
    parameters[3112] = {    "outside_charging_price" : variables[3658]['pi'].rename("outside_charging_price"),
                            "charging_externalload"  : variables[3658]["externaldemand"].rename(columns = {"EV_E_charged_outside" : "charging_externalload" })
                        }

    # Iteration 1
    i = 1
    for transformer in districts:
        for param in ["outside_charging_price","charging_externalload"]:
            vars()['reho_' + str(transformer)].parameters[param] = parameters[transformer][param]
        vars()['reho_' + str(transformer)].single_optimization(Pareto_ID = i)

        # getting variables for iteration
        pi = vars()['reho_' + str(transformer)].results_MP["totex"][0][0]["df_Dual_t"]["pi"].xs("Electricity")

        EV_E_charged_outside = vars()['reho_' + str(transformer)].results['totex'][0]['df_Unit_t'].reset_index()
        EV_E_charged_outside = EV_E_charged_outside[EV_E_charged_outside.Layer.isin(['work', 'leisure', 'travel'])].set_index(['Layer','Unit','Period','Time'])[['EV_E_charged_outside']]
        externaldemand = EV_E_charged_outside.reset_index().groupby(['Layer','Period','Time']).agg({"EV_E_charged_outside":'sum'})

        print(pi, EV_E_charged_outside)
        variables[transformer] = {  "pi": pi,
                                    "EV_E_charged_outside" : EV_E_charged_outside,
                                    "externaldemand" : externaldemand
                                     }
        
        # results formatting
        pi = pd.DataFrame(pi).rename(columns = {"pi" : f"{i}_{transformer}"})
        df_pi = pd.concat([df_pi,pi],axis = 1)
        EV_E_charged_outside = EV_E_charged_outside.rename(columns = {"EV_E_charged_outside" : f"{i}_{transformer}"})
        df_externalcharging = pd.concat([df_externalcharging,EV_E_charged_outside],axis = 1)


    print(df_pi)
    print(df_externalcharging)


    # for transformer in districts:
    #     pi,EV_E_charged_outside = run_district(transformer)
    #     EV_E_charged_outside = EV_E_charged_outside.reset_index().groupby(['Layer','Period','Time']).agg({"EV_E_charged_outside":'sum'})
    #     variables[transformer] = {  "pi": pi,
    #                                 "EV_E_charged_outside" : EV_E_charged_outside
    #                                  }

    #     pi = pd.DataFrame(pi).rename(columns = {"pi" : f"{i}_{transformer}"})
    #     df_pi = pd.concat([df_pi,pi],axis = 1)
    #     EV_E_charged_outside = EV_E_charged_outside.rename(columns = {"EV_E_charged_outside" : f"{i}_{transformer}"})
    #     df_externalcharging = pd.concat([df_externalcharging,EV_E_charged_outside],axis = 1)

    # print(df_pi)
    # print(df_externalcharging)
    # parameters[3658] = {    "outside_charging_price" : variables[3112]['pi'].rename("outside_charging_price"),
    #                         "charging_externalload"  : variables[3112]["EV_E_charged_outside"].rename(columns = {"EV_E_charged_outside" : "charging_externalload" })
    #                     }
    # parameters[3112] = {    "outside_charging_price" : variables[3658]['pi'].rename("outside_charging_price"),
    #                         "charging_externalload"  : variables[3658]["EV_E_charged_outside"].rename(columns = {"EV_E_charged_outside" : "charging_externalload" })
    #                     }

    # i = 1
    # for transformer in districts:
    #     pi,EV_E_charged_outside = run_district(transformer,parameters[transformer]['outside_charging_price'],parameters[transformer]['charging_externalload'])

    #     pi = pd.DataFrame(pi).rename(columns = {"pi" : f"{i}_{transformer}"})
    #     df_pi = pd.concat([df_pi,pi],axis = 1)
    #     EV_E_charged_outside = EV_E_charged_outside.reset_index().groupby(['Layer','Period','Time']).agg({"EV_E_charged_outside":'sum'})
    #     EV_E_charged_outside = EV_E_charged_outside.rename(columns = {"EV_E_charged_outside" : f"{i}_{transformer}"})
    #     df_externalcharging = pd.concat([df_externalcharging,EV_E_charged_outside],axis = 1)
    #     variables[transformer] = {  "pi": pi,
    #                                 "EV_E_charged_outside" : EV_E_charged_outside
    #                                  }
        
    print(df_pi)
    print(df_externalcharging)

