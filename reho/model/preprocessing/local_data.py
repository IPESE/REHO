from reho.model.preprocessing.QBuildings import *
import reho.model.preprocessing.weather as WD


def return_local_data(cluster, qbuildings_data):
    """
    Retrieve the data (weather and carbon emissions) corresponding to the buildings' location.

    Parameters
    ----------
    cluster : dict
        Define location of the buildings, and attributes for the data reduction process (clustering).

    Returns
    -------
    local_data : dict
        A dictionary containing the File_ID (string) and the following pandas dataframe:
        - df_Timestamp
        - df_Irradiation
        - df_Area
        - df_Cenpts
        - df_Westfacades_irr
        - df_Emissions
    """

    local_data = dict()

    # Weather
    File_ID = WD.get_cluster_file_ID(cluster)
    local_data['File_ID'] = File_ID

    path_to_timestamp = os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat')
    if not os.path.exists(path_to_timestamp):
        WD.generate_weather_data(cluster, qbuildings_data)

    local_data["df_Timestamp"] = pd.read_csv(path_to_timestamp, delimiter='\t', parse_dates=[0])

    # Solar
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

    # Carbon emissions
    local_data["df_Emissions"] = file_reader(path_to_emissions, index_col=[0, 1, 2])

    return local_data