import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import calendar
import datetime as dt
from reho.paths import *
from reho.model.preprocessing.clustering import Clustering
import pvlib
from pyproj import Transformer

__doc__ = """
Generates the meteorological data (temperature and solar irradiance).
"""


def get_weather_data(qbuildings_data, export_filename=None):
    """
    Using the pvlib library, connects to the PVGIS dabatase to extract the weather data based on the building's coordinates.
    """
    lat, long = Transformer.from_crs("EPSG:2056", "EPSG:4326").transform(qbuildings_data['buildings_data']['Building1']['x'],
                                                                         qbuildings_data['buildings_data']['Building1']['y'])

    pvgis_data = pvlib.iotools.get_pvgis_tmy(lat, long, outputformat='json', startyear=2005, endyear=2016)
    coordinates = pvgis_data[2]
    weather_data = pvgis_data[0]

    # Rename columns
    weather_data = weather_data.rename(columns={'temp_air': 'Text', 'ghi': 'Irr'})

    # Extract month, day, and hour
    weather_data['Month'] = weather_data.index.month
    weather_data['Day'] = weather_data.index.day
    weather_data['Hour'] = weather_data.index.hour + 1

    # Add a 'Weekday' column where 1 is a weekday and 0 is a weekend
    weather_data['Weekday'] = weather_data.index.weekday < 5  # Monday-Friday are weekdays
    weather_data['Weekday'] = weather_data['Weekday'].astype(int)  # Convert Boolean to int

    # Add unique identifier column 'id'
    weather_data['id'] = (weather_data.reset_index().index + 1).to_list()

    print(f'The weather data have been loaded from the PVGIS database for a location with coordinates {coordinates}.')

    if export_filename is not None:
        weather_data = weather_data[['id', 'Month', 'Day', 'Hour', 'Irr', 'Text', 'Weekday']]
        weather_data.to_csv(export_filename)

    return weather_data


def read_custom_weather(path_to_weather_file):
    """
    From the current directory, looks for a custom weather file.
    This file should be a .csv with the same structure as the examples provided in ``reho/scripts/examples/data/profiles/``.
    """

    custom_weather = file_reader(path_handler(path_to_weather_file))
    print(f'Weather data have been loaded from {path_handler(path_to_weather_file)}.')

    return custom_weather


