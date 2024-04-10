from reho.model.preprocessing.QBuildings import *
from reho.model.preprocessing.weather import get_cluster_file_ID


def return_location_data(cluster):
    """
        Reads .csv, .txt and .xlsx files to retrieve the local data (carbon emissions, solar irradiation) corresponding to the specified cluster.

        Parameters
        ----------
        cluster : dict
            Define location district, number of periods, and number of timesteps.

        Returns
        -------
        dict
            A dictionary containing pandas dataframe.
        """

    location_data = dict()

    # Carbon emissions
    location_data["df_Emissions"] = file_reader(path_to_emissions, index_col=[0, 1, 2])

    # Solar
    # TODO: These files are specific to Rolle.
    location_data["df_Irradiation"] = pd.read_csv(path_to_irradiation, index_col=[0])
    location_data["df_Area"] = pd.read_csv(path_to_areas, header=None)
    location_data["df_Cenpts"] = pd.read_csv(path_to_cenpts, header=None)

    File_ID = get_cluster_file_ID(cluster)
    path_to_timestamp = os.path.join(path_to_clustering, 'timestamp_' + File_ID + '.dat')
    location_data["df_Timestamp"] = pd.read_csv(path_to_timestamp, delimiter='\t', parse_dates=[0])

    path_to_westfacades_irr = os.path.join(path_to_clustering, 'westfacades_irr_' + File_ID + '.txt')
    # check if irradiation already exists:
    if not os.path.exists(path_to_westfacades_irr):
        location_data["df_Timestamp"].Date = pd.to_datetime(location_data["df_Timestamp"]['Date'], format="%m/%d/%Y/%H")
        frequency_dict = pd.Series(location_data["df_Timestamp"].Frequency.values, index=location_data["df_Timestamp"].Date).to_dict()
        frequency_dict['PeriodDuration'] = {p + 1: cluster['PeriodDuration'] for p in range(cluster['Periods'])}
        df_annual, irr_west = SKD.calc_orientation_profiles(270, 90, 0, location_data, frequency_dict)
        np.savetxt(path_to_westfacades_irr, irr_west)
    location_data["df_Westfacades_irr"] = pd.read_csv(path_to_westfacades_irr, header=None)[0].values

    return location_data