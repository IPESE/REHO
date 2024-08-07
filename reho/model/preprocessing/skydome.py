import numpy as np
import pandas as pd
import math
from datetime import timedelta
from reho.paths import *
import itertools as it
import matplotlib.pyplot as plt

__doc__ = """
Generates a skydome decomposition into patches for PV orientation.
"""


def convert_results_txt_to_csv(load_timesteps):
    """
    Loads one txt file for each hour/timestep in "load_timesteps".
    txt file contains oriented irradiation of each 145 skypatches.
    Combines all hours to one df.
    """

    df = pd.DataFrame()
    for ts in load_timesteps:
        result_file = os.path.join(path_to_skydome, 'results' + str(ts) + '.txt')

        gh_result = np.loadtxt(result_file)
        gh_result = gh_result.reshape(-1, len(gh_result))  # column to row

        df_hour = pd.DataFrame(gh_result, index=[int(ts)])
        df = pd.concat([df, df_hour])

    t1 = pd.to_datetime('1/1/2005', dayfirst=True, infer_datetime_format=True)

    # hour 1 is between 0:00 - 1:00 and is indexed with starting hour so 0:00
    for h in df.index.values:
        df.loc[h, 'time'] = t1 + timedelta(hours=(int(h) - 1))

    df = df.set_index('time')
    output_file = os.path.join(path_to_skydome, 'total_irradiation.csv')
    df.to_csv(output_file)
    print(df)


def skydome_to_df(local_data):
    """
    Reads two txt files: one containing the area and one the position of the center point of the 145 patches,
    which define the skydome. Calculates basic additional values and returns all data in one single df

    The irradiation dome is defined as a composition of patches, defined by their area and their centroids. Those
    patches do not depend on the location. The sky is always decomposed the same way, as done by
    `Lady Bug tool <https://www.ladybug.tools/ladybug/docs/index.html>`_.

    Returns
    -------
       pd.DataFrame
    """
    df_area = local_data["df_Area"]  # area of patches
    df_cenpts = local_data["df_Cenpts"]  # location of centre points

    df_dome = pd.DataFrame()
    df_dome['Area'] = df_area[0]
    df_dome['X'] = df_cenpts[0]
    df_dome['Y'] = df_cenpts[1]
    df_dome['Z'] = df_cenpts[2]

    # Add basic caluclations
    df_dome['XY'] = df_dome[['X', 'Y']].apply(f_sqrt, axis=1)
    df_dome['XYZ'] = df_dome[['XY', 'Z']].apply(f_sqrt, axis=1)
    df_dome['Sin_e'] = round(df_dome['Z'] / df_dome['XYZ'], 4)
    df_dome['Cos_e'] = round(df_dome['XY'] / df_dome['XYZ'], 4)
    df_dome['Cos_a'] = round(df_dome['Y'] / df_dome['XY'], 4)
    df_dome['Sin_a'] = round(df_dome['X'] / df_dome['XY'], 4)
    df_dome['azimuth'] = df_dome[['X', 'Y']].apply(f_atan, axis=1)
    df_dome['elevation'] = df_dome[['Z', 'XY']].apply(f_atan, axis=1)

    return df_dome


def irradiation_to_df(ampl, df_irradiation, df_time):
    """reads Irradiation values of all 145 for the timesteps given in the csv file.
     Converts them to float and returns them as df"""

    # change column name from string to int
    df_irradiation.columns = df_irradiation.columns.astype(int)
    # change values from string to float
    df_irradiation = df_irradiation.infer_objects()

    # parse index as datetime
    df_irradiation.index = pd.to_datetime(df_irradiation.index)

    # get relevant cluster information
    PeriodDuration = ampl.getParameter('TimeEnd').getValues().toPandas()

    # construct Multiindex
    df_p = pd.DataFrame()
    list_timesteps = []

    for p in df_time.index:
        date1 = df_time.xs(p).Date
        end = PeriodDuration.xs(p + 1).TimeEnd  # ampl starts at 1

        date2 = date1 + timedelta(hours=int(end) - 1)
        df_period = df_irradiation.loc[date1:date2]

        for t in np.arange(1, int(end) + 1):  # ampl starts at 1
            list_timesteps.append((p + 1, t))  # create ampl index

        df_p = pd.concat([df_p, df_period])

    idx = pd.MultiIndex.from_tuples(list_timesteps)

    # marry index and data
    df_irradiation = df_p.set_index(idx)

    df = df_irradiation.stack()
    df = df.reorder_levels([2, 0, 1])
    df = pd.DataFrame(df)
    df = df.rename(columns={0: 'Irr'})
    return df


