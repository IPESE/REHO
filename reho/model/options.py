"""Declarative defaults and validation for the three REHO option dictionaries.

A REHO run is configured by three plain dictionaries, all optional:

``method``
    *What* to model and *how* to solve it — optimization scope, profile
    generation, saving options. See :data:`DEFAULT_METHODS`.
``scenario``
    The objective function, the epsilon constraints and the units to
    enforce/exclude. See :data:`DEFAULT_SCENARIO`.
``DW_params``
    Hyper-parameters of the Dantzig-Wolfe decomposition. See
    :data:`DEFAULT_DW_PARAMS`.

Collecting the defaults here, as data, has three benefits over the long
``if 'key' not in dictionary`` chains they replace: the documentation tables can
be generated from them, a misspelled key is reported instead of being silently
ignored, and the coupling rules between options (for instance
``building-scale`` implying ``district-scale``) are stated in one readable place.
"""

import difflib
import warnings

__all__ = [
    "DEFAULT_DW_PARAMS",
    "DEFAULT_METHODS",
    "DEFAULT_SCENARIO",
    "METHOD_DESCRIPTIONS",
    "initialise_DW_params",
    "initialize_default_methods",
    "initialize_default_scenario",
]


# ---------------------------------------------------------------------------
# method
# ---------------------------------------------------------------------------

#: Default value of every supported ``method`` option.
DEFAULT_METHODS = {
    # -- Solar --------------------------------------------------------------
    "use_facades": False,
    "use_pv_orientation": False,
    # -- Optimization scope -------------------------------------------------
    "building-scale": False,
    "district-scale": False,
    "parallel_computation": True,
    "switch_off_second_objective": False,
    "skip_initiation": False,
    "fix_units": False,
    "include_all_solutions": False,
    # -- Demand profiles ----------------------------------------------------
    "include_stochasticity": False,
    "sd_stochasticity": [0.1, 1],
    "use_dynamic_emission_profiles": False,
    "use_custom_profiles": False,
    # -- Saving options -----------------------------------------------------
    "save_data_input": True,
    "save_timeseries": True,
    "save_streams": False,
    "extract_parameters": False,
    "print_logs": True,
    # -- Model extensions ---------------------------------------------------
    "actors_problem": False,
    "renovation": None,
    "DHN_CO2": False,
    "interperiod_storage": False,
    "external_district": False,
}

#: One-line description of each ``method`` option, used by the documentation.
METHOD_DESCRIPTIONS = {
    "use_facades": "Consider building facades as a surface available for PV panels.",
    "use_pv_orientation": "Account for roof orientation and the shadows cast by neighbouring buildings in the solar potential.",
    "building-scale": "Optimize each building as an independent system (one master-problem iteration).",
    "district-scale": "Allow energy exchanges between buildings and the use of district units (Dantzig-Wolfe decomposition).",
    "parallel_computation": "Solve the sub-problems in parallel processes.",
    "switch_off_second_objective": "Build the Pareto curve by minimizing only the first objective and constraining the second.",
    "skip_initiation": "Skip the sub-problem initiation round of the decomposition.",
    "fix_units": "Fix unit sizes to the values of ``REHO.df_fix_Units`` instead of optimizing them.",
    "include_all_solutions": "Let the master problem reuse the sub-problem solutions found for other Pareto points.",
    "include_stochasticity": "Add variability to the SIA typical consumption profiles.",
    "sd_stochasticity": "``[sd_consumption, sd_timeshift]`` used when ``include_stochasticity`` is enabled.",
    "use_dynamic_emission_profiles": "Use hourly electricity emission factors instead of a yearly constant.",
    "use_custom_profiles": "Replace the SIA profiles by custom files, as ``{'electricity'|'dhw'|'occupancy': path}``.",
    "save_data_input": "Store the optimization inputs (``df_Buildings``, ``df_Weather``, ``df_Index``) in the results.",
    "save_timeseries": "Store the time-resolved results (``df_Buildings_t``, ``df_Unit_t``).",
    "save_streams": "Store the heat-cascade stream results (``df_Streams_t``).",
    "extract_parameters": "Extract every parameter passed to AMPL, for debugging.",
    "print_logs": "Print the progress of the optimization.",
    "actors_problem": "Solve the multi-actor master problem, minimizing one stakeholder's costs under epsilon constraints on the others.",
    "renovation": "List of renovation packages to offer, e.g. ``['window/facade', 'roof']``. ``None`` disables renovation.",
    "DHN_CO2": "Use CO2 rather than water as the district-heating heat carrier.",
    "interperiod_storage": "Enable seasonal storage units, chained across typical periods.",
    "external_district": "Model exchanges with neighbouring districts declared in ``set_indexed['Districts']``.",
}


