import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import calendar
import datetime as dt
from reho.paths import *
from reho.model.preprocessing.clustering import ClusterClass


def get_cluster_file_ID(cluster):
    """
    Gets the weather file ID that corresponds to what was given in the reho initalization:
    ``cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}``

    Looks at data/weather/clustering results.
    If that file does not exist yet, run the ClusterClass to create the required file.

    Parameters
    ----------
    cluster : dict
        Dictionary that contains a 'Location' (str), some 'Attributes' (list, among 'I', 'T', 'W'), a number of periods
        'Periods' (int) and a 'PeriodDuration' (int)

    Returns
    -------
    A string that is the file ID

    Notes
    -----
    - The file ID is built by concatenating Location_Periods_PeriodDuration_Attributes.
    - The weather file is search using the Location
    - If one wants to use his own meteo file, he can add to the cluster dictionary a key ``weather_file`` with the path
      to the meteo. Should be a *.dat* with the same structure as the other weather_file.
    """
    # get correct file ID for weather file
    attributes = []

    if 'I' in cluster['Attributes']:
        I = '_I'
        attributes.append('Irr')
    else:
        I = ''
    if 'T' in cluster['Attributes']:
        T = '_T'
        attributes.append('Text')
    else:
        T = ''
    if 'W' in cluster['Attributes']:
        W = '_W'
        attributes.append('Weekday')
    else:
        W = ''
    if 'E' in cluster['Attributes']:
        E = '_E'
    else:
        E = ''

    File_ID = cluster['Location'] + '_' + str(cluster['Periods']) + '_' + str(cluster['PeriodDuration']) + \
              T + I + W + E

    among_cl_results = os.path.exists(os.path.join(path_to_clustering_results, 'timestamp_' + File_ID + '.dat'))
    if not among_cl_results or 'weather_file' in cluster.keys():
        if 'weather_file' in cluster.keys():
            df = read_hourly_dat(cluster['weather_file'])
        else:
            df = read_hourly_dat(cluster['Location'])
        df = df[attributes]
        cl = ClusterClass(data=df, Iter=[cluster['Periods']], option={"year-to-day": True, "extreme": []}, pd=cluster['PeriodDuration'])
        cl.run_clustering()

        generate_output_data(cl, attributes, cluster['Location'])

    return File_ID


def read_hourly_dat(location):

    if location.endswith('.dat'):
        df1 = np.loadtxt(path_handler(location), unpack=True, skiprows=1)
    else:
        df1 = np.loadtxt(os.path.join(path_to_weather, 'hour', location + '-hour.dat'), unpack=True, skiprows=1)
    df1 = pd.DataFrame(df1).transpose()
    df1 = df1.drop([5,6,7,8], axis=1)
    df1.columns = ['id', 'Month', 'Day', 'Hour', 'Irr', 'Text']
    df2 = pd.read_csv(os.path.join(path_to_weather, 'Weekday.txt'), index_col=[0], header=None)
    df1['Weekday'] = df2

    return df1


