import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import interp1d
import math
import scipy as sp

pd.set_option('display.max_rows', 700)
pd.set_option('display.max_columns', 700)
pd.set_option('display.width', 1000)

cm = plt.cm.get_cmap('Spectral')
EPFL_light_grey = '#CAC7C7'
EPFL_red = '#FF0000'
EPFL_leman = '#00A79F'
EPFL_canard = '#007480'
Salmon = '#FEA993'

colors_dict = {0: 'black', 1: EPFL_red, 2: EPFL_light_grey, 3: Salmon, 4: EPFL_leman, 5: EPFL_canard}
plt.rcParams.update({'font.size': 10})


def linerize_equal_steps (x, y):
    x.name = 'x'
    y.name = 'y'
    step = (x.max() - x.min()) / len(x)
    df = pd.concat([x, y], names =['x','y'], axis=1)

    df_new = pd.DataFrame(columns=['y'])
    for s in  np.arange(1,  len(x)+1 ):
        x_new = s*step
        ub = df[df.x >= x_new].x.min()
        lb = df[df.x < x_new].x.max()
        if math.isnan(ub) == True: # happens in case x_new == to last x in array
            y_new = df[df.x == lb].iloc[0].y # just return last point
        else:
            upper_bound = df[df.x == ub].iloc[0]
            lower_bound = df[df.x == lb].iloc[0]

            m = ((upper_bound.y - lower_bound.y) / (upper_bound.x - lower_bound.x))
            b = lower_bound.y- m * lower_bound.x

            y_new = m*x_new + b
        df_new.at[x_new, 'y'] = y_new
    return df_new

def split_orientation(az):

    if (az < 45) or  (az > 315):
        orientation = 'North'
    elif  (az >= 45) and (az < 135):
        orientation = 'East'
    elif (az >= 135) and (az < 225):
        orientation = 'South'
    elif (az >= 225) and (az <= 315):
        orientation = 'West'
    else:
        orientation = 'Other'

    return  orientation

def get_roof_max(df_nbr, hs_A):

    df_n = df_nbr.groupby(['Pareto_ID', 'Surface', 'Azimuth', 'Tilt']).sum()
    roofs = df_n[df_n.index.get_level_values(level='Tilt') != 90]

    #get total m2 PV
    total_roofs = roofs.groupby('Pareto_ID').sum()
    total_roofs['PV_m2'] = total_roofs.PVA_module_nbr*1.6
    # get occupation based on azimuth orientation
    roofs = roofs.reset_index(level = ['Azimuth'])
    roofs['Orientation'] = roofs.apply(lambda x: split_orientation(x['Azimuth']), axis=1)
    roofs = roofs.set_index('Orientation', append='True')
    roofs = roofs.groupby(['Pareto_ID', 'Orientation']).sum()
    max = roofs.PVA_module_nbr.groupby(level="Orientation").max()
    roofs['occupancy'] = roofs.PVA_module_nbr / max

    roofs_max = total_roofs.PV_m2.max()
    roofs_max_m2 = roofs_max /hs_A

    facades = df_n[df_n.index.get_level_values(level='Tilt') == 90]
    if not facades.empty:
        # get total m2 facades
        total_facades = facades.groupby('Pareto').sum()
        total_facades['PV_m2'] = total_facades.PVA_module_nbr*1.6
        # get occupation based on azimuth orientation
        facades = facades.reset_index(level=['Azimuth'])
        facades['Orientation'] = facades.apply(lambda x: split_orientation(x['Azimuth']), axis=1)
        facades = facades.set_index('Orientation', append='True')
        facades = facades.groupby(['Pareto', 'Orientation']).sum()
        max = facades.PVA_module_nbr.max(level=1)
        facades['occupancy'] = facades.PVA_module_nbr / max
        total_surface = total_facades['PV_m2'] + total_roofs['PV_m2']
    else:
        total_surface = total_roofs['PV_m2']
    total_surface_m2 = total_surface/hs_A

    return total_surface_m2, roofs_max_m2


