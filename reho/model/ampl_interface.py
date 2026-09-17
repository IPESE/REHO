"""Thin layer between REHO and the AMPL runtime.

Everything that knows *how* to talk to AMPL lives here:

- :func:`create_ampl_session` builds a configured :class:`amplpy.AMPL` instance,
  resolving the license the same way for the master problem and the sub-problems;
- :func:`exitcode_from_ampl` normalises AMPL's ``solve_result`` string;
- the ``*_UNIT_MODELS`` registries map a technology to the ``.mod`` file that
  implements it, so that adding a technology is a one-line data change instead
  of a new branch in an ``if``/``elif`` chain.

See also
--------
reho.model.sub_problem.SubProblem : building-scale problem, reads the building registries.
reho.model.master_problem.MasterProblem : district-scale problem, reads the district registries.
"""

import os

from amplpy import AMPL, Environment

from reho.logger import get_logger
from reho.paths import (
    load_ampl_environment,
    path_to_ampl_model,
    path_to_district_units,
    path_to_units,
    path_to_units_interperiod,
)

logger = get_logger(__name__)

__all__ = [
    "AMPL_LICENSE_HELP",
    "BUILDING_UNIT_MODELS",
    "DISTRICT_UNIT_MODELS",
    "INTERPERIOD_BUILDING_UNIT_MODELS",
    "INTERPERIOD_DISTRICT_UNIT_MODELS",
    "create_ampl_session",
    "exitcode_from_ampl",
    "read_unit_models",
]

AMPL_LICENSE_HELP = (
    "No AMPL license was found. Either install the bundled AMPL modules "
    "(`pip install --extra-index-url https://pypi.ampl.com ampl_module_base ampl_module_highs`) "
    "or point the AMPL_PATH environment variable at a local AMPL installation. See "
    "https://reho.readthedocs.io/en/main/sections/getting_started.html#ampl-license"
)

# ---------------------------------------------------------------------------
# Technology registries
# ---------------------------------------------------------------------------
# Each registry maps the key REHO uses to detect that a technology is part of
# the problem, to the AMPL file modelling it. Keeping them as data (rather than
# as if/elif chains) means a new technology is registered in a single place and
# can be listed, tested and documented programmatically. A technology made of
# several units is registered under the tuple of their keys: its file is read
# only when all of them are present.

#: ``UnitOfType`` -> model file(s), read from ``ampl_model/units/`` for each building.
#: Insertion order is the order in which AMPL reads the files, so keep it stable.
BUILDING_UNIT_MODELS = {
    "ElectricalHeater": "electrical_heater.mod",
    "NG_Boiler": "ng_boiler.mod",
    "OIL_Boiler": "oil_boiler.mod",
    "WOOD_Stove": "wood_stove.mod",
    "HeatPump": "heatpump.mod",
    "HeatPump_WH": "heatpump_waste_heat.mod",
    "AirConditioner": "air_conditioner.mod",
    "ThermalSolar": "thermal_solar.mod",
    "DataHeat": "data_heat.mod",
    "DHN_hex": ["dhn_hex.mod", "dhn_pipes.mod"],
    # Replaced by 'pv_orientation.mod' when method['use_pv_orientation'] is set,
    # see SubProblem.init_ampl_model.
    "PV": "pv.mod",
    "rSOC": "rsoc.mod",
    "Methanator": "methanator.mod",
    "FuelCell": "fuel_cell.mod",
    "Electrolyzer": "electrolyzer.mod",
    "WaterTankSH": "heatstorage.mod",
    "WaterTankDHW": "dhwstorage.mod",
    "Battery": "battery.mod",
}

#: ``UnitOfType`` -> model file, read from ``ampl_model/units/interperiod/``.
INTERPERIOD_BUILDING_UNIT_MODELS = {
    "Battery_interperiod": "battery_IP.mod",
    "H2storage": "H2storage_IP.mod",
    "CH4storage": "CH4storage_IP.mod",
    "CO2storage": "CO2storage_IP.mod",
    ("PTES_storage", "PTES_conversion"): "ptes_IP.mod",
}

#: District unit name -> model file, read from ``ampl_model/units/district_units/``.
DISTRICT_UNIT_MODELS = {
    "EV_district": "evehicle.mod",
    "Bike_district": "bike.mod",
    "ElectricBike_district": "ebike.mod",
    "ICE_district": "icevehicle.mod",
    "NG_Boiler_district": "ng_boiler_district.mod",
    "HeatPump_Geothermal_district": "heatpump_district.mod",
    "NG_Cogeneration_district": "ng_cogeneration_district.mod",
    "rSOC_district": "rsoc_district.mod",
    "MTR_district": "methanator_district.mod",
    "ElectricalHeater_other_district": "electrical_heater_district.mod",
    "Datacenter_district": "datacenter_district.mod",
    "ORC_DC_district": "ORC_DC_district.mod",
}

#: District unit name -> model file, read from ``ampl_model/units/interperiod/``.
INTERPERIOD_DISTRICT_UNIT_MODELS = {
    "Battery_IP_district": "battery_IP.mod",
    "CH4_storage_IP_district": "CH4storage_IP.mod",
    "H2_storage_IP_district": "H2storage_IP.mod",
    "CO2_storage_IP_district": "CO2storage_IP.mod",
    ("PTES_conv_IP_district", "PTES_storage_IP_district"): "ptes_IP.mod",
}