def generate_output_data(cl, attributes, location):
    """
    Generates the data for the cluster timesteps obtained from the ClusterClass.

    Calls for *write_dat_files* to generate the saves.

    Parameters
    ----------
    cl : ClusterClass
        A ClusterClass object where the run_clustering method has already been executed.
    attributes : list
        Contains string among 'Irr', 'Text', 'Weekday'.
    location : str
        Location of the corresponding weather data.

    See also
    --------
    reho.model.preprocessing.clustering.ClusterClass.run_clustering
    write_dat_files
    """
    
    data_idx = cl.results["idx"]
    # - construct : cluster data
    frame = []
    cl.nbr_opt = str(cl.nbr_opt)
    for idx in data_idx.loc[:, cl.nbr_opt].unique():  # get unique typical periods from index vector
        idx = int(idx)
        df = pd.DataFrame(
            np.reshape(cl.attr_org[idx - 1, :], (-1, int(cl.attr_org.shape[1] / len(attributes)))).transpose(),
            columns=attributes)  # put the attributes into columns of a df
        df["dt"] = sum(data_idx.loc[:, cl.nbr_opt] == idx)  # Frequency
        df["time.hh"] = np.arange(1, df.shape[0] + 1, 1)  # timesteps in typical period
        df["time.dd"] = idx  # typical period index
        frame.append(df.reindex(["time.dd", "time.hh"] + attributes + ["dt"], axis=1))

    data_cls = pd.concat(frame, axis=0)
    data_cls_mod = pd.DataFrame()
    if cl.modulo != 0:  # Not clear what is this
        df_mod = pd.DataFrame.from_dict(dict(zip(cl.data_org.columns, cl.mod_org)))
        max_time_dd = len(cl.attr_org)
        df_mod['time.dd'] = np.repeat(max_time_dd + 1, cl.modulo)
        df_mod['dt'] = np.repeat(1, cl.modulo)
        df_mod['time.hh'] = np.arange(1, cl.modulo + 1)
        data_cls_mod = df_mod
    data_cls = pd.concat([data_cls, data_cls_mod], ignore_index=True)

    # Determine the day of the max and min temperature
    T_idx = [cl.data_org[cl.data_org['Text'] == cl.data_org['Text'].min()].index[0],
             cl.data_org[cl.data_org['Text'] == cl.data_org['Text'].max()].index[0]]
    T_day = [math.floor(T_idx[0] / 24), math.floor(T_idx[1] / 24)]
    T_min = cl.data_org.iloc[[T_idx[0]]].copy()
    # Get the max/min irradiance from the same day
    T_max = cl.data_org.iloc[[T_idx[1]]].copy()
    T_max['Irr'] = cl.data_org.loc[T_day[1] * 24: T_day[1] * 24 + 24, 'Irr'].max()
    T_min.loc[:, ['time.dd', 'time.hh', 'dt']] = [T_day[0], 1, 1]
    T_max.loc[:, ['time.dd', 'time.hh', 'dt']] = [T_day[1], 1, 1]
    data_cls = pd.concat([data_cls, T_min.rename({T_idx[0]: 240}), T_max.rename({T_idx[1]: 241})])
    # Add a 10% margin for the extreme over 20 years TODO: question with Dorsan this factor
    data_cls.loc[[240, 241], ['Text', 'Irr']] = data_cls.loc[[240, 241], ['Text', 'Irr']] * 1.1
   
    # - construct : model data
    # - ** inter-period
    data_idy = pd.DataFrame(
        np.stack((np.arange(1, data_idx.loc[:, cl.nbr_opt].shape[0] + 1, 1), data_idx.loc[:, cl.nbr_opt].values),
                 axis=1), columns=["IndexYr", "inter_t"])
    if cl.modulo != 0:
        max_time_dd = len(cl.attr_org)
        data_idy = pd.concat([data_idy, pd.DataFrame([[max_time_dd + 1, max_time_dd + 1]], columns=data_idy.columns)],
                             ignore_index=True)

    # - ** intra-period
    data_idp = pd.DataFrame(
        np.stack((np.arange(1, data_cls.shape[0] + 1, 1), np.arange(1, data_cls.shape[0] + 1, 1)), axis=1),
        columns=["IndexDy", "intra_t"])
    data_idp["intra_end"] = [id + cl.pd if (id % cl.pd) == 0 else 0 for id in data_idp.index]
    
    # Call for the write dat function
    write_dat_files(attributes, location, data_cls, data_idy)
    
    return print(f'The data have been computed and saved at {path_to_clustering_results}.')


