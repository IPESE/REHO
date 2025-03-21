from datetime import timedelta
from reho.model.preprocessing.sia_parser import *
from reho.model.preprocessing.QBuildings import *

__doc__ = """
Generates the buildings profiles for domestic hot water (DHW) demand, domestic electricity demand, internal heat gains, and solar gains.
"""


def reference_temperature_profile(parameters_to_ampl, cluster):
    """
    Returns a reference temperature timeseries.
    """
    # TODO: time dependent indoor temperature f.e. lower at night

    total_timesteps = cluster['Periods'] * cluster['PeriodDuration'] + 2
    T_comfort_min_0 = parameters_to_ampl['T_comfort_min_0']

    np_temperature = np.array([])
    for key in parameters_to_ampl['T_comfort_min_0']:
        np_temperature = np.append(np_temperature, np.tile(T_comfort_min_0[key], total_timesteps))

    return np_temperature


def eud_profiles(buildings_data, cluster, df_SIA_380, df_SIA_2024, df_Timestamp, include_stochasticity=False, sd_stochasticity=None, use_custom_profiles=False):
    """
    Generates building-specific profiles for internal heat gains, DHW demand, and domestic electricity demand based on
    `SIA 2024 norms <https://shop.sia.ch/collection%20des%20normes/architecte/2024_2021_f/F/Product>`_.

    The SIA profiles are daily profiles with coefficient attributed to each month.
    This function extends the profiles to the periods used, according to the building's affectation.

    Parameters
    ----------
    buildings_data : dict
        Buildings data from QBuildingsReader class.
    df_SIA_380 : pd.DataFrame
        SIA norms.
    df_SIA_2024 : pd.DataFrame
        SIA norms.
    df_Timestamp : pd.DataFrame
        Information for clustering results, used to know the periods and period duration.
    cluster : dict
        Clustering parameters.
    include_stochasticity : bool
        Includes variability in the standard values given by the SIA profiles (see :ref:`tbl-methods`).
    sd_stochasticity : list
        Parameters of the stochasticity: first value is the standard deviation on the peak demand, second value is the standard deviation on the time-shift (see :ref:`tbl-methods`).
    use_custom_profiles : dict
        Allows to give custom profiles (see :ref:`tbl-methods`).

    Returns
    -------
    np.array
        Heat gains from people
    np.array
        DHW demand
    np.array
        Electricity demand

    See also
    --------
    reho.model.preprocessing.QBuildings.QBuildingsReader

    Notes
    -----
    - One building can have several affectations. In that case, the building is divided by the share of ERA by
      affectations and the profiles are summed.
    - To use custom profiles, use csv files with 8760 rows. The name of the columns should be the same as the buildings keys in `buildings_data`.

    .. caution::

        When using custom electricity profiles, the heat gains from electricity appliances are estimated through a conversion
        factor ``conv_heat_factor`` (default value = 70%).

    Examples
    --------
    >>> my_profiles = {'electricity': 'my_folder/electricity.csv'}
    >>> file_id = 'Geneva_10_24_T_I_W'
    >>> cluster = {'Location': 'Bruxelles', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}
    >>> people_gain, eud_dhw, eud_elec = eud_profiles(buildings_data, cluster, use_custom_profiles=my_profiles)
    """
    # get cluster information
    df_Timestamp.Date = df_Timestamp['Date']

    np_gain_all = np.array([])
    np_dhw_all = np.array([])
    np_el_all = np.array([])

    for b in buildings_data:  # iterate over buildings
        # get SIA Profiles
        classes = buildings_data[b]['id_class'].split('/')
        if isinstance(buildings_data[b]['ratio'], float):
            ratios = str(buildings_data[b]['ratio'])
        else:
            ratios = buildings_data[b]['ratio'].split('/')
        status_buildings = buildings_data[b]['status'].split(',')
        np_gain_b = np.zeros(cluster['Periods'] * cluster['PeriodDuration'] + 2)
        np_dhw_b = np.zeros(cluster['Periods'] * cluster['PeriodDuration'] + 2)
        np_el_b = np.zeros(cluster['Periods'] * cluster['PeriodDuration'] + 2)
        for i, class_380 in enumerate(classes):
            # share of rooms for building type
            rooms = read_sia2024_rooms_sia380_1(class_380, df_SIA_380)
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

            for p in df_Timestamp.index:  # get profiles for each typical day

                df_profiles = daily_profiles_with_monthly_deviation(status, rooms, df_Timestamp.xs(p).Date, df_SIA_2024)
                if include_stochasticity:
                    df_profiles = apply_stochasticity(df_profiles, RV_scaling, SF)

                elec_gain = df_profiles['elecgain_W/m2'] * area_net_floor
                elec = df_profiles['electricity_W/m2'] * area_net_floor

                people_gain = df_profiles['heatgainpeople_W/m2'] * area_net_floor
                hotwater = df_profiles['hotwater_l/m2'] * area_net_floor

                heatgain_day = (people_gain + elec_gain) / 1000  # kW profiles for each typical day
                hot_water_day = hotwater  # L profiles for each typical day
                electric_day = elec / 1000  # kW profiles for each typical day

                if p not in df_Timestamp.index.tolist()[-2:]:
                    # sort it correctly (if first hour is not 12:00)
                    begin = df_Timestamp.xs(p).Date.hour

                    # Size = 24 hours
                    heat_day = np.concatenate((heatgain_day.iloc[begin:].values, heatgain_day.iloc[:begin].values))
                    dhw_day = np.concatenate((hot_water_day.iloc[begin:].values, hot_water_day.iloc[:begin].values))
                    el_day = np.concatenate((electric_day.iloc[begin:].values, electric_day.iloc[:begin].values))

                    # Size = PeriodDuration (= TimeEnd in ampl)
                    heat_period = np.tile(heat_day, round(cluster['PeriodDuration'] / 24))
                    dhw_period = np.tile(dhw_day, round(cluster['PeriodDuration'] / 24))
                    el_period = np.tile(el_day, round(cluster['PeriodDuration'] / 24))

                elif p == df_Timestamp.index.tolist()[-2:][0]:  # Minimum period
                    heat_period = np.array([min(heatgain_day)])
                    dhw_period = np.array([max(dhw_day)])
                    el_period = np.array([max(el_day)])
                else:  # Maximum period
                    heat_period = np.array([max(heatgain_day)])
                    dhw_period = np.array([max(dhw_day)])
                    el_period = np.array([max(el_day)])

                np_gain = np.concatenate((np_gain, heat_period))
                np_dhw = np.concatenate((np_dhw, dhw_period))
                np_el = np.concatenate((np_el, el_period))

            # Sum values for all affectations of the building
            np_gain_b += np_gain
            np_dhw_b += np_dhw
            np_el_b += np_el

        # Append values for all buildings
        np_gain_all = np.append(np_gain_all, np_gain_b)
        np_dhw_all = np.append(np_dhw_all, np_dhw_b)
        np_el_all = np.append(np_el_all, np_el_b)

    # Overwrite with custom profiles if provided
    if use_custom_profiles:

        # Heat gains from people
        conv_heat_factor = 0.70
        np_gain_people = np.maximum(np_gain_all - conv_heat_factor * np_el_all, 0)

        if 'electricity' in use_custom_profiles:
            df = annual_to_typical(cluster, annual_file=use_custom_profiles['electricity'], df_Timestamp=df_Timestamp)
            np_el_all = np.array([])
            for b in buildings_data:
                el_b = df[b].values / 1000
                np_el_all = np.append(np_el_all, el_b)

            # Correct total heat gains
            np_gain_all = np_gain_people + conv_heat_factor * np_el_all

        if 'dhw' in use_custom_profiles:
            df = annual_to_typical(cluster, annual_file=use_custom_profiles['dhw'], df_Timestamp=df_Timestamp)
            np_dhw_all = np.array([])
            for b in buildings_data:
                dhw_b = df[b].values
                np_dhw_all = np.append(np_dhw_all, dhw_b)

    return np_gain_all, np_dhw_all, np_el_all


