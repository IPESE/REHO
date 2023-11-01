import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches

from matplotlib.lines import Line2D
from scipy.interpolate import interp1d
import math


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


def find_economic_bounds(df):

    x_first = np.array([])
    x_last = np.array([])
    for c in df.columns:
        first = df[c].first_valid_index()
        last = df [c].last_valid_index()

        #idx_f = df.index.get_loc(first)
        #if idx_f == 0:
        #    x_f = df.iloc[idx_f].name
        #else:
        #    x_f = df.iloc[idx_f-1].name

        x_first = np.append(x_first,first)
        x_last = np.append(x_last, last)
    df_aim = pd.DataFrame({'x_first':x_first, 'x_last':x_last}, index = df.columns)

    return df_aim


def find_roofs_coverage(df, roof):
    df = df.drop(columns=df.columns[df.iloc[0] > roof])
    x_array= np.array([])
    for c in df.columns:
        first = df[c].first_valid_index()
        f = interp1d(df[c].values, df.index)
        x = f(roof)
        x_array = np.append(x_array,x)
    df_aim = pd.DataFrame({'x': x_array }, index=df.columns)
    return df_aim


def plot_surfacetype(df_nbr,df_unit, hs_A,save_fig):
    PV = df_unit [df_unit.index.get_level_values('Unit').str.contains('PV')]
    PV = PV.groupby('Pareto').sum()

    CAPEX_m2 = PV.Costs_Unit_inv/hs_A

    panel_size = df_nbr.PVA_module_coverage.min()
    df_nbr['PV area'] = panel_size * df_nbr.PVA_module_nbr
    df_nbr['surface coverage'] = df_nbr.PVA_module_coverage * df_nbr.PVA_module_nbr

    df = df_nbr.groupby(['Pareto', 'Tilt']).sum()
    horizontal = df[df.index.get_level_values(level='Tilt') == 0]
    horizontal = horizontal.droplevel('Tilt')
    facades = df[df.index.get_level_values(level='Tilt') == 90]
    facades = facades.droplevel('Tilt')
    roof = df[df.index.get_level_values(level='Tilt') != 90]
    oriented_roof = roof[roof.index.get_level_values(level='Tilt') != 0]
    oriented_roof =oriented_roof.groupby('Pareto').sum()

    df_plot = pd.DataFrame()
    df_plot['horizontal roof'] = linerize_equal_steps(CAPEX_m2, horizontal['PV area'] ).y
    df_plot['oriented roof'] = linerize_equal_steps(CAPEX_m2, oriented_roof['PV area'] ).y
    df_plot['facades'] = linerize_equal_steps(CAPEX_m2, facades['PV area']).y

    df_plot = df_plot.fillna(0)
    all_roofs = roof.groupby('Pareto').sum()
    max_roof = all_roofs.max()
    max_facades = facades.max()

    roofs_coverage = all_roofs['surface coverage'] / max_roof['surface coverage']
    facades_coverage = facades['surface coverage'] / max_facades['surface coverage']

    roofs_coverage = linerize_equal_steps(CAPEX_m2, roofs_coverage)
    facades_coverage = linerize_equal_steps(CAPEX_m2, facades_coverage)
    #plotting
    fig, ax = plt.subplots(figsize=(6, 4.8))
    axx = ax.twinx()
    width = 1
    colors = {'roofs': '#2166ac', 'facades':'#67a9cf', 'oriented_roof': '#d1e5f0'}
    ax.bar(df_plot.index.values, df_plot['oriented roof'].values/hs_A,  label='roof, oriented modules', color = colors_dict[2], edgecolor = 'black')

    ax.bar(df_plot.index.values, df_plot['horizontal roof'].values/hs_A,  label='roof, horizontal modules', bottom =  df_plot['oriented roof'].values/hs_A, color =  colors_dict[5],edgecolor = 'black')

    ax.bar(df_plot.index.values,  df_plot['facades'].values/hs_A, label='facades',
           bottom=(df_plot['oriented roof'].values/hs_A+df_plot['horizontal roof'].values/hs_A), color =  colors_dict[4],edgecolor = 'black')

    roofs_coverage.at[0, 'y'] = 0
    roofs_coverage.sort_index(inplace=True)

    facades_coverage.at[0, 'y'] = 0
    facades_coverage.sort_index(inplace=True)

    axx.plot(roofs_coverage, color = colors_dict[1], label = 'roof coverage')
    axx.plot( facades_coverage, color =  colors_dict[3], label = 'facade coverage')

    ax.set_xlabel('PV investment cost [CHF/m$_{ERA}^2 \cdot yr $]')
    ax.set_ylabel('PV panels [m$^2$/m$^2_{ERA}$]')
    axx.set_ylabel('surface coverage [-]')
    axx.set_ylim(0,1.1)
    ax.legend(loc='upper center', bbox_to_anchor=(0.15, -0.2), frameon=False, ncol=1)
    axx.legend(loc='upper center', bbox_to_anchor=(0.85, -0.2), frameon=False, ncol=1)

    if save_fig == True:
        plt.tight_layout()
        format = 'pdf'
        plt.savefig((  'surface_type' +'.' + format), format=format, dpi=300)
    else:
        plt.show()

    return df_plot

