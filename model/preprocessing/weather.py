import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import calendar
import datetime as dt
from paths import *
from model.preprocessing.clustering import ClusterClass

def get_cluster_file_ID(cluster):
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

    if not os.path.exists(os.path.join(path_to_clustering_results, 'timestamp_' + File_ID + '.dat')):

        df = read_hourly_dat(cluster['Location'])
        df = df[attributes]

        cl = ClusterClass(data=df, Iter=[cluster['Periods']], option={"year-to-day": True, "extreme": []}, pd=cluster['PeriodDuration'])
        cl.run_clustering()

        generate_output_data(cl, attributes)
        write_dat_files(attributes, cluster['Location'])

    return File_ID


def read_hourly_dat(location):

    if location == 'Zurich':

        filename = os.path.join(path_to_weather, 'Zurich_data_cleaned.csv')

        if not os.path.exists(filename):
            df = pd.read_csv('zurich_2019.csv')
            df_loc= df[df['Standort'] == 'Zch_Stampfenbachstrasse']
            df_irr = df_loc[df_loc['Parameter'] == 'StrGlo']
            df_T = df_loc[df_loc['Parameter'] == 'T']

            df1 = pd.DataFrame([df_irr.Wert.values, df_T.Wert.values],  index=['Irr', 'Text'])
            df1 = df1.T
            df1[['Text', 'Irr']].to_csv('annual_weather.txt')
            df2 = pd.read_csv(os.path.join(path_to_weather, 'Weekday.txt'), index_col=[0], header=None)
            df1['Weekday'] = df2

            df_emission = pd.read_csv(path_to_emissions_matrix, index_col=[0, 1, 2])
            df_emission.columns = np.arange(1, 8761)
            df1['Emissions'] = df_emission.xs(['CH', 'IPCC 2013 climate change', 'GWP100a']).values
            df1.to_csv(filename)
        else:
            df1 = pd.read_csv(filename)
    else:
        df1 = np.loadtxt(os.path.join(path_to_weather, 'hour', location + '-hour.dat'), unpack=True, skiprows=1)
        df1 = pd.DataFrame(df1).transpose()
        df1 = df1.drop([5,6,7,8], axis=1)
        df1.columns = ['id', 'Month', 'Day', 'Hour', 'Irr', 'Text']
        df2 = pd.read_csv(os.path.join(path_to_weather, 'Weekday.txt'), index_col=[0], header=None)
        df1['Weekday'] = df2

    return df1


