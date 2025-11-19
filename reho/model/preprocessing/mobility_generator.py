import warnings
from reho.paths import *
import reho.model.preprocessing.weather as weather
import pandas as pd
import numpy as np
import copy

__doc__ = """
Processes data for parameters related to the Mobility Layer. 
"""


# PARAMETERS AND SETS =========================================================================================

def generate_mobility_parameters(cluster, parameters, infrastructure, modal_split):
    """
    This function initializes (almost) all the necessary parameters to run the mobility sector in REHO.
    Additionally to the parameters given, this function reads data in the file dailyprofiles.csv

    Parameters
    ----------
    cluster : dict
        to get periods characterisations (p,t)
    parameters : dictionary
        From the parameters will be extracted values related to the mobility namely DailyDist, Mode_Speed and Population. Population is a float, DailyDist a dict of float, Mode_Speed is a dictionnary given by the user in the scenario initialisation. It can contain customed values for only some modes while the other remain default. 
    infrastructure : list
        a list of all infrastructure units providing Mobility + "Public_transport" => which is the Network_supply['Mobility']
    modal_split : df
        a dataframe of the modal split for each category of distance

    Returns
    -------
    param_output : dict
        a dict of dataframes containing the profiles for each param. 

    .. caution::

        The default values in this function are a hardcoded copy of parameters DailyDist and Population in mobility.mod.
    """
    param_output = dict()
    if "DailyDist" in parameters:
        if isinstance(parameters['DailyDist'], dict):
            parameters['DailyDist'] = pd.DataFrame.from_dict(parameters['DailyDist'], orient='index', columns=["DailyDist"])
        DailyDist = parameters['DailyDist']
    else:
        DailyDist = pd.DataFrame([36.8], index=["all"], columns=["DailyDist"])  # km per day

    if "Population" in parameters:
        Population = parameters['Population']
    else:
        Population = 10  # km per day

    if "Mode_Speed" in parameters:
        mode_speed_custom = parameters['Mode_Speed']
    else:
        mode_speed_custom = pd.DataFrame()

    # Periods
    # TODO IMPLEMENTATION of flexible period duration

    File_ID = weather.get_cluster_file_ID(cluster)
    clustering_directory = os.path.join(path_to_clustering, File_ID)

    timestamp = pd.read_csv(os.path.join(clustering_directory, 'timestamp.csv'))

    if 'W' not in File_ID.split('_'):
        timestamp = timestamp.fillna(1)  # only weekdays

    days_mapping = {0: "wnd",  # Weekend
                    1: "wdy"  # Weekday
                    }
    modes = ['cars', 'PT', 'MD']

    # Read the profiles and the transportation Units
    profiles_input = pd.read_csv(os.path.join(path_to_mobility, "dailyprofiles.csv"), index_col=0)
    units = pd.read_csv(os.path.join(path_to_infrastructure, "district_units.csv"), sep=";")

    transportunits = np.setdiff1d(np.append(infrastructure.UnitsOfLayer["Mobility"], ['PT_train', "PT_bus"]), infrastructure.UnitsOfType["EV_charger"])
    units = units[units.Unit.isin(transportunits)]

    # Check that modal_split is consistent with DailyDist
    if modal_split is not None:
        d = set([x.split('_')[1] for x in modal_split.columns])
        d = d.difference(DailyDist.index)
        if not (len(d) == 0):
            raise warnings.warn(
                f"reho.modal_split contains invalid categories of distance {d}. \n Categories of distances labels should be in this list : {list(DailyDist.index)}")

    # Compute the parameters
    param_output['Domestic_energy_pkm'], param_output['Domestic_energy'] = get_mobility_demand(profiles_input, timestamp, days_mapping, DailyDist, Population)
    param_output['Daily_Profile'] = get_daily_profile(profiles_input, timestamp, days_mapping, transportunits)

    param_output['EV_charging_profile'] = get_EV_charging(units, timestamp, profiles_input, days_mapping)
    param_output['EV_plugged_out'] = get_EV_plugged_out(units, timestamp, profiles_input, days_mapping)
    param_output['EV_activity'] = get_activity_profile(units, timestamp, profiles_input, days_mapping)
    param_output['EBike_charging_profile'] = get_Ebike_charging(units, timestamp, profiles_input, days_mapping)

    param_output['Mode_Speed'] = get_mode_speed(units, mode_speed_custom)
    if modal_split is not None:
        param_output['min_share'], param_output['min_share_modes'] = get_min_share(modal_split, modes, transportunits)
        param_output['max_share'], param_output['max_share_modes'] = get_max_share(modal_split, modes, transportunits)
    param_output['DailyDist'] = DailyDist
    param_output['Population'] = Population

    return param_output


