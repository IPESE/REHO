from reho.paths import *
import pandas as pd
import numpy as np
import datetime

__doc__ = """
Characterizes the CO2 emissions related to electricity generated from the grid.
"""

def find_average_value(country, metric, emissions_matrix):
    # sort city to country
    emissions_matrix.columns = np.arange(1, 8761)
    emissions_matrix = emissions_matrix.xs((country, metric), level=(0,2))

    average = emissions_matrix.mean(axis = 1)
    if (metric == 'GWP100a') or (metric == 'GWP20a'):
        average = average/1000 #g/kWh to kg/kWh
    return average


def annual_to_typical_emissions(cluster, country, metric, df_time, df_emission):
    # get relevant cluster information
    if isinstance(cluster, pd.DataFrame):
        PeriodDuration = cluster[["TimeEnd"]]
    else:
        PeriodDuration = pd.DataFrame(np.concatenate([np.repeat(cluster['PeriodDuration'], cluster['Periods']), [1, 1]]), columns=["TimeEnd"])
        PeriodDuration.index = PeriodDuration.index + 1
    df_emission.columns = np.arange(1, 8761)

    # construct Multiindex
    df_p = pd.DataFrame()
    list_timesteps = []

    for p in df_time.index:
        start = datetime.datetime(2005, 1, 1)
        date = df_time.xs(p).Date
        difference = date - start
        dif_h = int(difference.total_seconds() / 3600)

        end = PeriodDuration.xs(p + 1).TimeEnd  # ampl starts at 1
        start = dif_h + 1
        ende = dif_h + end
        df_emission_p = df_emission.xs((country, metric), level=(0, 2))

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


def return_typical_emission_profiles(cluster, File_ID, metric, timestamp_file, emissions_matrix):

    country = 'CH'
    emission_file = os.path.join(path_to_clustering, metric + '_' + File_ID + '.dat')

    if os.path.exists(emission_file):
        df_E = pd.read_csv(emission_file, index_col=[0, 1, 2])
    else:
        df_E = annual_to_typical_emissions(cluster, country, metric, timestamp_file, emissions_matrix)
        df_E.to_csv(emission_file)

    return df_E

