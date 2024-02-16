from reho.model.preprocessing.sia_parser import *
from reho.model.preprocessing.QBuildings import *


def profile_reference_temperature(parameters_to_ampl, cluster):  # TODO: time dependent indoor temperature f.e. lower at night

    total_timesteps = cluster['Periods'] * cluster['PeriodDuration'] + 2
    T_comfort_min_0 = parameters_to_ampl['T_comfort_min_0']

    np_temperature = np.array([])
    for key in parameters_to_ampl['T_comfort_min_0']:
        np_temperature = np.append(np_temperature, np.tile(T_comfort_min_0[key], total_timesteps))

    return np_temperature


def profiles_from_sia2024(buildings_data, File_ID, cluster, include_stochasticity=False, sd_stochasticity=None):
    """
    Except if electricity, SH and DHW profiles are given by the user, REHO computes the End Use Demands from
    `SIA 2024 <https://shop.sia.ch/collection%20des%20normes/architecte/2024_2021_f/F/Product>`_.

    The SIA profiles are daily profiles with coefficient attributed to each month.
    This function extends the profiles to the periods used, according the building's affectation.

    Parameters
    ----------
    buildings_data : dict
        Dictionary of buildings data from QBuildingsReader class.
    File_ID : str
        File ID of the clustering results, used to know the periods and period duration.
    cluster : dict
        cluster parameter from the reho.model.reho.reho class
    include_stochasticity : bool
        Activate the method `include_stochasticity`, from the reho.model.reho.reho class, that includes variability
        in the values given by the SIA profiles.
    sd_stochasticity : dict
        Dictionary, from the reho.model.reho.reho class, that precises the parameters of the stochasticity (see :ref:`tbl-methods`).

    Returns
    -------
    Three Numpy arrays of shape (242,): the 1st one for the heat gains from people, the 2nd for DHW and the 3rd for
    the electricity demand.

    See also
    --------
    reho.model.preprocessing.QBuildings.QBuildingsReader :
        Class used to handle the buildings' data.
    reho.model.reho.reho :
        Wrapper Class that manages the optimization.

    Notes
    -----
    - One building can have several affectations. In that case, the building is divided by the share of ERA by
      affectations and the profiles are summed.

    """
    # get cluster information
    timestamp_file = os.path.join(path_to_clustering_results, 'timestamp_' + File_ID + '.dat')
    df = pd.read_csv(timestamp_file, delimiter='\t')
    df.Date = pd.to_datetime(df['Date'], format="%m/%d/%Y/%H")

    path_norms = os.path.join(path_to_sia, 'sia2024_data.xlsx')
    df_SIA = pd.read_excel(path_norms, sheet_name=['profiles', 'calculs', 'data'], engine='openpyxl',
                       index_col=[0], skiprows=[0, 2, 3, 4], header=[0])

    np_gain_all = np.array([])
    np_dhw_all = np.array([])
    np_el_all = np.array([])

    for b in buildings_data: #iterate over buildings
        # get SIA Profiles
        classes = buildings_data[b]['id_class'].split('/')
        if isinstance(buildings_data[b]['ratio'], float):
            ratios = str(buildings_data[b]['ratio'])
        else:
            ratios = buildings_data[b]['ratio'].split('/')
        status_buildings = buildings_data[b]['status'].split(',')
        np_gain_class = np.zeros(cluster['Periods'] * cluster['PeriodDuration'] + 2)
        np_dhw_class = np.zeros(cluster['Periods'] * cluster['PeriodDuration'] + 2)
        np_el_class = np.zeros(cluster['Periods'] * cluster['PeriodDuration'] + 2)
        for i, class_380 in enumerate(classes):
            # share of rooms for building type
            rooms = read_sia2024_rooms_sia380_1(class_380)
            status = ''.join(filter(str.isalnum, status_buildings[i]))
            if class_380 == 'I' or class_380 == 'II':
                area_net_floor = buildings_data[b]['ERA'] / 1.245
            else:
                area_net_floor = buildings_data[b]['ERA']
            area_net_floor = area_net_floor * float(ratios[i])
            np_gain = np.array([])
            np_dhw = np.array([])
            np_el = np.array([])

            if include_stochasticity:
                [RV_scaling, SF] = create_random_var(sd_stochasticity[0], sd_stochasticity[1])

            for p in df.index:  # get profiles for each typical day

                df_profiles = daily_profiles_with_monthly_deviation(status, rooms, df.xs(p).Date, df_SIA)

                if include_stochasticity:
                    df_profiles = apply_stochasticity(df_profiles, RV_scaling, SF)

                heatgain_day = (df_profiles['heatgainpeople_W/m2'] + df_profiles[
                    'electricity_W/m2']) * area_net_floor / 1000  # kW/m2

                hot_water_day = (df_profiles['hotwater_l/m2']) * area_net_floor  # L/m2

                electric_day = df_profiles['electricity_W/m2'] * area_net_floor / 1000  # kW/m2

                # sort it correctly (if first hour is not 12:00)
                begin = df.xs(p).Date.hour

                # Size = 24 hours
                heat_day = np.concatenate((heatgain_day.iloc[begin:].values, heatgain_day.iloc[:begin].values))
                dhw_day = np.concatenate((hot_water_day.iloc[begin:].values, hot_water_day.iloc[:begin].values))
                el_day = np.concatenate((electric_day.iloc[begin:].values, electric_day.iloc[:begin].values))

                # Size = PeriodDuration (= TimeEnd in ampl)
                heat_period = np.tile(heat_day, round(cluster['PeriodDuration']/24))
                dwh_period = np.tile(dhw_day, round(cluster['PeriodDuration']/24))
                el_period = np.tile(el_day, round(cluster['PeriodDuration']/24))

                np_gain = np.concatenate((np_gain, heat_period))
                np_dhw = np.concatenate((np_dhw, dwh_period))
                np_el = np.concatenate((np_el, el_period))

            # Size = Periods * PeriodDuration + 2 extreme periods
            np_gain = np.append(np_gain, [min(np_gain), max(np_gain)])
            np_dhw = np.append(np_dhw, [max(np_dhw), max(np_dhw)])
            np_el = np.append(np_el, [max(np_el), max(np_el)])
            np_gain_class += np_gain
            np_dhw_class += np_dhw
            np_el_class += np_el

        np_gain_all = np.append(np_gain_all, np_gain_class)
        np_dhw_all = np.append(np_dhw_all, np_dhw_class)
        np_el_all = np.append(np_el_all, np_el_class)

    return np_gain_all, np_dhw_all, np_el_all


