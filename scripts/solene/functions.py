import pandas as pd
from reho.paths import *
import matplotlib.pyplot as plt
from plotly.subplots import make_subplots
import plotly.express as px
import plotly.graph_objects as go


def linear_split_bin_table(df,col,lowerbound = None, upperbound = None):
    """
    Parameters
    col : the columns to apply the change upon

    """
    if upperbound:
        if upperbound in df.index:
            df_up = df.loc[df.index <= upperbound,:].copy()
        else:
            df_up = df.loc[df.index < upperbound,:].copy()
            last_bin = df.loc[df.index > upperbound,:].iloc[0]
            last_bin[col] = (upperbound - df_up.index[-1]) / (last_bin.name - df_up.index[-1] ) * last_bin[col]
            last_bin.name = upperbound
            df_up = pd.concat([df_up,last_bin.to_frame().T])
    
    if lowerbound:
        if upperbound:
            df_up = df_up.loc[df_up.index > lowerbound,:].copy()
        else:
            df_up = df.loc[df.index > lowerbound,:].copy()

        if not lowerbound in df.index:
            prev_bin = df.loc[df.index < lowerbound,:].iloc[-1]
            weight = (df_up.index[0] - lowerbound) / (df_up.index[0] - prev_bin.name) * df_up.iloc[0][col]
            df_up.at[df_up.index[0],col] = weight

    return df_up


def mobility_demand_from_WP1data_modes(DailyDist,max_dist = 70 ,nbins = 1,modalwindow = 0.01,  share_cars = None,share_EV_infleet = None ):
    """
    Donne les shares pour les modes MD/PT/cars. Voir twin function mobility_demand_from_WP1data_units qui donne pour les units et pas pour les modes

    Parameters
    -----------
    DailyDist : DailyDist total
    max_dist :

    """
    parameters = {"DailyDist" : {},
                }
    modalshares_csv = pd.DataFrame()
    modalshares_custom = pd.DataFrame()

    df_dist = pd.read_csv(os.path.join(path_to_mobility, 'WP1_distributionofdistances.csv'), index_col = 0)
    df_modalshares = pd.read_csv(os.path.join(path_to_mobility, 'WP1_modalsharesbydistances_work.tsv'), sep = "\t",index_col = 0)
    
    # mapping_modesunits = {
    #     "Marche"   :  "Bike_district",
    #     "Vélo"        : "Bike_district",
    #     "moto"        : "ICE_district",
    #     "voiture"     : "ICE_district",
    #     "tram/bus"    : "PT_bus",
    #     "train" : "PT_train"
    # }

    mapping_modesunits = {
        "Marche"   :  "MD",
        "Vélo"        : "MD",
        "moto"        : "cars",
        "voiture"     : "cars",
        "tram/bus"    : "PT",
        "train" : "PT"
    }

    df_dist_inf = linear_split_bin_table(df_dist,"weight",upperbound=max_dist)
    df_dist_inf.weight = df_dist_inf.weight /df_dist_inf.weight.sum()

    df_dist_inf['up'] = df_dist_inf.index
    df_dist_inf['low'] =   df_dist_inf.up.shift(1).fillna(0)
    df_dist_inf['mean'] = (df_dist_inf.up + df_dist_inf.low)/2
    df_dist_inf['pkm'] = df_dist_inf['mean'] * df_dist_inf['weight']
    df_dist_inf.pkm = df_dist_inf.pkm /df_dist_inf.pkm.sum()

    df_dist_inf = df_dist_inf.join(df_modalshares)
    df_dist_inf[df_modalshares.columns] = df_dist_inf[df_modalshares.columns].fillna(method = 'bfill').fillna(method = 'ffill')

    lowerbound = 0
    step = max_dist/nbins
    for i in range(nbins):
        upperbound = lowerbound + step
        df_bin = linear_split_bin_table(df_dist_inf,"pkm",lowerbound,upperbound)
        parameters['DailyDist'][f"D{i}"] = df_bin.pkm.sum() * DailyDist

        df_ms = df_bin[df_modalshares.columns].mul(df_bin['pkm'],axis = 0).sum()
        df_ms = df_ms.div(df_ms.sum())
        df_ms.index = df_ms.index.map(mapping_modesunits)
        df_ms = df_ms.groupby(df_ms.index).agg("sum")
        # df_ms['EV_district'] = df_ms.ICE_district
        df_ms_min = df_ms.copy()
        # df_ms_min.values.fill(0)

        # df_ms['cars'] = df_ms.ICE_district 
        # df_ms_min['cars'] = df_ms.ICE_district
        # df_ms['MD'] = df_ms.Bike_district 
        # df_ms_min['MD'] = df_ms.Bike_district
        # df_ms['PT'] = (df_ms.PT_train + df_ms.PT_bus) 
        # df_ms_min['PT'] = (df_ms.PT_train + df_ms.PT_bus)      
        

        # df_ms['cars'] = 1
        # df_ms_min['cars'] = 0
        # df_ms['MD'] = 1
        # df_ms_min['MD'] = 0
        # df_ms['PT'] = 1
        # df_ms_min['PT'] = 0

        modalshares_csv[f"min_D{i}"] = df_ms_min.apply(lambda x : max(x-modalwindow,0))
        modalshares_csv[f"max_D{i}"] = df_ms.apply(lambda x : min(x+modalwindow,1))
        modalshares_custom[f"D{i}"] = df_ms

        lowerbound = upperbound

    if share_cars:
        mean_share = sum(modalshares_csv.loc["cars",modalshares_csv.columns.str.startswith("max")].values * list(parameters["DailyDist"].values()))
        mean_share = mean_share/sum(parameters["DailyDist"].values())
        modalshares_custom.loc['cars',:] = modalshares_custom.loc['cars',:].apply(lambda x : x*share_cars/mean_share)
        
        modalshares_custom = modalshares_custom.T
        modalshares_custom[['MD','PT']] = modalshares_custom.apply(lambda x : (x.MD/(x.MD + x.PT) * (1-x.cars),x.PT/(x.MD + x.PT) * (1-x.cars)),axis = 1,result_type = 'expand')
        modalshares_custom = modalshares_custom.T

        for D in modalshares_custom.columns:
            modalshares_csv[f"min_{D}"] = modalshares_custom[D].apply(lambda x : max(x-modalwindow,0))
            modalshares_csv[f"max_{D}"] = modalshares_custom[D].apply(lambda x : min(x+modalwindow,1))

    if share_EV_infleet:
        modalshares_csv = modalshares_csv.T
        modalshares_csv['EV_district'] = share_EV_infleet * modalshares_csv["cars"]
        modalshares_csv = modalshares_csv.T

    modalshares_csv.to_csv(os.path.join(path_to_mobility, "modalshares.csv"))
    return parameters