def write_dat_files(attributes, location, values_cluster, index_inter):
    """
    Writes the clustering results computed from `generate_output_data` as .dat file at data/weather/clustering_results/

    Parameters
    ----------
    attributes : list
        List that contains string among 'Irr', 'Text', 'Weekday'.
        If 'Irr' is in the list, writes a file named 'GHI' + '_File_ID.dat'
        If 'Text' is in the list, writes a file named 'T' + '_File_ID.dat'
    location : str
        Location of the corresponding weather data.
    values_cluster : pd.DataFrame
        Produced by the *generate_output_data* function.
    index_inter : pd.DataFrame
        Produced by the *generate_output_data* function.

    Notes
    -----
    - Not depending on the attributes, time depending files are generated, namely 'frequency' + '_File_ID.dat',
      'index' + '_File_ID.dat' and 'timestamp' + '_File_ID.dat'.

    """

    df_dd = values_cluster['time.dd'].unique()  # id of typical period

    dp = np.array([])  # duration of period e.g. frequency
    pt = np.array([])  # period duration / number of timesteps in period

    for dd in df_dd:
        p = values_cluster.loc[values_cluster['time.dd'] == dd, 'dt'].unique()
        t = len(values_cluster.loc[values_cluster['time.dd'] == dd, 'dt'])

        dp = np.append(dp, p)
        pt = np.append(pt, t)

    # -------------------------------------------------------------------------------------
    # attributes for saving
    # -------------------------------------------------------------------------------------
    if 'Text' in attributes:
        T = '_T'
    else:
        T = ''
    if 'Irr' in attributes:
        I = '_I'
    else:
        I = ''
    if 'Weekday' in attributes:
        W = '_W'
    else:
        W = ''
    if 'Emissions' in attributes:
        E = '_E'
    else:
        E = ''
    File_ID = location + '_' + str(len(df_dd) - 2) + '_' + str(int(max(pt))) + T + I + W + E

    # -------------------------------------------------------------------------------------
    # T
    # -------------------------------------------------------------------------------------
    df_T = values_cluster['Text']
    filename = os.path.join(path_to_clustering_results, 'T_' + File_ID + '.dat')
    df_T.to_csv(filename, index=False, header=False)

    # -------------------------------------------------------------------------------------
    # GHI
    # -------------------------------------------------------------------------------------
    df_GHI = values_cluster['Irr']
    filename = os.path.join(path_to_clustering_results, 'GHI_' + File_ID + '.dat')
    df_GHI.to_csv(filename, index=False, header=False)

    # -------------------------------------------------------------------------------------
    # frequency
    # -------------------------------------------------------------------------------------
    if 'Weekday' in attributes:
        Weekday = np.array([])
        for dd in df_dd:
            w = values_cluster.loc[values_cluster['time.dd'] == dd, 'Weekday'].unique()
            Weekday = np.append(Weekday, w)

    filename = os.path.join(path_to_clustering_results, 'frequency_' + File_ID + '.dat')

    IterationFile = open(filename, 'w')

    IterationFile.write('\nset Period := ')
    for p in range(1, len(dp) + 1):  # +1 bc ampl starts at 0, +2 for extreme periods
        IterationFile.write('\n' + str(p))
    IterationFile.write('\n;')

    IterationFile.write('\nset PeriodStandard := ')
    for p in range(1, len(dp) - 1):  # +1 bc ampl starts at 0, -2 to exclude extreme periods
        IterationFile.write('\n' + str(p))
    IterationFile.write('\n;')

    IterationFile.write('\nparam: dp := ')
    for p, d in enumerate(dp):
        IterationFile.write('\n' + str(p + 1) + ' ' + str(d))
    IterationFile.write('\n;')

    IterationFile.write('\nparam: TimeEnd := ')
    for p, d in enumerate(pt):
        IterationFile.write('\n' + str(p + 1) + ' ' + str(d))
    IterationFile.write('\n;')
    IterationFile.close()

    # -------------------------------------------------------------------------------------
    # index
    # -------------------------------------------------------------------------------------
    df_time = pd.DataFrame()
    df_time['originalday'] = df_dd
    df_time['frequency'] = dp
    df_time['timesteps'] = pt
    dict_index = {}
    for i, dd in enumerate(df_dd): dict_index[dd] = i + 1
    index_inter['index_r'] = index_inter.inter_t.map(dict_index)
    df_time.index = df_time.index + 1

    df_aim = pd.DataFrame()
    for d in index_inter['index_r']:
        nt = int(df_time['timesteps'].xs(d))  # number of timesteps
        df_d = pd.DataFrame([np.repeat(d, nt), np.array(range(1, (nt + 1)))])
        df_aim = pd.concat([df_aim, df_d.transpose()], ignore_index=True)

    df_aim.index = df_aim.index + 1

    filename = os.path.join(path_to_clustering_results, 'index_' + File_ID + '.dat')
    IterationFile = open(filename, 'w')
    IterationFile.write('param : PeriodOfYear TimeOfYear := \n')
    IterationFile.write(df_aim.to_string(header=False))
    IterationFile.write('\n;')
    IterationFile.close()

    # -------------------------------------------------------------------------------------
    # Time stamp
    # -------------------------------------------------------------------------------------
    filename = os.path.join(path_to_clustering_results, 'timestamp_' + File_ID + '.dat')
    IterationFile = open(filename, 'w')
    header = 'Date\tDay\tFrequency\tWeekday\n'
    IterationFile.write(header)
    for key in dict_index:
        pt = df_time.iloc[0].timesteps  # take the same period duration also for modulo
        date = dt.datetime(2005, 1, 1) + dt.timedelta(hours=float((key - 1) * pt))

        if 'Weekday' in attributes:
            text = date.strftime("%m/%d/%Y/%H") + '\t' + str(key) + '\t' + str(dp[dict_index[key] - 1]) + '\t' + str(
                Weekday[dict_index[key] - 1])
        else:
            text = date.strftime("%m/%d/%Y/%H") + '\t' + str(key) + '\t' + str(dp[dict_index[key] - 1])
        IterationFile.write(text + '\n')
    IterationFile.close()

    return