def generate_output_data(cl, attributes):
    # - saving

    data_idx = cl.results["idx"]
    # data_prf = cl.kpis_clu.stack("dimension")
    # data_prf.to_csv(os.path.join(root_dir, "database", "climates", self.filename, "clustering_kpi.csv"), index=True)

    # - construct : cluster data
    frame = []
    cl.nbr_opt = str(cl.nbr_opt)
    for id in data_idx.loc[:, cl.nbr_opt].unique():  # get unique typical periods from index vector
        id = int(id)
        df = pd.DataFrame(
            np.reshape(cl.attr_org[id - 1, :], (-1, int(cl.attr_org.shape[1] / len(attributes)))).transpose(),
            columns=attributes)  # put the attributes into columns of a df
        df["dt"] = sum(data_idx.loc[:, cl.nbr_opt] == id)  # Frequency
        df["time.hh"] = np.arange(1, df.shape[0] + 1, 1)  # timesteps in typical period
        df["time.dd"] = id  # typical period index
        frame.append(df.reindex(["time.dd", "time.hh"] + attributes + ["dt"], axis=1))

    data_cls = pd.concat(frame, axis=0)
    data_cls_mod = pd.DataFrame()
    if cl.modulo != 0:
        df_mod = pd.DataFrame.from_dict(dict(zip(cl.data_org.columns, cl.mod_org)))
        max_time_dd = len(cl.attr_org)
        df_mod['time.dd'] = np.repeat(max_time_dd + 1, cl.modulo)
        df_mod['dt'] = np.repeat(1, cl.modulo)
        df_mod['time.hh'] = np.arange(1, cl.modulo + 1)
        data_cls_mod = df_mod
    data_cls = data_cls.append(data_cls_mod, ignore_index=True)
    data_cls.to_csv(os.path.join(path_to_clustering_results, 'temp/values-cluster.csv'), index=False)
    # - construct : model data
    # - ** inter-period
    data_idy = pd.DataFrame(
        np.stack((np.arange(1, data_idx.loc[:, cl.nbr_opt].shape[0] + 1, 1), data_idx.loc[:, cl.nbr_opt].values),
                 axis=1), columns=["IndexYr", "inter_t"])
    if cl.modulo != 0:
        max_time_dd = len(cl.attr_org)
        data_idy = data_idy.append(pd.DataFrame([[max_time_dd + 1, max_time_dd + 1]], columns=data_idy.columns),
                                   ignore_index=True)
    data_idy.to_csv(os.path.join(path_to_clustering_results, 'temp/index-inter.csv'), index=False)
    # - ** intra-period
    data_idp = pd.DataFrame(
        np.stack((np.arange(1, data_cls.shape[0] + 1, 1), np.arange(1, data_cls.shape[0] + 1, 1)), axis=1),
        columns=["IndexDy", "intra_t"])
    data_idp["intra_end"] = [id + cl.pd if (id % cl.pd) == 0 else 0 for id in data_idp.index]
    data_idp.to_csv(os.path.join(path_to_clustering_results, 'temp/index-intra.csv'), index=False)
    # - ** costs-period
    # cols = pd.MultiIndex.from_product([["Cost_supply_cst_r", "Cost_demand_cst_r"], self.grids], names=["Layer", "param"])
    # rows = pd.MultiIndex.from_arrays([data_cls.loc[:, "time.dd"].values, data_cls.loc[:, "time.hh"].values],
    #                                 names=["day", "hour"])
    # data_cts = pd.DataFrame(np.tile([0.24, 0.12, 0.08, 0, 0.08, 0], (data_cls.shape[0], 1)), columns=cols, index=rows)
    # data_cts.to_csv(os.path.join(root_dir, "database", "climates", self.filename, "values-costs.csv"), index=True)