def generate_weather_data(cluster, qbuildings_data):
    """
    This function is called if the clustered weather data specified by File_ID do not exist yet.
    Applies the clustering method (see Clustering class) and writes several .dat weather files.

    Parameters
    ----------
    cluster : dict
        Contains a 'Location' (str), some 'Attributes' (list, among 'T' (temperature), 'I' (irradiance), 'W' (weekday) and 'E' (emissions)), a number of periods 'Periods' (int) and a 'PeriodDuration' (int).
    qbuildings_data : dict
        Input data for the buildings.

    Notes
    ------
    .. caution::

        The extreme temperatures are estimated by adding 10% to the extreme found in the yearly weather data.

    See also
    --------
    reho.model.preprocessing.clustering.Clustering
    write_weather_files
    """

    if 'custom_weather' in cluster.keys():
        df = read_custom_weather(cluster['custom_weather'])
    else:
        df = get_weather_data(qbuildings_data).reset_index(drop=True)

    attributes = []
    if 'T' in cluster['Attributes']:
        attributes.append('Text')
    if 'I' in cluster['Attributes']:
        attributes.append('Irr')
    if 'W' in cluster['Attributes']:
        attributes.append('Weekday')
    if 'E' in cluster['Attributes']:
        attributes.append('Emissions')

    # Execute clustering
    df = df[attributes]
    cl = Clustering(data=df, nb_clusters=[cluster['Periods']], period_duration=cluster['PeriodDuration'], options={"year-to-day": True, "extreme": []})
    cl.run_clustering()

    # Construct cluster data
    data_idx = cl.results["idx"]
    frame = []
    cl.nbr_opt = str(cl.nbr_opt)

    # Get unique typical periods from index vector
    for idx in data_idx.loc[:, cl.nbr_opt].unique():
        idx = int(idx)
        # Reshape attributes dynamically according to the number of hours in a period
        df = pd.DataFrame(
            np.reshape(cl.attr_org[idx - 1, :], (-1, int(cl.attr_org.shape[1] / len(attributes)))).transpose(),
            columns=attributes)  # put the attributes into columns of a df

        df["dt"] = sum(data_idx.loc[:, cl.nbr_opt] == idx)  # Frequency
        df["time.hh"] = np.arange(1, df.shape[0] + 1, 1)  # timesteps in typical period
        df["time.dd"] = idx  # typical period index
        frame.append(df.reindex(["time.dd", "time.hh"] + attributes + ["dt"], axis=1))

    # Combine all periods into a single DataFrame
    data_cls = pd.concat(frame, axis=0)

    # If cl.modulo is not zero, handle the modulo case
    data_cls_mod = pd.DataFrame()
    if cl.modulo != 0:  # Handling modulo case
        df_mod = pd.DataFrame.from_dict(dict(zip(cl.data_org.columns, cl.mod_org)))
        max_time_dd = len(cl.attr_org)
        df_mod['time.dd'] = np.repeat(max_time_dd + 1, cl.modulo)
        df_mod['dt'] = np.repeat(1, cl.modulo)
        df_mod['time.hh'] = np.arange(1, cl.modulo + 1)
        data_cls_mod = df_mod

    # Concatenate the main and modified DataFrames
    data_cls = pd.concat([data_cls, data_cls_mod], ignore_index=True)

    hours_per_period = cluster['PeriodDuration']

    # Determine the period of the max and min temperature
    T_idx = [cl.data_org[cl.data_org['Text'] == cl.data_org['Text'].min()].index[0],
             cl.data_org[cl.data_org['Text'] == cl.data_org['Text'].max()].index[0]]
    T_period = [math.floor(T_idx[0] / hours_per_period), math.floor(T_idx[1] / hours_per_period)]

    # Create copies for the min and max temperature rows
    T_min = cl.data_org.iloc[[T_idx[0]]].copy()
    T_max = cl.data_org.iloc[[T_idx[1]]].copy()

    # Get the max irradiance from the same period (for the max temperature)
    T_max['Irr'] = cl.data_org.loc[T_period[1] * hours_per_period: (T_period[1] + 1) * hours_per_period - 1, 'Irr'].max()

    # Set the time for the new rows (variable hours per period)
    T_min[['time.dd', 'time.hh', 'dt']] = [T_period[0], 1, 1]
    T_max[['time.dd', 'time.hh', 'dt']] = [T_period[1], 1, 1]
    T_min["Text"] = -10.0

    # Append the new extreme values to the data
    new_index_min = len(data_cls)  # Dynamically find the next available index
    new_index_max = len(data_cls) + 1
    data_cls = pd.concat([data_cls, T_min.rename({T_idx[0]: new_index_min}), T_max.rename({T_idx[1]: new_index_max})])

    # Construct inter-period data
    data_idy = pd.DataFrame(
        np.stack((np.arange(1, data_idx.loc[:, cl.nbr_opt].shape[0] + 1, 1), data_idx.loc[:, cl.nbr_opt].values), axis=1), columns=["IndexYr", "inter_t"])
    if cl.modulo != 0:
        max_time_dd = len(cl.attr_org)
        data_idy = pd.concat([data_idy, pd.DataFrame([[max_time_dd + 1, max_time_dd + 1]], columns=data_idy.columns)],
                             ignore_index=True)

    write_weather_files(attributes, cluster, data_cls, data_idy)

    print(f'The data have been computed and saved in {path_to_clustering}.')