def plot_economical_feedin_price(bounds, resolution, Pareto):

    df_unit = return_district_result_object_dataframe(Pareto, 'df_Unit')
    df_KPI = return_district_result_object_dataframe(Pareto, 'df_KPI')
    hs_A = return_district_result_object_dataframe(Pareto, 'df_Buildings')["ERA"].xs(1, level=1).sum()

    df_nbr = return_district_result_object_dataframe(Pareto, 'df_PV_orientation')  # df_PVA_module_nbr, df_PV_orientation
    total_surface_m2, roof_max_m2 = get_roof_max(df_nbr, hs_A)
    # some data processing
    MWh_PV = {}
    for i in Pareto[0]:
        if "df_Annuals" in dir(Pareto[0][1]):
            id = ["PV" in id for id in Pareto[0][i].df_Annuals.xs("Electricity")["Supply_MWh"].index]
            MWh_PV[i] = Pareto[0][i].df_Annuals.xs("Electricity")["Supply_MWh"][id].sum()
        else:
            id = ["PV" in id for id in Pareto[0][i]["df_Annuals"].xs("Electricity")["Supply_MWh"].index]
            MWh_PV[i] = Pareto[0][i]["df_Annuals"].xs("Electricity")["Supply_MWh"][id].sum()
    MWh_PV = pd.DataFrame.from_dict(MWh_PV, orient="Index")[0]
    total_surface_m2.index.name = "Pareto"

    df_K = df_KPI.xs((0, 'Network'), level=('Scn_ID', 'Hub'))
    SC = df_K.SC
    MWh_PV.index=SC.index

    MWh_SC = MWh_PV.mul(SC)
    MWh_SC = MWh_SC.fillna(0)
    MWh_exp = MWh_PV - MWh_SC
    MWh_exp = MWh_exp.fillna(0)

    PV_kWyr = MWh_PV
    PV = df_unit[df_unit.index.get_level_values('Unit').str.contains('PV')]
    PV = PV.groupby('Pareto_ID').sum()
    PV_CHF = PV.Costs_Unit_inv

    PV_CHF_kWyr = PV_CHF.div(PV_kWyr)
    PV_CHF_kWyr = PV_CHF_kWyr.fillna(0)

    # linearize PV design trends (PV capacity, MWh exported and imported)
    PV_CHF_kWyr = linerize_equal_steps(total_surface_m2, PV_CHF_kWyr).y
    MWh_SC = linerize_equal_steps(total_surface_m2, MWh_SC).y
    MWh_exp = linerize_equal_steps(total_surface_m2, MWh_exp).y

    # find PV_kW_yr where all roofs are full
    PV_kWyr_function = linerize_equal_steps(total_surface_m2, PV_kWyr)
    PV_kWyr = PV_kWyr_function.y

    No_feed_in = resolution
    No_retail = resolution
    min_feed = bounds["feed_in"][0]
    max_feed = bounds["feed_in"][1]
    min_demand = bounds["retail"][0]
    max_demand = bounds["retail"][1]
    feed_in_prices = np.linspace(min_feed, max_feed, No_feed_in)
    retail_prices = np.linspace(min_demand, max_demand, No_retail)

    # build matrix economic revenues for each combination feed-in / retail tariffs
    zero_data = np.zeros(shape=(No_feed_in, No_retail))
    df_plot_last = pd.DataFrame(zero_data, columns=retail_prices)
    df_plot_inv_induced = pd.DataFrame(zero_data, columns=retail_prices)
    df_plot_first = pd.DataFrame(zero_data, columns=retail_prices)
    for d in retail_prices:
        y_last = np.array([])
        y_inv_induced = np.array([])
        y_first = np.array([])
        for x in feed_in_prices:
            AR_x = (MWh_exp * x * 1000 + MWh_SC * d * 1000) / PV_kWyr
            Revenues = AR_x - PV_CHF_kWyr
            # last point which is economic = last point which has "positive value" so we need to find the 0 point. revenues with discrete cost can have 2 - we need to find the second one!
            max_index = Revenues[Revenues == Revenues.max()].index[0]

            # MAX POINT WHERE it corosses the last time
            if (Revenues.loc[max_index:] < 0).any():  # there can be max profit - but it is always economic->check if revenue gets negative
                if (Revenues.loc[max_index:] < 0).all():  # it is never "positiv" always uneconomic
                    last_economic_point = np.nan
                    inv_induced = np.nan
                else:
                    f = interp1d(Revenues.loc[max_index:], PV_kWyr.loc[max_index:])
                    last_economic_point = f(0)
                    f2 = interp1d(PV_kWyr.loc[max_index:], PV_CHF_kWyr.loc[max_index:])
                    inv_induced = f2(last_economic_point.mean())
            else:
                last_economic_point = np.nan
                inv_induced = np.nan
            # MIN POINT WHERE it corosses the first time
            if (Revenues.loc[:max_index] < 0).any():
                if (Revenues.loc[:max_index] < 0).all():
                    first_economic_point = np.nan
                else:
                    f = interp1d(Revenues.loc[:max_index], PV_kWyr.loc[:max_index])
                    first_economic_point = f(0)
            else:
                first_economic_point = np.nan

            y_last = np.append(y_last, last_economic_point)
            y_inv_induced = np.append(y_inv_induced, inv_induced)
            y_first = np.append(y_first, first_economic_point)
        df_plot_last[d] = y_last
        df_plot_inv_induced[d] = y_inv_induced
        df_plot_first[d] = y_first

    df_plot_first = df_plot_first.set_index(feed_in_prices)
    df_plot_last = df_plot_last.set_index(feed_in_prices)
    df_plot_inv_induced = df_plot_inv_induced.set_index(feed_in_prices)
    return df_plot_last, feed_in_prices, No_feed_in, df_plot_inv_induced

