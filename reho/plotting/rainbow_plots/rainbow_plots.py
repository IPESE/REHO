import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import interp1d
import math
import pickle

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

def get_roof_max( df_nbr):

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


def plot_economical_feedin_price(df_KPI, df_unit, total_surface_m2, bounds, roof_max_m2, SS, CN, plot_type, resolution, save_fig):

    # some data processing
    MWh_PV = {}
    for i in Pareto[0]:
        if "df_Annuals" in dir(Pareto[0][1]):
            id = ["PV" in id for id in Pareto[0][i]["df_Annuals"].xs("Electricity")["Supply_MWh"].index]
            MWh_PV[i] = Pareto[0][i]["df_Annuals"].xs("Electricity")["Supply_MWh"][id].sum()
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

    PV_kWyr = MWh_PV * 1000 / 8760
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

    # plotting
    fig, ax = plt.subplots()
    for demand_price in df_plot_last.columns:
        if plot_type == "demand_feed_in_E_gen_pv":
            cs = ax.scatter(feed_in_prices, np.repeat(demand_price, No_feed_in), c=df_plot_last[demand_price].values, s=5, cmap=cm, vmin = df_plot_last.min().min(), vmax = df_plot_last.max().max() )
        elif plot_type == "E_gen_pv_demand_feed_in":
            cs = ax.scatter(np.repeat(demand_price, No_feed_in), df_plot_last[demand_price].values, c=feed_in_prices, s=5, cmap=cm, vmin = min_feed, vmax = max_feed)
        elif plot_type == "invest_demand_feed_in":
            cs = ax.scatter(np.repeat(demand_price, No_feed_in), df_plot_inv_induced[demand_price].values, c=feed_in_prices, s=5, cmap=cm, vmin=min_feed, vmax=max_feed)

    ax.annotate(' all PV investments \n economic', (0.1, 0.22), zorder=10)
    cbar = fig.colorbar(cs)

    if plot_type == "demand_feed_in_E_gen_pv":
        ax.set_xlim(min_feed, max_feed)
        ax.set_ylim(min_demand, max_demand)
        ax.set_xlabel('feed-in price  [CHF/kWh]')
        ax.set_ylabel('demand price [CHF/kWh]')
        cbar.ax.set_ylabel('$E ^{gen}_{PV}$ in last economic point [kWyr/yr]')

    elif plot_type == "E_gen_pv_demand_feed_in":
        ax.set_xlim(min_demand, max_demand)
        ax.set_ylim(df_plot_last.min().min(), df_plot_last.max().max())
        ax.set_xlabel('demand price [CHF/kWh]')
        ax.set_ylabel('$E ^{gen}_{PV}$ in last economic point [kWyr/yr]')
        cbar.ax.set_ylabel('feed-in price  [CHF/kWh]')

    elif plot_type == "invest_demand_feed_in":
        ax.set_xlim(min_demand, max_demand)
        ax.set_ylim(df_plot_inv_induced.min().min(),  df_plot_inv_induced.max().max())
        ax.set_xlabel('demand price [CHF/kWh]')
        ax.set_ylabel('investment [CHF/yr]')
        cbar.ax.set_ylabel('feed-in price  [CHF/kWh]')

    #ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.2), frameon=False, ncol=2)

    if save_fig == True:
        plt.tight_layout()
        format = 'png'
        plt.savefig(('Tarifs_lasteconomic' + '.' + format), format=format, dpi=300)
    else:
        plt.show()
    return