def write_weather_files(attributes, cluster, values_cluster, index_inter):
    """
    Writes the clustering results computed from ``generate_weather_data`` as .dat files.

    Parameters
    ----------
    attributes : list
        Contains the clustering attributes, among 'Text', Irr', 'Weekday', and 'Emissions'.
    cluster : dict
        Define location, number of periods, and number of timesteps.
    values_cluster : pd.DataFrame
        Produced by ``generate_weather_data``.
    index_inter : pd.DataFrame
        Produced by ``generate_weather_data``.

    Notes
    -----
    - Independently of the clustering attributes, time dependent files are generated:
        - 'frequency_File_ID.dat'
        - 'index_File_ID.dat'
        - 'timestamp_File_ID.dat'
    """

    File_ID = get_cluster_file_ID(cluster)

    if not os.path.isdir(path_to_clustering):
        os.makedirs(path_to_clustering)

    # -------------------------------------------------------------------------------------
    # T
    # -------------------------------------------------------------------------------------
    df_T = values_cluster['Text']
    filename = os.path.join(path_to_clustering, 'T_' + File_ID + '.dat')
    df_T.to_csv(filename, index=False, header=False)

    # -------------------------------------------------------------------------------------
    # Irr
    # -------------------------------------------------------------------------------------
    df_Irr = values_cluster['Irr']
    filename = os.path.join(path_to_clustering, 'Irr_' + File_ID + '.dat')
    df_Irr.to_csv(filename, index=False, header=False)

    # -------------------------------------------------------------------------------------
    # frequency
    # -------------------------------------------------------------------------------------
    df_dd = values_cluster['time.dd'].unique()  # id of typical period

    dp = np.array([])  # duration of period e.g. frequency
    pt = np.array([])  # period duration / number of timesteps in period

    for dd in df_dd:
        p = values_cluster.loc[values_cluster['time.dd'] == dd, 'dt'].unique()
        t = len(values_cluster.loc[values_cluster['time.dd'] == dd, 'dt'])

        dp = np.append(dp, p)
        pt = np.append(pt, t)

    if 'Weekday' in attributes:
        Weekday = np.array([])
        for dd in df_dd:
            w = values_cluster.loc[values_cluster['time.dd'] == dd, 'Weekday'].unique()
            Weekday = np.append(Weekday, w)

    filename = os.path.join(path_to_clustering, 'frequency_' + File_ID + '.dat')

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
    for i, dd in enumerate(df_dd):
        dict_index[dd] = i + 1
    index_inter['index_r'] = index_inter.inter_t.map(dict_index)
    df_time.index = df_time.index + 1

    df_aim = pd.DataFrame()
    for d in index_inter['index_r']:
        nt = int(df_time['timesteps'].xs(d))  # number of timesteps
        df_d = pd.DataFrame([np.repeat(d, nt), np.array(range(1, (nt + 1)))])
        df_aim = pd.concat([df_aim, df_d.transpose()], ignore_index=True)

    df_aim.index = df_aim.index + 1

    filename = os.path.join(path_to_clustering, 'index_' + File_ID + '.dat')
    IterationFile = open(filename, 'w')
    IterationFile.write('param : PeriodOfYear TimeOfYear := \n')
    IterationFile.write(df_aim.to_string(header=False))
    IterationFile.write('\n;')
    IterationFile.close()

    # -------------------------------------------------------------------------------------
    # Time stamp
    # -------------------------------------------------------------------------------------
    filename = os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat')
    IterationFile = open(filename, 'w')
    header = 'Date\tDay\tFrequency\tWeekday\n'
    IterationFile.write(header)
    for key in dict_index:
        pt = df_time.iloc[0].timesteps  # take the same period duration also for modulo
        date = dt.datetime(2005, 1, 1) + dt.timedelta(hours=float((key) * pt))

        if 'Weekday' in attributes:
            text = date.strftime("%m/%d/%Y/%H") + '\t' + str(key) + '\t' + str(dp[dict_index[key] - 1]) + '\t' + str(
                Weekday[dict_index[key] - 1])
        else:
            text = date.strftime("%m/%d/%Y/%H") + '\t' + str(key) + '\t' + str(dp[dict_index[key] - 1])
        IterationFile.write(text + '\n')
    IterationFile.close()


