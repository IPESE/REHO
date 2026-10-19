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


def irradiation_to_df(local_data):
    """
    Reads irradiation values of all 145 patches for the timesteps given in the csv file.
    Converts them to float and returns them as a DataFrame indexed by date and hour.

    Parameters
    ----------
    local_data : dict
        Dictionary containing the local data.

    Returns
    -------
    df : pd.DataFrame
        MultiIndexed DataFrame indexed by Patches, Period, Time with irradiation values.
    """

    df_normalized = local_data["Irr_yearly"]/local_data["Irr_yearly"].max().max()
    Irr = local_data['Irr']
    df_time = local_data['df_Timestamp']

    max_irradiation = Irr[:-2].max()
    df_irradiation = df_normalized.mul(max_irradiation, axis=0)

    PeriodDuration = local_data['Cluster']['PeriodDuration']

    # Handle normal periods
    df_p = pd.DataFrame()
    for date in df_time['Date'][:-2]:
        start_idx = date.timetuple().tm_yday*24
        df_period = df_irradiation.iloc[start_idx:start_idx + PeriodDuration].copy()
        df_period.index = pd.date_range(start=pd.to_datetime(date), periods=PeriodDuration, freq='H')
        df_p = pd.concat([df_p, df_period])

    # Handle extreme periods
    extreme_irradiations = Irr[-2:]
    extreme_periods = [df_normalized.mul(val).iloc[0:1] for val in extreme_irradiations]

    for df_extreme, date in zip(extreme_periods, df_time['Date'][-2:]):
        df_extreme.index = [pd.to_datetime(date)]
        df_p = pd.concat([df_p, df_extreme])

    # Final MultiIndex construction without names
    periods = np.repeat(range(1, len(df_time) - 1), PeriodDuration).tolist() + [len(df_time) - 1, len(df_time)]
    hours = np.tile(range(1, PeriodDuration + 1), len(df_time) - 2).tolist() + [1, 1]

    df_p.index = pd.MultiIndex.from_arrays([periods, hours])

    # Stack patches into final DataFrame with integer patch indices
    df_final = df_p.stack().to_frame()
    df_final.index = pd.MultiIndex.from_tuples(
        [(int(patch), period, hour) for (period, hour, patch) in df_final.index],
        names=[None, None, None]
    )

    # Sort index by Patch, Period, Hour
    df_final = df_final.sort_index(level=[0, 1, 2])

    df_final = df_final.rename(columns={0: 'Irr_patches'})

    return df_final
