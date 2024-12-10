import pandas as pd

from reho.paths import *
from reho.model.reho import *

import matplotlib.pyplot as plt
from plotly.subplots import make_subplots
import plotly.express as px
import plotly.graph_objects as go

# Support file for the scripts related to the mobility paper
# Ex : SA_1district.py, SA_cooptimisation.py, DailyDist_linearoptim.py, share_carslinearoptim.py


def compute_district_parameters(district_parameters):
    """
    Remplit le dict district_parameters à partir des données du clustering. Données nécessaires : nombre de maison dans le cluster N_house, la surface du cluster Scluster (ERA) et les valeurs rho (service, industry, household)
    
    Parameters
    ---------
    district_parameters : dict or dataframe
        One entry per district, containing a dict of parameters of the district. 
        ou alors un dataframe avec les données en colonnes et en index le nom du transformeur. 

    Returns
    ---------
    modified_parameters : dict
        modified dictionnary
    """
    # Casting to df
    if isinstance(district_parameters,dict):
        df = pd.DataFrame()
        for k in district_parameters.keys():
            cols = district_parameters[k]['rho']
            cols.index = [f"rho_{x}" for x in cols.index]
            cols.name = k
            cols['Scluster'] = district_parameters[k]['Scluster']
            cols['N_house'] = district_parameters[k]['N_house']
            df = df.join(cols,how = "outer")
        df = df.T
        modified_parameters = district_parameters
    elif isinstance(district_parameters,pd.DataFrame):
        modified_parameters = dict()
        try : 
            df = district_parameters[["N_house", 'rho_household', 'rho_industry', 'rho_service', 'scale-up',"Scluster"]].copy()
            df = df.rename(columns={"Scluster":"Sdistrict"})
            df = df.rename(columns={"scale-up":"Scluster"})
        except:
            try:
                df = district_parameters[["N_house",'rho_household', 'rho_industry', 'rho_service', 'ERA_m2']].copy()
                df = df.rename(columns={"ERA_m2":"Scluster"})
            except:
                raise ValueError("Mislabelled or missing columns in the dataframe. Should contain ['N_house', 'rho_household', 'rho_industry', 'rho_service'] and (['Scluster'] OR ['ERA_m2']) ")

    # Calculate the parameters
    df['Pop'] = df['Sdistrict'] * df['rho_household'] / 46.5 # 46.5 m² per person on average
    df['PopHouse'] = df['Pop']/df['N_house']
    df['f'] = df['Scluster'].mul(10**6)/ df['Sdistrict']

    # Casting to dict of parameters
    for d in df.index:
        modified_parameters[d] = {
            "PopHouse" : df.loc[d,"PopHouse"],
            "f" : df.loc[d,"f"],
            "Scluster" : df.loc[d,"Scluster"],
            "Sdistrict" : df.loc[d,"Sdistrict"],
        }

        rho = df.loc[d,df.columns.str.startswith('rho')]
        rho.index = [x[4:] for x in rho.index]
        rho = rho/rho.sum()
        modified_parameters[d]["rho"] = rho
    
    return modified_parameters

def calculate_modal_shares(results):
    """
    Parameters
    ---------
    results : dict of df
        de la forme reho.results['totex_1'][0]
    """
    df_unit_t = results['df_Unit_t']
    df_grid_t = results['df_Grid_t']

    df_shares = df_unit_t.xs('Mobility')['Units_supply'].copy()
    df_shares = df_shares.unstack(level = 'Unit')
    df_shares = df_shares.join(df_grid_t.xs(('Mobility','Network'))[['Grid_supply','Domestic_energy']])
    df_shares = df_shares.groupby('Period').agg('sum')
    df_shares.loc[:,~df_shares.columns.str.contains('Domestic_energy')] = df_shares.loc[:,~df_shares.columns.str.contains('Domestic_energy')].div(df_shares.Domestic_energy,axis = 0)

    if "EV_charger_district" in df_shares.columns:
        df_shares = df_shares.drop('EV_charger_district',axis = 1)

    return df_shares