def get_cluster_file_ID(cluster):
    """
    Gets the weather file ID that corresponds to the specifications provided in the reho initalization.

    The file ID is built by concatenating Location_Periods_PeriodDuration_Attributes.
    ``cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}``
    Will yield to:
    ``File_ID = 'Geneva_10_24_T_I_W'``

    Parameters
    ----------
    cluster : dict
        Contains a 'Location' (str), some 'Attributes' (list, among 'T' (temperature), 'I' (irradiance), 'W' (weekday) and 'E' (emissions)), a number of periods 'Periods' (int) and a 'PeriodDuration' (int).

    Returns
    -------
    str
        A literal representation to identify the location and clustering attritutes.
    """
    if 'T' in cluster['Attributes']:
        T = '_T'
    else:
        T = ''
    if 'I' in cluster['Attributes']:
        I = '_I'
    else:
        I = ''
    if 'W' in cluster['Attributes']:
        W = '_W'
    else:
        W = ''
    if 'E' in cluster['Attributes']:
        E = '_E'
    else:
        E = ''

    File_ID = cluster['Location'] + '_' + str(cluster['Periods']) + '_' + str(cluster['PeriodDuration']) + T + I + W + E

    return File_ID


def plot_cluster_KPI_separate(df, save_fig=False):
    # Transpose the DataFrame
    df = df.transpose()

    # Ensure proper column renaming
    df.columns.names = ['iteration', 'KPI']
    df = df.rename(index={'Text': 'Ambient Temperature', 'Irr': 'Global Irradiation'})

    # Select the relevant KPIs for plotting
    df_irr = df.xs('Global Irradiation', axis=0)
    df_T = df.xs('Ambient Temperature', axis=0)

    # Plot RMSD and LDC for Global Irradiation and Ambient Temperature
    fig, ax = plt.subplots()
    fig.set_size_inches(4, 8)
    df_irr[:, 'RMSD'].plot(linestyle='--', color='black', label='RMSD (Irr)', ax=ax)
    df_T[:, 'RMSD'].plot(linestyle='-', color='black', label='RMSD (T)', ax=ax)
    df_irr[:, 'LDC'].plot(linestyle='--', color="red", label='LDC (Irr)', ax=ax)
    df_T[:, 'LDC'].plot(linestyle='-', color="red", label='LDC (T)', ax=ax)

    plt.xlabel('Number of clusters [-]', fontsize=12)
    plt.ylabel('Key performance indicator (KPI) [-]', fontsize=12)
    plt.legend(title="KPI", fontsize=12)

    if save_fig:
        plt.tight_layout()
        plt.savefig('Cluster_KPIs.pdf', format='pdf', dpi=300)
    else:
        plt.show()

    # Plot MAE
    fig, ax = plt.subplots()
    fig.set_size_inches(5, 4)
    df_irr[:, 'MAE'].plot(linestyle='--', color='black', label='MAE (Irr)', ax=ax, marker='o')
    df_T[:, 'MAE'].plot(linestyle='-', color='black', label='MAE (T)', ax=ax, marker='o')
    df_irr[:, 'RMSD'].plot(linestyle='--', color='red', label='RMSD (Irr)', ax=ax, marker='o')
    df_T[:, 'RMSD'].plot(linestyle='-', color='red', label='RMSD (T)', ax=ax, marker='o')

    plt.xlabel('Number of clusters [-]', fontsize=10)
    plt.ylabel('Key performance indicator (KPI) [-]', fontsize=10)
    #plt.ylabel('Mean average error (MAE) [-]')
    plt.legend(title="KPI", fontsize=8)

    if save_fig:
        plt.tight_layout()
        plt.savefig('MAE_KPIs.png', format='png', dpi=300)
    else:
        plt.show()

    # Plot MAPE
    fig, ax = plt.subplots()
    fig.set_size_inches(4, 8)
    df_irr[:, 'MAPE'].plot(linestyle='--', color='black', label='MAPE (Irr)', ax=ax)
    df_T[:, 'MAPE'].plot(linestyle='-', color='black', label='MAPE (T)', ax=ax)

    plt.xlabel('Number of clusters [-]', fontsize=12)
    plt.ylabel('Mean average percentage error (MAPE) [-]', fontsize=12)
    plt.legend(title="KPI", fontsize=12)

    if save_fig:
        plt.tight_layout()
        plt.savefig('MAPE_KPIs.pdf', format='pdf', dpi=300)
    else:
        plt.show()


