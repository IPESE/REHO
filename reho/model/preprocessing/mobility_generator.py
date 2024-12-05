import warnings
from reho.paths import *
import reho.model.preprocessing.weather as weather
import pandas as pd
import numpy as np


def generate_mobility_parameters(cluster, parameters, transportunits):
    """
    This reads the input data on the file dailyprofiles.csv and initializes (almost) all the necessary parameters to run the mobility sector in REHO.

    Parameters:
    ----------
    cluster : 
        to get periods characterisations (p,t) => usually the value self.cluster_compact or 
    parameters :
        From the parameters will be extracted values related to the mobility namely DailyDist, Mode_Speed and Population. Population is a float, DailyDist a dict of float, Mode_Speed is a dictionnary given by the user in the scenario initialisation. It can contains customed values for only some modes while the other remain default. 
    transportunits : list
        a list of all infrastructure units providing Mobility + "Public_transport" => which is the Network_supply['Mobility']

    Returns:
    -------
    param_output : a dict of dataframes containing the profiles for each param. 

    ..caution:
    The default values in this function are a hardcoded copy of parameters DailyDist and Population in mobility.mod.
    """
    param_output = dict()
    
    if not "DailyDist" in parameters:
        parameters['DailyDist'] = {"all" : 36.8} # km per day
    if not "Population" in parameters:
        parameters['Population'] = 10 # km per day  
    else:
        if isinstance(parameters['Population'], np.ndarray):
            parameters['Population'] = parameters['Population'][0]
    if "Mode_Speed" in parameters:
        mode_speed_custom = parameters['Mode_Speed']
    else:
        mode_speed_custom = pd.DataFrame()

    # Periods
    # TODO IMPLEMENTATION of flexible period duration
    File_ID = weather.get_cluster_file_ID(cluster)
    if 'W' in File_ID.split('_'):
        timestamp = np.loadtxt(os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat'), usecols=(1, 2, 3), skiprows=1)
        timestamp = pd.DataFrame(timestamp, columns=["Day", "Frequency", "Weekday"])
    else:
        df = pd.read_csv(os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat'), delimiter='\t')
        timestamp = df.fillna(1)  # only weekdays

    days_mapping = {0: "wnd",  # Weekend
                    1: "wdy"  # Weekday
                    }
    modes = ['cars', 'PT', 'MD']

    # Read the profiles and the transportation Units
    profiles_input = pd.read_csv(os.path.join(path_to_mobility, "dailyprofiles.csv"), index_col=0)
    share_input = pd.read_csv(os.path.join(path_to_mobility, "modalshares.csv"), index_col=0)
    units = pd.read_csv(os.path.join(path_to_infrastructure, "district_units.csv"), sep=";")
    units = units[units.Unit.isin(transportunits)]

    # Check that the file modalshares.csv is consistent with DailyDist
    d = set([x.split('_')[1] for x in share_input.columns])
    d = d.difference(parameters['DailyDist'].keys())
    if not(len(d)==0):
        raise warnings.warn(f"The file modalshare.csv contains invalid categories of distance {d}. \n Categories of distances labels should be in this list : {list(parameters['DailyDist'].keys())}")


    param_output['Domestic_energy_pkm'], param_output['Domestic_energy'], profile = get_mobility_demand(profiles_input, timestamp, days_mapping, parameters['DailyDist'], parameters['Population'])
    param_output['Daily_Profile'] = get_daily_profile(profiles_input, timestamp, days_mapping, transportunits)

    param_output['EV_charging_profile'] = get_EV_charging(units, timestamp, profiles_input, days_mapping)
    param_output['EV_plugged_out'] = get_EV_plugged_out(units, timestamp, profiles_input, days_mapping, profile)
    param_output['EV_activity'] = get_activity_profile(units, timestamp, profiles_input, days_mapping)
    param_output['EBike_charging_profile'] = get_Ebike_charging(units, timestamp, profiles_input, days_mapping)

    param_output['Mode_Speed'] = get_mode_speed(units, mode_speed_custom)
    param_output['min_share'], param_output['min_share_modes'] = get_min_share(share_input, modes, transportunits)
    param_output['max_share'], param_output['max_share_modes'] = get_max_share(share_input, modes, transportunits)
    param_output['DailyDist'] = pd.DataFrame.from_dict(parameters['DailyDist'], orient='index', columns=["DailyDist"])

    return param_output


def get_mobility_demand(profiles_input, timestamp, days_mapping, DailyDist, Population):
    # The labels look like this : demwdy_def, demwdy_long => normalized mobility demand of a weekday
    profiles_demand = profiles_input.loc[:, profiles_input.columns.str.startswith("dem")]
    profiles_demand = profiles_demand * Population

    distances = DailyDist.keys()
    demand_pkm = pd.DataFrame(columns=['dist', 'p', 't', 'Domestic_energy_pkm'])

    for dist in distances:
        for j, day in enumerate(list(timestamp.Weekday)[:-2]):
            try:
                profile = profiles_demand[[f"dem{days_mapping[day]}_{dist}"]].copy()
                profile.rename(columns={f"dem{days_mapping[day]}_{dist}": "Domestic_energy_pkm"}, inplace=True)
            except:
                try:
                    profile = profiles_demand[[f"dem{days_mapping[day]}_def" ]].copy() # default profile
                    profile.rename(columns={f"dem{days_mapping[day]}_def": "Domestic_energy_pkm"}, inplace=True)
                except:
                    raise (f"Demand profile error : no default demand profile for {day} daytype")
            profile.index.name = 't'
            profile.reset_index(inplace=True)
            profile['p'] = j + 1

            profile["Domestic_energy_pkm"] *= DailyDist[dist]
            profile['dist'] = dist

            demand_pkm = pd.concat([demand_pkm, profile])

    extreme_hours = pd.concat([pd.DataFrame({"p": 11, "t": 1, "Domestic_energy_pkm": 0}, index=DailyDist.keys()),
                               pd.DataFrame({"p": 12, "t": 1, "Domestic_energy_pkm": 0}, index=DailyDist.keys())])

    extreme_hours.index.name = 'dist'
    extreme_hours.reset_index(inplace = True)
    demand_pkm = pd.concat([demand_pkm, extreme_hours])
    demand_pkm.set_index(['dist', 'p', 't'], inplace=True)

    mobility_demand = demand_pkm.groupby(['p','t']).agg('sum')
    mobility_demand.reset_index(inplace=True)
    mobility_demand['l'] = "Mobility"
    mobility_demand.set_index(['l', 'p', 't'], inplace=True)
    mobility_demand.rename(columns={"Domestic_energy_pkm" : "Domestic_energy"},inplace=True)
    return demand_pkm, mobility_demand, profile


def get_daily_profile(profiles_input, timestamp, days_mapping, transportunits):
    # Daily profiles (ex : Bikes and ICE)
    # The labels look like this : Bike_pfrwdy => the normalized daily profile of the Unit Bike_district on a weekday (_district is omitted)
    daily_profile = pd.DataFrame(columns=['u', 'p', 't', 'Daily_Profile'])

    for j, day in enumerate(list(timestamp.Weekday)[:-2]):
        try:
            dd = profiles_input[["dem" + days_mapping[day] + "_def"]].copy()
        except:
            raise ("day type not possible")
        dd_filter = dd.astype('bool')

        profile = profiles_input.loc[:, profiles_input.columns.str.contains(f"prf{days_mapping[day]}")].copy()
        profile = profile.multiply(dd_filter.iloc[:,0],axis = 'index')
        profile.columns = [x.split('_')[0] + "_district" for x in profile.columns]
        missing_units = set(transportunits) - set(profile.columns) - {'Public_transport'}
        for unit in missing_units:
            profile[unit] = dd  # fill missing series with the period demand profile

        profile.index.name = 't'
        profile.columns.name = 'u'
        profile = profile.stack().to_frame(name = "Daily_Profile")
        profile.reset_index(inplace=True)
        profile['p'] = j + 1
        daily_profile = pd.concat([daily_profile, profile])

    pd.concat([daily_profile, pd.DataFrame({"p": 11, "t": 1, "Daily_Profile": 0},index=["extremehour1"])])
    pd.concat([daily_profile, pd.DataFrame({"p": 12, "t": 1, "Daily_Profile": 0},index=["extremehour2"])])
    return daily_profile.set_index(['u', 'p', 't'])


def get_EV_charging(units, timestamp, profiles_input, days_mapping):
    # IN/OUT and activity profiles (ex : EV and Electric Bikes)
    # the default profiles are taken from EV_xxx
    EV_charging_profile = pd.DataFrame(columns=['u', 'p', 't', 'EV_charging_profile'])
    EV_units = list(units[units.UnitOfType == "EV"][['Unit', 'UnitOfType']].Unit)

    for j, day in enumerate(list(timestamp.Weekday)[:-2]):
        try:
            EV_profiles = profiles_input.loc[:, profiles_input.columns.str.startswith("EV_") & profiles_input.columns.str.contains(days_mapping[day])].copy()
        except:
            raise ("day type not possible")

        cpf = EV_profiles.loc[:, EV_profiles.columns.str.contains("cpf")].copy()
        cpf['default'] = cpf['EV_cpf' + days_mapping[day]]
        missing_units = set(EV_units) - set(cpf.columns)
        for unit in missing_units:
            cpf[unit] = cpf['default']
        cpf = cpf[EV_units]

        cpf.index.name = 't'
        cpf.columns.name = 'u'
        cpf = cpf.stack().to_frame(name="EV_charging_profile")
        cpf.reset_index(inplace=True)
        cpf['p'] = j + 1
        EV_charging_profile = pd.concat([EV_charging_profile, cpf])

    aaa = pd.DataFrame({"u": EV_charging_profile.u.unique(), "p": 11, "t": 1, "EV_charging_profile": 0}, index=[f"{x}1" for x in EV_charging_profile.u.unique()])
    EV_charging_profile = pd.concat([EV_charging_profile, aaa])
    EV_charging_profile = pd.concat([EV_charging_profile, pd.DataFrame({"u": EV_charging_profile.u.unique(), "p": 12, "t": 1, "EV_charging_profile": 0}, index=[[f"{x}2" for x in EV_charging_profile.u.unique()]])])
    return EV_charging_profile.set_index(['u', 'p', 't'])


def get_EV_plugged_out(units, timestamp, profiles_input, days_mapping, profile):
    EV_plugged_out = pd.DataFrame(columns=['u', 'p', 't', 'EV_plugged_out'])
    EV_units = list(units[units.UnitOfType == "EV"][['Unit', 'UnitOfType']].Unit)

    for j, day in enumerate(list(timestamp.Weekday)[:-2]):
        try:
            EV_profiles = profiles_input.loc[:, profiles_input.columns.str.startswith("EV_") & profiles_input.columns.str.contains(days_mapping[day])].copy()
        except:
            raise ("day type not possible")

        out = EV_profiles.loc[:, EV_profiles.columns.str.contains("out")].copy()
        out['default'] = out['EV_out' + days_mapping[day]]
        missing_units = set(EV_units) - set(profile.columns)
        for unit in missing_units:
            out[unit] = out['default']
        out = out[EV_units]
        out.index.name = 't'
        out.columns.name = 'u'
        out = out.stack().to_frame(name="EV_plugged_out")
        out.reset_index(inplace=True)
        out['p'] = j + 1
        EV_plugged_out = pd.concat([EV_plugged_out, out])

    EV_plugged_out = pd.concat([EV_plugged_out, pd.DataFrame({"u": EV_plugged_out.u.unique(), "p": 11, "t": 1, "EV_plugged_out": 0}, index=[[f"{x}1" for x in EV_plugged_out.u.unique()]])])
    EV_plugged_out = pd.concat([EV_plugged_out, pd.DataFrame({"u": EV_plugged_out.u.unique(), "p": 12, "t": 1, "EV_plugged_out": 0}, index=[[f"{x}2" for x in EV_plugged_out.u.unique()]])])
    return EV_plugged_out.set_index(['u', 'p', 't'])


def get_activity_profile(units, timestamp, profiles_input, days_mapping):
    activity_profile = pd.DataFrame(columns=['a', 'u', 'p', 't', 'EV_activity'])
    EV_units = list(units[units.UnitOfType == "EV"][['Unit', 'UnitOfType']].Unit)

    for j, day in enumerate(list(timestamp.Weekday)[:-2]):
        try:
            EV_profiles = profiles_input.loc[:, profiles_input.columns.str.startswith("EV_") & profiles_input.columns.str.contains(days_mapping[day])].copy()
        except:
            raise ("day type not possible")

        act = EV_profiles.loc[:, EV_profiles.columns.str.startswith("EV_a")].copy()
        act.columns = [x.split('_')[1][1:-3] for x in act.columns]
        act.columns.name = 'a'
        act.index.name = 't'
        act = act.stack().to_frame(name="default")
        act.reset_index(inplace=True)
        missing_units = set(EV_units) - set(act.columns)
        for unit in missing_units:
            act[unit] = act['default']
        act.set_index(['a', 't'], inplace=True)
        act = act[EV_units]
        act.columns.name = 'u'
        act = act.stack().to_frame(name="EV_activity")
        act.reset_index(inplace=True)
        act['p'] = j + 1
        activity_profile = pd.concat([activity_profile, act])

    return activity_profile.set_index(['a','u', 'p', 't'])


def get_Ebike_charging(units, timestamp, profiles_input, days_mapping):
    EBike_charging_profile = pd.DataFrame(columns=['u', 'p', 't', 'EBike_charging_profile'])
    EBike_units = list(units[units.UnitOfType == "EBike"][['Unit','UnitOfType']].Unit)

    for j, day in enumerate(list(timestamp.Weekday)[:-2]):
        try:
            EBike_profiles = profiles_input.loc[:, profiles_input.columns.str.startswith("EBike_") &
                                                   profiles_input.columns.str.contains(days_mapping[day])].copy()
        except:
            raise ("day type not possible")

        cpf = EBike_profiles.loc[:, EBike_profiles.columns.str.contains("cpf")].copy()
        cpf['default'] = cpf['EBike_cpf' + days_mapping[day]]
        missing_units = set(EBike_units) - set(cpf.columns)
        for unit in missing_units:
            cpf[unit] = cpf['default']
        cpf = cpf[EBike_units]

        cpf.index.name = 't'
        cpf.columns.name = 'u'
        cpf = cpf.stack().to_frame(name="EBike_charging_profile")
        cpf.reset_index(inplace=True)
        cpf['p'] = j + 1

        EBike_charging_profile = pd.concat([EBike_charging_profile, cpf])
    return EBike_charging_profile.set_index(['u', 'p', 't'])


def get_mode_speed(units, mode_speed_custom):
    default_speed = pd.DataFrame({"UnitOfType": ['Bike', 'EV', 'ICE', 'PT_train', 'PT_bus', "EBike"],
                                  "Mode_Speed": [13.3, 37, 37, 60, 18, 17]})

    mode_speed = units[['Unit', 'UnitOfType']].copy()
    mode_speed = mode_speed.merge(default_speed, how='outer')
    mode_speed['Unit'].fillna(mode_speed['UnitOfType'], axis=0, inplace=True)
    mode_speed = mode_speed.set_index(['Unit'])[['Mode_Speed']]

    mode_speed_custom = pd.DataFrame.from_dict(mode_speed_custom, orient='index', columns=["Mode_Speed"])
    mode_speed.update(mode_speed_custom)
    return mode_speed.dropna()


def get_min_share(share_input, modes, transportunits):
    minshare = share_input.loc[:,share_input.columns.str.startswith("min")]
    minshare.columns = [x.split('_')[1] for x in minshare.columns]

    minshare.columns.name = "dist"
    minshare = minshare.join(pd.DataFrame(index = modes + list(transportunits)),how = 'outer').fillna(0)
    minshare = minshare.stack()
    minshare_modes = minshare[minshare.index.get_level_values(0).isin(modes)]
    minshare = minshare[minshare.index.get_level_values(0).isin(transportunits)]
    minshare_modes.name = "min_share_modes"
    minshare.name = "min_share"
    return minshare, minshare_modes


def get_max_share(share_input, modes, transportunits):
    maxshare = share_input.loc[:,share_input.columns.str.startswith("max")]
    maxshare.columns = [x.split('_')[1] for x in maxshare.columns]

    maxshare.columns.name = "dist"
    maxshare = maxshare.join(pd.DataFrame(index = modes + list(transportunits)),how = 'outer').fillna(1)
    maxshare = maxshare.stack()
    maxshare_modes = maxshare[maxshare.index.get_level_values(0).isin(modes)]
    maxshare = maxshare[maxshare.index.get_level_values(0).isin(transportunits)]
    maxshare_modes.name = "max_share_modes"
    maxshare.name = "max_share"
    return maxshare, maxshare_modes


def generate_transport_units_sets(transportunits):
    """

    Creates the sets transport_Units_MD and transport_Units_cars that are subsets of the available transport units, respectively for soft mobility and cars. 
    Used later to constrain the maximum and minimum share of public transport, soft mobility, cars in the total mobility supply.

    Parameters
    ----------
    transportunits : dict of arrays
        Each key of the dict is a UnitOfType label containing a list of all the Units names. should be something like self.infrastructure.UnitsOfType

    Returns
    -------
    transport_Units_MD : set
    transport_Units_cars :set
    """
    soft_mobility_UnitofType_all = {"Bike", "EBike"}
    cars_UnitofType_all = {"EV","ICE"}

    transport_Units_MD = list()
    for key in soft_mobility_UnitofType_all:
        if key in transportunits.keys():
            transport_Units_MD = transport_Units_MD + list(transportunits[key])

    transport_Units_cars = list()
    for key in cars_UnitofType_all:
        if key in transportunits.keys():
            transport_Units_cars = transport_Units_cars + list(transportunits[key])

    transport_Units_cars = np.array(transport_Units_cars)
    transport_Units_MD = np.array(transport_Units_MD)

    return transport_Units_MD,transport_Units_cars


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
    for act in share.columns:
        if act in rho.columns:
            share[act] = rho[act] / rho[act][rho.index.isin(ext_districts)].sum()
    share = share.stack().to_frame(name= "share_activity").reorder_levels([1,0])
    share.loc['travel'] = 0 # additionnal precaution
    return share


def compute_iterative_parameters(reho_models, Scn_ID, iter, district_parameters, only_prices=False):
    """"
    This function is used in the iterative scenario to iteratively calculate multiple districts with EVs being able to charge at the different districts.
    The load is expressed using the corrective parameter f.

    Parameters
    ----------
    reho_models : dict of reho objects
        Dictionary of reho object, one for each district
    Scn_ID : str or int
        label for the scenario
    iter : int
        iteration of the city scale optimization
    district_parameters : dict of dict
        Each key of the dict refers to a district d. Used to extract the scale parameter f : district_parameters[d]['f']
    only_prices : bool
        if False, only returns the parameters Cost_demand_ext and Cost_supply_ext
        if True, additionally returns the parameter EV_charger_supply_ext
    Returns
    -------
    parameters : dict of dict
        For each district d, returns a dict of the parameters to be inputted in the next optimisation. Parameters include Cost_demand_ext, Cost_supply_ext, EV_charger_supply_ext. 

    """
    parameters = dict()
    df_prices = pd.DataFrame()
    for d in district_parameters.keys():
        parameters[d] = {}
        pi = reho_models[d].results_MP[Scn_ID][iter][0]["df_Dual_t"]["pi"].xs("Electricity")
        parameters[d]["Cost_supply_ext"] = pi.rename("Cost_supply_ext").drop([11, 12], level="Period")

        price = pi.to_frame().copy()
        price['district'] = d
        price = price.set_index('district', append=True).reorder_levels([2, 0, 1]).drop([11, 12], level="Period")
        df_prices = pd.concat([df_prices, price])

    for d in district_parameters.keys():
        parameters[d]["Cost_demand_ext"] = df_prices.drop(d, level="district").rename(columns={'pi': 'Cost_demand_ext'})

    if not only_prices:
        # scale charging loads asked to external districts
        df_load = pd.DataFrame()
        for d in district_parameters.keys():
            df_unit_t = reho_models[d].results[Scn_ID][iter]["df_Unit_t"]
            EV_demand_ext = df_unit_t.loc[:, df_unit_t.columns.str.contains("EV_demand_ext")].xs("Electricity").xs("EV_district")
            activities = [x.split('[')[1].split(",")[0] for x in EV_demand_ext.columns]
            districts = [x.split('[')[1].split(",")[1].replace("]", "") for x in EV_demand_ext.columns]
            EV_demand_ext.columns = pd.MultiIndex.from_arrays([activities, districts], names=['activity','district'])
            EV_demand_ext = EV_demand_ext.stack(level=1).reorder_levels([2, 0, 1]) * district_parameters[d]['f']
            EV_demand_ext = EV_demand_ext * district_parameters[d]['f']
            df_load = pd.concat([df_load, EV_demand_ext]) # list of all external loads scaled to city level

        df_load = df_load.groupby(["district", "Period", "Time"]).sum()
        df_load = df_load.stack().unstack(level='district').reorder_levels([2, 0, 1])
        df_load.columns = df_load.columns.astype(float).astype(int) # load per district and activity at the city level

        for d in district_parameters.keys():
            parameters[d]["EV_charger_supply_ext"] = df_load[[d]].rename(columns={d: "EV_charger_supply_ext"}) / district_parameters[d]['f']

    return parameters

