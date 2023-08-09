import pandas as pd
from paths import *
from datetime import timedelta
import numpy as np
import datetime
import model.preprocessing.weather as weather_cluster


def Spotload15_to_egid60():

    profile_file = 'data/electricityProfiles.csv'
    table_file = 'data/electricityTable.csv'

    path_to_electricity_profiles_file = os.path.join(path_to_electricity_profiles,profile_file)
    path_to_E_table_file = os.path.join(path_to_electricity_profiles, table_file)

    print('Read files...')

    loadTable = pd.read_csv(path_to_E_table_file, sep=',')
    loadTable = loadTable[loadTable.status != 40] #exclude load for heat
    pvar = pd.read_csv(path_to_electricity_profiles_file, sep=',', parse_dates=[0])

    print(loadTable.head(5))
    print(pvar.head(5))

    # Hourly aggregation
    print('Hourly aggregation...')
    times = pd.DatetimeIndex(pvar.timestep)
    pvar['year'] = times.year
    pvar['month'] = times.month
    pvar['day'] = times.day
    pvar['hour'] = times.hour+1
    pvar.drop(columns=['timestep'])
    pvar_h = pvar.groupby(by=['year', 'month', 'day', 'hour'], as_index=False).mean() # dont sum its in W not Wh
    pvar_h.index += 1
    pvar_h.index.name = 'h'
    #pvar_h.to_csv('electricityProfiles_annual.csv', index=True, sep=',')

    # Building (egid) aggregation
    egid = pd.unique(loadTable.egid)
    print ('Number of buildigs', len(egid))
    pvar_h_egid = pd.DataFrame(columns=egid)

    print('Building (egid) aggregation...')
    for e in egid:
        load_name = loadTable.loc[loadTable['egid'] == e].load_name.values
        pvar_h_egid[e] = pvar_h[load_name].sum(axis=1)
    filename= 'data/electricityProfiles_annual_egid.csv'
    file_path = os.path.join(path_to_electricity_profiles, filename)
    pvar_h_egid.to_csv(file_path, index=True, sep=',')

    return pvar_h_egid

def annual_2_typical(typical_days_string):

    annual_file = os.path.join (path_to_electricity_profiles, 'data/electricityProfiles_annual_egid.csv')

    df = pd.read_csv(annual_file, sep=',')
    t1 = pd.to_datetime('1/1/2005', dayfirst=True, infer_datetime_format=True)

    # hour 1 is between 0:00 - 1:00 and is indexed with starting hour so 0:00
    for h in df.index.values:
        df.loc[h, 'h'] = t1 + timedelta(hours=(int(h)-1))

    df = df.set_index('h')

    df_typical = pd.DataFrame()
    for i, td in enumerate(typical_days_string):
        df_typical = pd.concat([df_typical, df[td]],  sort = True)
        #df_typical.loc[td,'TypdayID'] = int(i)

    #save profiles in csv
    filename = 'typical_profiles.csv'
    file_path = os.path.join(path_to_electricity_profiles, filename)
    df_typical.to_csv(file_path)
    print('Typical profiles saved')

    return df_typical

def electricity_to_df(electricity_csv, cluster):
    df_E = pd.read_csv(electricity_csv, index_col=[0])
    #from  W to kW
    df_E = df_E/1000
    #change column name from string to int
    df_E.columns = df_E.columns.astype(int)

    # get relevant cluster information
    FileID = weather_cluster.get_cluster_file_ID(cluster)
    thisfile = os.path.join(path_to_clustering_results, 'timestamp_'+ FileID +'.dat')
    df = pd.read_csv(thisfile, delimiter='\t', parse_dates=[0])

    # construct Multiindex
    df_p = pd.DataFrame()
    list_timesteps = []

    for p in df.index:
        start = datetime.datetime(2005, 1, 1)
        date = df.xs(p).Date
        difference = date - start
        dif_h = int(difference.total_seconds() / 3600)

        end = cluster["PeriodDuration"]

        df_period =       df_E.loc[dif_h + 1: dif_h + end]

        for t in np.arange(1, int(end)+1): #ampl starts at 1
            list_timesteps.append((p +1 , t)) #create ample index

        df_p = pd.concat([df_p, df_period])

    idx = pd.MultiIndex.from_tuples(list_timesteps)

    # marry index and data
    df_E =  df_p.set_index(idx)

    #add extreme conditions
    #TODO Find better conditions

    for egid in df_E.columns.values:
        df_E.loc[(df.index[-1]+2, 1), egid] = max(df_E[egid]) #+1 bc of ampl +1 to be the next period
        df_E.loc[(df.index[-1]+3, 1), egid] = max(df_E[egid])

    return df_E

def generate_aggregated_load_profile(file, egid):
    df_E = pd.read_csv(file, index_col=[0])
    df_E.columns = df_E.columns.astype(int)
    df_E[12345678] = df_E[egid].sum(axis = 1)

    #save profiles in csv
    filename = 'typical_profiles.csv'
    file_path = os.path.join(path_to_electricity_profiles, filename)
    df_E.to_csv(file_path)
    print('Typical profiles saved')

if __name__ == '__main__':


    thisfile = os.path.join(path_to_clustering_results,'timestamp.dat')
    df = pd.read_csv(thisfile, delimiter='\t')

    typical_days_string = df.Date.values
    electricity_csv = os.path.join(path_to_electricity_profiles, 'typical_profiles.csv')
    egid_array = [3104398, 280091601, 829062, 829080, 829694, 829691,
           829050, 829048, 829051, 829044, 3104571, 280082734,
           829713, 829043, 829082, 829049, 829692,
           829057, 829053, 829067, 829052, 280065226, 829058,
           829081, 829040, 829695, 829056, 829696, 829698,
           829055, 829063, 829066, 3104580, 829045, 829047,
           829046, 829054]

    df = Spotload15_to_egid60()
    df_annual = df.sum() / 1000000
    print (df_annual)

    #annual_2_typical(typical_days_string)
    #electricity_to_df(electricity_csv)
    #generate_aggregated_load_profile(electricity_csv, egid_array)