def plot_gen_elec(df_Parameter, total_surface_m2,save_fig = False):
    df_p = df_Parameter.groupby('Scenario').sum()
    PV_kWyr = df_p.MWh_PV*1000/8760

    z = np.polyfit(total_surface_m2,PV_kWyr, 2)
    p =  np.poly1d(z)
    print(p)
    x_array = np.linspace(total_surface_m2.min(), total_surface_m2.max(),50)

    fig, ax = plt.subplots()
    #ax.plot(total_surface_m2, PV_kWyr , color= EPFL_red, linestyle = ':')
    ax.plot(x_array, p(x_array), color = 'black' )
    ax.set_xlabel('PV panels [m$^2$/ m$^2_{ERA}$]')
    ax.set_ylabel('$E ^{PV,gen}$ in last economic point [kWyr/yr]')

    if save_fig == True:
        plt.tight_layout()
        format = 'pdf'
        plt.savefig(('kWyr_m2' + '.' + format), format=format, dpi=300)
    else:
        plt.show()

def plot_orientation(df_nbr, hs_A, df_unit, save_fig):
    PV = df_unit [df_unit.index.get_level_values('Unit').str.contains('PV')]
    PV = PV.groupby('Pareto').sum()

    PV_m2 = PV.Costs_Unit_inv/hs_A

    panel_size = df_nbr.PVA_module_coverage.min()
    df_nbr['PV area'] = panel_size * df_nbr.PVA_module_nbr
    df_nbr['surface coverage'] = df_nbr.PVA_module_coverage * df_nbr.PVA_module_nbr
    df = df_nbr.groupby(['Pareto', 'Azimuth', 'Tilt']).sum()

    horizontal = df[df.index.get_level_values(level='Tilt') == 0]
    horizontal =    horizontal.groupby('Pareto').sum()
    horizontal = linerize_equal_steps(PV_m2, horizontal['PV area'])
    oriented = df[df.index.get_level_values(level='Tilt') != 0]
    oriented = oriented.reset_index(level = ['Azimuth','Tilt'])
    oriented['Orientation'] = oriented.apply(lambda x : split_orientation(x['Azimuth']), axis = 1)

    oriented = oriented.set_index('Orientation', append = True)
    facades = oriented[oriented['Tilt'] == 90]
    roofs = oriented[oriented['Tilt'] != 90]
    roofs = roofs.groupby(level=[0, 1]).sum()
    facades = facades.groupby(level=[0, 1]).sum()

    West_roofs = roofs.xs('West', level = 'Orientation')
    West = linerize_equal_steps(PV_m2, West_roofs['PV area'])
    South_roofs = roofs.xs('South', level='Orientation')
    South =   linerize_equal_steps(PV_m2, South_roofs['PV area'])
    East_roofs = roofs.xs('East', level='Orientation')
    East = linerize_equal_steps(PV_m2, East_roofs['PV area'])
    North_roofs = roofs.xs('North', level='Orientation')
    North =  linerize_equal_steps(PV_m2, North_roofs['PV area'])

    West_facades = facades.xs('West', level = 'Orientation')
    West_f = linerize_equal_steps(PV_m2, West_facades['PV area'])
    South_facades = facades.xs('South', level='Orientation')
    South_f = linerize_equal_steps(PV_m2, South_facades['PV area'])
    East_facades = facades.xs('East', level='Orientation')
    East_f = linerize_equal_steps(PV_m2, East_facades['PV area'])
    North_facades = facades.xs('North', level='Orientation')
    North_f = linerize_equal_steps(PV_m2, North_facades['PV area'])

    #plotting
    fig, ax = plt.subplots(figsize=(10, 4))
    ax1 = ax.twinx()
    idx =horizontal.index.values
    width = 0.3

    colors = {'horizontal': '#2166ac', 'south':'#67a9cf', 'west': '#d1e5f0', 'east': '#fddbc7', 'north':'#ef8a62'}
    colors = {'horizontal': colors_dict[1], 'south':colors_dict[2], 'west': colors_dict[3], 'east': colors_dict[5], 'north':colors_dict[4]}

    # Roofs-----
    ax.bar((idx-width), horizontal.y/hs_A,  label='horizontal',width=width, color = colors['horizontal'],edgecolor = 'black')
    ax.bar(idx, South.y/hs_A,  label='south',width=width, color = colors['south'],edgecolor = 'black')
    ax.bar(idx, West.y/hs_A,  label='west', bottom =  South.y/hs_A, width=width, color = colors['west'],edgecolor = 'black')
    ax.bar(idx, East.y/hs_A,  label='east', bottom = (South.y+West.y)/hs_A,width=width,  color = colors['east'],edgecolor = 'black')
    ax.bar(idx, North.y/hs_A, label='north', bottom=(South.y + West.y+East.y)/hs_A,width=width,  color=colors['north'],edgecolor = 'black')

    # Facades-----
    ax.bar((idx+width), South_f.y/hs_A,width=width,hatch= '\\\\', color=colors['south'],edgecolor = 'black')
    ax.bar((idx+width), West_f.y/hs_A, bottom= South_f.y/hs_A, width=width, color=colors['west'],hatch= '\\\\',edgecolor = 'black')
    ax.bar((idx+width), East_f.y/hs_A,  bottom= (South_f.y + West_f.y)/hs_A, width=width, color=colors['east'],hatch= '\\\\',edgecolor = 'black')
    ax.bar((idx+width), North_f.y/hs_A, bottom= (South_f.y + West_f.y + East_f.y)/hs_A, width=width, color=colors['north'],hatch= '\\\\',edgecolor = 'black')

    ax.set_xticks(idx.round(1))
    ax.set_xlabel('PV investment cost [CHF/ m$^2_{ERA} \cdot yr$ ]')
    ax.set_ylabel('PV panels [m$^2$/ m$^2_{ERA}$]')

    ax.legend(loc='upper center', bbox_to_anchor=(0.2, -0.2), frameon=False, ncol=3)
    circ2 = mpatches.Patch(facecolor='white',  edgecolor = 'black', hatch=r'\\\\', label='facades')
    circ1 = mpatches.Patch(facecolor='white',  edgecolor = 'black',label='roof')
    ax1.legend(handles=[circ1, circ2],  loc='upper center', bbox_to_anchor=(0.8, -0.2), frameon=False, ncol=2)

    if save_fig == True:
        plt.tight_layout()
        format = 'pdf'
        plt.savefig((  'surface_direction' +'.' + format), format=format, dpi=300)
    else:
        plt.show()

