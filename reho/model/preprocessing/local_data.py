from reho.model.preprocessing.QBuildings import *
import reho.model.preprocessing.weather as weather
from reho.model.preprocessing.emissions_parser import annual_to_typical_emissions

__doc__ = """
Handles data specific to the location.
"""


def return_local_data(cluster, qbuildings_data):
    """
    Retrieves the data (weather and carbon emissions) corresponding to the buildings' location.

    Parameters
    ----------
    cluster : dict
        Defines location of the buildings, and clustering attributes for the data reduction process.
    qbuildings_data : dict
        Buildings characterization

    Returns
    -------
    dict
        File_ID (string) to identify the location and clustering attritutes, and the following pandas dataframes:
            - df_Timestamp
            - df_Irradiation
            - df_Area
            - df_Cenpts
            - df_Westfacades_irr
            - df_Emissions
    """

    local_data = dict()

    # Weather
    File_ID = weather.get_cluster_file_ID(cluster)
    local_data['File_ID'] = File_ID

    path_to_timestamp = os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat')
    if not os.path.exists(path_to_timestamp):
        weather.generate_weather_data(cluster, qbuildings_data)

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
        df_annual, irr_west = skydome.calc_orientation_profiles(270, 90, 0, local_data, frequency_dict)
        np.savetxt(path_to_westfacades_irr, irr_west)
    local_data["df_Westfacades_irr"] = pd.read_csv(path_to_westfacades_irr, header=None)[0].values

    # Carbon emissions
    local_data["df_Emissions"] = file_reader(path_to_emissions, index_col=[0, 1, 2])
    local_data["df_Emissions_GWP100a"] = annual_to_typical_emissions(cluster, 'CH', "GWP100a", local_data["df_Timestamp"], local_data["df_Emissions"])

    return local_data
