import os

from reho.paths import path_to_clustering, path_to_emissions
import pandas as pd
import numpy as np
import datetime

__doc__ = """
Characterizes the CO2 emissions related to electricity generated from the grid.
"""


def find_average_value(country, metric):
    """
    Annual average of an hourly indicator of a country's electricity mix.

    The hourly values come from the 2019 electricity matrix shipped with REHO
    (``electricity_matrix_2019_reduced.csv``).

    Parameters
    ----------
    country : str
        Country of the electricity mix: ``'CH'``, ``'DE'``, ``'FR'`` or ``'PL'``.
    metric : str
        Indicator: ``'GWP100a'`` or ``'GWP20a'`` (global warming potential), ``'method 1'`` or
        ``'method 2'`` (renewable share), or ``'total'`` (ecological footprint and ecological scarcity).

    Returns
    -------
    pandas.Series
        Average of the 8760 hourly values, indexed by indicator family (e.g. ``'RE share'``).
        Global warming potentials are converted from g to kg CO2-eq/kWh.
    """

    emissions_matrix = pd.read_csv(path_to_emissions, index_col=[0, 1, 2])

    # sort city to country
    emissions_matrix.columns = np.arange(1, 8761)
    emissions_matrix = emissions_matrix.xs((country, metric), level=(0, 2))

    average = emissions_matrix.mean(axis=1)
    if (metric == 'GWP100a') or (metric == 'GWP20a'):
        average = average / 1000  # g/kWh to kg/kWh

    return average


def return_typical_emission_profiles(local_data, metric, df_time):
    """
    Hourly profile of an electricity-mix indicator on the typical periods, for Switzerland.

    The profile is cached as ``<metric>.csv`` in the clustering directory of the location
    (``data/clustering/<File_ID>/``), and built by :func:`annual_to_typical_emissions` when that
    file does not exist yet.

    Parameters
    ----------
    local_data : dict
        Location data returned by :func:`~reho.model.preprocessing.local_data.return_local_data`;
        ``File_ID`` and ``Cluster`` are used.
    metric : str
        Indicator, see :func:`find_average_value`.
    df_time : pandas.DataFrame
        Date of each typical period, i.e. ``local_data['df_Timestamp']``.

    Returns
    -------
    pandas.DataFrame
        Indicator values in column ``GWP_supply``, indexed by ``('Electricity', Period, Time)``.
    """
    country = 'CH'

    clustering_directory = os.path.join(path_to_clustering, local_data['File_ID'])
    emission_file = os.path.join(clustering_directory, metric + '.csv')

    if os.path.exists(emission_file):
        df_E = pd.read_csv(emission_file, index_col=[0, 1, 2])
    else:
        df_E = annual_to_typical_emissions(local_data["Cluster"], country, metric, df_time)
        df_E.to_csv(emission_file)

    return df_E


def annual_to_typical_emissions(cluster, country, metric, df_time):
    """
    Extract the hourly values of an electricity-mix indicator for each typical period.

    Each typical period takes the values of the hours of the year it was selected from.

    Parameters
    ----------
    cluster : dict or pandas.DataFrame
        Clustering options with ``Periods`` and ``PeriodDuration``, the two extreme periods lasting
        one hour each; or directly the duration of each period, in a column ``TimeEnd`` indexed from 1.
    country : str
        Country of the electricity mix, see :func:`find_average_value`.
    metric : str
        Indicator, see :func:`find_average_value`.
    df_time : pandas.DataFrame
        Date of each period in a column ``Date``, one row per period in order,
        i.e. ``local_data['df_Timestamp']``.

    Returns
    -------
    pandas.DataFrame
        Indicator values in column ``GWP_supply`` (whatever the metric), indexed by
        ``('Electricity', Period, Time)`` with periods and times counted from 1.
        Global warming potentials are converted from g to kg CO2-eq/kWh.

    Notes
    -----
    Hours are counted from 1 January 2005, so the dates of ``df_time`` are expected in 2005.
    """

    emissions_matrix = pd.read_csv(path_to_emissions, index_col=[0, 1, 2])

    # get relevant cluster information
    if isinstance(cluster, pd.DataFrame):
        PeriodDuration = cluster[["TimeEnd"]]
    else:
        PeriodDuration = pd.DataFrame(np.concatenate([np.repeat(cluster['PeriodDuration'], cluster['Periods']), [1, 1]]), columns=["TimeEnd"])
        PeriodDuration.index = PeriodDuration.index + 1
    emissions_matrix.columns = np.arange(1, 8761)

    # construct Multiindex
    df_p = pd.DataFrame()
    list_timesteps = []

    for p in df_time.index:
        start = datetime.datetime(2005, 1, 1)  # TODO should be corrected: years range from 2005 to 2020
        date = df_time.xs(p).Date
        difference = date - start
        dif_h = int(difference.total_seconds() / 3600)

        end = PeriodDuration.xs(p + 1).TimeEnd  # ampl starts at 1
        start = dif_h + 1
        ende = dif_h + end
        df_emission_p = emissions_matrix.xs((country, metric), level=(0, 2))

        df_emission_p = df_emission_p.loc[:, start: ende]
        np_period = df_emission_p.values[0]
        if (metric == 'GWP100a') or (metric == 'GWP20a'):
            np_period = np_period / 1000  # g/kWh to kg/kWh

        df_period = pd.DataFrame(np_period)
        for t in np.arange(1, int(end) + 1):  # ampl starts at 1
            list_timesteps.append(('Electricity', p + 1, t))  # create ampl index

        df_p = pd.concat((df_p, df_period))

    idx = pd.MultiIndex.from_tuples(list_timesteps)

    # marry index and data
    df_E = df_p.set_index(idx)
    df_E = df_E.rename(columns={0: 'GWP_supply'})

    return df_E