def plot_cluster_KPI_separate(df, save_fig):
    plt.rcParams.update({'font.size': 18})
    print(df)
    df = df.transpose()
    df.columns.names = ['KPI']
    df.rename({'Irr': 'Global Irradiation', 'Text': 'Ambient Temperature'}, inplace=True)
    df_irr = df.xs('Global Irradiation', level=1)
    df_T = df.xs('Ambient Temperature', level=1)

    fig, ax = plt.subplots()
    fig.set_size_inches(4, 8)
    df_irr['RMSD'].plot(linestyle='--', color='black', label='RMSD (GHI)', ax=ax)
    df_T['RMSD'].plot(linestyle='-', color='black', label='RMSD (T)', ax=ax)
    df_irr['LDC'].plot(linestyle='--', color="red", label='LDC (GHI)', ax=ax)
    df_T['LDC'].plot(linestyle='-', color="red", label='LDC (T)', ax=ax)

    plt.xlabel('number of clusters [-]')
    plt.ylabel('key performance indicator (KPI) [-]')
    # plt.title('KPI for $ \u2B27 $ =  Global Irradiation, $\u00D7$ = Ambient Temperature', size = 14)
    plt.legend(title="KPI")

    # plt.ylim([0,0.40])
    if save_fig:
        plt.tight_layout()
        export_format = 'pdf'
        plt.savefig(('Cluster_KPIs' + '.' + export_format), format=export_format, dpi=300)
    else:
        plt.show()

    fig, ax = plt.subplots()
    fig.set_size_inches(4, 8)
    df_irr['MAE'].plot(linestyle='--', color='black', label='MAE (GHI)', ax=ax)
    df_T['MAE'].plot(linestyle='-', color='black', label='MAE (T)', ax=ax)

    plt.xlabel('number of clusters [-]')
    plt.ylabel('mean average error (MAE)  [-]')
    # plt.title('KPI for $ \u2B27 $ =  Global Irradiation, $\u00D7$ = Ambient Temperature', size = 14)
    plt.legend(title="KPI")
    # plt.ylim([0,0.40])
    if save_fig:
        plt.tight_layout()
        export_format = 'pdf'
        plt.savefig(('MAE_KPIs' + '.' + export_format), format=export_format, dpi=300)
    else:
        plt.show()

    fig, ax = plt.subplots()
    fig.set_size_inches(4, 8)
    df_irr['MAPE'].plot(linestyle='--', color='black', label='MAPE  (GHI)', ax=ax)
    df_T['MAPE'].plot(linestyle='-', color='black', label='MAPE  (T)', ax=ax)

    plt.xlabel('number of clusters [-]')
    plt.ylabel('mean average percentage error  [-]')
    # plt.title('KPI for $ \u2B27 $ =  Global Irradiation, $\u00D7$ = Ambient Temperature', size = 14)
    plt.legend(title="KPI")
    # plt.ylim([0,0.40])
    if save_fig:
        plt.tight_layout()
        export_format = 'pdf'
        plt.savefig(('MAPE_KPIs' + '.' + export_format), format=export_format, dpi=300)
    else:
        plt.show()