def mobility_demand_from_WP1data_units(DailyDist,max_dist = 70 ,nbins = 1,modalwindow = 0.01):
    """
    Donne les shares pour les units et les modes MD/PT/cars. Voir twin function mobility_demand_from_WP1data_modes 

    Parameters
    -----------
    DailyDist : DailyDist total
    max_dist :

    """
    parameters = {"DailyDist" : {},
                }
    modalshares_csv = pd.DataFrame()
    df_dist = pd.read_csv(os.path.join(path_to_mobility, 'WP1_distributionofdistances.csv'), index_col=0)
    df_modalshares = pd.read_csv(os.path.join(path_to_mobility, 'WP1_modalsharesbydistances_work.tsv'), sep="\t", index_col=0)

    mapping_modesunits = {
        "Marche"   :  "Bike_district",
        "Vélo"        : "Bike_district",
        "moto"        : "ICE_district",
        "voiture"     : "ICE_district",
        "tram/bus"    : "PT_bus",
        "train" : "PT_train"
    }


    df_dist_inf = linear_split_bin_table(df_dist,"weight",upperbound=max_dist)
    df_dist_inf.weight = df_dist_inf.weight /df_dist_inf.weight.sum()

    df_dist_inf['up'] = df_dist_inf.index
    df_dist_inf['low'] =   df_dist_inf.up.shift(1).fillna(0)
    df_dist_inf['mean'] = (df_dist_inf.up + df_dist_inf.low)/2
    df_dist_inf['pkm'] = df_dist_inf['mean'] * df_dist_inf['weight']
    df_dist_inf.pkm = df_dist_inf.pkm /df_dist_inf.pkm.sum()

    df_dist_inf = df_dist_inf.join(df_modalshares)
    df_dist_inf[df_modalshares.columns] = df_dist_inf[df_modalshares.columns].fillna(method = 'bfill').fillna(method = 'ffill')

    lowerbound = 0
    step = max_dist/nbins
    for i in range(nbins):
        upperbound = lowerbound + step
        df_bin = linear_split_bin_table(df_dist_inf,"pkm",lowerbound,upperbound)
        parameters['DailyDist'][f"D{i}"] = df_bin.pkm.sum() * DailyDist

        df_ms = df_bin[df_modalshares.columns].mul(df_bin['pkm'],axis = 0).sum()
        df_ms = df_ms.div(df_ms.sum())
        df_ms.index = df_ms.index.map(mapping_modesunits)
        df_ms = df_ms.groupby(df_ms.index).agg("sum")
        df_ms['EV_district'] = df_ms.ICE_district
        df_ms_min = df_ms.copy()
        df_ms_min.values.fill(0)

        df_ms['cars'] = df_ms.ICE_district 
        df_ms_min['cars'] = df_ms.ICE_district
        df_ms['MD'] = df_ms.Bike_district 
        df_ms_min['MD'] = df_ms.Bike_district
        df_ms['PT'] = (df_ms.PT_train + df_ms.PT_bus) 
        df_ms_min['PT'] = (df_ms.PT_train + df_ms.PT_bus)      
        

        modalshares_csv[f"min_D{i}"] = df_ms_min.apply(lambda x : max(x-modalwindow,0))
        modalshares_csv[f"max_D{i}"] = df_ms.apply(lambda x : min(x+modalwindow,1))

        lowerbound = upperbound

    modalshares_csv.to_csv(os.path.join(path_to_mobility, "modalshares.csv"))
    return parameters

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