def plot_LDC(cl, save_fig=False):
    nbr_plot = cl.nbr_opt
    print('Plotting for number of typical days:', nbr_plot)

    # Get original (non-clustered) data
    T_org = cl.data_org['Text']
    IRR_org = cl.data_org['Irr']

    # Get clustered data and undo normalization
    df_clu = cl.attr_clu.xs(str(nbr_plot))
    T_clu = df_clu['Text'] * (T_org.max() - T_org.min()) + T_org.min()
    IRR_clu = df_clu['Irr'] * (IRR_org.max() - IRR_org.min()) + IRR_org.min()

    # Get assigned typical period
    res = cl.results['idx'][str(nbr_plot)]
    for i, d in enumerate(res.unique()):
        res = np.where(res == d, i + 1, res)

    # Repeat result to match time steps
    res = np.repeat(res, cl.period_duration)
    modulo = cl.data_org.shape[0] % cl.period_duration
    res = np.append(res, np.repeat(int(nbr_plot) + 1, modulo))

    # Plot original and clustered data
    fig, ax = plt.subplots(2, 1, sharex=True, figsize=(10, 8))

    ax[0].plot(T_org, color='grey', alpha=0.5)
    sc = ax[0].scatter(T_clu.index, T_clu.values, s=10, c=res, cmap='viridis')
    ax[1].plot(IRR_org, color='grey', alpha=0.5)
    ax[1].scatter(IRR_clu.index, IRR_clu.values, s=10, c=res, cmap='viridis')

    plt.xticks(np.arange(8760, step=730), calendar.month_name[1:13], rotation=30, fontsize=16)
    ax[0].set_ylabel('Temperature [°C]')
    ax[1].set_ylabel('Global Irradiation [W/m$^2$]')

    # Add period legend
    legend1 = ax[0].legend(*sc.legend_elements(), loc='upper right', bbox_to_anchor=(1.0, 1.0), title="Period", ncol=2, fontsize=10)
    ax[0].add_artist(legend1)

    if save_fig:
        plt.tight_layout()
        plt.savefig('Year_Cluster.pdf', format='pdf', dpi=300)
    else:
        plt.show()

    # Sorted DataFrames for LDC plots
    df_T = pd.DataFrame(T_clu, columns=['Text'])
    df_T['Period'] = res
    df_T = df_T.sort_values(by=['Text'], ascending=False, ignore_index=True)

    df_Irr = pd.DataFrame(IRR_clu, columns=['Irr'])
    df_Irr['Period'] = res
    df_Irr = df_Irr.sort_values(by=['Irr'], ascending=False, ignore_index=True)

    # Sorting original data
    T_sort = T_org.sort_values(ascending=False, ignore_index=True)
    IRR_sort = IRR_org.sort_values(ascending=False, ignore_index=True)

    # Plot sorted LDC data
    # fig, ax = plt.subplots(2, 1, sharex=True, figsize=(10, 8))
    # sc3=ax[0].scatter(T_sort.index, T_sort.values, color='grey', alpha=0.5, label="Original Weather Data")
    # sc=ax[0].scatter(df_T.index, df_T['Text'], c=df_T['Period'], cmap='viridis', s=20)
    # ax[1].scatter(IRR_sort.index, IRR_sort.values, color='grey', alpha=0.5)
    # sc2=ax[1].scatter(df_Irr.index, df_Irr['Irr'], c=df_Irr['Period'], cmap='viridis', s=20)
    #
    # ax[0].set_ylabel('Temperature [°C]')
    # ax[1].set_ylabel('Global Irradiation [W/m$^2$]')
    # plt.xlabel('Hours [h]')
    # ax[0].legend(loc='upper left', title="Original Weather Data", ncol=2)
    # legend2 = ax[0].legend(*sc.legend_elements(), loc='upper right', bbox_to_anchor=(1.0, 1.0), title="Period", ncol=2)
    # ax[0].add_artist(legend2)
    #
    #
    # legend3 = ax[0].legend(*sc2.legend_elements(), loc='upper right', bbox_to_anchor=(1.0, 1.0), title="Period", ncol=2)
    # ax[0].add_artist(legend3)
    #
    # if save_fig:
    #     plt.tight_layout()
    #     plt.savefig('LDC.pdf', format='pdf', dpi=300)
    # else:
    #     plt.show()
    fig, ax = plt.subplots(2, 1, sharex=True, figsize=(10, 9.5))

    # Scatter plots for first subplot (Temperature)
    sc1 = ax[0].scatter(T_sort.index, T_sort.values, color='grey', alpha=0.5)
    sc2 = ax[0].scatter(df_T.index, df_T['Text'], c=df_T['Period'], cmap='viridis', s=20)

    # Scatter plots for second subplot (Irradiation)
    sc3 = ax[1].scatter(IRR_sort.index, IRR_sort.values, color='grey', alpha=0.5)
    sc4 = ax[1].scatter(df_Irr.index, df_Irr['Irr'], c=df_Irr['Period'], cmap='viridis', s=20)

    # Set labels
    ax[0].set_ylabel('Temperature [°C]', fontsize=14)
    ax[1].set_ylabel('Global Irradiation [W/m$^2$]', fontsize=14)
    plt.xlabel('Hours [h]', fontsize=14)

    # Create the legend elements for both the grey and color-mapped scatter plots
    # Original Data Legend for the first plot (Temperature)
    handles_T, labels_T = sc2.legend_elements()
    handles_T = [sc1] + handles_T  # Add grey scatter as the first handle
    labels_T = ["Original weather data"] + [f"Period {label}" for label in
                                            labels_T]  # Add "Period" in front of each label

    # Period Legend for the first plot (Temperature)
    legend2 = ax[0].legend(handles=handles_T, labels=labels_T, loc='upper right', ncol=2, fontsize=10)
    ax[0].add_artist(legend2)

    # Original Data Legend for the second plot (Irradiation)
    handles_IRR, labels_IRR = sc4.legend_elements()
    handles_IRR = [sc3] + handles_IRR  # Add grey scatter as the first handle
    labels_IRR = ["Original weather data"] + [f"Period {label}" for label in
                                              labels_IRR]  # Add "Period" in front of each label

    # Period Legend for the second plot (Irradiation)
    legend3 = ax[1].legend(handles=handles_IRR, labels=labels_IRR, loc='upper right',
                           ncol=2, fontsize=11)
    ax[1].add_artist(legend3)

    # Tight layout and saving the figure
    if save_fig:
        plt.tight_layout()
        plt.savefig('LDC.pdf', format='pdf', dpi=300)
    else:
        plt.show()

