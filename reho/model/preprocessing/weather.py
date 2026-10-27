import os

from perfectdays.api.reho import generate_weather_data as _generate_weather_data
from perfectdays.api.reho import get_cluster_file_ID

from reho.logger import get_logger

logger = get_logger(__name__)

__doc__ = """
Generates the meteorological data (temperature and solar irradiance), reduced to typical periods.

The weather comes from `perfectdays <https://perfectdays.readthedocs.io/>`_: in Switzerland, its 1 km grid,
which corrects the temperature bias of the 30 km PVGIS data in Alpine terrain; elsewhere in Europe, PVGIS. The
clustering into typical periods and the files written are perfectdays's as well.
"""

__all__ = ["generate_weather_data", "get_cluster_file_ID", "typical_periods_are_current",
           "TYPICAL_PERIODS_VERSION", "TYPICAL_PERIODS_VERSION_FILE"]

#: Version of the typical-period files written by :func:`generate_weather_data`. Increase it when
#: these files change, so that the files cached by earlier versions of REHO are rebuilt. Version 2
#: fixed a one-day shift between each typical period and the day of the year it was selected from.
#: Version 3 moved the weather step to perfectdays: weather from its Swiss grid in Switzerland,
#: k-medoids by PAM, and ``SourceYear`` and ``SourcePeriod`` in ``timestamp.csv`` instead of ``RowOffset``.
TYPICAL_PERIODS_VERSION = 3

#: File, in each clustering directory, recording the version of its typical periods.
TYPICAL_PERIODS_VERSION_FILE = "typical_periods_version.txt"


def typical_periods_are_current(clustering_directory):
    """
    Whether a clustering directory holds typical periods written by this version of REHO.

    Parameters
    ----------
    clustering_directory : str
        Directory of the typical periods of a location, e.g. ``data/clustering/Geneva_10_24_T_I_W``.

    Returns
    -------
    bool
        False when the directory does not exist, or when its typical periods were written by an
        earlier version of REHO and must be rebuilt.
    """
    try:
        with open(os.path.join(clustering_directory, TYPICAL_PERIODS_VERSION_FILE)) as file:
            return int(file.read().strip()) == TYPICAL_PERIODS_VERSION
    except (OSError, ValueError):
        return False


def generate_weather_data(cluster, qbuildings_data, clustering_directory):
    """
    Builds the typical periods of a location and writes them in ``clustering_directory``.

    Called when the typical periods specified by File_ID do not exist yet, or were written by an
    earlier version of REHO (see :func:`typical_periods_are_current`).

    Parameters
    ----------
    cluster : dict
        Contains a 'Location' (str), some 'Attributes' (list, among 'T' (temperature), 'I' (irradiance) and
        'W' (weekday)), a number of periods 'Periods' (int) and a 'PeriodDuration' (int). Optionally:

        - 'custom_weather' (str): path of an annual weather file, which overrides every source.
        - 'Year' (int or list): the year(s) to take the weather from, clustered together. By default, every
          year stored in the Swiss grid in Switzerland, and the PVGIS typical meteorological year elsewhere.
        - 'Scenario' (str): a climate scenario such as ``'rcp45_2050'`` (Switzerland only).
        - 'Source' (str): ``'swissweathergrid'`` or ``'pvgis'``, to force a source.
        - 'Coordinates' (tuple): WGS 84 (lat, lon), instead of the position of the first building.
        - 'per_month' (bool): cluster each month apart.
    qbuildings_data : dict
        Input data for the buildings; the first building locates the district.
    clustering_directory: str
        Path to the directory where the clustering files will be saved.

    Returns
    -------
    perfectdays.TypicalPeriods
        The typical periods written.

    Notes
    -----
    - Files generated: 'annual_data.csv', 'typical_data.csv', 'frequency.csv', 'index.csv' and 'timestamp.csv'.
    - In Switzerland, the weather comes from the Swiss grid when it is available for the requested years (from the
      database at ``$WEATHER_DATA_DSN``, local solution files, or its Zenodo record, downloaded once and cached),
      and falls back to PVGIS with a warning otherwise.

    See also
    --------
    perfectdays.api.reho.generate_weather_data
    perfectdays.get_typical_periods : the same, with the clustering quality.
    """
    typical_periods = _generate_weather_data(cluster, qbuildings_data, clustering_directory)
    # Written last, so that a generation interrupted midway is redone the next time
    with open(os.path.join(clustering_directory, TYPICAL_PERIODS_VERSION_FILE), 'w') as file:
        file.write(str(TYPICAL_PERIODS_VERSION))

    logger.info('Weather from %s, clustering finished, results saved in %s.',
                typical_periods.meta.get("source"), clustering_directory)
    return typical_periods