def irradiation_to_df_general(df_irradiation):
    """reads Irradiation values of all 145 for the timesteps given in the csv file.
     Converts them to float and returns them as df"""

    # change column name from string to int
    df_irradiation.columns = df_irradiation.columns.astype(int)
    # change values from string to float
    df_irradiation = df_irradiation.infer_objects()

    return df_irradiation


def irradiation_to_typical_df(typical_days_string, df_profiles):
    """reads Irradiation values of all 145 for the timesteps given in the csv file.
     Converts them to float and returns them as df"""

    df_profiles.set_index('time', inplace=True)
    df_profiles.index = pd.to_datetime(df_profiles.index)

    # select typical days, keep typday index as reference
    df_typical = pd.DataFrame()
    for i, td in enumerate(typical_days_string):
        df_typical = pd.concat([df_typical, df_profiles[td]], sort=True)

    # save profiles in csv
    df_typical.to_csv(os.path.join(path_to_skydome, 'typical_irradiation.csv'))

    return df_typical


def f_sqrt(x):
    """
    Calculates the square root of a vector with two elements
    """
    return math.hypot(x[0], x[1])


def f_atan(x):
    """
    math.atan2(y, x) : Returns atan(y / x), in radians. The result is between -pi and pi. The vector in the plane from
    the origin to point (x, y) makes this angle with the positive X axis. The point of atan2() is that the signs of both
    inputs are known to it, so it can compute the correct quadrant for the angle. For example, atan(1) and atan2(1, 1)
    are both pi/4, but atan2(-1, -1) is -3*pi/4.
    ATTENTION: skydome is clockwise and uses the angle with positive Y axis, so x[0] has to be X and x[1] the Y value
    """
    x[0] = round(x[0], 8)
    x[1] = round(x[1], 8)
    azimuth = math.degrees(math.atan2(x[0], x[1]))

    if azimuth < 0:
        azimuth = azimuth + 360
    else:
        azimuth = azimuth

    return int(round(azimuth))


def f_cos(x):
    a1 = math.radians(x[0])
    a2 = math.radians(x[1])  # cos(-a) = cos(a)
    return math.cos(a1 - a2)