def get_mobility_demand(profiles_input, timestamp, days_mapping, DailyDist, Population):
    """
    Formatting of the parameters Domestic_energy_pkm and Domestic_energy

    Parameters
    ----------
    profiles_input : df
        a dataframe of 24h profile data. 
    timestamp : df
        from the reho.cluster, to get the type of day (weekday, weekend) for each Period.
    days_mapping : dict
        mapping between the labels of profile_input and timestamp
    DailyDist : float
    Population : float

    Returns
    -------
    demand_pkm : df
        the param Domestic_energy_pkm[dist,p,t] by categories of distance
    mobility_demand : df
        the param Domestic_energy[Mobility,p,t]
    """
    # The labels look like this : demwdy_def, demwdy_long => normalized mobility demand of a weekday
    profiles_demand = profiles_input.loc[:, profiles_input.columns.str.startswith("dem")]
    profiles_demand = profiles_demand * Population

    distances = DailyDist.index
    demand_pkm = pd.DataFrame(columns=['dist', 'p', 't', 'Domestic_energy_pkm'])

    for dist in distances:
        for j, day in enumerate(list(timestamp.Weekday)[:-2]):
            try:
                profile = profiles_demand[[f"dem{days_mapping[day]}_{dist}"]].copy()
                profile.rename(columns={f"dem{days_mapping[day]}_{dist}": "Domestic_energy_pkm"}, inplace=True)
            except:
                try:
                    profile = profiles_demand[[f"dem{days_mapping[day]}_def"]].copy()  # default profile
                    profile.rename(columns={f"dem{days_mapping[day]}_def": "Domestic_energy_pkm"}, inplace=True)
                except:
                    raise (f"Demand profile error : no default demand profile for {day} daytype")
            profile.index.name = 't'
            profile.reset_index(inplace=True)
            profile['p'] = j + 1

            profile["Domestic_energy_pkm"] *= DailyDist.loc[dist].values[0]
            profile['dist'] = dist

            demand_pkm = pd.concat([demand_pkm, profile])

    extreme_hours = pd.concat([pd.DataFrame({"p": len(timestamp)-1, "t": 1, "Domestic_energy_pkm": 0}, index=DailyDist.index),
                               pd.DataFrame({"p": len(timestamp), "t": 1, "Domestic_energy_pkm": 0}, index=DailyDist.index)])

    extreme_hours.index.name = 'dist'
    extreme_hours.reset_index(inplace=True)
    demand_pkm = pd.concat([demand_pkm, extreme_hours])
    demand_pkm.set_index(['dist', 'p', 't'], inplace=True)

    mobility_demand = demand_pkm.groupby(['p', 't']).agg('sum')
    mobility_demand.reset_index(inplace=True)
    mobility_demand['l'] = "Mobility"
    mobility_demand.set_index(['l', 'p', 't'], inplace=True)
    mobility_demand.rename(columns={"Domestic_energy_pkm": "Domestic_energy"}, inplace=True)
    return demand_pkm, mobility_demand


