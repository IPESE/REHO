import pandas as pd
from reho.paths import *
from datetime import timedelta
import numpy as np
import datetime

def annual_to_typical(typical_days, annual_file='annual_profiles.csv', typical_file='typical_profiles.csv'):

    df_annual = pd.read_csv(os.path.join(path_to_electricity, annual_file), sep=',')
    t1 = pd.to_datetime('1/1/2005', dayfirst=True, infer_datetime_format=True)

    # hour 1 is between 0:00 - 1:00 and is indexed with starting hour so 0:00
    for h in df_annual.index.values:
        df_annual.loc[h, 'h'] = t1 + timedelta(hours=(int(h)-1))

    df_annual = df_annual.set_index('h')

    df_typical = pd.DataFrame()
    for i, td in enumerate(typical_days):
        df_typical = pd.concat([df_typical, df_annual[td]],  sort = True)
        #df_typical.loc[td,'TypdayID'] = int(i)

    df_typical.to_csv(os.path.join(path_to_electricity, typical_file))

    return


def read_typical_profiles(typical_file='typical_profiles.csv', File_ID='Geneva_10_24_T_I'):

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
            list_timesteps.append((p +1 , t)) #create ample index

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

    File_ID = 'Geneva_10_24_T_I'
    timestamp_file = os.path.join(path_to_clustering_results, 'timestamp_' + File_ID + '.dat')
    df_time = pd.read_csv(timestamp_file, delimiter='\t')

    typical_days = df_time.Date.values

    #annual_to_typical(typical_days, annual_file, typical_file)
    read_typical_profiles(typical_file)