def write_dat_files(attributes, location):

    df = pd.read_csv(os.path.join(path_to_clustering_results, 'temp/values-cluster.csv'))

    df_dd = df['time.dd'].unique()  # id of typical period

    dp = np.array([])  # duration of period e.g. frequency
    pt = np.array([])  # period duration / number of timesteps in period

    for dd in df_dd:
        p = df.loc[df['time.dd'] == dd, 'dt'].unique()
        t = len(df.loc[df['time.dd'] == dd, 'dt'])

        dp = np.append(dp, p)
        pt = np.append(pt, t)

    # -------------------------------------------------------------------------------------
    # attributes for saving
    # -------------------------------------------------------------------------------------
    nop = len(df_dd)  # number of periods
    max_pt = int(max(pt))  # maximum period duration
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
        E ='_E'
    else:
        E = ''
    File_ID = location + '_' + str(nop) + '_' + str(max_pt)  + T  + I +  W  + E

    # -------------------------------------------------------------------------------------
    # T
    # -------------------------------------------------------------------------------------
    data = pd.Series([-5, 35])
    df_T = df['Text']
    df_T = df_T.append(data, ignore_index=True)

    filename = os.path.join(path_to_clustering_results, 'T_' + File_ID + '.dat')

    df_T.to_csv(filename, index=False, header=False)

    print(filename + ' generated and saved')

    # -------------------------------------------------------------------------------------
    # GHI
    # -------------------------------------------------------------------------------------
    df_GHI = df['Irr']
    data = pd.Series([0, df_GHI.max()])
    df_GHI = df_GHI.append(data, ignore_index=True)

    filename = os.path.join(path_to_clustering_results, 'GHI_' + File_ID + '.dat')
    df_GHI.to_csv(filename, index=False, header=False)
    print(filename + ' generated and saved')

    # -------------------------------------------------------------------------------------
    # frequency
    # -------------------------------------------------------------------------------------
    df_time = pd.DataFrame()
    df_time['originalday'] = df_dd
    df_time['frequency'] = dp
    df_time['timesteps'] = pt

    if 'Weekday' in attributes:
        Weekday = np.array([])
        for dd in df_dd:
            w = df.loc[df['time.dd'] == dd, 'Weekday'].unique()
            Weekday = np.append(Weekday, w)

    filename = os.path.join(path_to_clustering_results, 'frequency_' + File_ID + '.dat')

    IterationFile = open(filename, 'w')

    IterationFile.write('\nset Period := ')
    for p in range(1, len(dp) + 3):  # +1 bc ampl starts at 0, +2 for extreme periods
        IterationFile.write('\n' + str(p))
    IterationFile.write('\n;')
    IterationFile.write('\nset PeriodStandard := ')

    for p in range(1, len(dp) + 1):  # +1 bc ampl starts at 0
        IterationFile.write('\n' + str(p))
    IterationFile.write('\n;')

    IterationFile.write('\nparam: dp := ')

    for p, d in enumerate(dp):
        IterationFile.write('\n' + str(p + 1) + ' ' + str(d))

    IterationFile.write('\n' + str(len(dp) + 1) + ' ' + str(1))  # extreme periods
    IterationFile.write('\n' + str(len(dp) + 2) + ' ' + str(1))
    IterationFile.write('\n;')

    IterationFile.write('\nparam: TimeEnd := ')

    for p, d in enumerate(pt):
        IterationFile.write('\n' + str(p + 1) + ' ' + str(d))

    IterationFile.write('\n' + str(len(pt) + 1) + ' ' + str(1))  # extreme periods
    IterationFile.write('\n' + str(len(pt) + 2) + ' ' + str(1))
    IterationFile.write('\n;')

    IterationFile.close()
    print(filename + ' generated and saved')

    # -------------------------------------------------------------------------------------
    # index
    # -------------------------------------------------------------------------------------
    df = pd.read_csv(os.path.join(path_to_clustering_results, 'temp/index-inter.csv'))
    dict = {}
    for i, dd in enumerate(df_dd): dict[dd] = i + 1
    df['index_r'] = df.inter_t.map(dict)
    df_time['index_r'] = df['index_r'].unique()
    df_time = df_time.set_index('index_r', drop=True)

    df_aim = pd.DataFrame()

    for d in df['index_r']:
        nt = int(df_time['timesteps'].xs(d))  # number of timesteps

        df_d = pd.DataFrame([np.repeat(d, nt), np.array(range(1, (nt + 1)))])
        df_aim = df_aim.append(df_d.transpose(), ignore_index=True)

    df_aim.index = df_aim.index + 1

    filename = os.path.join(path_to_clustering_results, 'index_' + File_ID + '.dat')

    IterationFile = open(filename, 'w')
    IterationFile.write('param : PeriodOfYear TimeOfYear := \n')
    IterationFile.write(df_aim.to_string(header=False))

    IterationFile.write('\n;')

    print(filename + ' generated and saved')
    IterationFile.close()

    # -------------------------------------------------------------------------------------
    # Time stamp
    # -------------------------------------------------------------------------------------
    filename = os.path.join(path_to_clustering_results, 'timestamp_' + File_ID + '.dat')
    IterationFile = open(filename, 'w')
    header = 'Date\tDay\tFrequency\tWeekday\n'
    print(header)
    IterationFile.write(header)
    for key in dict:
        pt = df_time.iloc[0].timesteps  # take the same period duration also for modulo
        date = dt.datetime(2005, 1, 1) + dt.timedelta(hours=float((key - 1) * pt))

        if 'Weekday' in attributes:
            text = date.strftime("%m/%d/%Y/%H") + '\t' + str(key) + '\t' + str(dp[dict[key] - 1]) + '\t' + str(
                Weekday[dict[key] - 1])
        else:
            text = date.strftime("%m/%d/%Y/%H") + '\t' + str(key) + '\t' + str(dp[dict[key] - 1])
        IterationFile.write(text + '\n')
        print(text)
    print(filename + ' generated and saved')
    IterationFile.close()


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
        format = 'pdf'
        plt.savefig(('Cluster_KPIs' + '.' + format), format=format, dpi=300)
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
        format = 'pdf'
        plt.savefig(('MAE_KPIs' + '.' + format), format=format, dpi=300)
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
        format = 'pdf'
        plt.savefig(('MAPE_KPIs' + '.' + format), format=format, dpi=300)
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