def get_daily_profile(profiles_input, timestamp, days_mapping, transportunits):
    """
    Formatting of the parameters Daily_Profile[u,p,t], used for example for the Bikes and ICE transport units. Either a profile is declared in the file dailyprofiles.csv, or the default profile taken is equal to the daily demand profile of a given day (demwdy_def and demwnd_def). 

    Parameters
    ----------
    profiles_input : df
        a dataframe of 24h profile data. 
    timestamp : df
        from the reho.cluster, to get the type of day (weekday, weekend) for each Period.
    days_mapping : dict
        mapping between the labels of profile_input and timestamp
    transportunits : list

    Returns
    -------
    daily_profile : df
       the parameter Daily_Profile[u,p,t] 
    """

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
        profile = profile.multiply(dd_filter.iloc[:, 0], axis='index')
        profile.columns = [x.split('_')[0] + "_district" for x in profile.columns]
        missing_units = set(transportunits) - set(profile.columns) - {'Public_transport'}
        for unit in missing_units:
            profile[unit] = dd  # fill missing series with the period demand profile

        profile.index.name = 't'
        profile.columns.name = 'u'
        profile = profile.stack().to_frame(name="Daily_Profile")
        profile.reset_index(inplace=True)
        profile['p'] = j + 1
        daily_profile = pd.concat([daily_profile, profile])

    pd.concat([daily_profile, pd.DataFrame({"p": len(timestamp)-1, "t": 1, "Daily_Profile": 0}, index=["extremehour1"])])
    pd.concat([daily_profile, pd.DataFrame({"p": len(timestamp), "t": 1, "Daily_Profile": 0}, index=["extremehour2"])])
    return daily_profile.set_index(['u', 'p', 't'])


def get_EV_charging(units, timestamp, profiles_input, days_mapping):
    """
    Formatting of the parameter EV_charging_profile[u,p,t]. Data is taken from dailyprofiles.csv (columns EV_cpfwnd and EV_cpfwdy). Each Unit (from UnitOfType[EV]) can be provided with a personnalized profile, otherwise the default value EV_cpfxxx is taken. 

    Parameters
    ----------
    profiles_input : df
        a dataframe of 24h profile data. 
    timestamp : df
        from the reho.cluster, to get the type of day (weekday, weekend) for each Period.
    days_mapping : dict
        mapping between the labels of profile_input and timestamp
    units : df
        dataframe from district_units.csv

    Returns
    -------
    EV_charging_profile : df
       the parameter EV_charging_profile[u,p,t] 
    """
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

    aaa = pd.DataFrame({"u": EV_charging_profile.u.unique(), "p": len(timestamp)-1, "t": 1, "EV_charging_profile": 0},
                       index=[f"{x}1" for x in EV_charging_profile.u.unique()])
    EV_charging_profile = pd.concat([EV_charging_profile, aaa])
    EV_charging_profile = pd.concat([EV_charging_profile, pd.DataFrame({"u": EV_charging_profile.u.unique(), "p": len(timestamp), "t": 1, "EV_charging_profile": 0},
                                                                       index=[[f"{x}2" for x in EV_charging_profile.u.unique()]])])
    return EV_charging_profile.set_index(['u', 'p', 't'])


def get_EV_plugged_out(units, timestamp, profiles_input, days_mapping):
    """
    Formatting of the parameter EV_plugged_out[u,p,t]. Data is taken from dailyprofiles.csv (columns EV_outwnd and EV_outwdy). Each Unit (from UnitOfType[EV]) can be provided with a personnalized profile, otherwise the default value EV_outxxx is taken. 

    Parameters
    ----------
    profiles_input : df
        a dataframe of 24h profile data. 
    timestamp : df
        from the reho.cluster, to get the type of day (weekday, weekend) for each Period.
    days_mapping : dict
        mapping between the labels of profile_input and timestamp
    units : df
        dataframe from district_units.csv

    Returns
    -------
    EV_plugged_out : df
       the parameter EV_plugged_out[u,p,t] 
    """
    EV_plugged_out = pd.DataFrame(columns=['u', 'p', 't', 'EV_plugged_out'])
    EV_units = list(units[units.UnitOfType == "EV"][['Unit', 'UnitOfType']].Unit)

    for j, day in enumerate(list(timestamp.Weekday)[:-2]):
        try:
            EV_profiles = profiles_input.loc[:, profiles_input.columns.str.startswith("EV_") & profiles_input.columns.str.contains(days_mapping[day])].copy()
        except:
            raise ("day type not possible")

        out = EV_profiles.loc[:, EV_profiles.columns.str.contains("out")].copy()
        out['default'] = out['EV_out' + days_mapping[day]]
        for unit in set(EV_units):
            out[unit] = out['default']
        out = out[EV_units]
        out.index.name = 't'
        out.columns.name = 'u'
        out = out.stack().to_frame(name="EV_plugged_out")
        out.reset_index(inplace=True)
        out['p'] = j + 1
        EV_plugged_out = pd.concat([EV_plugged_out, out])

    EV_plugged_out = pd.concat([EV_plugged_out, pd.DataFrame({"u": EV_plugged_out.u.unique(), "p": len(timestamp)-1, "t": 1, "EV_plugged_out": 0},
                                                             index=[[f"{x}1" for x in EV_plugged_out.u.unique()]])])
    EV_plugged_out = pd.concat([EV_plugged_out, pd.DataFrame({"u": EV_plugged_out.u.unique(), "p": len(timestamp), "t": 1, "EV_plugged_out": 0},
                                                             index=[[f"{x}2" for x in EV_plugged_out.u.unique()]])])
    return EV_plugged_out.set_index(['u', 'p', 't'])