def apply_stochasticity(df_profiles, scale, SF):
    """
    Returns the daily profiles where an intensity variation (scale) and time shift factor (SF) have been applied.
    """
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
    """
    Creates an array of random variables for the use of ``apply_stochasticity``.

    Notes
    -----
    The array is hard-coded to be of dimension [1,5], as it applies on the daily profiles for electricity demand, DHW demand, occupancy, electricity heat gains, and heat gains from people.

    See also
    --------
    reho.model.preprocessing.buildings_profiles.apply_stochasticity
    reho.model.preprocessing.sia_parser.daily_profiles_with_monthly_deviation
    """
    # constraints
    if sd_amplitude < 0:
        sd_amplitude = 0
    if sd_timeshift < 0:
        sd_timeshift = 0

    # create the random variable for the intensity variation
    mu = 1
    RV_scaling = np.random.normal(mu, sd_amplitude, 5)
    if RV_scaling.argmin() < 0:
        print("-------------- Negative value in the intensity variation --------------")

    # create the random variable for time-shift in standard profiles
    mu = 0
    SF = np.random.normal(mu, sd_timeshift, 5)

    return RV_scaling, SF


def annual_to_typical(cluster, annual_file, df_Timestamp, typical_file=None):
    """
    From an annual profile (8760 values), extracts the values corresponding to the typical days.

    Parameters
    ----------
    cluster : dict
        Dictionary containing 'PeriodDuration' indicating number of hours per typical day.
    annual_file : str
        Path to annual CSV file containing at least a 'time(UTC)' column.
    df_Timestamp : pd.DataFrame
        DataFrame containing at least a 'Date' column indicating typical day dates.
    typical_file : str, optional
        Path to save the extracted typical day CSV file.

    Returns
    -------
    df_typical : pd.DataFrame
        DataFrame indexed by ['Period', 'Hour'] containing typical day data.
    """

    # Load annual data
    df_annual = pd.read_csv(annual_file, parse_dates=['time(UTC)'])
    df_annual.set_index('time(UTC)', inplace=True)

    # Ensure timezone consistency
    # annual_tz = df_annual.index.tz

    typical_dates = pd.to_datetime(df_Timestamp['Date']).dt.normalize()

    df_typical = pd.DataFrame()

    # Extract data for typical days (excluding extreme periods)
    for date in typical_dates[:-2]:
        day_data = df_annual[date:date + timedelta(hours=23)]
        df_typical = pd.concat([df_typical, day_data])

    # Handle extreme periods (minimum and maximum of the annual data)
    min_values = df_annual.min().to_frame().T
    max_values = df_annual.max().to_frame().T

    df_typical = pd.concat([df_typical, min_values, max_values], ignore_index=True)

    # Create multi-index [Period, Hour]
    regular_periods = len(typical_dates) - 2
    periods = list(range(1, regular_periods + 1))
    hours = list(range(1, cluster['PeriodDuration'] + 1))

    # Add extreme periods with duration = 1
    periods += [regular_periods + 1, regular_periods + 2]
    hours += [1, 1]

    df_typical.index = pd.MultiIndex.from_tuples(
        [(p, h) for p in range(1, regular_periods + 1) for h in range(1, cluster['PeriodDuration'] + 1)] +
        [(regular_periods + 1, 1), (regular_periods + 2, 1)],
        names=['Period', 'Hour']
    )

    if typical_file:
        df_typical.to_csv(typical_file)

    return df_typical


