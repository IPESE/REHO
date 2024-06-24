from reho.model.reho import *
import datetime

if __name__ == '__main__':
    date = datetime.datetime.now().strftime("%d_%H%M")
    run_label = '1district'

    # Parameters ==================================================================================================================
    ## PARAMETERS : MODAL SHARES 
    share_car = 0.66
    share_PT  = 0.24
    share_MD = 0.1 # mobilité douce : "soft mobility" ? (from FSO : include biking, walking, electric biking)
    
    share_ICE = 0.4
    share_EV = 0.26
    share_train = 0.2
    share_Ebike = 0.02 # only max

    perc_point_window = 0.03 # the range between the max and the min constraint (in percentage points)
    
    ## PARAMETERS : DISTRICT    

    district_parameters = {
        7724  : {"PopHouse" : 4.52, "rho" : pd.Series([95,3,2],index=['household','industry','service']), "f" : 3.23 , "Scluster" : 12156} ,
        8538  : {"PopHouse" : 10.5, "rho" : pd.Series([89,2,6],index=['household','industry','service']), "f" : 44.3 , "Scluster" : 4890383} ,
        13569 : {"PopHouse" : 7.71, "rho" : pd.Series([96,2,1],index=['household','industry','service']), "f" : 243.98 , "Scluster" : 3552764}  ,
        13219 : {"PopHouse" : 9.59, "rho" : pd.Series([61,17,17],index=['household','industry','service']), "f" : 31.84 , "Scluster" : 3003409},
        13228 : {"PopHouse" : 11.29, "rho" : pd.Series([52,21,5],index=['household','industry','service']), "f" : 58.39 , "Scluster" : 3301366}

    }

    district = 7724
    n_buildings = 2


    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(transformer=district, nb_buildings=n_buildings) 

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

    parameters = {'Population': n_buildings * district_parameters[district]['PopHouse'] ,
            # All the modal share and techno share parameters           
                "max_share_cars" : share_car + perc_point_window/2,
                "min_share_cars" : share_car - perc_point_window/2,
                "max_share_PT" : share_PT + perc_point_window/2,
                "min_share_PT" : share_PT - perc_point_window/2,
                "max_share_MD" : share_MD + perc_point_window/2,
                "min_share_MD" : share_MD - perc_point_window/2,
                "max_share_ICE" : share_ICE + perc_point_window/2,
                "min_share_ICE" : share_ICE - perc_point_window/2,
                "max_share_EV" : share_EV + perc_point_window/2,
                "min_share_EV" : share_EV - perc_point_window/2,
                "max_share_PT_train" : share_train + perc_point_window/2,
                "min_share_PT_train" : share_train - perc_point_window/2,
                "max_share_EBikes" : share_Ebike,
                }

    # Set method options
    method = {'building-scale': True}
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario,
                method=method, parameters=parameters, solver="gurobiasl")

    # Set specific parameters
    # reho.parameters['TransformerCapacity'] = np.array([1e6, 1e6, 0, 1e6])  # TODO : robustesse of mobility Network
    # reho.parameters['Mode_Speed'] = {'Bike2_district': 20}
    # reho.parameters['DailyDist'] = 9

    # reho.parameters.update(EV_gen.scenario_profiles_temp(cluster))

    # Other params 
    # Mobility demand profile can be changed in the csv file data/mobility/dailyprofiles.csv + function get_demand_profiles

    # Run optimization
    reho.single_optimization()

    # Save results
    reho.save_results(format=['save_all', 'pickle'], filename=f'mob1district_{date}_{district}')
    # reho.save_mobility_results(filename = f"3f_mobility{date}")

    # # getting parameters for iteration
    print(reho.results_MP["totex"][0][0]["df_Dual_t"]["pi"].xs("Electricity"))