def get_activity_profile(units, timestamp, profiles_input, days_mapping):
    """
    Formatting of the parameter EV_activity[a,u,p,t]. Data is taken from dailyprofiles.csv (columns EV_aAAddd, with AA the activity label and ddd the type of day).

    Parameters
    ----------
    units : df
        dataframe from district_units.csv
    profiles_input : df
        a dataframe of 24h profile data. 
    timestamp : df
        from the reho.cluster, to get the type of day (weekday, weekend) for each Period.
    days_mapping : dict
        mapping between the labels of profile_input and timestamp

    Returns
    -------
    activity_profile : df
       the parameter EV_activity[a,u,p,t] 
    """

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

    return activity_profile.set_index(['a', 'u', 'p', 't'])


def get_Ebike_charging(units, timestamp, profiles_input, days_mapping):
    """
    Formatting of the parameter EBike_charging_profile[u,p,t]. Data is taken from dailyprofiles.csv (columns EBike_cpfddd, with ddd the type of day).

    Parameters
    ----------
    units : df
        dataframe from district_units.csv
    profiles_input : df
        a dataframe of 24h profile data. 
    timestamp : df
        from the reho.cluster, to get the type of day (weekday, weekend) for each Period.
    days_mapping : dict
        mapping between the labels of profile_input and timestamp

    Returns
    -------
    EBike_charging_profile : df
       the parameter EBike_charging_profile[u,p,t] 
    """
    EBike_charging_profile = pd.DataFrame(columns=['u', 'p', 't', 'EBike_charging_profile'])
    EBike_units = list(units[units.UnitOfType == "EBike"][['Unit', 'UnitOfType']].Unit)

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
    """
    Formatting of the parameter Mode_speed[u]. Default values are taken from OFS microcensus report. 

    Parameters
    ----------
    units : df
        dataframe from district_units.csv
    mode_speed_custom : df or dict
        customized speed given by the user. 

    Returns
    -------
    mode_speed : df
       the parameter Mode_Speed[u] 
    """
    default_speed = pd.DataFrame({"UnitOfType": ['Bike', 'EV', 'ICE', 'PT_train', 'PT_bus', "EBike"],
                                  "Mode_Speed": [13.3, 37, 37, 60, 18, 17]})

    mode_speed = units[['Unit', 'UnitOfType']].copy()
    mode_speed = mode_speed.merge(default_speed, how='left')
    mode_speed['Unit'].fillna(mode_speed['UnitOfType'], axis=0, inplace=True)
    mode_speed = mode_speed.set_index(['Unit'])[['Mode_Speed']]

    mode_speed_custom = pd.DataFrame.from_dict(mode_speed_custom, orient='index', columns=["Mode_Speed"])
    mode_speed.update(mode_speed_custom)
    return mode_speed.dropna()