def plot_rainbow(df_plot_last, feed_in_prices, No_feed_in, df_plot_inv_induced, bounds, save_fig, plot_type):
    # plotting
    fig, ax = plt.subplots()
    for demand_price in df_plot_last.columns:
        if plot_type == "demand_feed_in_E_gen_pv":
            if all(pd.isnull(df_plot_last[demand_price].values)):
                c_list = ["white"] * No_feed_in
            else:
                c_list = df_plot_last[demand_price].values
            cs = ax.scatter(feed_in_prices, np.repeat(demand_price, No_feed_in), c=c_list, s=5, cmap=cm, vmin = df_plot_last.min().min(), vmax = df_plot_last.max().max() )
        elif plot_type == "E_gen_pv_demand_feed_in":
            cs = ax.scatter(np.repeat(demand_price, No_feed_in), df_plot_last[demand_price].values, c=feed_in_prices, s=5, cmap=cm, vmin=bounds["feed_in"][0], vmax=bounds["feed_in"][1])
        elif plot_type == "invest_demand_feed_in":
            cs = ax.scatter(np.repeat(demand_price, No_feed_in), df_plot_inv_induced[demand_price].values, c=feed_in_prices, s=5, cmap=cm, vmin=bounds["feed_in"][0], vmax=bounds["feed_in"][1])

    ax.annotate(' all PV investments \n economic feasible', (0.1, 0.22), zorder=10)
    cbar = fig.colorbar(cs)

    if plot_type == "demand_feed_in_E_gen_pv":
        ax.set_xlim(bounds["feed_in"][0], bounds["feed_in"][1])
        ax.set_ylim(bounds["retail"][0], bounds["retail"][1])
        ax.set_xlabel('feed-in tariff  [CHF/kWh]', fontsize=14)
        ax.set_ylabel('retail tariff [CHF/kWh]', fontsize=14)
        cbar.ax.set_ylabel('PV electricity generated [TWh/yr]', fontsize=14)

    elif plot_type == "E_gen_pv_demand_feed_in":
        ax.set_xlim(bounds["retail"][0], bounds["retail"][1])
        ax.set_ylim(df_plot_last.min().min(), df_plot_last.max().max())
        ax.set_xlabel('retail tariff [CHF/kWh]')
        ax.set_ylabel('PV electricity generated [TWh/yr]')
        cbar.ax.set_ylabel('feed-in tariff  [CHF/kWh]')

    elif plot_type == "invest_demand_feed_in":
        ax.set_xlim(bounds["retail"][0], bounds["retail"][1])
        ax.set_ylim(df_plot_inv_induced.min().min(),  df_plot_inv_induced.max().max())
        ax.set_xlabel('retail tariff [CHF/kWh]')
        ax.set_ylabel('investment [CHF/yr]')
        cbar.ax.set_ylabel('feed-in tariff  [CHF/kWh]')

    #ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.2), frameon=False, ncol=2)

    if save_fig == True:
        plt.tight_layout()
        format = 'png'
        plt.savefig(('PV_rainbow_CH' + '.' + format), format=format, dpi=300)
    plt.show()
    return



