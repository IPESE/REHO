import pvlib as pvlib
from pyproj import Transformer
from reho.model.preprocessing.QBuildings import *
import reho.model.preprocessing.weather as weather
from datetime import timedelta

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
        - Cluster (dict) to identify the location and clustering attributes
        - File_ID (string) to identify the location and clustering attritutes
        - T_ext (np.array) to represent the external temperature for typical days
        - Irr (np.array) to represent the solar irradiance for typical days
        - df_Timestamp (pd.DataFrame) to represent the timestamps for the typical days
    """

    local_data = dict()

    # Cluster
    local_data["Cluster"] = cluster

    # Weather
    File_ID = weather.get_cluster_file_ID(cluster)
    local_data["File_ID"] = File_ID

    clustering_directory = os.path.join(path_to_clustering, File_ID)
    if not os.path.exists(clustering_directory):
        os.makedirs(clustering_directory)
        weather.generate_weather_data(cluster, qbuildings_data, clustering_directory)

    local_data["df_Timestamp"] = pd.read_csv(os.path.join(clustering_directory, 'timestamp.csv'))
    local_data["df_Timestamp"]["Date"] = pd.to_datetime(local_data["df_Timestamp"]["Date"])

    bui_id = list(qbuildings_data['buildings_data'].keys())[0]
    lat, long = Transformer.from_crs("EPSG:2056", "EPSG:4326").transform(qbuildings_data['buildings_data'][bui_id]['x'], qbuildings_data['buildings_data'][bui_id]['y'])
    df_sun_position = pd.DataFrame()
    for day in local_data["df_Timestamp"]["Date"][0:-2]:
        for i in range(24):
            df_sun_position = pd.concat([df_sun_position, pvlib.solarposition.get_solarposition(day+timedelta(hours=i), lat, long)])
    for day in local_data["df_Timestamp"]["Date"][-2:]:
        df_sun_position = pd.concat([df_sun_position, pvlib.solarposition.get_solarposition(day + timedelta(hours=13), lat, long)])
    local_data["sun_azimuth"] = df_sun_position["azimuth"] - 90

    typical_data = pd.read_csv(os.path.join(clustering_directory, 'typical_data.csv'))
    local_data["T_ext"] = typical_data['Text'].values
    local_data["Irr"] = typical_data['Irr'].values
    local_data["Irr_yearly"] = pd.read_csv(os.path.join(path_to_skydome, 'total_irradiation.csv')).drop(columns=["time"])

    # renovation
    local_data["df_renovation_targets"] = pd.read_csv(os.path.join(path_to_infrastructure, 'U_values.csv'), sep=";").set_index("period")
    local_data["df_renovation"] = pd.read_csv(os.path.join(path_to_infrastructure, 'renovation.csv')).set_index(["year", "element"])
    return local_data
