from reho.paths import *
import pandas as pd
import numpy as np
import datetime

__doc__ = """
*Characterizes the CO2 emissions related to electricity generated from the grid.*
"""

def find_average_value(country, metric):
    # sort city to country
    df = pd.read_csv(path_to_emissions_matrix, index_col = [0,1,2])
    df.columns = np.arange(1, 8761)
    df = df.xs((country, metric), level=(0,2))

    average = df.mean(axis = 1)
    if (metric  == 'GWP100a') or (metric == 'GWP20a'):
        average = average/1000 #g/kWh to kg/kWh
    return average


def annual_to_typical_emissions(cluster, File_ID, country, metric):

    # get relevant cluster information
    filename = os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat')
    df = pd.read_csv(filename, delimiter='\t', parse_dates=[0])
    if isinstance(cluster, pd.DataFrame):
        PeriodDuration = cluster[["TimeEnd"]]
    else:
        PeriodDuration = pd.DataFrame(np.concatenate([np.repeat(cluster['PeriodDuration'], cluster['Periods']), [1, 1]]), columns=["TimeEnd"])
        PeriodDuration.index = PeriodDuration.index + 1
    df_emission = pd.read_csv(path_to_emissions_matrix, index_col=[0, 1, 2])
    df_emission.columns = np.arange(1, 8761)

    # construct Multiindex
    df_p = pd.DataFrame()
    list_timesteps = []

    for p in df.index:
        start = datetime.datetime(2005, 1, 1)
        date = df.xs(p).Date
        difference = date - start
        dif_h = int(difference.total_seconds() / 3600)

        end = PeriodDuration.xs(p + 1).TimeEnd  # ampl starts at 1

        start = dif_h + 1
        ende = dif_h + end
        df_emission_p = df_emission.xs((country, metric), level=(0, 2))

        df_emission_p = df_emission_p.loc[:, start: ende]
        np_period = df_emission_p.values[0]
        # np_period =      return_emission_values(dict_loc[location], metric,dif_h+1, dif_h + end).values[0]
        if (metric == 'GWP100a') or (metric == 'GWP20a'):
            np_period = np_period / 1000  # g/kWh to kg/kWh

        df_period = pd.DataFrame(np_period)
        for t in np.arange(1, int(end) + 1):  # ampl starts at 1
            list_timesteps.append(('Electricity', p + 1, t))  # create ample index

        df_p = pd.concat((df_p, df_period))

    idx = pd.MultiIndex.from_tuples(list_timesteps)
    # marry index and data
    df_E = df_p.set_index(idx)

    df_E = df_E.rename(columns={0: 'GWP_supply'})

    return df_E


def return_typical_emission_profiles(cluster, File_ID, metric):

    country = 'CH'
    emission_file = os.path.join(path_to_clustering, metric + '_' + File_ID + '.dat')

    if os.path.exists(emission_file):
        df_E = pd.read_csv(emission_file, index_col=[0, 1, 2])
    else:
        df_E = annual_to_typical_emissions(cluster, File_ID, country, metric)
        df_E.to_csv(emission_file)

    return df_E

