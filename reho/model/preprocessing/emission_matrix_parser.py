from reho.paths import *
import pandas as pd
import numpy as np
import datetime

def reduce_matrix_file():
    df = pd.read_csv(path_to_emissions_matrix_full,  header=None, index_col=[0, 1, 2, 3])

    df_time = df.xs(['datetime'], level=[2])
    df_time = pd.to_datetime(df_time.iloc[0])

    df_small = df.xs(['consumption'], level=[3])

    #df_small.columns = df_time.values
    df_small = df_small.astype(float)

    df_small.to_csv(path_to_emissions_matrix)

    return df_small

def find_average_value(country, value):
    # sort city to country
    df = pd.read_csv(path_to_emissions_matrix, index_col = [0,1,2])
    df.columns = np.arange(1, 8761)
    df = df.xs((country, value), level=(0,2))

    average = df.mean(axis = 1)
    if (value  == 'GWP100a') or (value == 'GWP20a'):
        average = average/1000 #g/kWh to kg/kWh
    return average

def interpolate(series):

    id = series[series.isnull()].index

    for i in id:
        # make sure that value before/after is not nan otherwise take value before
        first = i-1
        counter = 0
        while first  in id:
            first -= 1
            counter += 1
            if counter == 100:
                break

        second = i + 1
        counter = 0
        while second in id:
            second += 1
            counter += 1
            if counter ==100:
                break
        #average between 2 last existing data
        series.loc[i] = 0.5 * (series.loc[first] + series.loc[second])

    if series.isnull().any():
        raise('there are still nan values in data')

    return series


def interpolate_nan_values():
    df = pd.read_csv(path_to_emissions_matrix, index_col = [0,1,2])
    df.columns = np.arange(1, 8761)
    df.apply(lambda x: interpolate(x), axis = 1)

    df.to_csv(path_to_emissions_matrix)


def return_emission_df(cluster, File_ID, country, value):
    # get relevant cluster information
    thisfile = os.path.join(path_to_clustering_results, 'timestamp_' + File_ID + '.dat')
    df = pd.read_csv(thisfile, delimiter='\t', parse_dates=[0])
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
        df_emission_p = df_emission.xs((country, value), level=(0, 2))

        df_emission_p = df_emission_p.loc[:, start: ende]
        np_period = df_emission_p.values[0]
        # np_period =      return_emission_values(dict_loc[location], value,dif_h+1, dif_h + end).values[0]
        if (value == 'GWP100a') or (value == 'GWP20a'):
            np_period = np_period / 1000  # g/kWh to kg/kWh

        df_period = pd.DataFrame(np_period)
        for t in np.arange(1, int(end) + 1):  # ampl starts at 1
            list_timesteps.append(('Electricity', p + 1, t))  # create ample index

        df_p = pd.concat((df_p, df_period))

    idx = pd.MultiIndex.from_tuples(list_timesteps)
    # marry index and data
    df_E = df_p.set_index(idx)

    # add extreme conditions
    # TODO Find better conditions

    df_E.loc[('Electricity', df.index[-1] + 2, 1), 0] = 0  # +1 bc of ampl +1 to be the next period
    df_E.loc[('Electricity', df.index[-1] + 3, 1), 0] = 0
    df_E = df_E.rename(columns={0: 'GWP_supply'})

    return df_E


def select_typical_emission_profiles(cluster, File_ID, value):
    # sort city to country
    country = 'CH'
    emission_file = os.path.join(path_to_emissions, value + File_ID + '.dat')
    if os.path.exists(emission_file):
        df_E = pd.read_csv(emission_file, index_col=[0, 1, 2])
    else:
        df_E = return_emission_df(cluster, File_ID, country, value)
        df_E.to_csv(emission_file)

    df_E = df_E.rename(columns={df_E.columns[0]: 'GWP_supply'})
    return df_E

if __name__ == '__main__':

    df_small = reduce_matrix_file()
    #interpolate_nan_values()
    #data = return_emission_values('CH',value = 'GWP100a', start = 0, end = 300)

    #print(data)

    #av = find_average_value('Geneva', 'GWP100a')

    #print('average: ' + str(av) + ' kg/kWh')