def initialize_default_methods(method=None, strict=False):
    """Complete a ``method`` dictionary with REHO's defaults and apply its coupling rules.

    Parameters
    ----------
    method : dict, optional
        User-supplied options. Unknown keys are reported (see ``strict``).
        The dictionary is updated **in place** and also returned, as callers
        historically relied on both behaviours.
    strict : bool, optional
        Raise :class:`KeyError` on an unknown option instead of warning.
        Default is False.

    Returns
    -------
    dict
        The completed ``method`` dictionary.

    Raises
    ------
    KeyError
        If ``strict`` is True and an option is not recognised.

    Notes
    -----
    Two coupling rules are applied after the defaults:

    - ``actors_problem`` implies ``district-scale`` and ``include_all_solutions``;
    - ``building-scale`` implies ``district-scale`` (the decomposition is reused
      with a single master-problem iteration) and disables
      ``include_all_solutions``, so that successive scenarios stay independent.

    Examples
    --------
    >>> initialize_default_methods({'building-scale': True})['district-scale']
    True
    """
    method = {} if method is None else method
    _warn_about_unknown_keys(method, DEFAULT_METHODS, "method", strict)

    for key, default in DEFAULT_METHODS.items():
        method.setdefault(key, default)

    if method["actors_problem"]:
        method["include_all_solutions"] = True
        method["district-scale"] = True

    if method["building-scale"]:
        # Avoid interactions between successive optimization scenarios.
        method["include_all_solutions"] = False
        # The building-scale approach reuses the decomposition machinery, with a
        # single master-problem iteration (DW_params['max_iter'] = 1).
        method["district-scale"] = True

    return method


# ---------------------------------------------------------------------------
# scenario
# ---------------------------------------------------------------------------

#: Default value of every supported ``scenario`` key.
DEFAULT_SCENARIO = {
    "Objective": "TOTEX",
    "name": "default_name",
    "EMOO": {},
    "specific": [],
    "enforce_units": [],
    "exclude_units": [],
}

#: ``scenario`` keys that are optional and have no default value.
_OPTIONAL_SCENARIO_KEYS = {"nPareto"}


def initialize_default_scenario(scenario=None, strict=False):
    """Complete a ``scenario`` dictionary with REHO's defaults.

    Parameters
    ----------
    scenario : dict, optional
        User-supplied scenario. A **copy** is completed and returned, so the
        caller's dictionary is left untouched.
    strict : bool, optional
        Raise :class:`KeyError` on an unknown key instead of warning. Default is False.

    Returns
    -------
    dict
        A completed copy of ``scenario``, with ``EMOO``, ``specific``,
        ``enforce_units`` and ``exclude_units`` always present.
    """
    scenario = {} if scenario is None else dict(scenario)
    _warn_about_unknown_keys(
        scenario, {**DEFAULT_SCENARIO, **{k: None for k in _OPTIONAL_SCENARIO_KEYS}}, "scenario", strict
    )

    for key, default in DEFAULT_SCENARIO.items():
        if key not in scenario:
            scenario[key] = default.copy() if isinstance(default, (dict, list)) else default
        elif isinstance(scenario[key], (dict, list)):
            # Detach the mutable containers from the caller's dictionary: REHO adds
            # epsilon constraints to scenario['EMOO'] as it walks a Pareto front, and
            # that must not leak back into the script's own scenario.
            scenario[key] = scenario[key].copy()

    scenario["EMOO"].setdefault("EMOO_grid", 0.0)
    return scenario