#: Directory holding each registry, used by :func:`read_unit_models`.
_REGISTRY_DIRECTORIES = {
    id(BUILDING_UNIT_MODELS): path_to_units,
    id(INTERPERIOD_BUILDING_UNIT_MODELS): path_to_units_interperiod,
    id(DISTRICT_UNIT_MODELS): path_to_district_units,
    id(INTERPERIOD_DISTRICT_UNIT_MODELS): path_to_units_interperiod,
}


def read_unit_models(ampl, registry, selected, directory=None, overrides=None):
    """Read the ``.mod`` files of the technologies present in the problem.

    Parameters
    ----------
    ampl : amplpy.AMPL
        Session to read the model files into.
    registry : dict
        One of the ``*_UNIT_MODELS`` mappings: key -> file name or list of file names. A key
        may be a tuple of keys, all of which must be selected.
    selected : iterable of str
        Technology keys actually present in the problem (``UnitTypes``,
        ``UnitsOfDistrict``, ...). Keys absent from ``registry`` are ignored,
        which lets callers pass the full list without filtering it first.
    directory : str, optional
        Directory holding the files. Defaults to the one registered for ``registry``.
    overrides : dict, optional
        Per-key replacement of the registered file(s), for technologies with
        several formulations (e.g. ``{'PV': 'pv_orientation.mod'}``).

    Returns
    -------
    list of str
        The file names that were read, in registry order (deterministic, so two
        runs build the exact same AMPL model).
    """
    directory = _REGISTRY_DIRECTORIES[id(registry)] if directory is None else directory
    overrides = overrides or {}
    selected = set(selected)
    ampl.cd(directory)

    read = []
    for key, files in registry.items():
        if not all(required in selected for required in (key if isinstance(key, tuple) else (key,))):
            continue
        files = overrides.get(key, files)
        for file_name in [files] if isinstance(files, str) else files:
            ampl.read(file_name)
            read.append(file_name)
    return read


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

#: Numerical options shared by every REHO problem.
_COMMON_OPTIONS = {
    "solution_round": 11,
    # Ignore differences between upper and lower bounds within this tolerance.
    "presolve_eps": 1e-4,
    # Tolerance added to / subtracted from each upper / lower bound.
    "presolve_inteps": 1e-6,
    "presolve_fixeps": 1e-9,
}


def create_ampl_session(solver, print_logs=True, options=None, evals=(), fallback_to_modules=True, solver_threads=None):
    """Create and configure an AMPL session.

    The license is resolved in this order:

    1. a local AMPL installation pointed at by the ``AMPL_PATH`` environment
       variable (possibly declared in a ``.env`` file, see
       :func:`reho.paths.load_ampl_environment`);
    2. the ``ampl_module_*`` wheels installed alongside REHO.

    Parameters
    ----------
    solver : str
        Solver name passed to AMPL (``highs``, ``gurobi``, ``cplex``, ``cbc``, ...).
    print_logs : bool, optional
        Whether AMPL and the solver may write to the console. Default is True.
    options : dict, optional
        Extra ``option name value`` pairs, merged over the REHO defaults.
    evals : iterable of str, optional
        Raw AMPL statements evaluated right after the options are set.
    fallback_to_modules : bool, optional
        Whether to fall back on the ``amplpy`` modules when ``AMPL_PATH`` is set
        but unusable. Default is True.
    solver_threads : int, optional
        Maximum number of threads of the solver, applied to Gurobi only. Default
        is None, which lets the solver decide.

    Returns
    -------
    amplpy.AMPL
        A session with the REHO numerical options applied and its working
        directory set to ``ampl_model/``.

    Raises
    ------
    RuntimeError
        If no usable AMPL license could be found.
    """
    load_ampl_environment()
    ampl = _open_ampl(fallback_to_modules)

    for name, value in {**_COMMON_OPTIONS, **(options or {})}.items():
        ampl.setOption(name, value)

    if not print_logs:
        ampl.setOption("show_stats", 0)
        ampl.setOption("solver_msg", 0)

    ampl.setOption("solver", solver)
    if solver == "gurobi":
        # One string literal: AMPL joins adjacent literals without a space.
        gurobi_options = "NodeFileStart=0.5 IntFeasTol=1e-6"
        if solver_threads:
            gurobi_options += f" threads={int(solver_threads)}"
        ampl.eval(f"option gurobi_options '{gurobi_options}';")

    for statement in evals:
        ampl.eval(statement)

    ampl.cd(path_to_ampl_model)
    return ampl


def _open_ampl(fallback_to_modules):
    """Instantiate :class:`amplpy.AMPL`, trying the local license then the modules."""
    ampl_path = os.environ.get("AMPL_PATH")
    if ampl_path:
        try:
            return AMPL(Environment(ampl_path))
        except Exception as exc:
            if not fallback_to_modules:
                raise RuntimeError(
                    f"Failed to use the local AMPL license at AMPL_PATH={ampl_path!r}: {exc}"
                ) from exc
            logger.warning(
                "Failed to use the local AMPL license at AMPL_PATH=%r (%s). "
                "Falling back to the amplpy modules.", ampl_path, exc
            )

    try:
        from amplpy import modules

        modules.load()
        return AMPL()
    except Exception as exc:
        raise RuntimeError(AMPL_LICENSE_HELP) from exc


def exitcode_from_ampl(ampl):
    """Return ``0`` when AMPL solved the problem, and its ``solve_result`` otherwise.

    Parameters
    ----------
    ampl : amplpy.AMPL
        A session on which ``solve()`` has been called.

    Returns
    -------
    int or str
        ``0`` on success, else the raw AMPL status (``'infeasible'``,
        ``'solved?'``, ``'limit'``, ...).
    """
    solve_result = ampl.getData("solve_result").toList()[0]
    return 0 if solve_result == "solved" else solve_result