def solar_gains_profile(buildings_data, sia_data, local_data):
    """
    Computes the solar heat gains from the irradiance. Heat gains depend on the facades surfaces and on a window fraction (obtained from SIA 2024).

    Parameters
    ----------
    buildings_data : dict
        Building-specific data.
    sia_data : dict
        SIA norms.
    local_data : dict
        Location-specific data.

    Returns
    -------
    np.array
        Solar gains for each timesteps.
    """

    irr = local_data["Irr"] * 0.6  # factor to convert global to horizontal irradiance

    g = np.repeat(0.5, len(irr))  # g-value SIA 2024
    g[irr > 0.2] = 0.1  # assumption that if irradiation exceeds 200 W/m2, we use sunblinds

    np_gains = np.array([])
    for b in buildings_data:
        A_facades = buildings_data[b]['area_facade_m2']
        classes = buildings_data[b]['id_class'].split('/')
        if isinstance(buildings_data[b]['ratio'], float):
            ratios = str(buildings_data[b]['ratio'])
        else:
            ratios = buildings_data[b]['ratio'].split('/')
        glass_fraction_building = 0
        for i, class_380 in enumerate(classes):
            # share of rooms for building type
            rooms = read_sia2024_rooms_sia380_1(class_380, sia_data["df_SIA_380"])
            df = sia_data["df_SIA_2024"]['data']
            glass_fraction_2024 = df['Taux de surface vitrée']
            glass_fraction_rooms = (glass_fraction_2024 * rooms).sum()
            glass_fraction_building += glass_fraction_rooms * float(ratios[i])
        gains = irr / 1000 * g * 0.9 * glass_fraction_building / 100 * A_facades
        # glass fraction on facades from SIA 2024, 0.9 SIA 2024: acknowledge perpendicular rays
        np_gains = np.append(np_gains, gains)

    return np_gains
