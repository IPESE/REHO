"""Locations of the files shipped with REHO, and small file-reading helpers.

Two families of paths coexist in REHO and must not be confused:

**Package paths** (``path_to_data``, ``path_to_ampl_model``, ...) point inside
the installed ``reho`` package. They are constants, resolved once at import.

**Working-directory paths** (``path_to_clustering``, ``path_to_configurations``)
point inside the *user's* project, next to the script being run. Read as
attributes of this module, they are resolved against the current working
directory on every access. REHO's own modules import them by name, though,
which fixes them when ``reho`` is imported: a script that needs another location
changes its working directory before importing REHO, not after.

Importing this module has no side effect: it does not read ``.env`` files, does
not change pandas' global display options, and does not print. Applications that
want the AMPL license path to come from a ``.env`` file call
:func:`load_ampl_environment` explicitly — :class:`reho.model.reho.REHO` does it
for them.
"""

import os
from csv import Error as CsvError, Sniffer
from pathlib import Path

import geopandas as gpd
from pandas import read_csv, read_excel, read_table

from reho.logger import get_logger

logger = get_logger(__name__)

__all__ = [
    "path_to_reho",
    "path_to_data",
    "path_to_model",
    "path_to_plotting",
    "path_to_ampl_model",
    "path_to_units",
    "path_to_district_units",
    "path_to_units_interperiod",
    "path_to_elcom",
    "path_to_emissions",
    "path_to_infrastructure",
    "path_to_qbuildings",
    "path_to_mobility",
    "path_to_sia",
    "path_to_sia_equivalence",
    "path_to_sia_norms",
    "path_to_skydome",
    "path_to_actor",
    # Resolved by the module __getattr__ below (PEP 562), so linters cannot see them.
    "path_to_clustering",  # noqa: F822
    "path_to_configurations",  # noqa: F822
    "load_ampl_environment",
    "path_handler",
    "file_reader",
]

# ---------------------------------------------------------------------------
# Package paths (constant)
# ---------------------------------------------------------------------------

path_to_reho = os.path.dirname(__file__)
path_to_data = os.path.join(path_to_reho, "data")
path_to_model = os.path.join(path_to_reho, "model")
path_to_plotting = os.path.join(path_to_reho, "plotting")

# AMPL model
path_to_ampl_model = os.path.join(path_to_model, "ampl_model")
path_to_units = os.path.join(path_to_ampl_model, "units")
path_to_district_units = os.path.join(path_to_units, "district_units")
path_to_units_interperiod = os.path.join(path_to_units, "interperiod")

# Data
path_to_elcom = os.path.join(path_to_data, "elcom")
path_to_emissions = os.path.join(path_to_data, "emissions", "electricity_matrix_2019_reduced.csv")
path_to_infrastructure = os.path.join(path_to_data, "infrastructure")
path_to_qbuildings = os.path.join(path_to_data, "QBuildings")
path_to_mobility = os.path.join(path_to_data, "mobility")
path_to_sia = os.path.join(path_to_data, "SIA")
path_to_sia_equivalence = os.path.join(path_to_sia, "sia2024_rooms_sia380_1.csv")
path_to_sia_norms = os.path.join(path_to_sia, "sia2024_data.xlsx")
path_to_skydome = os.path.join(path_to_data, "skydome")
path_to_actor = os.path.join(path_to_data, "actor")


# ---------------------------------------------------------------------------
# Working-directory paths (resolved on access, see PEP 562)
# ---------------------------------------------------------------------------

#: Sub-paths of the current working directory, resolved lazily.
_CWD_RELATIVE_PATHS = {
    "path_to_clustering": ("data", "clustering"),
    "path_to_configurations": ("results", "configurations"),
}


def __getattr__(name):
    """Resolve working-directory-dependent paths at access time.

    ``reho.paths.path_to_clustering`` therefore always reflects the current
    working directory, whereas a name bound by ``from reho.paths import ...`` is,
    as usual, fixed when that import runs.
    """
    try:
        parts = _CWD_RELATIVE_PATHS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    return os.path.join(os.getcwd(), *parts)


def __dir__():
    return sorted(set(globals()) | set(_CWD_RELATIVE_PATHS))


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