def plot_roofs_difference(save_fig = False):
    index_dec = np.array([ 0.        ,  0.04886507,  1.38464427,  3.03571922,  4.65111638,
        6.27173878,  7.90589409,  9.58227119, 11.24572972, 12.7887025 ,
       14.13185107, 15.06501024, 15.62314813, 15.73976427])
    dec_roofs = np.array([0.        , 0.00108009, 0.11643364, 0.39843414, 0.64539651,
       0.89035357, 0.98129153, 0.99894526, 1.        , 1.        ,
       1.        , 1.        , 1.        , 1.        ])
    dec_facades = np.array([0.00000000e+00, 0.00000000e+00, 0.00000000e+00, 0.00000000e+00,
       5.19643115e-04, 4.01793770e-02, 1.74204892e-01, 3.43910172e-01,
       5.20813627e-01, 6.85336510e-01, 8.28552695e-01, 9.28052856e-01,
       9.87565540e-01, 1.00000000e+00])

    index_cen = np.array([ 0. ,  0.99367998,  2.97739579,  5.20059912,  7.53919993,
        9.88993299, 12.11380631, 14.20393584, 15.26565466, 15.7398966 ])
    cen_roofs = np.array([0. , 0.18790761, 0.52842439, 0.75434397, 0.9135417 ,
       0.99999541, 1., 1., 0.9999939 , 1. ])
    cen_facades = np.array([0. , 0. , 0. , 0.07621941, 0.20187081,
       0.37621794, 0.61334846, 0.83621986, 0.94943408, 1. ])

    fig, ax = plt.subplots(figsize=(6, 4.8))
    axx = ax.twinx()

    ax.plot(index_cen, cen_roofs, color=colors_dict[1], label='roof')
    ax.plot(index_cen, cen_facades, color=colors_dict[3],label='facade')
    ax.plot(index_dec, dec_roofs, linestyle = '--', color=colors_dict[1])
    ax.plot(index_dec, dec_facades,linestyle = '--',  color=colors_dict[3])

    ax.set_xlabel('PV investment cost [CHF/m$_{ERA}^2 \cdot yr $]')
    ax.set_ylabel('surface coverage [-]')

    ax.legend( title = 'surface coverage', bbox_to_anchor=(0.3, -0.2), frameon=False,)
    custom_lines = [Line2D([0], [0], color='black', linewidth=1.5,),
                    Line2D([0], [0], color='black', linewidth=1.5, linestyle='--')
                    ]
    axx.legend(custom_lines, ['centralized', 'building-scale'],
              bbox_to_anchor=(1, -0.2), frameon=False, ncol = 1, title = 'optimization strategy')
    axx.set_axis_off()

    if save_fig == True:
        plt.tight_layout()
        format = 'pdf'
        plt.savefig(('surface_type_diff' + '.' + format), format=format, dpi=300)
    else:
        plt.show()
    return

