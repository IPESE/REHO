
from reho.paths import *
import reho.model.preprocessing.weather as WD
import pandas as pd
import numpy as np


def generate_EV_plugged_out_profiles_district(cluster):
    #TODO IMPLEMENTATION of flexible period duration
    File_ID = WD.get_cluster_file_ID(cluster)

    if 'W' in File_ID.split('_'):
         use_weekdays = True
    else:
        use_weekdays = False


    if use_weekdays:
        timestamp = np.loadtxt(os.path.join(path_to_clustering_results, 'timestamp_' + File_ID + '.dat'), usecols=(1, 2, 3), skiprows=1)
        timestamp = pd.DataFrame(timestamp, columns=("Day", "Frequency", "Weekday"))
    else:
        df = pd.read_csv(os.path.join(path_to_clustering_results, 'timestamp_' + File_ID + '.dat'), delimiter = '\t')
        timestamp = df.fillna(1) #only weekdays

    # Federal Office of Statistic, Comportement de la population en matiere de transports, 2015
    profiles_weekday = [0.01, 0.0, 0.0, 0.0, 0.0, 0.03, 0.1, 0.12, 0.11, 0.12, 0.12, 0.14, 0.13, 0.14, 0.13, 0.13, 0.18, 0.2, 0.15, 0.1, 0.07, 0.06, 0.05, 0.03]
    profiles_weekend = [0.01, 0.0, 0.0, 0.0, 0.0, 0.00, 0.0, 0.00, 0.03, 0.10, 0.12, 0.11, 0.12, 0.12, 0.14, 0.13, 0.14, 0.13, 0.15, 0.1, 0.07, 0.06, 0.05, 0.03]

    # UK department for transport Electric Chargepoint Analysis 2017: Domestics
    profiles_weekday = [0.0, 0.0, 0.0, 0.0, 0.01, 0.02, 0.08, 0.2, 0.31, 0.35, 0.38, 0.39, 0.39, 0.38, 0.38, 0.36, 0.31, 0.24, 0.18, 0.13, 0.09, 0.05, 0.03, 0.01]
    profiles_weekend = [0.0, 0.0, 0.0, 0.0, 0.01, 0.02, 0.08, 0.2, 0.31, 0.35, 0.38, 0.39, 0.39, 0.38, 0.38, 0.36, 0.31, 0.24, 0.18, 0.13, 0.09, 0.05, 0.03, 0.01]

    plugging_in_weekday = [0.017, 0.006, 0.004, 0.003, 0.004, 0.005, 0.01, 0.019, 0.03, 0.034, 0.036, 0.042, 0.043, 0.045, 0.047, 0.067, 0.088, 0.111, 0.109, 0.087, 0.069, 0.058, 0.043, 0.023]
    plugging_in_weekend = [0.017, 0.006, 0.004, 0.003, 0.004, 0.005, 0.01, 0.019, 0.03, 0.034, 0.036, 0.042, 0.043, 0.045, 0.047, 0.067, 0.088, 0.111, 0.109, 0.087, 0.069, 0.058, 0.043, 0.023]

    EV_plugged_out = [] # all vehicules not connected
    EV_plugging_in = [] # vehicules connecting at time t
    # iter over the typical periods
    for j, day in enumerate(list(timestamp.Weekday)):
            if day == 0:
                profile = profiles_weekend
                profile_plug_in = plugging_in_weekend
            elif day == 1:
                profile = profiles_weekday
                profile_plug_in = plugging_in_weekday
                #profile = np.tile(profiles_weekday, 365).tolist() # workaround -  whole year profile
            else:
                raise ("day type not possible")

            EV_plugged_out = EV_plugged_out + profile
            EV_plugging_in = EV_plugging_in + profile_plug_in

    EV_plugged_out = EV_plugged_out + [0.0, 0.0] # extreme hours
    EV_plugged_out = np.array(EV_plugged_out)

    EV_plugging_in = EV_plugging_in + [0.0, 0.0] # extreme hours
    EV_plugging_in = np.array(EV_plugging_in)
    return EV_plugged_out, EV_plugging_in