def get_min_share(modal_split, modes, transportunits):
    """
    Formatting of the parameters min_share[u,dist] and min_share_modes[u,dist]. 

    Parameters
    ----------
    modal_split : df
        dataframe with columns for the categories of distance and rows for the units and modes.
    modes : list
        list of modes (usually cars, PT and MD)
    transportunits : list
        list of transport units. 

    Returns
    -------
    minshare : df
       the parameter min_share[u,dist] 
    minshare_modes : df
       the parameter min_share_modes[u,dist] 
    """
    minshare = modal_split.loc[:, modal_split.columns.str.startswith("min")]
    minshare.columns = [x.split('_')[1] for x in minshare.columns]

    minshare.columns.name = "dist"
    minshare = minshare.join(pd.DataFrame(index=modes + list(transportunits)), how='outer').fillna(0)
    minshare = minshare.stack()
    minshare_modes = minshare[minshare.index.get_level_values(0).isin(modes)]
    minshare = minshare[minshare.index.get_level_values(0).isin(transportunits)]
    minshare_modes.name = "min_share_modes"
    minshare.name = "min_share"
    return minshare, minshare_modes


def get_max_share(modal_split, modes, transportunits):
    """
    Formatting of the parameters max_share[u,dist] and max_share_modes[u,dist]. 

    Parameters
    ----------
    modal_split : df
        dataframe with columns for the categories of distance and rows for the units and modes.
    modes : list
        list of modes (usually cars, PT and MD)
    transportunits : list
        list of transport units. 

    Returns
    -------
    maxshare : df
       the parameter max_share[u,dist] 
    maxshare_modes : df
       the parameter max_share_modes[u,dist] 
    """
    maxshare = modal_split.loc[:, modal_split.columns.str.startswith("max")]
    maxshare.columns = [x.split('_')[1] for x in maxshare.columns]

    maxshare.columns.name = "dist"
    maxshare = maxshare.join(pd.DataFrame(index=modes + list(transportunits)), how='outer').fillna(1)
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
    cars_UnitofType_all = {"EV", "ICE"}

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

    return transport_Units_MD, transport_Units_cars


# FUNCTIONS FOR CO-OPTIMIZATION =========================================================================================

def rho_param(ext_districts, rho, activities=["work", "leisure", "travel"]):
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
    share = pd.DataFrame(index=ext_districts, columns=activities).fillna(1 / len(ext_districts))
    for act in share.columns:
        if act in rho.columns:
            share[act] = rho[act] / rho[act][rho.index.isin(ext_districts)].sum()
    share = share.stack().to_frame(name="share_activity").reorder_levels([1, 0])
    share.loc['travel'] = 0  # additionnal precaution
    return share


# FUNCTIONS PROCESSING OF WP1 DATA =======================================================================================
# stored in the files WP1_distributionofdistances.csv and WP1_modalsharesbydistances (work and leisure)

def linear_split_bin_table(df, col, lowerbound=None, upperbound=None):
    """
    Cuts off a discrete bin distribution data serie to the desired bounds. First and last bin are calculated proportionnally to the size of the bin. 

    Parameters
    -------------
    df : dataframe
        data
    col : str
        the columns of the df on which the split operation is applied
    lowerbound : float or None
    upperbound : float or None
    """
    if upperbound:
        if upperbound in df.index:
            df_up = df.loc[df.index <= upperbound, :].copy()
        else:
            df_up = df.loc[df.index < upperbound, :].copy()
            last_bin = df.loc[df.index > upperbound, :].iloc[0]
            last_bin[col] = (upperbound - df_up.index[-1]) / (last_bin.name - df_up.index[-1]) * last_bin[col]
            last_bin.name = upperbound
            df_up = pd.concat([df_up, last_bin.to_frame().T])

    if lowerbound:
        if upperbound:
            df_up = df_up.loc[df_up.index > lowerbound, :].copy()
        else:
            df_up = df.loc[df.index > lowerbound, :].copy()

        if not lowerbound in df.index:
            prev_bin = df.loc[df.index < lowerbound, :].iloc[-1]
            weight = (df_up.index[0] - lowerbound) / (df_up.index[0] - prev_bin.name) * df_up.iloc[0][col]
            df_up.at[df_up.index[0], col] = weight

    return df_up