def plot_pkm(results,run_label = ""):
    """
    results : reho.results[Scn_ID][Pareto_ID] ex: reho.results['totex'][0]

    run_label : used for the title of the graph
    """
    # dataframe
    df_Unit_t = results['df_Unit_t']
    df_Grid_t = results['df_Grid_t']

    df_Unit_t_pkm = df_Unit_t[df_Unit_t.index.get_level_values("Layer") == "Mobility"]
    df_Grid_t_pkm = df_Grid_t[(df_Grid_t.index.get_level_values("Layer") == "Mobility") & (df_Grid_t.index.get_level_values("Hub") == "Network") ]
    df_Grid_t_pkm.reset_index("Hub", inplace=True)

    df_pkm = df_Unit_t_pkm[['Units_supply']].unstack(level='Unit')
    df_pkm['PT'] = df_Grid_t_pkm['Grid_supply']
    df_pkm['Domestic_energy'] = df_Grid_t_pkm['Domestic_energy']

    modes = [x if y=="" else y.strip('_district') for x,y in df_pkm.columns]
    colors = dict()
    for m,c in zip(modes,px.colors.qualitative.Plotly):
        colors[m] = c

    # plot
    # fig, axs = plt.subplots(2, 5,sharey=True,figsize  = (15,10))
    fig = make_subplots(rows=2, cols=5, shared_yaxes= True,
                        shared_xaxes=True,subplot_titles = range(1,11))
    # for axe,i in zip(axs.ravel(),range(1,11)):
    for (r,c),i in zip(fig._get_subplot_coordinates(),range(1,11)):
        df_plot = df_pkm.xs(level="Period",key = i).applymap(lambda x: max(x, 0))
        df_plot.columns = [x if y=="" else y.strip('_district') for x,y in df_plot.columns]
        # df_plot.loc[:,df_plot.columns != 'Domestic_energy'].plot.area(ax=axe)
        df_plot = df_plot.loc[:,df_plot.columns != 'Domestic_energy']
        df_plot = df_plot.droplevel("Layer")
        for mode in df_plot:
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot[mode].values, mode='lines', 
                                     name=mode,marker=dict(color=colors[mode]),stackgroup='one'),
                            row=r, col=c)

        # px.line(df_plot.loc[:,df_plot.columns != 'Domestic_energy'],row = row, col = col)
    # plt.show()
    fig.update_layout(title_text=f"{run_label} - Mobility demand [pkm]")
    return df_pkm,fig

def remove_nan_QBuilding(buildings_data):
    for bui in buildings_data["buildings_data"]:
        bui_class = buildings_data["buildings_data"][bui]["id_class"]
        buildings_data["buildings_data"][bui]["id_class"] = buildings_data["buildings_data"][bui]["id_class"].replace("nan", "II")
        buildings_data["buildings_data"][bui]["id_class"] = buildings_data["buildings_data"][bui]["id_class"].replace("VIII", "III")
        buildings_data["buildings_data"][bui]["ratio"] = buildings_data["buildings_data"][bui]["ratio"].replace("nan", "0.0")
        if bui_class != buildings_data["buildings_data"][bui]["id_class"]:
            print(bui, "had nan class and was", bui_class)
        if math.isnan(buildings_data["buildings_data"][bui]["U_h"]):
            buildings_data["buildings_data"][bui]["U_h"] = 0.00181
        if math.isnan(buildings_data["buildings_data"][bui]["HeatCapacity"]):
            buildings_data["buildings_data"][bui]["HeatCapacity"] = 120
        if math.isnan(buildings_data["buildings_data"][bui]["T_comfort_min_0"]):
            buildings_data["buildings_data"][bui]["T_comfort_min_0"] = 20
    return buildings_data

def filter_data(reho, s):
    for i in reho.results[f'S{s + 1}']:
        df_Unit_t_local = reho.results[f'S{s + 1}'][i]["df_Unit_t"]
        reho.results[f'S{s + 1}'][i]["df_Unit_t"] = df_Unit_t_local[df_Unit_t_local.index.get_level_values("Unit").str.contains("district")]
        df_Grid_t_local = reho.results[f'S{s + 1}'][i]["df_Grid_t"]
        reho.results[f'S{s + 1}'][i]["df_Grid_t"] = df_Grid_t_local[["Grid_demand", "Grid_supply"]]
        reho.results[f'S{s + 1}'][i]["df_Grid_t_net"] = df_Grid_t_local.xs("Network", level="Hub")
    return reho