def load_ampl_environment(override=False):
    """Load the ``.env`` file that declares ``AMPL_PATH``, if there is one.

    Two locations are searched, in order: the installed ``reho`` package
    directory, then the current working directory. The first hit wins.

    Parameters
    ----------
    override : bool, optional
        Whether values found in the file replace already-set environment
        variables. Default is False.

    Returns
    -------
    str or None
        Path of the ``.env`` file that was loaded, or None when none was found.

    Notes
    -----
    REHO can run without any ``.env`` file: :mod:`amplpy` then falls back to the
    ``ampl_module_*`` wheels declared as dependencies. Set ``AMPL_PATH`` only to
    point at a locally installed AMPL with its own license.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional at runtime
        return None

    for candidate in (os.path.join(path_to_reho, ".env"), os.path.join(os.getcwd(), ".env")):
        if os.path.isfile(candidate):
            load_dotenv(dotenv_path=candidate, override=override)
            logger.debug("Loaded environment variables from %s", candidate)
            return candidate
    return None


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def path_handler(path_given):
    """Resolve a path to an existing file, whether it is absolute or relative.

    Parameters
    ----------
    path_given : str or pathlib.Path
        Absolute path, or path relative to the current working directory.

    Returns
    -------
    str
        The resolved absolute path.

    Raises
    ------
    FileNotFoundError
        If the path does not point to an existing file.
    """
    path_given = os.fspath(path_given)
    resolved = path_given if os.path.isabs(path_given) else os.path.realpath(path_given)
    if os.path.isfile(resolved):
        return resolved

    kind = "absolute" if os.path.isabs(path_given) else "relative"
    raise FileNotFoundError(
        f"The {kind} path {path_given!r} is not a valid file (resolved to {resolved!r}, "
        f"current working directory is {os.getcwd()!r})."
    )


#: Delimiters :func:`_sniff_delimiter` considers, in order of preference.
_CANDIDATE_DELIMITERS = (";", ",", "\t", "|")

#: Number of lines inspected to decide which delimiter a file uses.
_SNIFF_LINES = 10


def _sniff_delimiter(file, default=","):
    """Guess the delimiter of a character-separated file.

    Several lines are inspected rather than only the header, and a candidate is
    accepted only if it splits every one of them into the same number of fields.
    Looking at the header alone misreads files whose column names contain a comma
    (``sia2024_rooms_sia380_1.csv`` has a ``shed, warehouse`` column).

    Parameters
    ----------
    file : str or pathlib.Path
        File to inspect.
    default : str, optional
        Delimiter returned when no candidate is consistent. Default is ``','``.

    Returns
    -------
    str
        The delimiter.
    """
    with open(file, "r") as handle:
        lines = [line for _, line in zip(range(_SNIFF_LINES), handle) if line.strip()]

    if not lines:
        return default

    best, best_count = None, 0
    for delimiter in _CANDIDATE_DELIMITERS:
        counts = {line.count(delimiter) for line in lines}
        if len(counts) == 1 and (count := counts.pop()) > best_count:
            best, best_count = delimiter, count

    if best is not None:
        return best

    # No candidate splits every line the same way; fall back on csv's own heuristic.
    try:
        return Sniffer().sniff(lines[0].strip()).delimiter
    except CsvError:
        logger.debug("Could not detect the delimiter of %s, assuming %r.", file, default)
        return default


def file_reader(file, index_col=None):
    """Read a tabular data file, whatever its format.

    Supported extensions are ``.csv``, ``.dat``, ``.txt`` (delimiter guessed from
    the header), ``.xlsx``, ``.gpkg``, and anything else that
    :func:`pandas.read_table` accepts.

    Parameters
    ----------
    file : str or pathlib.Path
        Absolute path, or path relative to the current working directory.
    index_col : int or str or list, optional
        Column(s) to use as the DataFrame index, passed to the pandas reader.

    Returns
    -------
    pandas.DataFrame or geopandas.GeoDataFrame

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file exists but cannot be parsed.
    """
    path = Path(path_handler(file))
    suffix = path.suffix.lower()
    try:
        if suffix in (".csv", ".dat", ".txt"):
            return read_csv(path, sep=_sniff_delimiter(path), index_col=index_col)
        if suffix == ".gpkg":
            return gpd.read_file(path)
        if suffix in (".xlsx", ".xls", ".xlsm"):
            return read_excel(path, index_col=index_col)
        return read_table(path, index_col=index_col)
    except Exception as exc:
        raise ValueError(f"Could not read the data file {str(path)!r}: {exc}") from exc


def configure_pandas_display():
    """Widen pandas' console output, as REHO's own scripts prefer it.

    Kept as an opt-in function: a library changing global pandas options on
    import would silently reformat every other DataFrame in the user's session.
    """
    from pandas import set_option

    set_option("display.expand_frame_repr", False)
