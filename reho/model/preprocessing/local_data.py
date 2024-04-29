from reho.model.preprocessing.QBuildings import *
import reho.model.preprocessing.weather as WD


def return_local_data(cluster, qbuildings_data):
    """
    Reads .csv, .txt and .xlsx files to retrieve the local data (carbon tag, solar irradiation) corresponding to the buildings' area (cluster).

    Parameters
    ----------
    cluster : dict
        Define location district, number of periods, and number of timesteps.

    Returns
    -------
    local_data : dict
        A dictionary containing the following pandas dataframe: df_Emissions, df_Irradiation, df_Area, df_Cenpts, df_Timestamp, df_Westfacades_irr.
    """

    local_data = dict()

    # Carbon emissions
    local_data["df_Emissions"] = file_reader(path_to_emissions, index_col=[0, 1, 2])

    # Weather
    File_ID = WD.get_cluster_file_ID(cluster)
    local_data['File_ID'] = File_ID

    among_cl_results = os.path.exists(os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat'))
    if not among_cl_results or 'weather_file' in cluster.keys():
        WD.generate_weather_data(cluster, qbuildings_data)
    path_to_timestamp = os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat')
    local_data["df_Timestamp"] = pd.read_csv(path_to_timestamp, delimiter='\t', parse_dates=[0])

    # Solar
    # TODO: These files are specific to Rolle.
    local_data["df_Irradiation"] = pd.read_csv(path_to_irradiation, index_col=[0])
    local_data["df_Area"] = pd.read_csv(path_to_areas, header=None)
    local_data["df_Cenpts"] = pd.read_csv(path_to_cenpts, header=None)

    path_to_westfacades_irr = os.path.join(path_to_clustering, 'westfacades_irr_' + File_ID + '.txt')
    # check if irradiation already exists:
    if not os.path.exists(path_to_westfacades_irr):
        local_data["df_Timestamp"].Date = pd.to_datetime(local_data["df_Timestamp"]['Date'], format="%m/%d/%Y/%H")
        frequency_dict = pd.Series(local_data["df_Timestamp"].Frequency.values, index=local_data["df_Timestamp"].Date).to_dict()
        frequency_dict['PeriodDuration'] = {p + 1: cluster['PeriodDuration'] for p in range(cluster['Periods'])}
        df_annual, irr_west = SKD.calc_orientation_profiles(270, 90, 0, local_data, frequency_dict)
        np.savetxt(path_to_westfacades_irr, irr_west)
    local_data["df_Westfacades_irr"] = pd.read_csv(path_to_westfacades_irr, header=None)[0].values

    return local_data