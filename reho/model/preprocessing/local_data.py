"""Location-dependent input data: weather, sun position, renovation references.

Everything that depends on *where* the district is — but not on *which* buildings
compose it — is gathered by :func:`return_local_data` into a single dictionary
passed to every sub-problem.
"""

import os
from datetime import timedelta

import pandas as pd
import pvlib
from pyproj import Transformer

import reho.model.preprocessing.weather as weather
from reho.logger import get_logger
from reho.paths import path_to_clustering, path_to_infrastructure, path_to_skydome

__all__ = ["return_local_data"]

logger = get_logger(__name__)

#: Coordinate reference system of the buildings' x/y coordinates (CH1903+ / LV95).
CRS_BUILDINGS = "EPSG:2056"

#: Coordinate reference system expected by pvlib (WGS 84 latitude/longitude).
CRS_WGS84 = "EPSG:4326"

#: Hour at which the sun position is evaluated for the two extreme periods, which
#: last a single timestep and stand for the coldest and the warmest hour of the year.
EXTREME_PERIOD_HOUR = 13


def return_local_data(cluster, qbuildings_data):
    """
    Retrieve the data (weather, sun position and renovation references) corresponding to the buildings' location.

    The weather file of the requested location and clustering options is generated
    on first use and cached under ``data/clustering/<File_ID>/`` in the working
    directory, so a second run with the same options reuses it. A cache written by an
    earlier version of REHO is rebuilt, see
    :func:`~reho.model.preprocessing.weather.typical_periods_are_current`.

    Parameters
    ----------
    cluster : dict
        Defines the location of the buildings and the clustering attributes of the
        data-reduction process: ``Location``, ``Attributes``, ``Periods``,
        ``PeriodDuration``, and optionally ``custom_weather``.
    qbuildings_data : dict
        Buildings characterization; only the coordinates of the first building are
        used, as the whole district shares one weather series.

    Returns
    -------
    dict
        - ``Cluster`` (dict): the clustering options, echoed back.
        - ``File_ID`` (str): identifier of the location and clustering attributes.
        - ``df_Timestamp`` (pd.DataFrame): date and frequency of each typical period.
        - ``sun_azimuth`` (pd.Series): solar azimuth at each timestep [deg].
        - ``T_ext`` (np.ndarray): ambient temperature of the typical periods [degC].
        - ``Irr`` (np.ndarray): global solar irradiance of the typical periods [W/m2].
        - ``Irr_yearly`` (pd.DataFrame): yearly irradiance per sky patch [W/m2].
        - ``df_renovation_targets`` (pd.DataFrame): U-values before and after renovation, per construction period.
        - ``df_renovation`` (pd.DataFrame): cost and embodied emissions of each renovation measure.

    See also
    --------
    reho.model.preprocessing.weather.generate_weather_data : builds the typical periods.
    """
    local_data = {"Cluster": cluster}

    # Weather: build the typical periods once, then reuse the cached files.
    File_ID = weather.get_cluster_file_ID(cluster)
    local_data["File_ID"] = File_ID

    clustering_directory = os.path.join(path_to_clustering, File_ID)
    if not weather.typical_periods_are_current(clustering_directory):
        if os.path.isdir(clustering_directory):
            logger.warning(
                "The typical periods cached in %s were written by an earlier version of REHO and are rebuilt: "
                "results will differ from the runs that used them.", clustering_directory
            )
        os.makedirs(clustering_directory, exist_ok=True)
        weather.generate_weather_data(cluster, qbuildings_data, clustering_directory)

    df_timestamp = pd.read_csv(os.path.join(clustering_directory, "timestamp.csv"))
    df_timestamp["Date"] = pd.to_datetime(df_timestamp["Date"])
    local_data["df_Timestamp"] = df_timestamp

    local_data["sun_azimuth"] = _sun_azimuth(df_timestamp, qbuildings_data, cluster["PeriodDuration"])

    typical_data = pd.read_csv(os.path.join(clustering_directory, "typical_data.csv"))
    local_data["T_ext"] = typical_data["Text"].values
    local_data["Irr"] = typical_data["Irr"].values
    local_data["Irr_yearly"] = pd.read_csv(os.path.join(path_to_skydome, "total_irradiation.csv")).drop(columns=["time"])

    # Renovation references
    local_data["df_renovation_targets"] = pd.read_csv(
        os.path.join(path_to_infrastructure, "U_values.csv"), sep=";"
    ).set_index("period")
    local_data["df_renovation"] = pd.read_csv(
        os.path.join(path_to_infrastructure, "renovation.csv")
    ).set_index(["year", "element"])

    return local_data


def _sun_azimuth(df_timestamp, qbuildings_data, period_duration):
    """Solar azimuth at every timestep of the typical periods, relative to east.

    The district is small enough for one sun position to apply to all of its
    buildings, so the coordinates of the first one are used.

    Parameters
    ----------
    df_timestamp : pandas.DataFrame
        Start date of each typical period; the last two rows are the extreme periods.
    qbuildings_data : dict
        Buildings characterization, holding ``x`` and ``y`` in :data:`CRS_BUILDINGS`.
    period_duration : int
        Number of timesteps in a regular typical period.

    Returns
    -------
    pandas.Series
        Azimuth of the sun, shifted by -90 degrees so that 0 points east, as the
        PV orientation model expects.
    """
    reference_building = next(iter(qbuildings_data["buildings_data"].values()))
    latitude, longitude = Transformer.from_crs(CRS_BUILDINGS, CRS_WGS84).transform(
        reference_building["x"], reference_building["y"]
    )

    timestamps = [
        day + timedelta(hours=hour)
        for day in df_timestamp["Date"][:-2]
        for hour in range(period_duration)
    ]
    # The two extreme periods are single timesteps: evaluate them at midday.
    timestamps += [day + timedelta(hours=EXTREME_PERIOD_HOUR) for day in df_timestamp["Date"][-2:]]

    positions = pd.concat([pvlib.solarposition.get_solarposition(ts, latitude, longitude) for ts in timestamps])
    return positions["azimuth"] - 90