# ---------------------------------------------------------------------------
# DW_params
# ---------------------------------------------------------------------------

#: Default hyper-parameters of the Dantzig-Wolfe decomposition.
#: ``timesteps`` and ``n_houses`` are derived from the problem, see
#: :func:`initialise_DW_params`.
DEFAULT_DW_PARAMS = {
    "max_iter": 15,
    "iter_no_improv": 5,
    "threshold_subP_value": 0,
    "threshold_no_improv": 0.00005,
    "grid_cost_exchange": 0.0,
    "weight_lagrange_cst": 2.0,
}

#: Description of each decomposition hyper-parameter, used by the documentation.
DW_PARAMS_DESCRIPTIONS = {
    "max_iter": "Maximum number of master-problem iterations; the last one solves the binary master problem.",
    "iter_no_improv": "Number of consecutive iterations without improvement that stops the decomposition.",
    "threshold_subP_value": "Reduced cost above which a sub-problem solution is considered non-improving.",
    "threshold_no_improv": "Relative objective improvement below which an iteration counts as 'no improvement'.",
    "grid_cost_exchange": "Cost charged on energy exchanged between buildings.",
    "weight_lagrange_cst": "Weight of the Lagrangian term in the sub-problem objective.",
    "timesteps": "Number of timesteps, derived from the cluster: ``Periods * PeriodDuration + 2`` extreme periods.",
    "n_houses": "Number of buildings in the district, derived from ``qbuildings_data``.",
}


def initialise_DW_params(DW_params=None, cluster=None, buildings_data=None, building_scale=False, strict=False):
    """Complete the decomposition hyper-parameters with defaults and derived values.

    Parameters
    ----------
    DW_params : dict, optional
        User-supplied hyper-parameters, updated in place and returned.
    cluster : dict, optional
        Clustering options, used to derive ``timesteps``.
    buildings_data : dict, optional
        Buildings of the district, used to derive ``n_houses``.
    building_scale : bool, optional
        When True, ``max_iter`` is forced to 1: each building is solved on its
        own and the master problem runs only once.
    strict : bool, optional
        Raise :class:`KeyError` on an unknown key instead of warning. Default is False.

    Returns
    -------
    dict
        The completed hyper-parameters.
    """
    DW_params = {} if DW_params is None else DW_params
    known = {**DEFAULT_DW_PARAMS, "timesteps": None, "n_houses": None}
    _warn_about_unknown_keys(DW_params, known, "DW_params", strict)

    for key, default in DEFAULT_DW_PARAMS.items():
        DW_params.setdefault(key, default)

    if "timesteps" not in DW_params and cluster is not None:
        # Two extreme periods (coldest and warmest hour) are appended to the typical periods.
        DW_params["timesteps"] = cluster["Periods"] * cluster["PeriodDuration"] + 2
    if "n_houses" not in DW_params and buildings_data is not None:
        DW_params["n_houses"] = len(buildings_data)

    if building_scale:
        DW_params["max_iter"] = 1

    return DW_params


# ---------------------------------------------------------------------------
# Shared validation
# ---------------------------------------------------------------------------


def _warn_about_unknown_keys(given, known, label, strict):
    """Report keys that REHO does not recognise, suggesting the closest match.

    A misspelled option used to be silently ignored, which is the worst possible
    outcome: the run succeeds and answers a different question than the one asked.
    """
    unknown = [key for key in given if key not in known]
    if not unknown:
        return

    messages = []
    for key in unknown:
        close = difflib.get_close_matches(str(key), [str(k) for k in known], n=1, cutoff=0.6)
        hint = f", did you mean {close[0]!r}?" if close else ""
        messages.append(f"{key!r}{hint}")

    message = f"Unknown {label} option(s): " + "; ".join(messages) + ". They will be ignored."
    if strict:
        raise KeyError(message)
    warnings.warn(message, stacklevel=3)
