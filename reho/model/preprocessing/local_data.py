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
        - File_ID (string) to identify the location and clustering attritutes
        - df_Timestamp
        - df_Emissions
    """

    local_data = dict()

    # Weather
    File_ID = weather.get_cluster_file_ID(cluster)
    local_data['File_ID'] = File_ID

    clustering_directory = os.path.join(path_to_clustering, File_ID)
    if not os.path.exists(clustering_directory):
        os.makedirs(clustering_directory)
        weather_data = weather.generate_weather_data(cluster, qbuildings_data, clustering_directory)
        weather_data.to_csv(os.path.join(clustering_directory, 'annual_data.csv'), index=False)

    local_data["T_ext"] = np.loadtxt(os.path.join(clustering_directory, 'Text.dat'))
    local_data["Irr"] = np.loadtxt(os.path.join(clustering_directory, 'Irr.dat'))
    local_data["df_Timestamp"] = pd.read_csv(os.path.join(clustering_directory, 'timestamp.dat'), delimiter='\t', parse_dates=[0])

    # Carbon emissions
    local_data["df_Emissions"] = file_reader(path_to_emissions, index_col=[0, 1, 2])
    local_data["df_Emissions_GWP100a"] = annual_to_typical_emissions(cluster, 'CH', "GWP100a", local_data["df_Timestamp"], local_data["df_Emissions"])

    return local_data