def plot_LDC(cl, location, save_fig):
    nbr_plot = cl.nbr_opt
    print('plotting for number of typical days: ', nbr_plot)

    # get original, not clustered data
    T_org = cl.data_org['Text']
    IRR_org = cl.data_org['Irr']
   # E_org= cl.data_org['Emissions']

    # get clustered data and undo normalization
    df_clu = cl.attr_clu.xs(str(nbr_plot), axis=1)
    T_clu = df_clu['Text'] * (T_org.max() - T_org.min()) + T_org.min()
    IRR_clu = df_clu['Irr'] * (IRR_org.max() - IRR_org.min()) + IRR_org.min()
  #  E_clu= df_clu['Emissions']* (E_org.max() - E_org.min()) + E_org.min()


    # get assigned typical period
    res = cl.results['idx'][str(nbr_plot)]
    # instead of typical period (f.e. day 340) get index (1)
    for i, d in enumerate(res.unique()): res = np.where(res == d, i + 1, res)
    # get array of 8760 -modulo timesteps
    res = np.repeat(res, cl.pd)

    # add modulo
    modulo = cl.data_org.shape[0] % cl.pd
    res = np.append(res, np.repeat(int(nbr_plot) + 1, modulo))  # add modulo as extra period

    # ----------------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------------

    fig, ax = plt.subplots(2, 1, sharex=True, figsize=(10, 8))


    ax[0].plot(T_org, color='grey', alpha=0.5)
    sc = ax[0].scatter(T_clu.index, T_clu.values, s=10, c=res, cmap=cm)
    ax[1].plot(IRR_org, color='grey', alpha=0.5)
    ax[1].scatter(IRR_clu.index, IRR_clu.values, s=10, c=res, cmap=cm)
    #ax[2].plot(E_org, color='grey', alpha=0.5)
    #ax[2].scatter(E_clu.index, E_clu.values, s=10, c=res, cmap=cm)


    # set months instead of timestep as xticks
    plt.xticks(np.arange(8760, step=730), calendar.month_name[1:13], rotation=20)

    ax[0].set_ylabel('temperature [C]')
    ax[1].set_ylabel('global irradiation [W/m$^2$]')
  #  ax[2].set_ylabel('global warming potential [gCO2/kWh]')
    # plt.subplots_adjust(bottom=0.1, right=0.8, top=0.9)

    legend1 = ax[0].legend(*sc.legend_elements(),
                           loc='upper right', bbox_to_anchor=(1.0, 1.0), title="Period", ncol=2)
    ax[0].add_artist(legend1)

    if save_fig:
        plt.tight_layout()
        format = 'pdf'
        plt.savefig(('Year_Cluster' + '.' + format), format=format, dpi=300)
    else:
        plt.show()

    df_T = pd.DataFrame(T_clu)
    df_T['Period'] = res
    df_T = df_T.sort_values(by=['Text'], ignore_index=True, ascending=False)

    df_Irr = pd.DataFrame(IRR_clu)
    df_Irr['Period'] = res
    df_Irr = df_Irr.sort_values(by=['Irr'], ignore_index=True, ascending=False)

   # df_E = pd.DataFrame(E_clu)
   # df_E['Period'] = res
   # df_E = df_E.sort_values(by=['Emissions'], ignore_index=True, ascending=False)

    T_sort = T_org.sort_values(ascending=False, ignore_index=True)
    IRR_sort = IRR_org.sort_values(ascending=False, ignore_index=True)
  #  E_sort =  E_org.sort_values(ascending=False, ignore_index=True)


    fig, ax = plt.subplots(2, 1, sharex=True, figsize=(10, 8))
    ax[0].scatter(T_sort.index, T_sort.values, color='grey', alpha=0.5)
    ax[0].scatter(df_T.index, df_T['Text'], c=df_T['Period'], cmap=cm, s=20)

    ax[1].scatter(IRR_sort.index, IRR_sort.values, color='grey', alpha=0.5)
    ax[1].scatter(df_Irr.index, df_Irr['Irr'], c=df_Irr['Period'], cmap=cm, s=20)

  #  ax[2].scatter(E_sort.index, E_sort.values, color='grey', alpha=0.5)
   # ax[2].scatter(df_E.index, df_E['Emissions'], c=df_Irr['Period'], cmap=cm, s=20)

    ax[0].set_ylabel('temperature [C]')
    ax[1].set_ylabel('global irradiation [W/m$^2$]')
   # ax[2].set_ylabel('global warming potential [gCO2/kWh]')

    plt.xlabel('Hours [h]')

    legend1 = ax[0].legend(*sc.legend_elements(),
                           loc='upper right', bbox_to_anchor=(1.0, 1.0), title="Period", ncol=2)
    ax[0].add_artist(legend1)

    if save_fig:
        plt.tight_layout()
        format = 'pdf'
        plt.savefig(('LDC' + '.' + format), format=format, dpi=300)
    else:
        plt.show()

if __name__ == '__main__':
    cm = plt.cm.get_cmap('Spectral_r')

    # Location = ['Bern-Liebefeld', 'Geneve-Cointrin', 'La_Chaux-de-Fonds', 'Moleson', 'Zermatt', 'Zuerich-SMA'][4]
    Location = 'Pully'
    Attributes = ['Text', 'Irr']
    Iter = [10]

    df = read_hourly_dat(Location)
    df = df[Attributes]

    cl = ClusterClass(data=df, Iter=Iter, option={"year-to-day": True, "extreme": []}, pd=24)
    cl.run_clustering()

    plot_cluster_KPI_separate(cl.kpis_clu, save_fig=False)
    plot_LDC(cl, Location, save_fig=False)
    generate_output_data(cl, Attributes)
    write_dat_files(Attributes, Location)