def apply_stochasticity(df_profiles, scale, SF):

    # implement the intensity variation in standard profiles
    df_profiles = df_profiles * scale

    # implement the time shift in standard profiles
    shift_index = np.sign(SF) + np.int_(SF)
    shift_factor = SF - np.int_(SF)
    temp = df_profiles.to_numpy()
    temp_shifted = np.zeros((df_profiles.shape[0], df_profiles.shape[1]))
    for i in range(0, df_profiles.shape[1]):
        temp_shifted[:, i] = np.roll(temp[:, i], int(shift_index[i]), axis=0)
        if abs(shift_index[i]) > 1:
            temp[:, i] = np.roll(temp[:, i], int(shift_index[i] - np.sign(SF[i])), axis=0)
    final = temp * (1 - abs(shift_factor)) + temp_shifted * abs(shift_factor)
    df_profiles = pd.DataFrame(final, columns=df_profiles.columns, index=df_profiles.index)

    return df_profiles


def create_random_var(sd_amplitude, sd_timeshift):
    # constraints
    if sd_amplitude < 0: sd_amplitude = 0
    if sd_timeshift < 0: sd_timeshift = 0

    # create the random variable for the intensity variation
    mu = 1
    RV_scaling = np.random.normal(mu, sd_amplitude, 4)
    if RV_scaling.argmin() < 0: print("-------------- Negative value in the intensity variation --------------")

    # create the random variable for time-shift in standard profiles
    mu = 0
    SF = np.random.normal(mu, sd_timeshift, 4)

    return RV_scaling, SF


def solar_gains_profile(ampl, buildings_data, File_ID):
    """
    Computes the solar heat gains from the irradiance.

    It uses a typical irradiation file and uses `calc_orientation_profiles` to obtain the irradiation on the west
    facades. Additionally, the solar gains depends on the facades and on a window fraction (obtained from SIA 2024).

    Parameters
    ----------
    ampl : AMPL
        The AMPL object created in the reho.model.reho.reho class.
    buildings_data : dict
        Dictionary of buildings data from QBuildingsReader class.
    File_ID : str
        File ID of the clustering results, used to know the periods and period duration.

    Returns
    -------
    A Numpy array of shape (242,) with the solar gains for each timesteps.
    """
    # Number of days computation
    PeriodDuration = ampl.getParameter('TimeEnd').getValues().toPandas()
    timestamp_file = os.path.join(path_to_clustering_results, 'timestamp_'+File_ID+'.dat')
    df = pd.read_csv(timestamp_file, delimiter='\t')
    df.Date = pd.to_datetime(df['Date'], format="%m/%d/%Y/%H")

    frequency_dict = pd.Series(df.Frequency.values, index=df.Date).to_dict()
    frequency_dict['PeriodDuration'] ={}
    for p in ampl.getSet('PeriodStandard').getValues().toList():
        frequency_dict['PeriodDuration'][p] = PeriodDuration.loc[p].TimeEnd


    # get west_facades irradiation
    # check if irradiation already exists:
    filename = os.path.join(path_to_clustering_results, 'westfacades_irr_' + File_ID + '.txt')
    if not os.path.exists(filename):
        df_annual, irr_west = skd.calc_orientation_profiles(270, 90, 0, total_irradiation_csv, frequency_dict)
        np.savetxt(filename, irr_west)
    else:
        irr_west = pd.read_csv(filename, header=None)[0].values

    g = np.repeat(0.5, len(irr_west))  # g-value SIA 2024
    g[irr_west > 0.2] = 0.1  # assumption that if irradiation exceeds 200 W/m2, we use sunblinds

    np_gains = np.array([])
    for b in buildings_data:
        A_facades = buildings_data[b]['area_facade_m2']
        classes = buildings_data[b]['id_class'].split('/')
        if isinstance(buildings_data[b]['ratio'], float):
            ratios = str(buildings_data[b]['ratio'])
        else:
            ratios = buildings_data[b]['ratio'].split('/')
        status_buildings = buildings_data[b]['status'].split(',')
        glass_fraction_building = 0
        for i, class_380 in enumerate(classes):
            # share of rooms for building type
            rooms = read_sia2024_rooms_sia380_1(class_380)
            path_norms = os.path.join(path_to_sia, 'sia2024_data.xlsx')
            df = pd.read_excel(path_norms, sheet_name='data', engine='openpyxl', index_col=[0],
                               skiprows=[0, 2, 3, 4], header=[0])
            glass_fraction_2024 = df['Taux de surface vitrée']
            glass_fraction_rooms = (glass_fraction_2024 * rooms).sum()
            glass_fraction_building += glass_fraction_rooms * float(ratios[i])
        gains = irr_west / 1000 * g * 0.9 * glass_fraction_building / 100 * A_facades
        # glass fraction on facades from SIA 2024, 0.9 SIA 2024: acknowledge perpendicular rays
        np_gains = np.append(np_gains, gains)

    return np_gains