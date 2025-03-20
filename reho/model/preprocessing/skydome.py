from datetime import timedelta

import numpy as np
import pandas as pd

from reho.paths import *

__doc__ = """
Generates a skydome decomposition into patches for PV orientation.
"""


def generate_skydome():
    """
    Reads two txt files: one containing the area and one the position of the center point of the 145 patches,
    which define the skydome. Calculates basic additional values and writes all data in one single df.

    The irradiation dome is defined as a composition of patches, defined by their area and their centroids. Those
    patches do not depend on the location. The sky is always decomposed the same way, as done by
    `Lady Bug tool <https://www.ladybug.tools/ladybug/docs/index.html>`_.

    """

    df_area = pd.read_csv(os.path.join(path_to_skydome, 'skyPatchesAreas.csv'), header=None)  # area of patches
    df_cenpts = pd.read_csv(os.path.join(path_to_skydome, 'skyPatchesCenPts.csv'), header=None)  # location of centre points

    df_dome = pd.DataFrame()
    df_dome['Area'] = df_area[0]
    df_dome['X'] = df_cenpts[0]
    df_dome['Y'] = df_cenpts[1]
    df_dome['Z'] = df_cenpts[2]

    # Add basic caluclations

    df_dome['XY'] = np.hypot(df_dome['X'], df_dome['Y'])
    df_dome['XYZ'] = np.hypot(df_dome['XY'], df_dome['Z'])

    df_dome['azimuth'] = np.degrees(np.arctan2(df_dome['X'].round(8), df_dome['Y'].round(8))) % 360
    df_dome['azimuth'] = df_dome['azimuth'].round().astype(int)

    df_dome['elevation'] = np.degrees(np.arctan2(df_dome['Z'].round(8), df_dome['XY'].round(8))) % 360
    df_dome['elevation'] = df_dome['elevation'].round().astype(int)

    df_dome['Sin_e'] = round(df_dome['Z'] / df_dome['XYZ'], 4)
    df_dome['Cos_e'] = round(df_dome['XY'] / df_dome['XYZ'], 4)
    df_dome['Cos_a'] = round(df_dome['Y'] / df_dome['XY'], 4)
    df_dome['Sin_a'] = round(df_dome['X'] / df_dome['XY'], 4)

    df_dome.to_csv(os.path.join(path_to_skydome, 'skydome.csv'))


def irradiation_to_df(ampl, local_data):
    """
    Reads irradiation values of all 145 patches for the timesteps given in the csv file. Converts them to float and returns them as df
    """

    df_normalized = pd.read_csv(os.path.join(path_to_skydome, 'normalized_irradiance.csv'))
    Irr = local_data['Irr']
    df_time = local_data['df_Timestamp']

    df_irradiation = df_normalized.mul(Irr[:-2].max(), axis=0)

    # get relevant cluster information
    PeriodDuration = ampl.getParameter('TimeEnd').getValues().toPandas()

    # construct Multiindex
    df_p = pd.DataFrame()
    list_timesteps = []

    for p in df_time.index:
        date1 = df_time.xs(p).Date
        end = PeriodDuration.xs(p + 1).TimeEnd

        date2 = date1 + timedelta(hours=int(end) - 1)
        df_period = df_irradiation.loc[date1:date2]

        for t in np.arange(1, int(end) + 1):
            list_timesteps.append((p + 1, t))

        df_p = pd.concat([df_p, df_period])

    idx = pd.MultiIndex.from_tuples(list_timesteps)

    # marry index and data
    df_irradiation = df_p.set_index(idx)

    df = df_irradiation.stack()
    df = df.reorder_levels([2, 0, 1])
    df = pd.DataFrame(df)
    df = df.rename(columns={0: 'Irr_patches'})

    return df