# Uncomment this to plot plots for all typical days.
# def plot_LDC(cl, save_fig=True):
#     for nbr_plot in [12,24,36,48]:  # Ensure this list exists with all desired cluster values
#         cl.nbr_opt = nbr_plot
#         print('Plotting for number of typical days:', nbr_plot)
#
#         # Get original data
#         T_org = cl.data_org['Text']
#         IRR_org = cl.data_org['Irr']
#
#         # Clustered data (unnormalized)
#         df_clu = cl.attr_clu.xs(str(nbr_plot))
#         T_clu = df_clu['Text'] * (T_org.max() - T_org.min()) + T_org.min()
#         IRR_clu = df_clu['Irr'] * (IRR_org.max() - IRR_org.min()) + IRR_org.min()
#
#         # Assigned periods
#         res = cl.results['idx'][str(nbr_plot)]
#         for i, d in enumerate(res.unique()):
#             res = np.where(res == d, i + 1, res)
#         res = np.repeat(res, cl.period_duration)
#         modulo = cl.data_org.shape[0] % cl.period_duration
#         res = np.append(res, np.repeat(int(nbr_plot) + 1, modulo))
#
#         # Sort data
#         df_T = pd.DataFrame(T_clu, columns=['Text'])
#         df_T['Period'] = res
#         df_T = df_T.sort_values(by=['Text'], ascending=False, ignore_index=True)
#
#         df_Irr = pd.DataFrame(IRR_clu, columns=['Irr'])
#         df_Irr['Period'] = res
#         df_Irr = df_Irr.sort_values(by=['Irr'], ascending=False, ignore_index=True)
#
#         T_sort = T_org.sort_values(ascending=False, ignore_index=True)
#         IRR_sort = IRR_org.sort_values(ascending=False, ignore_index=True)
#
#         # Plot
#         fig, ax = plt.subplots(2, 1, sharex=True, figsize=(6, 5.5))
#         sc1 = ax[0].scatter(T_sort.index, T_sort.values, color='grey', alpha=0.5)
#         sc2 = ax[0].scatter(df_T.index, df_T['Text'], c=df_T['Period'], cmap='viridis', s=15)
#         sc3 = ax[1].scatter(IRR_sort.index, IRR_sort.values, color='grey', alpha=0.5)
#         sc4 = ax[1].scatter(df_Irr.index, df_Irr['Irr'], c=df_Irr['Period'], cmap='viridis', s=15)
#
#         ax[0].set_ylabel('Temperature [°C]', fontsize=10)
#         ax[1].set_ylabel('Global Irradiation [W/m$^2$]', fontsize=10)
#         plt.xlabel('Hours [h]', fontsize=10)
#
#         # # Legends
#         # handles_T, labels_T = sc2.legend_elements()
#         # handles_T = [sc1] + handles_T
#         # labels_T = ["Original weather data"] + [f"Period {label}" for label in labels_T]
#         # ax[0].legend(handles=handles_T, labels=labels_T, loc='upper right', ncol=2, fontsize=7)
#         #
#         # handles_IRR, labels_IRR = sc4.legend_elements()
#         # handles_IRR = [sc3] + handles_IRR
#         # labels_IRR = ["Original weather data"] + [f"Period {label}" for label in labels_IRR]
#         # ax[1].legend(handles=handles_IRR, labels=labels_IRR, loc='upper right', ncol=2, fontsize=7)
#
#         def remove_fraction(handles, labels, fraction=1 / 3):
#             n = len(labels)
#             step = max(1, int(1 / fraction))  # e.g., 3 for 1/3 removal
#             # Keep first handle (original data), then pick others skipping some
#             new_handles = [handles[0]] + [h for i, h in enumerate(handles[1:], start=1) if i % step != 0]
#             new_labels = [labels[0]] + [l for i, l in enumerate(labels[1:], start=1) if i % step != 0]
#             return new_handles, new_labels
#
#         # For Temperature plot legend
#         handles_T, labels_T = sc2.legend_elements()
#         handles_T = [sc1] + handles_T  # add original data handle
#         labels_T = ["Original weather data"] + [f"Period {label}" for label in labels_T]
#         handles_T, labels_T = remove_fraction(handles_T, labels_T, fraction=1 / 3)
#         ax[0].legend(handles=handles_T, labels=labels_T, loc='upper right', ncol=2, fontsize=8)
#
#         # For Irradiation plot legend
#         handles_IRR, labels_IRR = sc4.legend_elements()
#         handles_IRR = [sc3] + handles_IRR  # add original data handle
#         labels_IRR = ["Original weather data"] + [f"Period {label}" for label in labels_IRR]
#         handles_IRR, labels_IRR = remove_fraction(handles_IRR, labels_IRR, fraction=1 / 3)
#         ax[1].legend(handles=handles_IRR, labels=labels_IRR, loc='upper right', ncol=2, fontsize=8)
#
#         plt.tight_layout()
#
#         if save_fig:
#             filename = f"LDC_{nbr_plot}_typical_days.png"
#             plt.savefig(filename, format='png', dpi=300)
#             plt.close(fig)  # Avoid display and memory overload
#         else:
#             plt.show()


