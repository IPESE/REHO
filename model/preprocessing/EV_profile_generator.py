
from paths import *
import model.preprocessing.weather as WD
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt


def generate_EV_plug_out_profiles_district(cluster):
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

    pluging_in_weekday = [0.017, 0.006, 0.004, 0.003, 0.004, 0.005, 0.01, 0.019, 0.03, 0.034, 0.036, 0.042, 0.043, 0.045, 0.047, 0.067, 0.088, 0.111, 0.109, 0.087, 0.069, 0.058, 0.043, 0.023]
    pluging_in_weekend = [0.017, 0.006, 0.004, 0.003, 0.004, 0.005, 0.01, 0.019, 0.03, 0.034, 0.036, 0.042, 0.043, 0.045, 0.047, 0.067, 0.088, 0.111, 0.109, 0.087, 0.069, 0.058, 0.043, 0.023]

    EV_pluged_out = [] # all vehicules not connected
    EV_pluging_in = [] # vehicules connecting at time t
    # iter over the typical periods
    for j, day in enumerate(list(timestamp.Weekday)):
            if day == 0:
                profile = profiles_weekend
                profile_plug_in = pluging_in_weekend
            elif day == 1:
                profile = profiles_weekday
                profile_plug_in = pluging_in_weekday
                #profile = np.tile(profiles_weekday, 365).tolist() # workaround -  whole year profile
            else:
                raise ("day type not possible")

            EV_pluged_out = EV_pluged_out + profile
            EV_pluging_in = EV_pluging_in + profile_plug_in

    EV_pluged_out = EV_pluged_out + [0.0, 0.0] # extreme hours
    EV_pluged_out = np.array(EV_pluged_out)

    EV_pluging_in = EV_pluging_in + [0.0, 0.0] # extreme hours
    EV_pluging_in = np.array(EV_pluging_in)
    #plot_EV_occupancy_profile(EV_plug_out)
    return EV_pluged_out, EV_pluging_in



def generate_EV_plug_out_profiles(cluster, n_houses=31):

    File_ID = WD.get_cluster_file_ID(cluster)

    if 'W' in File_ID.split('_'):
        use_weekdays = True
    else:
        use_weekdays = False


    if use_weekdays:
        timestamp = np.loadtxt(os.path.join(path_to_clustering_results, 'timestamp_' + File_ID + '.dat'), usecols=(1,2,3), skiprows=1)
        timestamp = pd.DataFrame(timestamp, columns=("Day", "Frequency", "Weekday"))


    else:
        timestamp = np.loadtxt(os.path.join(path_to_clustering_results, 'timestamp_' + File_ID + '.dat'), usecols=(1, 2),
                               skiprows=1)
        timestamp = pd.DataFrame(timestamp, columns=("Day", "Frequency"))
        timestamp['Weekday'] = np.repeat(1, len(timestamp))

    profiles_weekday = {"House1": {8: 9}, "House2": {8: 10}, "House3": {9: 11}, "House4": {7: 9},
                        "House5": {8: 8}, "House6": {8: 8}, "House7": {9: 11}, "House8": {7: 9},
                        "House9": {8: 8}, "House10": {8: 8}, "House11": {9: 10}, "House12": {7: 9},
                        "House13": {8: 8}, "House14": {8: 10}, "House15": {9: 10}, "House16": {7: 9},
                        "House17": {8: 9}, "House18": {8: 10}, "House19": {9: 10}, "House20": {7: 8},
                        "House21": {8: 9}, "House22": {8: 10}, "House23": {9: 8}, "House24": {7: 8},
                        "House25": {8: 9}, "House26": {8: 10}, "House27": {9: 8}, "House28": {7: 8},
                        "House29": {10: 9}, "House30": {6: 9}, "House31": {9: 8}}

    profiles_weekend = {"House1": {10: 7}, "House2": {11: 5}, "House3": {12: 5}, "House4": {13: 5},
                        "House5": {10: 8}, "House6": {11: 6}, "House7": {12: 6}, "House8": {13: 6},
                        "House9": {10: 6}, "House10": {11: 7}, "House11": {12: 7}, "House12": {13: 7},
                        "House13": {10: 7}, "House14": {11: 8}, "House15": {12: 8}, "House16": {13: 5},
                        "House17": {10: 8}, "House18": {11: 6}, "House19": {12: 6}, "House20": {13: 6},
                        "House21": {10: 6}, "House22": {11: 7}, "House23": {12: 7}, "House24": {13: 7},
                        "House25": {10: 7}, "House26": {11: 7}, "House27": {12: 8}, "House28": {13: 5},
                        "House29": {10: 7}, "House30": {11: 8}, "House31": {12: 8}}

    profiles_weekday_items = profiles_weekday.items()
    profiles_weekday = dict(list(profiles_weekday_items)[:n_houses])

    profiles_weekend_items = profiles_weekend.items()
    profiles_weekend = dict(list(profiles_weekend_items)[:n_houses])

    periods = cluster['Periods']
    hours = cluster['PeriodDuration']
    len_time_array = (periods*hours+2)
    EV_plug_out = {}

    # iter over the houses of the district
    for i, house in enumerate(profiles_weekday):
        EV_plug_out_house = np.zeros(len_time_array)

        # iter over the typical periods
        for j, day in enumerate(list(timestamp.Weekday)):
            if day == 0: profile = profiles_weekend
            elif day == 1: profile = profiles_weekday
            else: raise("day type not possible")

            # iter over the occupancy profile per day
            for key in profile[house]:
                plug_out_duration = profile[house][key]
                plug_out_start = key
                IDs = list(range(plug_out_start-1+hours*j, plug_out_start-1+plug_out_duration+hours*j))
                EV_plug_out_house[IDs] = 1
            EV_plug_out[i] = EV_plug_out_house

    EV_plug_out = np.concatenate(list(EV_plug_out.values()))
    plot_EV_occupancy_profile(EV_plug_out, n_houses)
    return EV_plug_out


def plot_EV_occupancy_profile(EV_plug_out):
    idx = list(range(1,25))
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.fill_between(idx, EV_plug_out[72:96]*100, color="royalblue", label="weekdays", alpha=0.3)
    ax.fill_between(idx, EV_plug_out[96:120]*100, color="mediumseagreen", label="weekends", alpha=0.3)
    ax.plot(idx, EV_plug_out[72:96]*100, color="royalblue", alpha=0.3)
    ax.plot(idx, EV_plug_out[96:120]*100, color="mediumseagreen", alpha=0.3)

    ax.set_ylabel('share EVs plug-out [%]', fontsize=22)
    ax.set_xlabel('time [hours]', fontsize=22)
    ax.set_xlim([1,24])
    id = list(range(1,25,2))
    plt.xticks(id, fontsize=19)
    plt.yticks(fontsize=19)
    ax.legend(loc="upper left", fontsize=22)

    plt.tight_layout()
    format = 'pdf'
    plt.savefig(('EV_profile' + '.' + format), format=format, dpi=300)
    plt.show()
    print("")