def return_district_result_object_dataframe(dict_results, result_dataframe):
    if result_dataframe in dir(dict_results[0][1]):
        t = {(j, k): getattr(dict_results[j][k], result_dataframe)
                for j in dict_results.keys()
                for k in dict_results[j].keys()}
    else:
        t = {(j, k): dict_results[j][k][result_dataframe]
             for j in dict_results.keys()
             for k in dict_results[j].keys()}

    df_district_results = pd.concat(t.values(), keys=t.keys(), names=['Scn_ID', 'Pareto_ID'], axis=0)
    df_district_results = df_district_results.sort_index()

    return df_district_results

def plot_rainbow_CH(Pareto_list, extrapolation=None, bounds=None, resolution=100, std_filter=1.5, plot_type="demand_feed_in_E_gen_pv"):

    if extrapolation is None:
        extrapolation = {17335: 54.5, 277: 428.55, 10559: 281.57, 14824: 98.57, 17316: 207.82}
    extrapolation = pd.DataFrame.from_dict(extrapolation, orient="Index")  # ERA CH districts mio m2
    extrapolation = extrapolation / extrapolation.sum()

    if bounds is None:
        bounds = {"feed_in": [0.0, 0.15], "retail": [0.05, 0.25]}

    PV_area = {}
    df_plot_last = {}
    df_plot_inv_induced = {}

    # get data
    for n, pareto in enumerate(Pareto_list):
        print("district:", n, " processed")
        PV_area[n] = return_district_result_object_dataframe(pareto, 'df_PV_Surface').groupby("Pareto_ID").sum().max()[0]
        df_plot_last[n], feed_in_prices, No_feed_in, df_plot_inv_induced[n] = plot_economical_feedin_price(bounds, resolution, pareto)

        # get last economic retail tariffs
        last_id = []
        for idx, col in enumerate(df_plot_last[n]):
            if df_plot_last[n][col].sum() != 0:
                last_id = np.concatenate([last_id, [df_plot_last[n][col][df_plot_last[n][col] > 0].index[-1]]])
            else:
                last_id = np.concatenate([last_id, [np.nan]])
        last_id = pd.DataFrame(last_id)
        last_id[0] = last_id[0].interpolate()


        for idx, col in enumerate(df_plot_last[n]):
            df_plot_last[n][col] = df_plot_last[n][col].replace(np.nan, 0)
            index_max_PV = df_plot_last[n][col].loc[last_id.loc[idx][0]:].index[1:]
            df_plot_last[n][col].loc[index_max_PV] = df_plot_last[n].max().max()

    # aggregate data and extrapolate to CH
    df_plot_last_CH = df_plot_last[0] * 0

    for n in PV_area:
        df_plot_last_CH = df_plot_last_CH + df_plot_last[n] / PV_area[n] * extrapolation[0].loc[n] * 140  # 140 km2 roof area usable (EnergyScope)

    df_plot_last_CH = sp.ndimage.filters.gaussian_filter(df_plot_last_CH, std_filter, mode='nearest')
    df_plot_last_CH = pd.DataFrame(df_plot_last_CH)
    df_plot_last_CH.columns = np.linspace(bounds["retail"][0], bounds["retail"][1], No_feed_in)
    df_plot_last_CH.index = np.linspace(bounds["feed_in"][0], bounds["feed_in"][1], No_feed_in)


    # create bounds
    max_value = df_plot_last_CH.max().max()

    for col in df_plot_last_CH:
        df_plot_last_CH[col].mask(df_plot_last_CH[col] < 0.3, np.nan, inplace=True)
        df_plot_last_CH[col].mask(df_plot_last_CH[col] > max_value - 0.1, np.nan, inplace=True)

    plot_rainbow(df_plot_last_CH, feed_in_prices, No_feed_in, df_plot_inv_induced, bounds, save_fig=True, plot_type=plot_type)



if __name__ == '__main__':
    pd.set_option('display.max_rows', 700)
    pd.set_option('display.max_columns', 700)
    pd.set_option('display.width', 1000)

    plot_type = ["demand_feed_in_E_gen_pv", "E_gen_pv_demand_feed_in", "invest_demand_feed_in"][0]
    resolution = 150
    bounds = {"feed_in": [0.0, 0.18], "retail": [0.05, 0.30]}


