from reho.paths import *
import reho.model.preprocessing.weather as WD
import pandas as pd
import numpy as np


def generate_EV_plugged_out_profiles_district(cluster):
    """
    Computes hourly electric vehicle (EV) profiles for each typical day considering weekdays and weekends. Data are taken from
    `UK Department for Transport 2013 <https://www.gov.uk/government/collections/energy-and-environment-statistics#publications>`_
    and `SFSO 2015 <https://www.bfs.admin.ch/asset/fr/1840478>`_. The EV occupancy profiles are used to
    optimize EV electricity demand profiles with the evehicle.mod ampl model.



    Parameters
    ----------
    cluster : dict
        Define location district, number of periods, and number of timesteps.

    Returns
    -------
    EV_plugged_out : array
        Hourly profile of the share of vehicles being plugged out of the district LV grid.
    EV_plugging_in : array
        Hourly profile of the share of vehicles connecting to the district LV grid.

    Notes
    -----
    - EV_plugged_out, EV_plugging_in

    """
    # TODO IMPLEMENTATION of flexible period duration
    File_ID = WD.get_cluster_file_ID(cluster)

    if 'W' in File_ID.split('_'):
        use_weekdays = True
    else:
        use_weekdays = False

    if use_weekdays:
        timestamp = np.loadtxt(os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat'), usecols=(1, 2, 3),
                               skiprows=1)
        timestamp = pd.DataFrame(timestamp, columns=("Day", "Frequency", "Weekday"))
    else:
        df = pd.read_csv(os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat'), delimiter='\t')
        timestamp = df.fillna(1)  # only weekdays

    # Federal Office of Statistic, Comportement de la population en matiere de transports, 2015
    profiles_weekday = [0.01, 0.0, 0.0, 0.0, 0.0, 0.03, 0.1, 0.12, 0.11, 0.12, 0.12, 0.14, 0.13, 0.14, 0.13, 0.13, 0.18,
                        0.2, 0.15, 0.1, 0.07, 0.06, 0.05, 0.03]
    profiles_weekend = [0.01, 0.0, 0.0, 0.0, 0.0, 0.00, 0.0, 0.00, 0.03, 0.10, 0.12, 0.11, 0.12, 0.12, 0.14, 0.13, 0.14,
                        0.13, 0.15, 0.1, 0.07, 0.06, 0.05, 0.03]

    # UK department for transport Electric Chargepoint Analysis 2017: Domestics
    profiles_weekday = [0.0, 0.0, 0.0, 0.0, 0.01, 0.02, 0.08, 0.2, 0.31, 0.35, 0.38, 0.39, 0.39, 0.38, 0.38, 0.36, 0.31,
                        0.24, 0.18, 0.13, 0.09, 0.05, 0.03, 0.01]
    profiles_weekend = [0.0, 0.0, 0.0, 0.0, 0.01, 0.02, 0.08, 0.2, 0.31, 0.35, 0.38, 0.39, 0.39, 0.38, 0.38, 0.36, 0.31,
                        0.24, 0.18, 0.13, 0.09, 0.05, 0.03, 0.01]

    plugging_in_weekday = [0.017, 0.006, 0.004, 0.003, 0.004, 0.005, 0.01, 0.019, 0.03, 0.034, 0.036, 0.042, 0.043,
                           0.045, 0.047, 0.067, 0.088, 0.111, 0.109, 0.087, 0.069, 0.058, 0.043, 0.023]
    plugging_in_weekend = [0.017, 0.006, 0.004, 0.003, 0.004, 0.005, 0.01, 0.019, 0.03, 0.034, 0.036, 0.042, 0.043,
                           0.045, 0.047, 0.067, 0.088, 0.111, 0.109, 0.087, 0.069, 0.058, 0.043, 0.023]

    EV_plugged_out = []  # all vehicules not connected
    EV_plugging_in = []  # vehicules connecting at time t
    # iter over the typical periods
    for j, day in enumerate(list(timestamp.Weekday)[:-2]):
        if day == 0:
            profile = profiles_weekend
            profile_plug_in = plugging_in_weekend
        elif day == 1:
            profile = profiles_weekday
            profile_plug_in = plugging_in_weekday
            # profile = np.tile(profiles_weekday, 365).tolist() # workaround -  whole year profile
        else:
            raise ("day type not possible")

        EV_plugged_out = EV_plugged_out + profile
        EV_plugging_in = EV_plugging_in + profile_plug_in

    EV_plugged_out = EV_plugged_out + [0.0, 0.0]  # extreme hours
    EV_plugged_out = np.array(EV_plugged_out)

    EV_plugging_in = EV_plugging_in + [0.0, 0.0]  # extreme hours
    EV_plugging_in = np.array(EV_plugging_in)

    return EV_plugged_out, EV_plugging_in


def generate_mobility_parameters(cluster, population, dailydist,mode_speed_custom,transportunits):
    """
    Based on EV_profile_generator_structure

    This reads the input data on the file dailyprofiles.csv and initializes (almost) all the necessary parameters to run the mobility sector in REHO.

    Parameters:
    ----------
    cluster : 
        to get periods characterisations (p,t) => usually the value self.cluster_compact or 
    mode_speed_custom : None or a dictionnay
        either None or a dictionnay given by the user in the scenario initialisation
    dailydist : float
        duplicata of the ampl param Dailydist, declared later in the program (TODO : Could be coded better bc the duplicatas are not linked)
    population : float
        the input reho.parameters['Population'] in the initialisation of the scenario. 
    transportunits : list
        a list of all infrastructure units providing Mobility + "Public_transport" => which is the Network supply['Mobility']

    Returns:
    -------
    param_output : a dict of dataframes containing the profiles for each param. 
    """
    param_output = dict()
    
    if dailydist is None:
        dailydist = 36.8 # km per day
    if mode_speed_custom is None:
        mode_speed_custom = pd.DataFrame()

    # Periods
    # TODO IMPLEMENTATION of flexible period duration
    File_ID = WD.get_cluster_file_ID(cluster)

    if 'W' in File_ID.split('_'):
        use_weekdays = True
    else:
        use_weekdays = False

    if use_weekdays:
        timestamp = np.loadtxt(os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat'), usecols=(1, 2, 3),
                               skiprows=1)
        timestamp = pd.DataFrame(timestamp, columns=("Day", "Frequency", "Weekday"))
    else:
        df = pd.read_csv(os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat'), delimiter='\t')
        timestamp = df.fillna(1)  # only weekdays

    # Label mapping of the types of days
    days_mapping = {0: "wnd",  # Weekend
                    1: "wdy"  # Weekday
                    }

    # Read the profiles and the transportation Units
    profiles_input = pd.read_csv(os.path.join(path_to_mobility, "dailyprofiles.csv"), index_col=0)
    units = pd.read_csv(os.path.join(path_to_infrastructure,"district_units.csv"),sep = ";")
    units = units[units.Unit.isin(transportunits)]

    # Domestic demand ================================================================================================
    # The labels look like this : demwdy => normalized mobility demand of a weekday
    columns = ["dem" + x for x in days_mapping.values()]
    profiles_input[columns] *= population
    profiles_input[columns] *= dailydist

    mobility_demand = pd.DataFrame(columns=['l', 'p', 't', 'Domestic_energy'])

    # iter over the typical periods 
    for j, day in enumerate(list(timestamp.Weekday)[:-2]):
        try:
            profile = profiles_input[["dem" + days_mapping[day]]].copy()
        except:
            raise ("day type not possible")
        profile.rename(columns={"dem" + days_mapping[day]: "Domestic_energy"}, inplace=True)
        profile.index.name = 't'
        profile.reset_index(inplace=True)
        profile['p'] = j + 1

        mobility_demand = pd.concat([mobility_demand, profile])

    # extreme hours
    pd.concat([mobility_demand, pd.DataFrame({"p": 11, "t": 1, "Domestic_energy": 0}, index=["extremehour1"])])
    pd.concat([mobility_demand, pd.DataFrame({"p": 12, "t": 1, "Domestic_energy": 0}, index=["extremehour2"])])

    mobility_demand['l'] = "Mobility"
    mobility_demand.set_index(['l', 'p', 't'], inplace=True)
    param_output['Domestic_energy'] = mobility_demand

    # Daily profiles (ex : Bikes and ICE) ==============================================================================
    # The labels look like this : Bike_pfrwdy => the normalized daily profile of the Unit Bike_district on a weekday (_district is omitted)
    daily_profile = pd.DataFrame(columns=['u', 'p', 't', 'Daily_Profile'])

    # iter over the typical periods 
    for j, day in enumerate(list(timestamp.Weekday)[:-2]):
        # get daily demand
        try:
            dd = profiles_input[["dem" + days_mapping[day]]].copy()
        except:
            raise ("day type not possible")
        dd_filter = dd.astype('bool')

        profile = profiles_input.loc[:, profiles_input.columns.str.contains(f"prf{days_mapping[day]}")].copy()
        profile = profile.multiply(dd_filter.iloc[:,0],axis = 'index')
        profile.columns = [x.split('_')[0] + "_district" for x in profile.columns]
        missing_units = set(transportunits) - set(profile.columns)
        for unit in missing_units:
            profile[unit] = dd  # fill missing series with the period demand profile


        profile.index.name = 't'
        profile.columns.name = 'u'
        profile = profile.stack().to_frame(name = "Daily_Profile")
        profile.reset_index(inplace=True)
        profile['p'] = j + 1

        daily_profile = pd.concat([daily_profile, profile])

    # extreme hours
    pd.concat([daily_profile, pd.DataFrame({"p": 11, "t": 1, "Daily_Profile": 0},index=["extremehour1"])])
    pd.concat([daily_profile, pd.DataFrame({"p": 12, "t": 1, "Daily_Profile": 0},index=["extremehour2"])])

    daily_profile.set_index(['u', 'p', 't'], inplace=True)
    param_output['Daily_Profile'] = daily_profile

    # IN/OUT and activity profiles (ex : EV and Electric Bikes) ========================================================
    # the default profiles are taken from EV_xxx
    EV_plugged_out = pd.DataFrame(columns=['u', 'p', 't', 'EV_plugged_out'])
    EV_plugging_in = pd.DataFrame(columns=['u', 'p', 't', 'EV_plugging_in'])
    activity_profile = pd.DataFrame(columns=['a', 'u', 'p', 't', 'EV_activity'])
    Bikes_plugging_in = pd.DataFrame(columns=['u', 'p', 't', 'Bikes_plugging_in'])

    EV_units = list(units[units.UnitOfType == "EV"][['Unit','UnitOfType']].Unit)
    EBike_units = list(units[units.UnitOfType == "EBike"][['Unit','UnitOfType']].Unit)

    # iter over the typical periods 
    for j, day in enumerate(list(timestamp.Weekday)[:-2]):
        try:
            EV_profiles = profiles_input.loc[:,profiles_input.columns.str.startswith("EV_") & 
                                    profiles_input.columns.str.contains(days_mapping[day])].copy()
        except:
            raise ("day type not possible")
        

        # EV plugging in
        pli = EV_profiles.loc[:,EV_profiles.columns.str.contains("pli")].copy()
        pli['default'] = pli['EV_pli'+days_mapping[day]]
        missing_units = set(EV_units) - set(pli.columns)
        for unit in missing_units:
            pli[unit] = pli['default']
        pli = pli[EV_units]

        pli.index.name = 't'
        pli.columns.name = 'u'
        pli = pli.stack().to_frame(name = "EV_plugging_in")
        pli.reset_index(inplace=True)
        pli['p'] = j + 1

        EV_plugging_in = pd.concat([EV_plugging_in, pli])

        # EV plugged out
        out = EV_profiles.loc[:,EV_profiles.columns.str.contains("out")].copy()
        out['default'] = out['EV_out'+days_mapping[day]]
        missing_units = set(EV_units) - set(profile.columns)
        for unit in missing_units:
            out[unit] = out['default']
        out = out[EV_units]

        out.index.name = 't'
        out.columns.name = 'u'
        out = out.stack().to_frame(name = "EV_plugged_out")
        out.reset_index(inplace=True)
        out['p'] = j + 1

        EV_plugged_out = pd.concat([EV_plugged_out, out])

        # activity profiles
        act = EV_profiles.loc[:,EV_profiles.columns.str.startswith("EV_a")].copy()
        act.columns = [x.split('_')[1][1:-3] for x in act.columns]
        act.columns.name = 'a'
        act.index.name = 't'
        act = act.stack().to_frame(name = "default")
        act.reset_index(inplace=True)
        missing_units = set(EV_units) - set(act.columns)
        for unit in missing_units:
            act[unit] = act['default']
        act.set_index(['a','t'],inplace=True)
        act = act[EV_units]
        act.columns.name = 'u'
        act = act.stack().to_frame(name = "EV_activity")
        act.reset_index(inplace=True)
        act['p'] = j + 1

        activity_profile = pd.concat([activity_profile, act])

        # Bike plugging in
        try:
            EBike_profiles = profiles_input.loc[:,profiles_input.columns.str.startswith("EBike_") &
                                    profiles_input.columns.str.contains(days_mapping[day])].copy()
        except:
            raise ("day type not possible")

        pli = EBike_profiles.loc[:, EBike_profiles.columns.str.contains("pli")].copy()
        pli['default'] = pli['EBike_pli' + days_mapping[day]]
        missing_units = set(EBike_units) - set(pli.columns)
        for unit in missing_units:
            pli[unit] = pli['default']
        pli = pli[EBike_units]

        pli.index.name = 't'
        pli.columns.name = 'u'
        pli = pli.stack().to_frame(name="Bikes_plugging_in")
        pli.reset_index(inplace=True)
        pli['p'] = j + 1

        Bikes_plugging_in = pd.concat([Bikes_plugging_in, pli])


    # extreme hours
    aaa = pd.DataFrame({"u": EV_plugging_in.u.unique(),"p": 11, "t": 1, "EV_plugging_in": 0},index=[f"{x}1" for x in EV_plugging_in.u.unique()])
    EV_plugging_in = pd.concat([EV_plugging_in, aaa])
    EV_plugging_in = pd.concat([EV_plugging_in, pd.DataFrame({"u" : EV_plugging_in.u.unique(),"p": 12, "t": 1, "EV_plugging_in": 0},index=[[f"{x}2" for x in EV_plugging_in.u.unique()]])])
    EV_plugged_out =  pd.concat([EV_plugged_out, pd.DataFrame({"u" : EV_plugged_out.u.unique(),"p": 11, "t": 1, "EV_plugged_out": 0},index=[[f"{x}1" for x in EV_plugged_out.u.unique()]])])
    EV_plugged_out = pd.concat([EV_plugged_out, pd.DataFrame({"u" : EV_plugged_out.u.unique(),"p": 12, "t": 1, "EV_plugged_out": 0},index=[[f"{x}2" for x in EV_plugged_out.u.unique()]])])
    

    EV_plugging_in.set_index(['u', 'p', 't'], inplace=True)
    param_output['EV_plugging_in'] = EV_plugging_in

    EV_plugged_out.set_index(['u', 'p', 't'], inplace=True)
    param_output['EV_plugged_out'] = EV_plugged_out

    activity_profile.set_index(['a','u', 'p', 't'], inplace=True)
    param_output['EV_activity'] = activity_profile

    Bikes_plugging_in.set_index(['u', 'p', 't'], inplace=True)
    param_output['Bikes_plugging_in'] = Bikes_plugging_in

    # Mode_Speed =======================================================================================================
    default_speed = pd.DataFrame({ "UnitOfType" : ['Bike','EV','ICE','Public_transport',"EBike"],
                                   "Mode_Speed" : [13.3,37,37,18,17]})

    mode_speed = units[['Unit','UnitOfType']].copy()
    mode_speed = mode_speed.merge(default_speed, how = 'outer')
    mode_speed['Unit'].fillna(mode_speed['UnitOfType'],axis = 0,inplace=True)
    mode_speed = mode_speed.set_index(['Unit'])[['Mode_Speed']]
    
    mode_speed_custom = pd.DataFrame.from_dict(mode_speed_custom,orient='index',columns = ["Mode_Speed"])
    mode_speed.update(mode_speed_custom)

    param_output['Mode_Speed'] = mode_speed

    return param_output


def bike_temp(cluster):
    """
    Temporary function to be removed
    """
    File_ID = WD.get_cluster_file_ID(cluster)

    if 'W' in File_ID.split('_'):
        use_weekdays = True
    else:
        use_weekdays = False

    if use_weekdays:
        timestamp = np.loadtxt(os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat'), usecols=(1, 2, 3),
                               skiprows=1)
        timestamp = pd.DataFrame(timestamp, columns=("Day", "Frequency", "Weekday"))
    else:
        df = pd.read_csv(os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat'), delimiter='\t')
        timestamp = df.fillna(1)  # only weekdays

    profiles_input = pd.read_csv(os.path.join(path_to_mobility, "dailyprofiles.csv"), index_col=0)
    bikedailyprofile = pd.DataFrame(columns=['u', 'p', 't', 'Daily_Profile'])
    for j, day in enumerate(list(timestamp.Weekday)[:-2]):
        try:
            profile = profiles_input[["Bike_prfwdy"]].copy()
        except:
            raise ("day type not possible")
        profile.rename(columns={"Bike_prfwdy": "Daily_Profile"}, inplace=True)
        profile.index.name = 't'
        profile.reset_index(inplace=True)
        profile['p'] = j + 1
        bikedailyprofile = pd.concat([bikedailyprofile, profile])

    pd.concat([bikedailyprofile, pd.DataFrame({"p": 11, "t": 1, "Daily_Profile": 0}, index=["extremehour1"])])
    pd.concat([bikedailyprofile, pd.DataFrame({"p": 12, "t": 1, "Daily_Profile": 0}, index=["extremehour2"])])

    bikedailyprofile['u'] = "Bike_district"
    bikedailyprofile.set_index(['u', 'p', 't'], inplace=True)

    return bikedailyprofile


def scenario_profiles_temp(cluster):
    """
    Temporary function to be removed
    """
    File_ID = WD.get_cluster_file_ID(cluster)

    if 'W' in File_ID.split('_'):
        use_weekdays = True
    else:
        use_weekdays = False

    if use_weekdays:
        timestamp = np.loadtxt(os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat'), usecols=(1, 2, 3),
                               skiprows=1)
        timestamp = pd.DataFrame(timestamp, columns=("Day", "Frequency", "Weekday"))
    else:
        df = pd.read_csv(os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat'), delimiter='\t')
        timestamp = df.fillna(1)  # only weekdays

    profiles_input = pd.read_csv(os.path.join(path_to_mobility, "dailyprofiles.csv"), index_col=0)
    bikedailyprofile = pd.DataFrame(columns=['u', 'p', 't', 'Daily_Profile'])
    for j, day in enumerate(list(timestamp.Weekday)[:-2]):
        try:
            profile = profiles_input[["Bike_prfwnd"]].copy()
        except:
            raise ("day type not possible")
        profile.rename(columns={"Bike_prfwnd": "Daily_Profile"}, inplace=True)
        profile.index.name = 't'
        profile.reset_index(inplace=True)
        profile['p'] = j + 1
        bikedailyprofile = pd.concat([bikedailyprofile, profile])

    pd.concat([bikedailyprofile, pd.DataFrame({"p": 11, "t": 1, "Daily_Profile": 0}, index=["extremehour1"])])
    pd.concat([bikedailyprofile, pd.DataFrame({"p": 12, "t": 1, "Daily_Profile": 0}, index=["extremehour2"])])

    bikedailyprofile['u'] = "Bike_district"
    bikedailyprofile.set_index(['u', 'p', 't'], inplace=True)

    output = {
        "Daily_Profile": bikedailyprofile
    }
    return output



def rho_param(ext_districts,rho,activities = ["work","leisure","travel"]):
    """
    This function is used in the iterative scenario to iteratively calculate multiple districts with EVs being able to charge at the different districts.
    
    This function is used to calculate the parameter S from the share of activities S(a) in each districts.
    For each activity, if a distribution is provided by the parameter rho, then S = rho_d / sum over ext_d(rho)
    Otherwise, we assume equal distribution over the districts and S = 1/len(nb_ext_d)
    Parameters
    ----------
    ext_districts : 

    Returns
    -------
    share : dataframe
        dataframe with index (activity, district) containing the distribution accross all district for each activity. 
    

    """
    share = pd.DataFrame(index=ext_districts,columns=activities).fillna(1/len(ext_districts))
    for act in rho.columns:
        share[act] = rho[act] / rho[act][rho.index.isin(ext_districts)].sum()
    share = share.stack().to_frame(name= "share_district_activity").reorder_levels([1,0])
    share.loc['travel'] = 0 # additionnal precaution
    return share


def compute_iterative_parameters(variables,parameters,only_pi = False):
    """"
    This function is used in the iterative scenario to iteratively calculate multiple districts with EVs being able to charge at the different districts.
    """
    if only_pi:
        df_prices = pd.DataFrame()
        for d in variables.keys():
            price = variables[d]['pi'].to_frame().copy()
            price['district'] = d
            price = price.set_index('district',append = True).reorder_levels([2,0,1])
            df_prices = pd.concat([df_prices,price])

        for d in variables.keys():
            parameters[d] = {   "outside_charging_price"    : df_prices[df_prices.index.get_level_values(level="district") != d].rename(columns = {'pi' : 'outside_charging_price'}),
                                "externalload_sellingprice" : variables[d]['pi'].rename("externalload_sellingprice")
                                }

    else:
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



def check_convergence(deltas,df_delta,variables,iteration,criteria = ('total')):
    """"
    This function is used in the iterative scenario to iteratively calculate multiple districts with EVs being able to charge at the different districts.
    Parameters
    ----------
    criteria : tuple, optional
        Choose on which indexes to match the load and demand. Default is time matching (p,t). Write 'by_activity' for activity matching (a,p,t)

    """
    termination_threshold = 0.1 # 10% TODO : mettre ces tuning parametres somewhere else
    termination_iter = 3
    
    # Compute Delta
    df_demand = pd.DataFrame()
    df_load = pd.DataFrame()
    for k in variables.keys():
        df = variables[k]['externaldemand'].groupby(["Period","Time"]).agg("sum")
        if 'by_activity' in criteria:
            df.columns.name = "Activity"
            df_demand[k] = df.stack()
        else:
            df_demand[k] = df.agg('sum',axis = 1)

        
        df = variables[k]['externalload']
        if 'by_activity' in criteria:
            df.columns.name = "Activity"
            df_load[k] = df.stack()
        else:
            df_load[k] = df.agg('sum',axis = 1)

    df_delta[f"demand{iteration}"] = df_demand.sum(axis=1)
    df_delta[f"load{iteration}"] = df_load.sum(axis=1)

    df_delta[f"delta{iteration}"] = df_delta[f"demand{iteration}"] - df_delta[f"load{iteration}"]
    delta = df_delta[f"delta{iteration}"].apply(lambda x : x*x).sum()
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

