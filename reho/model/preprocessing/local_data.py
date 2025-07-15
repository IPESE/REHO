import pandas as pd

from reho.model.preprocessing.QBuildings import *
import reho.model.preprocessing.weather as weather

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

    typical_data = pd.read_csv(os.path.join(clustering_directory, 'typical_data.csv'))
    local_data["T_ext"] = typical_data['Text'].values
    local_data["Irr"] = typical_data['Irr'].values
    local_data["Irr_yearly"] = pd.read_csv(os.path.join(path_to_skydome, 'total_irradiation.csv')).drop(columns=["time"])

    local_data["df_Timestamp"] = pd.read_csv(os.path.join(clustering_directory, 'timestamp.csv'))
    local_data["df_Timestamp"]["Date"] = pd.to_datetime(local_data["df_Timestamp"]["Date"])

    # Refurbishment
    local_data["df_Refurbishment_targets"] = pd.read_csv(os.path.join(path_to_infrastructure, 'U_values.csv')).set_index("period")
    local_data["df_Refurbishment"] = pd.read_csv(os.path.join(path_to_infrastructure, 'refurbishment.csv')).set_index(["year", "element"])
    return local_data