def calc_orientation_profiles(azimuth, tilt, design_lim_angle, local_data, typical_frequency):
    cos_a = round(math.cos(math.radians(azimuth)), 8)
    sin_a = round(math.sin(math.radians(azimuth)), 8)
    sin_y = round(math.sin(math.radians(tilt)), 8)
    cos_y = round(math.cos(math.radians(tilt)), 8)
    print('PANEL ORIENTATION: azimuth ', azimuth, ', tilt ', tilt)

    df_dome = skydome_to_df(local_data)
    df_irradiation = irradiation_to_df_general(local_data["df_Irradiation"])

    df_irradiation_pos = pd.DataFrame()
    df_irradiation_neg = pd.DataFrame()
    for pt in df_irradiation.columns.values:

        azi_pt = df_dome.xs(pt)['azimuth']
        ele_pt = df_dome.xs(pt)['elevation']
        # ------------------------------
        # piecewise linerization skydome
        # ------------------------------
        delta_azi = np.cos(np.radians(azi_pt - azimuth))
        if delta_azi > 0:
            lim_angle = np.rad2deg(np.arctan(delta_azi * np.tan(np.radians(design_lim_angle))))
        else:
            lim_angle = -1

        if (lim_angle > (ele_pt - 6)) & (lim_angle < (ele_pt + 6)):
            linear_factor = 1 - ((lim_angle - (ele_pt - 6)) / 12)

        elif lim_angle >= (ele_pt + 6):
            linear_factor = 0

        elif lim_angle <= (ele_pt - 6):
            linear_factor = 1

        else:
            linear_factor = 'here is a problem linearization of skydome'
        if linear_factor < 0:
            raise 'linear factor negative, changes irradiation direction'

        # calculation orientation in skydome, rotation
        rotation = - sin_a * sin_y * df_dome.xs(pt)['Sin_a'] * df_dome.xs(pt)['Cos_e'] \
                   - sin_y * cos_a * df_dome.xs(pt)['Cos_a'] * df_dome.xs(pt)['Cos_e'] - cos_y * df_dome.xs(pt)['Sin_e']
        irradiation_patch = round(df_irradiation[pt] * rotation * linear_factor, 10)
        if irradiation_patch.min() < 0:
            df_irradiation_neg[pt] = irradiation_patch
        else:
            df_irradiation_pos[pt] = irradiation_patch
    print('Limiting angle design', design_lim_angle)
    print(len(df_irradiation_pos.columns), 'patches can NOT be seen')
    print(len(df_irradiation_neg.columns), 'patches can be seen')

    df_irradiation_panel_t = df_irradiation_neg.sum(axis=1)

    df_irradiation_panel_t.index = pd.to_datetime(df_irradiation_panel_t.index)  # convert index to datetime
    df_irradiation_panel_t = df_irradiation_panel_t.sort_index()

    # construct annual sum
    df_period = np.array([])

    period_duration = typical_frequency.pop('PeriodDuration')

    for number, key in enumerate(list(typical_frequency.keys())[:-2]):
        hours_component = int(period_duration[number + 1])
        end = key + timedelta(hours=hours_component - 1)
        irr_day = -1 * df_irradiation_panel_t.loc[key: end]
        df_period = np.append(df_period, irr_day.values)

    df_period = np.append(df_period, [df_period.min(), df_period.max()])

    return df_irradiation_panel_t, df_period


def calc_orientated_surface(azimuth, tilt, design_lim_angle, local_data, irradiation_file, typical_frequency):

    df_irradiation_panel_t, df_typical = calc_orientation_profiles(azimuth, tilt, design_lim_angle, local_data, irradiation_file, typical_frequency)

    # construct annual sum
    df_period = pd.DataFrame()

    for key, value in typical_frequency.items():
        irr_day = df_irradiation_panel_t.xs(key).sum() * (-value)
        df_period = df_period.append([irr_day])

    annual_irr = round(df_period.sum().values[0] / 1000, 2)

    print('Sum of typical days is', annual_irr, 'kWh/m2')

    return azimuth, tilt, annual_irr


def construct_annual_orientation_df(limiting_angle, local_data):
    azimuth = np.array(range(0, 360))
    tilt = np.array(range(0, 90, 5))

    df = pd.DataFrame()
    for (a, t) in it.product(azimuth, tilt):
        azimuth, tilt, annual_irr = calc_orientated_surface(a, t, limiting_angle, local_data)
        d = {'azimuth': azimuth, 'tilt': tilt, 'irr': annual_irr}
        df = pd.concat([df, d], ignore_index=True)
    print(df)
    filename = 'orientated_irr_linearized' + str(limiting_angle) + '.csv'
    df.to_csv(filename)
    print('Data saved in: ' + filename)


