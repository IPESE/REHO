
import pandas as pd
import numpy as np
from reho.paths import *
from matplotlib import pyplot as plt

__doc__ = """
*Reconstructs a yearly profile from the clustering periods.*
"""

def yearly_profile(df_cluster, df):

    df_year = np.zeros(8760)
    for id in df.index:
        id_p = df.iloc[int(id-1)][1]
        id_t = df.iloc[int(id-1)][2]
        df_year[int(id-1)] = df_cluster.xs(id_p).xs(id_t)
    return df_year


def build_profiles(timeserie, timeserie_2, location, bui_list):
    """
    input:
    timeserie: dataframe Streams_Q
    timeserie: dataframe domestic electricity
    location: string
    bui_list: list building id

    return:
    df: dataframe hourly consumption profile for a year for electricity, SH and DHW for all buildings in bui_list
    """
    elec_needs = timeserie_2.groupby(level=["Period", "Time"]).sum()
    timeserie = timeserie.groupby(level=["Stream", "Period", "Time"]).sum()
    SH_needs = timeserie.xs("Building1_c_lt") * 0
    DHW_needs = timeserie.xs("Building1_c_lt") * 0

    for bui in bui_list:
        SH_needs = SH_needs + timeserie.xs(bui + "_c_lt") + timeserie.xs(bui + "_c_mt") + timeserie.xs(bui + "_h_lt")
        DHW_needs = DHW_needs + timeserie.xs("WaterTankDHW_" + bui + "_c_ht")

    thisfile = os.path.join(path_to_clustering, 'index_' + location + '_10_24_T_I.dat')
    df = np.loadtxt(thisfile, skiprows=1, max_rows=8760)
    df = pd.DataFrame(df).set_index(0)

    elec_yearly = yearly_profile(elec_needs, df)
    stream_Q_SH_yearly = yearly_profile(SH_needs, df)
    stream_Q_DHW_yearly = yearly_profile(DHW_needs, df)


    df["Elec[kW]"] = elec_yearly
    df["SH[kW]"] = stream_Q_SH_yearly
    df["DHW[kW]"] = stream_Q_DHW_yearly

    df[1] = np.repeat(list(np.arange(1,366)),24)
    df.columns = ["day", "hour", "Elec[kW]", "SH[kW]", "DHW[kW]"]
    df = df.set_index(["day", "hour"])
    return df


def build_all_profiles(pareto, zones, T_list=[]):
    """
    Take weather location + temperature levels and build hourly consumption profiles.
    Save nested dictionary. First level is temperature level, second level location.
    """
    bui_list = pareto["Lugano_21"][0]["df_Buildings"].index.values
    df = {}
    for temperature in T_list:
        df[temperature] = {}
        for location in zones:
            timeserie = pareto[location + '_' + str(temperature)][0]["df_Stream_t"].Streams_Q
            timeserie_2 = pareto[location + '_' + str(temperature)][0]["df_Buildings_t"].Domestic_electricity

            df[temperature][location] = build_profiles(timeserie, timeserie_2, location, bui_list)
    return df


def plot_profiles(timeserie, timestep, temperature, location, resource, save=False):

    if timestep == "day":
        average_demand = np.sum(timeserie.reshape(-1, 24), axis=1)/1000
        idx = list(range(1, 366))
    elif timestep == "hour":
        average_demand = timeserie
        idx = list(range(1, 365 * 24 + 1))
        average_demand = average_demand[0:200]
        idx = idx[0:200]
    else:
        average_demand = timeserie / 1000
        idx = list(range(1, 365 * 24 + 1))

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(idx, average_demand, color="royalblue")
    ax.set_ylabel('energy needs [kW]', fontsize=19)
    ax.set_xlabel('time [' + timestep + ']', fontsize=19)
    title = location + ' ' + str(temperature) + ' ' + resource
    plt.title(title)

    if save:
        plt.tight_layout()
        format = 'png'
        plt.savefig((location + '_' + str(temperature) + '_' + resource + '_' + timestep + '.' + format), format=format, dpi=300, bbox_inches='tight')
    else:
        plt.show()


def extrapolate_to_CH(df_res, attribute):
    zones = {'Disentis_21': 30.20, 'Davos_21': 70.21, 'Lugano_21': 29.45, 'Bern-Liebefeld_21': 133.35, 'Piotta_21': 12.46, 'Geneve-Cointrin_21': 75.25, 'Zuerich-SMA_21': 318.63}
    surface_district = {key: df_res[key][0]["df_Buildings"]["ERA"].sum() for key in df_res}
    df_CH = pd.DataFrame()

    for location in df_res:
        df_loc = df_res[location][0][attribute] / surface_district[location] * zones[location] * 1e6
        df_loc = df_loc.fillna(0)
        df_CH.index = df_loc.index
        df_CH = df_CH.add(df_loc, fill_value=0)
    return df_CH

def filter_idx(df, name):

    idx = [name in idx for idx in df.index]
    return df[idx]

if __name__ =='__main__':

    generate_profiles = True
    plot_demand = False
    zones = {'Disentis_21': 30.20, 'Davos_21': 70.21, 'Lugano_21': 29.45, 'Bern-Liebefeld_21': 133.35, 'Piotta_21': 12.46, 'Geneve-Cointrin_21': 75.25, 'Zuerich-SMA_21': 318.63}
    T_list = [21]

    if generate_profiles:
        filename = pd.read_pickle("EV_demand_profile.pickle")

        thisfile = os.path.join(path_to_clustering, 'index_Geneva_10_24_T_I_W.dat')
        df = np.loadtxt(thisfile, skiprows=1, max_rows=8760)
        df = pd.DataFrame(df).set_index(0)

        df_year = yearly_profile(filename, df)
        df_year = pd.DataFrame(df_year)
        df_year.columns = ["EV_elec_demand_kW"]
        df_year.to_csv("EV_demand.csv")

    if plot_demand:
        df_CH = pd.read_pickle("data_T_in_CH/CH_heat_loads_max_PV")
        for temperature in df_CH:
            for demand in df_CH[temperature]:
                plot_profiles(np.array(df_CH[temperature][demand]), "hour", temperature, "CH", demand, save=False)
