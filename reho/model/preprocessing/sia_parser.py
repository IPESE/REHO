import pandas as pd
import numpy as np

__doc__ = """
Collects data from the `SIA Swiss norms <https://www.sia.ch/fr/services/sia-norm/>`_ , which are used to distinguish between eight different building types in their usage and behavior.
"""


def read_sia2024_rooms_sia380_1(digit, df_SIA_380):
    """
    Room mix of a SIA 380/1 building category.

    Parameters
    ----------
    digit : str
        SIA 380/1 category, as a Roman numeral from ``'I'`` (collective housing) to ``'XIII'`` (other).
    df_SIA_380 : pandas.DataFrame
        Content of ``sia2024_rooms_sia380_1.csv``: one row per SIA 2024 room type, one column per
        SIA 380/1 category named in words (``'collective housing'``, ...).

    Returns
    -------
    pandas.Series
        Area share of each SIA 2024 room type in the category, NaN for the room types it does not contain.
    """
    dict_affiliation2digit = {'collective housing': 'I',
                              'individual housing': 'II',
                              'administrative': 'III',
                              'school': 'IV',
                              'commercial': 'V',
                              'restaurant': 'VI',
                              'gathering places': 'VII',
                              'hospital': 'VIII',
                              'industry': 'IX',
                              'shed, warehouse': 'X',
                              'sports facilities': 'XI',
                              'covered swimming-pool': 'XII',
                              'other': 'XIII'}

    df_SIA_380 = df_SIA_380.rename(columns=dict_affiliation2digit)

    return df_SIA_380[digit]


def read_sia_2024_profiles(status, df):
    """
    Daily profiles of every SIA 2024 room type, for a given energy standard.

    Each profile has one row per room type and one column per hour of the day. The appliance
    profiles are normalized by their peak, then scaled to the installed power of the chosen standard.

    Parameters
    ----------
    status : str
        Energy standard, which sets the power of the appliances: ``'existing'`` (high),
        ``'standard'`` (medium), ``'aim'`` or ``'target'`` (low).
    df : dict of pandas.DataFrame
        Sheets of ``sia2024_data.xlsx``; ``calculs`` (hourly profiles) and ``data`` (installed
        powers) are used.

    Returns
    -------
    df_el_add : pandas.DataFrame
        Additional lighting, e.g. of showrooms [W/m2].
    df_el_light : pandas.DataFrame
        Lighting [W/m2].
    df_el_appliance : pandas.DataFrame
        Electrical appliances [W/m2].
    df_dhw : pandas.DataFrame
        Useful domestic hot water [l/m2].
    df_occupancy : pandas.DataFrame
        Utilization rate [-].
    df_heat_gain : pandas.DataFrame
        Heat gains from people [W/m2].

    Raises
    ------
    ValueError
        If ``status`` is not one of the values above.
    """
    df_el_appliance = df["calculs"].iloc[:, 1:25]
    df_el_ap_norm = df_el_appliance.div(df_el_appliance.max(axis=1), axis=0)  # normalize profile
    df_el_ap_norm = df_el_ap_norm.fillna(0)

    # status allows to scale the domestic electricity consumption
    if status == 'existing':  # high electricity consumption
        df_existing = df["data"].iloc[:, 38]
        df_el_appliance = df_el_ap_norm.mul(df_existing.values, axis=0)
    elif status == 'standard':  # medium electricity consumption
        df_standard = df["data"].iloc[:, 36]
        df_el_appliance = df_el_ap_norm.mul(df_standard, axis=0)
    elif (status == 'aim') or (status == 'target'):  # low electricity consumption
        df_aim = df["data"].iloc[:, 37]
        df_el_appliance = df_el_ap_norm.mul(df_aim, axis=0)
    else:
        raise ValueError(
            f"Unknown building status {status!r}. Expected one of 'existing', 'standard', 'aim' or 'target'."
        )

    df_el_light = df["calculs"].iloc[:, 26:50]
    df_el_light.columns = df_el_appliance.columns  # columns 1-24 - hours of the day

    df_el_add = df["calculs"].iloc[:, 52:76]  # additional light profile f.e. for "showrooms"
    df_el_add.columns = df_el_appliance.columns  # columns 1-24 - hours of the day

    df_heat_gain = df["calculs"].iloc[:, 102:126]  # heatgain by people
    df_heat_gain.columns = df_el_appliance.columns  # columns 1-24 - hours of the day

    df_dhw = df["calculs"].iloc[:, 127:151]
    df_dhw.columns = df_el_appliance.columns  # columns 1-24 - hours of the day

    df_occupancy = df["calculs"].iloc[:, 208:232]
    df_occupancy.columns = df_el_appliance.columns  # columns 1-24 - hours of the day

    return df_el_add, df_el_light, df_el_appliance, df_dhw, df_occupancy, df_heat_gain