def limiting_angle_for_tilt():
    a = 180
    limit_angle = np.array(range(0, 21, 1))
    tilt_1 = np.array(range(1, 5, 1))
    tilt_2 = np.array(range(5, 95, 5))
    tilt = np.append(tilt_1, tilt_2)

    df = pd.DataFrame()

    for (l, t) in it.product(limit_angle, tilt):
        azimuth, tilt, annual_irr = calc_orientated_surface(a, t, l)

        d = {'tilt': tilt, 'limit_angle': l, 'irr': annual_irr}
        df = pd.concat([df, d], ignore_index=True)
    print(df)
    filename = 'irr_tilt_limiting_angle_azi' + str(a) + '.csv'
    df.to_csv(filename)
    print('Data saved in: ' + filename)


def plot_irr(save_fig):
    cm = plt.cm.get_cmap('Spectral_r')

    # cm = plt.cm.get_cmap('cividis')
    # cm = plt.cm.get_cmap('tab20c')

    # cm = plt.cm.get_cmap('GnBu')

    filename = os.path.join(path_to_skydome, 'orientated_irr.csv')

    df = pd.read_csv(filename, index_col=0)

    df_2 = df[(df['azimuth'] >= 80) & (df['azimuth'] <= 280)]
    df_3 = df_2[(df_2['irr'] >= 950) & (df_2['irr'] <= 1200)]

    condition = np.array(range(0, 90, 5))
    df_3 = df_3.loc[df_3.tilt.isin(condition)]

    #################################################################################################################
    # plotting: for all: plot df, for only tip plot df_3 (next line ax = df_3.plot....) change ax_xlim([])
    ###############################################################################################################

    ax = df.plot.scatter(x='azimuth', y='irr', c='tilt', cmap=cm, alpha=1, edgecolors='none', vmin=0, vmax=90)

    # az_max = df_3.xs(df_3['irr'].idxmax())['azimuth']
    # irr_max = df_3.xs(df_3['irr'].idxmax())['irr']
    # tilt_max = df_3.xs(df_3['irr'].idxmax())['tilt']

    # plt.scatter(az_max, irr_max, color='black')

    # plt.text((az_max+5), irr_max, 'azimuth: '+str(int(az_max))+', ' + 'tilt: '+ str(int(tilt_max)))
    ax.set_xlim([90, 280])
    ax.set_xlim([0, 360])
    ax.set_xlabel('Azimuth angle [degree]')
    f = plt.gcf()

    cax = f.get_axes()[1]
    xax = f.get_axes()[0]

    cax.set_ylabel('Tilt angle [degree]')
    xax.set_ylabel('Annual irradiation density [kWh/m2]')

    plt.tight_layout()

    if save_fig:
        export_format = 'pdf'
        plt.savefig(('all_irr_spectral' + '.' + str(export_format)), format=export_format)
    else:
        plt.show()


if __name__ == '__main__':

    irradiation_file = os.path.join(path_to_skydome, 'typical_irradiation.csv')
    typical_days_string = ['20050921', '20050228', '20050810', '20050313', '20050725',
                           '20050107', '20050911',
                           '20050618']
    typical_frequency = {'20050921': 54, '20050228': 46, '20050810': 17, '20050313': 49, '20050725': 52,
                         '20050107': 68, '20050911': 49, '20050618': 30}

    # thisfile = os.path.join(path_to_clustering, 'timestamp.dat')
    # df = pd.read_csv(thisfile, delimiter='\t')

    # typical_days_string = df.Date.values

    # load_timesteps = np.array(range(1,8760))
    # convert_results_txt_to_csv(load_timesteps)
    # irradiation_to_typical_df(typical_days_string)
    # skydome_to_tilt(tilt = 30)

    # limiting_angle = 10  # = 0 for no irradiation losses
    # construct_annual_orientation_df(limiting_angle)
    # df_good = irradiation_to_df_general(irradiation_csv)
    # df_wrong = irradiation_to_df(irradiation_csv)

    # azimuth = 175
    # tilt = 20
    # design_lim_angle = 20
    # print('design limiting angle:', design_lim_angle)
    calc_orientated_surface(270, 90, 0, irradiation_file, typical_frequency)
    # limiting_angle_for_tilt()
    # df = skydome_to_df()
    # print(df)