def plot_cinv_kWh(df_KPI,df_unit, total_surface_m2, roof_max_m2, save_fig):
    MWh_PV = pd.DataFrame([Pareto[0][i]["df_Annuals"].xs("Electricity")["Supply_MWh"][-n_house:].sum() for i in Pareto[0]])[0]
    PV_kWyr = MWh_PV*1000/8760
    PV = df_unit [df_unit.index.get_level_values('Unit').str.contains('PV')]
    PV = PV.groupby('Pareto_ID').sum()

    PV_CHF = PV.Costs_Unit_inv
    PV_kWyr.index = PV_CHF.index
    PV_CHF_kWyr = PV_CHF/ PV_kWyr
    df_K = df_KPI.xs((0, 'Network'), level=('Scn_ID', 'Hub'))

    SC = df_K.SC
    MWh_SC = MWh_PV.mul(SC)
    MWh_exp = MWh_PV- MWh_SC
    MWh_exp = MWh_exp.fillna(0)

    AR_CHF_KWyr = (MWh_exp*0.08*1000 + MWh_SC*0.20*1000)/ PV_kWyr
    AR_0_feed = (MWh_exp*0.0 *1000 + MWh_SC*0.25*1000)/ PV_kWyr
    AR_10_feed = (MWh_exp* 0.08 * 1000 + MWh_SC * 0.15 * 1000) / PV_kWyr

    df_plot = pd.DataFrame()
    df_plot['AR'] = linerize_equal_steps(total_surface_m2,AR_CHF_KWyr).y
    df_plot['PV_CHF'] = linerize_equal_steps(total_surface_m2, PV_CHF_kWyr).y
    df_plot['AR_0_feed']= linerize_equal_steps(total_surface_m2,AR_0_feed ).y
    df_plot['AR_10_feed']= linerize_equal_steps(total_surface_m2,AR_10_feed ).y

    # plotting
    fig, ax = plt.subplots(figsize=(6, 4.8))
    ax.plot(df_plot.index, df_plot.PV_CHF, color=colors_dict[3], label='PV investment')
    ax.plot(df_plot.index, df_plot.AR, color=colors_dict[4], label='Annual Revenues (AR)')
    ax.plot(df_plot.index, df_plot.AR_0_feed,color=colors_dict[4],linestyle=':', label='AR- Tariffs 0ct/25ct')
    ax.plot(df_plot.index, df_plot.AR_10_feed,color=colors_dict[4],linestyle='--',  label='AR- Tariffs 8ct/15ct')

    ax.scatter(0.88, 925, color='grey', zorder= 10) #cogen
    ax.annotate('A', (0.87, 970), fontsize=14)

    ax.scatter(0.7, 850, color='grey', zorder=10)  # cogen
    ax.annotate('B', (0.7, 760), fontsize=14)

    ax.axvline(roof_max_m2, linestyle='--', color='grey', alpha=0.6)
    ax.text(roof_max_m2 + 0.02, 1400 , r'available roof area', color='grey')

    ax.set_xlabel('PV panels [m$_{PV}^2$/m$_{ERA}^2$]')
    ax.set_ylabel('CHF per  $E ^{gen}_{PV}$ [ CHF/ (kWyr/yr)]')
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.2), frameon=False, ncol=2)
    if save_fig == True:
        plt.tight_layout()
        format = 'pdf'
        plt.savefig(('AR_Inv_PVlab_profiles_cogen_only' + '.' + format), format=format, dpi=300)
    else:
        plt.show()

    fig, ax = plt.subplots(figsize=(6, 4.8))
    ax.plot(df_plot.index, df_plot.AR- df_plot.PV_CHF, color=colors_dict[4], label='Annual benefits- current Tarrifs (8ct/20ct)')
    ax.plot(df_plot.index, df_plot.AR_0_feed- df_plot.PV_CHF, color=colors_dict[4], linestyle=':', label='Annual benefits- Tariffs 0ct/25ct')
    ax.plot(df_plot.index, df_plot.AR_10_feed- df_plot.PV_CHF, color=colors_dict[4], linestyle='--', label='Annual benefits- Tariffs 8ct/15ct')

    ax.scatter(0.975,0, color='grey', zorder= 10)
    ax.annotate('A', (0.975, 20), fontsize=14)

    ax.scatter(0.745, 0, color='grey', zorder=10)
    ax.annotate('B', (0.745, 20), fontsize=14)

    ax.axvline(roof_max_m2, linestyle='--', color='grey', alpha=0.6)
    ax.text(roof_max_m2 + 0.02, 600, r'available roof area', color='grey')

    ax.axhline(0, color='black')
    ax.set_xlabel('PV panels [m$_{PV}^2$/m$_{ERA}^2$]')
    ax.set_ylabel('CHF per  $E ^{gen}_{PV}$ [ CHF/ (kWyr/yr)]')
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.2), frameon=False, ncol=1)
    if save_fig == True:
        plt.tight_layout()
        format = 'pdf'
        plt.savefig(('benefits_PVlab_boiler' + '.' + format), format=format, dpi=300)
    else:
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

if __name__ == '__main__':
    pd.set_option('display.max_rows', 700)
    pd.set_option('display.max_columns', 700)
    pd.set_option('display.width', 1000)
cm = plt.cm.get_cmap('Spectral')

EPFL_light_grey=  '#CAC7C7'
EPFL_red=  '#FF0000'
EPFL_leman = '#00A79F'
EPFL_canard = '#007480'
Salmon =  '#FEA993'

colors_dict = {0:'black', 1: EPFL_red, 2: EPFL_light_grey, 3: Salmon, 4: EPFL_leman, 5: EPFL_canard}

n = [277, 10559, 14824, 17316, 17335][0]
picklename = 'Pareto_DWD' + str(n) + '.pickle'
with open('../../shared_executables_REHO/plotting/ECOS paper/2023/results/' + picklename, 'rb') as f:
    Pareto = pickle.load(f)
Pareto = Pareto[n].results

df_u = return_district_result_object_dataframe(Pareto, 'df_Unit')
df_g = return_district_result_object_dataframe(Pareto, 'df_Grid_t')

#df_irr = UF.return_district_result_object_dataframe(Pareto, 'df_PV_Surface_profiles')
df_t = return_district_result_object_dataframe(Pareto, 'df_Time')
df_t = df_t.groupby(level=['Period']).mean()

df_KPI = return_district_result_object_dataframe(Pareto, 'df_KPI')
hs_A = return_district_result_object_dataframe(Pareto, 'df_Buildings')["ERA"].xs(1, level=1).sum()

df_nbr = return_district_result_object_dataframe(Pareto, '["df_PV_orientation"]') # df_PVA_module_nbr, ["df_PV_orientation"]
total_surface_m2, roof_max_m2 = get_roof_max(df_nbr)

n_house = len(return_district_result_object_dataframe(Pareto, 'df_Buildings')["ERA"].xs(1, level=1))
plt.rcParams.update({'font.size': 10})

m2_SS = 0.39
m2_carbon_neutral = 0.40
plot_type = ["demand_feed_in_E_gen_pv", "E_gen_pv_demand_feed_in", "invest_demand_feed_in"][0]
resolution = 50
bounds = {"feed_in": [0.0, 0.15], "retail": [0.05, 0.25]}
#plot_cinv_kWh(df_KPI, df_u, total_surface_m2, roof_max_m2,save_fig= False)
plot_economical_feedin_price(df_KPI, df_u,  total_surface_m2, bounds, roof_max_m2, m2_SS, m2_carbon_neutral, plot_type, resolution, save_fig= False)





#df_m2 = plot_surfacetype(df_nbr, df_u, hs_A.values[0], save_fig=False)
#plot_gen_elec(df_Parameter, total_surface_m2,save_fig=True)
#plot_orientation(df_nbr, hs_A.values[0], df_u, save_fig=False)
#plot_roofs_difference(save_fig=False)
#plot_horizontal_roofs(df_nbr, df_u, hs_A.values[0], save_fig=False)
#max_grid_exchange(df_g)