def plot_horizontal_roofs(df_nbr, df_unit, hs_A, save_fig):

    PV = df_unit [df_unit.index.get_level_values('Unit').str.contains('PV')]
    PV = PV.groupby('Pareto').sum()
    CAPEX_m2 = PV.Costs_Unit_inv/hs_A

    panel_size = df_nbr.PVA_module_coverage.min()
    df_nbr['PV area'] = panel_size * df_nbr.PVA_module_nbr
    df_nbr['surface coverage'] = df_nbr.PVA_module_coverage * df_nbr.PVA_module_nbr
    horizontal_roofs = df_nbr[df_nbr.index.get_level_values(level='Tilt') == 0]
    h_index = horizontal_roofs.index.get_level_values('Surface')

    df = df_nbr.reset_index(level='Surface')
    df_h = df.loc[df['Surface'].isin(h_index)]
    df = df_h.groupby(['Pareto', 'Tilt']).sum()

    horizontal = df[df.index.get_level_values(level='Tilt') == 0]
    horizontal = horizontal.droplevel('Tilt')
    roof = df[df.index.get_level_values(level='Tilt') != 90]
    oriented_roof = roof[roof.index.get_level_values(level='Tilt') != 0]
    oriented_roof =oriented_roof.groupby('Pareto').sum()

    df_plot = pd.DataFrame()
    df_plot['horizontal roof'] = linerize_equal_steps(CAPEX_m2, horizontal['PV area'] ).y
    df_plot['oriented roof'] = linerize_equal_steps(CAPEX_m2, oriented_roof['PV area'] ).y

    df_plot = df_plot.fillna(0)
    all_roofs = roof.groupby('Pareto').sum()
    max_roof = all_roofs.max()
    roofs_coverage = all_roofs['surface coverage'] / max_roof['surface coverage']
    roofs_coverage = linerize_equal_steps(CAPEX_m2, roofs_coverage)

    #plotting
    fig, ax = plt.subplots(figsize=(6, 4.8))
    axx = ax.twinx()
    width = 1
    colors = {'roofs': '#2166ac', 'facades':'#67a9cf', 'oriented_roof': '#d1e5f0'}
    ax.bar(df_plot.index.values, df_plot['oriented roof'].values/hs_A,  label='roof, oriented modules', color = colors_dict[2], edgecolor = 'black')
    ax.bar(df_plot.index.values, df_plot['horizontal roof'].values/hs_A,  label='roof, horizontal modules', bottom =  df_plot['oriented roof'].values/hs_A, color =  colors_dict[5],edgecolor = 'black')

    roofs_coverage.at[0, 'y'] = 0
    roofs_coverage.sort_index(inplace=True)
    axx.plot(roofs_coverage, color = colors_dict[1], label = 'roof coverage')
    ax.set_xlabel('PV investment cost [CHF/m$_{ERA}^2 \cdot yr $]')
    ax.set_ylabel('PV panels [m$^2$/m$^2_{ERA}$]')
    axx.set_ylabel('surface coverage [-]')
    axx.set_ylim(0,1.1)

    ax.legend(loc='upper center', bbox_to_anchor=(0.15, -0.2), frameon=False, ncol=1)
    axx.legend(loc='upper center', bbox_to_anchor=(0.85, -0.2), frameon=False, ncol=1)

    if save_fig == True:
        plt.tight_layout()
        format = 'pdf'
        plt.savefig((  'roof_type' +'.' + format), format=format, dpi=300)
    else:
        plt.show()
    return