def daily_profiles_with_monthly_deviation(status, rooms, date, df):
    """
    Returns daily profiles for electricity demand, DHW demand, occupancy, electricity heat gains, and heat gains from people.
    The profiles are based on the SIA norms and vary according to the building specifications (rooms, renovation status) and the date (weekday, month).
    """
    # get monthly deviation
    df_months = df['profiles'].iloc[:, 49:61]

    # rename to match python timestamp
    dict_months = {'Janvier': 1, 'Fevrier': 2, 'Mars': 3, 'Avril': 4, 'Mai': 5, 'Juin': 6,
                   'Juillet': 7, 'Aout': 8, 'Septembre': 9, 'Octobre': 10, 'Novembre': 11, 'Decembre': 12}
    df_months = df_months.rename(columns=dict_months)

    monthly_factor = df_months[date.month]

    # get weekly deviation
    df_free = df['profiles'].iloc[:, 61]  # 0 no days unused, 2 = weekend unused, 1 = Sundays unused

    weekly_factor = np.repeat(1, len(rooms))
    if date.weekday() == 6:  # 6 = Sunday
        weekly_factor[(df_free == 1) | (df_free == 2)] = 0  # rooms which are not used on a Sunday
    if date.weekday() == 5:  # 5 = Saturday
        weekly_factor[df_free == 2] = 0  # rooms which are not used on a Saturday

    # get 2024 profiles
    df_el_add, df_el_light, df_el_appliance, df_dhw, df_occupancy, df_heat_gain = read_sia_2024_profiles(status, df)
    df_el = df_el_appliance + df_el_light + df_el_add  # W/m2
    df_el_gain = df_el_appliance + df_el_light
    # adjust for current day of the year
    df_el = df_el.multiply(weekly_factor * monthly_factor, axis=0)
    df_el_gain = df_el_gain.multiply(weekly_factor * monthly_factor, axis=0)
    df_dhw = df_dhw.multiply(weekly_factor * monthly_factor, axis=0)
    df_occupancy = df_occupancy.multiply(weekly_factor * monthly_factor, axis=0)
    df_heat_gain = df_heat_gain.multiply(weekly_factor * monthly_factor, axis=0)

    # get profiles for each room. multiply by usage. nan if not appearing in building
    df_el = df_el.multiply(rooms.values, axis=0).dropna()
    df_el_gain = df_el_gain.multiply(rooms.values, axis=0).dropna()
    df_dhw = df_dhw.multiply(rooms.values, axis=0).dropna()
    df_occupancy = df_occupancy.multiply(rooms.values, axis=0).dropna()
    df_heat_gain = df_heat_gain.multiply(rooms.values, axis=0).dropna()

    # aggregate
    conv_heat_factor = 0.70
    df_profiles = pd.DataFrame()
    df_profiles['electricity_W/m2'] = df_el.sum(axis=0)
    df_profiles['hotwater_l/m2'] = df_dhw.sum(axis=0)
    df_profiles['occupancy'] = df_occupancy.sum(axis=0)
    df_profiles['elecgain_W/m2'] = df_el_gain.sum(axis=0) * conv_heat_factor
    df_profiles['heatgainpeople_W/m2'] = df_heat_gain.sum(axis=0)

    return df_profiles