def mobility_demand_from_WP1data(pkm_demand, max_dist=70, nbins=1, modalwindow=0.01, share_cars=None, share_EV_infleet=None):
    """
    This functions computes parameters related to mobility from data tables provided by WP1 (OFS data). Parameters computed include : DailyDist and the modal_split dataframe. 

    Parameters
    -----------
    pkm_demand : float
        Total number of km travelled/day/cap
    max_dist :  float
        trip length cutoff 
    nbins : int
        number of categories of distance
    modal_window : float
        delta between max and min share bounds is modal_window*2
    share_cars : float in [0,1]
        modifies the modal shares PT and MD in consequence. 
    share_EV_infleet : Float in [0,1]
        the share of EVs in the car fleet
    
    Returns
    ---------
    DailyDist : dict 
    modal_split : df for reho.modal_split
    """
    DailyDist = {}
    modal_split = pd.DataFrame()
    modal_split_custom = pd.DataFrame()

    df_dist = pd.read_csv(os.path.join(path_to_mobility, 'WP1_distributionofdistances.csv'), index_col=0)
    df_modal_split = pd.read_csv(os.path.join(path_to_mobility, 'WP1_modalsharesbydistances_work.tsv'), sep="\t", index_col=0)

    mapping_modesunits = {
        "Marche": "MD",
        "Vélo": "MD",
        "moto": "cars",
        "voiture": "cars",
        "tram/bus": "PT",
        "train": "PT"
    }

    df_dist_inf = linear_split_bin_table(df_dist, "weight", upperbound=max_dist)
    df_dist_inf.weight = df_dist_inf.weight / df_dist_inf.weight.sum()

    df_dist_inf['up'] = df_dist_inf.index
    df_dist_inf['low'] = df_dist_inf.up.shift(1).fillna(0)
    df_dist_inf['mean'] = (df_dist_inf.up + df_dist_inf.low) / 2
    df_dist_inf['pkm'] = df_dist_inf['mean'] * df_dist_inf['weight']
    df_dist_inf.pkm = df_dist_inf.pkm / df_dist_inf.pkm.sum()

    df_dist_inf = df_dist_inf.join(df_modal_split)
    df_dist_inf[df_modal_split.columns] = df_dist_inf[df_modal_split.columns].fillna(method='bfill').fillna(method='ffill')

    lowerbound = 0
    step = max_dist / nbins
    for i in range(nbins):
        upperbound = lowerbound + step
        df_bin = linear_split_bin_table(df_dist_inf, "pkm", lowerbound, upperbound)
        DailyDist[f"D{i}"] = df_bin.pkm.sum() * pkm_demand

        df_ms = df_bin[df_modal_split.columns].mul(df_bin['pkm'], axis=0).sum()
        df_ms = df_ms.div(df_ms.sum())
        df_ms.index = df_ms.index.map(mapping_modesunits)
        df_ms = df_ms.groupby(df_ms.index).agg("sum")
        df_ms_min = df_ms.copy()

        modal_split[f"min_D{i}"] = df_ms_min.apply(lambda x: max(x - modalwindow, 0))
        modal_split[f"max_D{i}"] = df_ms.apply(lambda x: min(x + modalwindow, 1))
        modal_split_custom[f"D{i}"] = df_ms

        lowerbound = upperbound

    if not (share_cars is None):
        mean_share = sum(modal_split.loc["cars", modal_split.columns.str.startswith("max")].values * list(DailyDist.values()))
        mean_share = mean_share / sum(DailyDist.values())
        modal_split_custom.loc['cars', :] = modal_split_custom.loc['cars', :].apply(lambda x: x * share_cars / mean_share)

        modal_split_custom = modal_split_custom.T
        modal_split_custom[['MD', 'PT']] = modal_split_custom.apply(lambda x: (x.MD / (x.MD + x.PT) * (1 - x.cars), x.PT / (x.MD + x.PT) * (1 - x.cars)),
                                                                    axis=1, result_type='expand')
        modal_split_custom = modal_split_custom.T

        for D in modal_split_custom.columns:
            modal_split[f"min_{D}"] = modal_split_custom[D].apply(lambda x: max(x - modalwindow, 0))
            modal_split[f"max_{D}"] = modal_split_custom[D].apply(lambda x: min(x + modalwindow, 1))

    if not (share_EV_infleet is None):
        modal_split = modal_split.T
        modal_split['EV_district'] = share_EV_infleet * modal_split["cars"]
        modal_split = modal_split.T

    return DailyDist, modal_split