def max_grid_exchange(df_g, total_surface_m2, save_fig = False):
    idx = total_surface_m2
    df = df_g.xs([31, 0, 'Electricity', 'Network'], level=['egid', 'GM', 'Layer', 'House'])
    df_d = pd.DataFrame(df.Grid_demand)
    df_d_m =df_d.groupby(['Pareto']).max()
    df_s = pd.DataFrame(df.Grid_supply)
    df_s = df_s.drop(12, level='Period')
    df_s = df_s.drop(11, level='Period')
    df_s_max =-df_s.groupby(['Pareto']).max()

    fig, ax = plt.subplots(figsize=(6, 4.8))
    ax.plot(idx, df_d_m, color = 'black')
    ax.plot(idx, df_s_max, color = 'black')
    ax.set_xlabel('PV panels [m$_{PV}^2$/m$_{ERA}^2$]')
    ax.set_ylabel('electricity [kWh/h]')

    if save_fig == True:
        plt.tight_layout()
        format = 'pdf'
        plt.savefig(('Grid_capacity' + '.' + format), format=format, dpi=300)
    else:
        plt.show()
    return


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

colors_dict = {0:'black', 1: EPFL_red, 2:EPFL_light_grey, 3:Salmon, 4:EPFL_leman, 5:EPFL_canard}

