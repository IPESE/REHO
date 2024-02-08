import pandas as pd
from reho.paths import *
from datetime import timedelta
import numpy as np
import datetime


def read_typical_profiles(typical_file='typical_profiles.csv', File_ID='Geneva_10_24_T_I_W'):

    df_E = pd.read_csv(os.path.join(path_to_electricity, typical_file), index_col=[0])
    df_E = df_E/1000  # from  W to kW
    df_E.columns = df_E.columns.astype(int)  # change column name from string to int

    timestamp = os.path.join(path_to_clustering_results, 'timestamp_'+ File_ID +'.dat')
    df = pd.read_csv(timestamp, delimiter='\t', parse_dates=[0])

    # construct Multiindex
    df_p = pd.DataFrame()
    list_timesteps = []

    for p in df.index:
        start = datetime.datetime(2005, 1, 1)
        date = df.xs(p).Date
        difference = date - start
        dif_h = int(difference.total_seconds() / 3600)

        end = 24  # cluster["PeriodDuration"]
        print(p)
        df_period = df_E.loc[dif_h + 1: dif_h + end]

        for t in np.arange(1, int(end)+1): #ampl starts at 1
            list_timesteps.append((p +1, t)) #create ample index

        df_p = pd.concat([df_p, df_period])

    idx = pd.MultiIndex.from_tuples(list_timesteps)

    # marry index and data
    df_E = df_p.set_index(idx)

    # TODO Find better conditions for extreme conditions
    for egid in df_E.columns.values:
        df_E.loc[(df.index[-1]+2, 1), egid] = max(df_E[egid]) #+1 bc of ampl +1 to be the next period
        df_E.loc[(df.index[-1]+3, 1), egid] = max(df_E[egid])

    return df_E


if __name__ == '__main__':

    annual_file = 'annual_profiles.csv'
    typical_file = 'typical_profiles.csv'

    File_ID = 'Geneva_10_24_T_I_W'
    timestamp_file = os.path.join(path_to_clustering_results, 'timestamp_' + File_ID + '.dat')
    df_time = pd.read_csv(timestamp_file, delimiter='\t')

    typical_days = df_time.Date.values
    cluster = {'Location': 'Bruxelles', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24,
               'meteo_file': 'custom_meteo.dat'}
    annual_to_typical(cluster, annual_file, typical_file)
    read_typical_profiles(typical_file)