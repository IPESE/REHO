"""
reho_pipeline.py
================

A pipeline broken into separate, independently-inspectable stages -- run one,
look at its output, THEN move to the next.

  STEP 1: get_results(...)
      Loads REHO result .pickle files into one summary DataFrame: TOTEX,
      OPEX, CAPEX, CO2, unit sizes (rSOC_mult, Bat_mult, ...), the baseline
      (deterministic) design metrics needed for the uncertainty analysis
      (per-technology size/CAPEX, ERA_tot, ...), etc., with optional
      filtering. Internally uses `extract_design_metrics(...)`, which reads
      EVERY technology's size/CAPEX/cinv1 from a single `tech_registry` dict
      (default: DEFAULT_TECH_REGISTRY) -- define your own registry in the
      notebook and pass it as `tech_registry=` to override/extend it.
      Supports two pickle layouts via `pareto_mode` (see get_results'
      docstring): one-run-per-file (default), or a single pickle holding an
      entire Pareto front (+ optionally a single-objective-optimal point).
      -> summary_df   (one row per scenario -- this IS your one extraction step)

  STEP 2: sample_uncertainty_draws(uncertainty_distributions, N_runs)
      Draws the uncertain parameters -- whatever keys are in
      `uncertainty_distributions` (e.g. read from an Excel sheet) -- and
      NOTHING else. Output columns are named EXACTLY like those keys, no
      renaming. The same draws are reused for every design (paired Monte
      Carlo), so this doesn't depend on summary_df at all. Inspect this
      dataframe (ranges, histograms) before it ever touches a cost formula.
      -> df_draws (one row per run_id)

  STEP 3: compute_uncertain_economics(summary_df, df_draws, tech_registry=...)
      Reads the design columns straight off `summary_df` (no separate
      design-prep step -- get_results already produces everything needed)
      and applies df_draws to every design, computing the perturbed
      CAPEX/OPEX/TOTEX/GWP (and per-technology CAPEX), each paired with that
      design's baseline (deterministic) value. Still absolute -- no
      normalization yet. EVERY technology (which df_Unit pattern it matches,
      which summary_df columns hold its size/CAPEX/cinv1, which df_draws
      column holds its cinv2, whether its lifetime is fixed or swept) comes
      from `tech_registry` -- pass the SAME registry you gave get_results.
      -> df_mc (one row per design_id x run_id), with `{metric}_baseline_abs`
         / `{metric}_perturbed_abs` columns

  STEP 4: normalize_uncertainty_results(df_mc, tech_registry=...)
      Explicit, opt-in step: divides the absolute totals by each row's own
      ERA_tot to get per-m2 numbers (or leaves them absolute if
      normalize_by_ERA=False). Adds `{metric}_baseline` / `{metric}_perturbed`
      without touching the `_abs` columns. The metric list defaults to
      CAPEX/OPEX/TOTEX/GWP plus every technology's capex_metric from
      tech_registry -- pass the same registry again to stay consistent.
      -> df_mc (same shape, extra columns)

  STEP 5: summarize_uncertainty(df_mc) / plot_uncertainty_band(df_mc)
      Per-design statistics (median, 50%/95% CI) sorted by ascending baseline
      CAPEX, and the corresponding band plot (optionally colored/marked by
      'techno').

Typical usage in a notebook (one cell per step, so you can check each output)
------------------------------------------------------------------------------
    import os
    from scipy import stats
    from reho_pipeline import (
        get_results, DEFAULT_TECH_REGISTRY,
        sample_uncertainty_draws, compute_uncertain_economics, normalize_uncertainty_results,
        summarize_uncertainty, plot_uncertainty_band,
    )

    # Define your OWN registry -- start from the default, override as needed
    TECH_REGISTRY = dict(DEFAULT_TECH_REGISTRY)
    # TECH_REGISTRY['ptes_storage']['cinv2_role'] = 'ptes_tank_capex'  # only if it differs

    # STEP 1
    results_folder = 'results'
    my_scenario_names = [f[:-7] for f in os.listdir(results_folder) if f.endswith(".pickle")]
    summary_df, all_results = get_results(
        results_folder=results_folder, all_results=my_scenario_names, filter=None,
        feed_in_pos=7, retail_pos=4, techno_pos=2, tech_registry=TECH_REGISTRY,
    )
    summary_df[['scenario', 'ERA_tot', 'TOTEX', 'CO2', 'rSOC_mult', 'Bat_mult']]  # <- check it

    # STEP 2
    uncertainty_distributions = {...}  # same dict you already build elsewhere
    df_draws = sample_uncertainty_draws(uncertainty_distributions, N_runs=1000,
                                         corr_factor={'rsoc_lifetime': 1000 / 8760})
    df_draws.describe()  # <- check ranges look sane

    # STEP 3 -- SAME registry as STEP 1
    df_mc = compute_uncertain_economics(summary_df, df_draws, tech_registry=TECH_REGISTRY)

    # STEP 4 -- SAME registry again
    df_mc = normalize_uncertainty_results(df_mc, tech_registry=TECH_REGISTRY, normalize_by_ERA=True)

    # STEP 5
    fig, ax, df_summary = plot_uncertainty_band(df_mc, x_col='CAPEX', y_col='TOTEX')
"""

import os

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


# =============================================================================
# Generic safe getter
# =============================================================================

def safe_get(getter, default=0):
    try:
        return getter()
    except Exception:
        return default


# =============================================================================
# SINGLE SOURCE OF TRUTH for every technology in the uncertainty pipeline.
# extract_design_metrics, get_results, compute_uncertain_economics, and
# normalize_uncertainty_results ALL read from this same registry (or one you
# pass in) -- so a technology's size/CAPEX/cinv1/cinv2/lifetime can never
# drift out of sync between functions again. Add a new technology here (one
# dict entry) and it automatically propagates everywhere.
#
# Fields per entry:
#   unit_pattern   -- string matched against df_Unit's index (str.contains)
#   size_metric    -- summary_df column name for installed size
#   capex_metric   -- summary_df column name for baseline (deterministic) CAPEX
#   cinv1_key      -- summary_df column name for the fixed cinv1 constant
#   cinv1_default  -- default value for cinv1_key
#   cinv2_role     -- key name in uncertainty_distributions / df_draws for cinv2
#   lifetime       -- fixed years (float), OR a df_draws column name (str) if swept
# =============================================================================
DEFAULT_TECH_REGISTRY = {
    'battery': {
        'unit_pattern':  'Battery_IP',
        'size_metric':   'Battery_size',
        'capex_metric':  'Battery_CAPEX',
        'cinv1_key':     'battery_cinv1',
        'cinv1_default': 30000,
        'cinv2_role':    'battery_capex',
        'lifetime':      15.0,
    },
    'rsoc': {
        'unit_pattern':  'rSOC',
        'size_metric':   'rSOC_size',
        'capex_metric':  'rSOC_CAPEX',
        'cinv1_key':     'rSOC_cinv1',
        'cinv1_default': 25000,
        'cinv2_role':    'rsoc_capex',
        'lifetime':      'rsoc_lifetime',
    },
    'ch4_storage': {
        'unit_pattern':  'CH4_storage_IP',
        'size_metric':   'CH4_storage_size',
        'capex_metric':  'CH4_storage_CAPEX',
        'cinv1_key':     'CH4_storage_cinv1',
        'cinv1_default': 20000,
        'cinv2_role':    'ch4_tank_capex',
        'lifetime':      25.0,
    },
    'ptes_storage': {
        'unit_pattern':  'PTES_storage_IP',
        'size_metric':   'PTES_storage_size',
        'capex_metric':  'PTES_tank_CAPEX',
        'cinv1_key':     'PTES_storage_cinv1',
        'cinv1_default': 20000,
        'cinv2_role':    'ptes_tank_capex',
        'lifetime':      25.0,
    },
}


# =============================================================================
# 1. Design-metric extraction (generalized `extract_metrics`)
# =============================================================================

def extract_design_metrics(key_data0, cinv_defaults=None, norm_ERA=False, tech_registry=None):
    """
    Extract the metrics needed for the uncertainty/Monte-Carlo analysis from a
    single solution dict (what you called `p` before, i.e. `key_data[0]` in
    `get_results`).

    Unlike the original `extract_metrics`, this does NOT assume a single
    building called 'Building1' or specific unit names like 'Battery_Building1'.
    Instead it aggregates across the whole network using the same
    `str.contains(...)` + `.sum()` pattern already used in `get_results`, so it
    works for single- or multi-building networks alike.

    Every technology is read generically from `tech_registry` (default
    DEFAULT_TECH_REGISTRY) -- there is no per-technology hardcoded line in
    this function. Add a technology to the registry and it appears here
    automatically.

    Parameters
    ----------
    key_data0 : dict
        One solution's result dict (e.g. `results[key_name][0]` inside
        `get_results`, or a Pareto-front / TOTEX-optimal solution dict).
    cinv_defaults : dict, optional
        Overrides for any cinv1 constant (keyed by `cinv1_key`).
    tech_registry : dict, optional
        Defaults to DEFAULT_TECH_REGISTRY. Pass your own to add/remove/rename
        technologies without touching this function.

    Returns
    -------
    dict of metrics, directly mergeable into a summary_data row.
    """
    tech_registry = tech_registry or DEFAULT_TECH_REGISTRY
    p = key_data0

    df_unit = p['df_Unit']
    df_annuals = p['df_Annuals']

    metrics = {}
    metrics['ERA'] = ERA_tot = p['df_Buildings']["ERA"].sum()
    # --- Electricity flows at the network level -----------------------------
    metrics['Elec_import'] = safe_get(lambda: df_annuals.loc['Electricity', 'Network']['Supply_MWh'])
    metrics['Elec_export'] = safe_get(lambda: df_annuals.loc['Electricity', 'Network']['Demand_MWh'])

    def unit_sum(pattern, col):
        mask = df_unit.index.to_series().astype(str).str.contains(pattern)
        return safe_get(lambda: df_unit.loc[mask, col].sum())

    def unit_capex(pattern):
        mask = df_unit.index.to_series().astype(str).str.contains(pattern)
        inv = safe_get(lambda: df_unit.loc[mask, 'Costs_Unit_inv'].sum())
        rep = safe_get(lambda: df_unit.loc[mask, 'Costs_Unit_rep'].sum())
        return inv + rep

    # --- Generic per-technology extraction, driven ENTIRELY by tech_registry ---
    cinv = {}
    for tech, spec in tech_registry.items():
        metrics[spec['size_metric']] = unit_sum(spec['unit_pattern'], 'Units_Mult')
        metrics[spec['capex_metric']] = unit_capex(spec['unit_pattern'])
        cinv[spec['cinv1_key']] = spec['cinv1_default']

    # PTES_conv is intentionally NOT in the registry (not an uncertain/swept
    # technology) -- it's still tracked here for visibility, and its cost
    # automatically ends up inside CAPEX_fixed downstream (CAPEX_fixed =
    # CAPEX - sum(registered tech CAPEX)), with no special-casing needed.
    metrics['PTES_conv_CAPEX'] = unit_capex('PTES_conv_IP')

    # Extract economics dataframe
    df_Economics = p['df_Economics']

    # Focus only on the 'costs' performance type
    df_costs = df_Economics.xs('costs', level='Perf_type').copy()
    df_impact = df_Economics.xs('impact', level='Perf_type').copy()

    # If df_costs has MultiIndex columns (from 3 header rows), flatten them first:
    df_costs.columns = ['_'.join([str(c) for c in col if str(c) != '']) for col in df_costs.columns.values]

    df_costs.drop(columns=['operation_avoided_PV', 'operation_avoided_BA_out', 'operation_avoided_onsite_el',
                           'operation_avoided_PV_SC', 'operation_avoided_SC', 'operation_avoided_PVC'], inplace=True)
    # Then sum numeric values per row
    df_costs.loc[:, df_costs.columns.str.contains('revenues')] *= -1
    df_costs['row_sum'] = df_costs.select_dtypes(include='number').sum(axis=1)

    # CAPEX, OPEX, TOTEX

    # Then access the 'row_sum'
    totex = df_costs.loc['Network', 'row_sum']
    opex = df_costs.loc[:, df_costs.columns.str.contains('operation', case=False)].sum(axis=1)['Network']
    capex = df_costs.loc[:, df_costs.columns.str.contains('investment', case=False)].sum(axis=1)['Network']
    # If df_costs has MultiIndex columns (from 3 header rows), flatten them first:
    df_impact.columns = ['_'.join([str(c) for c in col if str(c) != '']) for col in df_impact.columns.values]

    df_impact.drop(columns=['operation_avoided_PV', 'operation_avoided_BA_out', 'operation_avoided_onsite_el',
                            'operation_avoided_PV_SC', 'operation_avoided_SC', 'operation_avoided_PVC'],
                   inplace=True)
    # Then sum numeric values per row
    df_impact.loc[:, df_impact.columns.str.contains('revenues')] *= -1
    df_impact['row_sum'] = df_impact.select_dtypes(include='number').sum(axis=1)
    impact = df_impact['row_sum'].sum()

    metrics['CAPEX'] = capex
    metrics['OPEX'] = opex
    metrics['TOTEX'] = totex
    metrics['GWP'] = impact

    if cinv_defaults:
        cinv.update(cinv_defaults)
    metrics.update(cinv)

    return metrics


def _design_columns(tech_registry):
    """
    Columns `compute_uncertain_economics` (and get_results' CAPEX_fixed
    calculation) need -- DERIVED from tech_registry, never a static list, so
    it can't drift out of sync with what extract_design_metrics produces.
    """
    return (
        ['ERA_tot', 'Elec_import', 'Elec_export', 'CAPEX_fixed', 'OPEX_fixed', 'CAPEX', 'OPEX', 'TOTEX', 'GWP']
        + [spec['size_metric'] for spec in tech_registry.values()]
        + [spec['capex_metric'] for spec in tech_registry.values()]
        + [spec['cinv1_key'] for spec in tech_registry.values()]
    )


# =============================================================================
# 1b. Pickle-layout resolution -- shared by get_results (multi-pickle /
#     pareto) and by the adaptability-analysis module (which needs to reach
#     into an arbitrary Pareto point's own df_Unit directly).
# =============================================================================

def resolve_solution_items(results, pareto_mode):
    """
    Walk a SINGLE loaded pickle (`results`, i.e. `pd.read_pickle(...)`'s
    return value) and return a list of `(key_name, key_data0)` pairs, where
    `key_data0` is always a plain REHO solution dict (has 'df_Unit',
    'df_Annuals', 'df_Performance', ...) -- regardless of which of the two
    on-disk layouts produced it.

    - `pareto_mode=False` (the original, one-run-per-file layout):
      `results = {key_name: {0: solution_dict, ...}, ...}`
      -> `key_data0 = results[key_name][0]`

    - `pareto_mode=True` (a single pickle holding an entire Pareto front,
      optionally alongside single-objective-optimal points):
      `results = {'pareto': {idx: solution_dict, ...}, 'totex': {0: solution_dict}, ...}`
      Each point is auto-detected as either already a solution dict (has
      'df_Unit') or one level deeper wrapped as `{0: solution_dict}` -- so no
      group name is hardcoded; any group shaped either way is picked up
      (e.g. an extra CO2-optimal point) with no new parameter needed.
      Returned key names are `f"{group_name}_{point_id}"`, e.g. 'pareto_3',
      'totex_0'.
    """
    if pareto_mode:
        solution_items = []
        for group_name, group_data in results.items():
            if not isinstance(group_data, dict) or len(group_data) == 0:
                continue
            for point_id, point_data in group_data.items():
                if isinstance(point_data, dict) and 'df_Unit' in point_data:
                    key_data0 = point_data
                elif isinstance(point_data, dict) and 0 in point_data:
                    key_data0 = point_data[0]
                else:
                    continue
                solution_items.append((f"{group_name}_{point_id}", key_data0))
        return solution_items
    else:
        return [
            (key_name, key_data[0])
            for key_name, key_data in results.items()
            if isinstance(key_data, dict) and len(key_data) > 0
        ]


# =============================================================================
# 2. get_results: pickle loader + KPI extraction + design-metric extraction
# =============================================================================

def get_results(results_folder, all_results, filter=None, per_x_m2=1, norm_ERA=True,
                 feed_in_pos=None, retail_pos=None, cinv_defaults=None, techno_pos=None,
                 tech_registry=None, pareto_mode=False):
    """
    Load a set of REHO result pickles into one summary DataFrame.

    In addition to the original KPI columns (totex, opex, capex, CO2, unit
    multiplicities, self-sufficiency, etc.), each row now also contains the
    design metrics required by the uncertainty pipeline: every technology's
    size/CAPEX/cinv1 (as defined by `tech_registry`, default
    DEFAULT_TECH_REGISTRY), OPEX, CAPEX, GWP, TOTEX, plus the derived
    CAPEX_fixed, OPEX_fixed columns. 'retail_elec' and 'feed_in_elec' (the
    actual tariffs for this scenario, read from its name via
    feed_in_pos/retail_pos) are used to compute OPEX_fixed. 'techno' (read
    from the scenario name via techno_pos, with a fallback re-labeling step
    below) identifies which technology family a design belongs to.

    Note: this reuses the existing 'capex'/'opex'/'totex' (lowercase) KPI
    columns you already had, which may be normalized per m2 (per_x_m2, norm_ERA).
    The new 'CAPEX'/'OPEX'/'TOTEX'/'GWP' (uppercase) columns are the *absolute*,
    non-normalized design metrics needed for the uncertainty analysis -- keep
    that distinction in mind if both appear in the same DataFrame.

    Pass `tech_registry` (default DEFAULT_TECH_REGISTRY) to add/remove/rename
    technologies -- pass the SAME registry to `compute_uncertain_economics`
    and `normalize_uncertainty_results` afterward.

    Parameters
    ----------
    pareto_mode : bool, default False
        - False (default): each file in `results_folder` holds ONE run, keyed
          by scenario name, each value being `{0: solution_dict, ...}` -- the
          original structure (`results[key_name][0]`).
        - True: each file holds MULTIPLE points directly, grouped by
          category, e.g. `{'pareto': {idx: solution_dict, ...}, 'totex':
          {0: solution_dict}}` (a single pickle containing an entire Pareto
          front, optionally alongside a single-objective-optimal point).
          See `resolve_solution_items` for the exact auto-detection rule.
          Every extracted quantity is identical to the non-pareto case; only
          how we reach `key_data0` changes.
    """
    tech_registry = tech_registry or DEFAULT_TECH_REGISTRY
    summary_data = []
    all_results_list = {}
    for r in all_results:
        if filter:
            if filter not in r:
                continue
        try:
            results = pd.read_pickle(os.path.join(results_folder, r + ".pickle"))
            all_results_list[r] = results
            try:
                sample_values = results['Sobol_building']['sample_values']
                feed_in_T = -1e6
                retail_T = -1e6
                techno = 'not_specified'
            except Exception:
                sample_values = {}
                feed_in_T = float(r.split("_")[feed_in_pos]) if feed_in_pos else -1e6
                retail_T = float(r.split("_")[retail_pos]) if retail_pos else -1e6
                techno = (r.split("_")[techno_pos]) if techno_pos else 'not_specified'

            try:
                # ---- resolve (key_name, key_data0) pairs -- THIS is the only
                # part that differs between the two pickle structures. Every
                # extraction line below is unchanged and works off `key_data0`
                # (a solution dict) exactly like it used to work off `key_data[0]`.
                solution_items = resolve_solution_items(results, pareto_mode)

                for key_name, key_data0 in solution_items:

                    ERA_tot = key_data0['df_Buildings']["ERA"].sum()

                    # Extract economics dataframe
                    df_Economics = key_data0['df_Economics']

                    # Focus only on the 'costs' performance type
                    df_costs = df_Economics.xs('costs', level='Perf_type').copy()
                    df_impact = df_Economics.xs('impact', level='Perf_type').copy()

                    df_costs.columns = ['_'.join([str(c) for c in col if str(c) != '']) for col in df_costs.columns.values]

                    df_costs.drop(columns=['operation_avoided_PV', 'operation_avoided_BA_out', 'operation_avoided_onsite_el',
                                            'operation_avoided_PV_SC', 'operation_avoided_SC', 'operation_avoided_PVC'], inplace=True)
                    df_costs.loc[:, df_costs.columns.str.contains('revenues')] *= -1
                    df_costs['row_sum'] = df_costs.select_dtypes(include='number').sum(axis=1)

                    totex = df_costs.loc['Network', 'row_sum']
                    opex = df_costs.loc[:, df_costs.columns.str.contains('operation', case=False)].sum(axis=1)['Network']
                    capex = df_costs.loc[:, df_costs.columns.str.contains('investment', case=False)].sum(axis=1)['Network']

                    df_impact.columns = ['_'.join([str(c) for c in col if str(c) != '']) for col in df_impact.columns.values]

                    df_impact.drop(columns=['operation_avoided_PV', 'operation_avoided_BA_out', 'operation_avoided_onsite_el',
                                             'operation_avoided_PV_SC', 'operation_avoided_SC', 'operation_avoided_PVC'],
                                    inplace=True)
                    df_impact.loc[:, df_impact.columns.str.contains('revenues')] *= -1
                    df_impact['row_sum'] = df_impact.select_dtypes(include='number').sum(axis=1)
                    impact = df_impact['row_sum'].sum()

                    df_unit = key_data0['df_Unit']
                    df_grid_t = key_data0['df_Grid_t'].groupby(level=(0, 2, 3)).sum().loc['Electricity']
                    df_grid_t = df_grid_t[df_grid_t.index.get_level_values(0) <= 10]

                    SH_heat_tot = key_data0['df_Annuals'].loc['SH']['Demand_MWh'].sum()
                    elec_appliances_tot = key_data0['df_Annuals'].loc['Electricity'].loc[lambda df: df.index.str.startswith('Building')][
                        'Demand_MWh'].sum()
                    Elec_tot_from_Network = key_data0['df_Annuals'].loc['Electricity', 'Network']['Supply_MWh']
                    Elec_tot_to_Network = key_data0['df_Annuals'].loc['Electricity', 'Network']['Demand_MWh']
                    try:
                        H2_export = key_data0['df_Annuals'].loc['Hydrogen', 'Network']['Demand_MWh']
                    except Exception:
                        H2_export = 0
                    df_annuals_elec = key_data0['df_Annuals'].loc['Electricity']
                    local_prod = df_annuals_elec[df_annuals_elec.index.to_series().astype(str).str.contains("PV")]['Supply_MWh'].sum()

                    try:
                        network_C = key_data0['df_Grid'].loc['Network', 'Electricity']['Capacity']
                    except KeyError:
                        building_labels = [idx for idx in key_data0['df_Grid'].index.get_level_values(0)
                                            if str(idx).startswith('Building')]
                        if building_labels:
                            network_C = key_data0['df_Grid'].loc[building_labels[0], 'Electricity']['Capacity']
                        else:
                            network_C = float('nan')

                    try:
                        U_h = key_data0['df_Buildings']['U_h'][0]
                        ERA = key_data0['df_Buildings']['ERA'][0]
                        roof = key_data0['df_Buildings']['SolarRoofArea'][0]
                        ERA_roof_ratio = ERA / roof
                        egid = key_data0['df_Buildings']['egid'][0]
                    except Exception:
                        U_h = -1e6
                        ERA_roof_ratio = 1e6
                        egid = None

                    norm_fac = ERA_tot if norm_ERA else 1

                    storage_elec_out_tot = 0
                    for stor in ['rSOC', 'PTES', 'Battery']:
                        storage_elec_out_tot += df_annuals_elec[df_annuals_elec.index.to_series().astype(str).str.contains(stor)]['Supply_MWh'].sum()

                    CAPEX_tot_storage = 0
                    for stor in ['rSOC', 'MTR', 'conv', 'Battery', 'storage']:
                        CAPEX_tot_storage += df_unit.loc[df_unit.index.str.contains(stor)]['Costs_Unit_inv'].sum()
                        CAPEX_tot_storage += df_unit.loc[df_unit.index.str.contains(stor)]['Costs_Unit_rep'].sum()

                    storage_dis_power = 0
                    for stor in ['rSOC', 'conv']:
                        storage_dis_power += df_unit.loc[df_unit.index.str.contains(stor)]['Units_Mult'].sum()

                    try:
                        df_interperiod = key_data0['df_Interperiod']
                        max_bat_power = max(df_interperiod['BAT_E_stored_IP'] - df_interperiod['BAT_E_stored_IP'].shift(-1))
                        storage_dis_power += max_bat_power
                    except Exception:
                        pass

                    # ---- design metrics for the uncertainty analysis, driven
                    # by tech_registry (SAME registry across the whole pipeline) ----
                    design_metrics = extract_design_metrics(
                        key_data0, cinv_defaults=cinv_defaults, tech_registry=tech_registry
                    )

                    if techno == 'rSOC' and df_unit[(df_unit.index.to_series().astype(str).str.contains("rSOC"))]['Units_Mult'].sum() <= 0:
                        if df_unit[(df_unit.index.to_series().astype(str).str.contains("Battery_IP"))]['Units_Mult'].sum() <= 0:
                            techno = 'PV-HP'
                        else:
                            techno = 'Batt'

                    if techno == 'PTES' and df_unit[(df_unit.index.to_series().astype(str).str.contains("PTES_conv"))]['Units_Mult'].sum() <= 0:
                        if df_unit[(df_unit.index.to_series().astype(str).str.contains("Battery_IP"))]['Units_Mult'].sum() <= 0:
                            techno = 'PV-HP'
                        else:
                            techno = 'Batt'

                    if techno == 'Batt' and df_unit[(df_unit.index.to_series().astype(str).str.contains("Battery_IP"))]['Units_Mult'].sum() <= 0:
                        techno = 'PV-HP'

                    summary_data.append({
                        **sample_values,
                        'scenario': r + "__" + key_name,
                        'techno': techno,
                        'ERA_tot': ERA_tot,
                        'totex': totex / norm_fac * per_x_m2,
                        'opex': opex / norm_fac * per_x_m2,
                        'capex': capex / norm_fac * per_x_m2,
                        'heat_SH': SH_heat_tot / norm_fac * per_x_m2,
                        'elec_appliances_tot': elec_appliances_tot,
                        'CO2': impact / norm_fac * per_x_m2,
                        'peak_district_elec_dem': key_data0['df_Buildings_t'].groupby(level=(1, 2)).sum()['Domestic_electricity'].max() / norm_fac * per_x_m2,
                        'V_stor_H2': safe_get(lambda: key_data0['df_Interperiod'].loc['storage info', 'Volume'].get('H2_stor_stored', 0)) / norm_fac * per_x_m2,
                        'V_stor_CH4': safe_get(lambda: key_data0['df_Interperiod'].loc['storage info', 'Volume'].get('CH4_stor_stored', 0)) / norm_fac * per_x_m2,
                        'V_stor_H2_kWh': df_unit[df_unit.index.to_series().astype(str).str.contains("H2_storage_IP")]['Units_Mult'].sum() / norm_fac * per_x_m2,
                        'V_stor_CH4_kWh': df_unit[df_unit.index.to_series().astype(str).str.contains("CH4_storage_IP")]['Units_Mult'].sum() / norm_fac * per_x_m2,
                        'PV_mult': df_unit[df_unit.index.to_series().astype(str).str.contains("PV")]['Units_Mult'].sum() / norm_fac * per_x_m2,
                        'burner_mult': df_unit[df_unit.index.to_series().astype(str).str.contains("NG_Boiler")]['Units_Mult'].sum() / norm_fac * per_x_m2,
                        'rSOC_mult': df_unit[(df_unit.index.to_series().astype(str).str.contains("rSOC"))]['Units_Mult'].sum() / norm_fac * per_x_m2,
                        'PTES_mult': df_unit[(df_unit.index.to_series().astype(str).str.contains("PTES_conv"))]['Units_Mult'].sum() / norm_fac * per_x_m2,
                        'PTES_storage_mult': df_unit[(df_unit.index.to_series().astype(str).str.contains("PTES_storage"))]['Units_Mult'].sum() / norm_fac * per_x_m2,
                        'HP_mult': df_unit[df_unit.index.to_series().astype(str).str.contains("HeatPump")]['Units_Mult'].sum() / norm_fac * per_x_m2,
                        'MTR_mult': df_unit[df_unit.index.to_series().astype(str).str.contains("MTR")]['Units_Mult'].sum() / norm_fac * per_x_m2,
                        'Bat_mult': df_unit[df_unit.index.to_series().astype(str).str.contains("Battery_IP")]['Units_Mult'].sum() / norm_fac * per_x_m2,
                        'elec_network_capacity': network_C,
                        'max_elec_peak_dem': df_grid_t['Grid_supply'].max() / norm_fac * per_x_m2,
                        'max_elec_peak_inj': df_grid_t['Grid_demand'].max() / norm_fac * per_x_m2,
                        'egid': egid,
                        'retail_elec': retail_T,
                        'feed_in_elec': feed_in_T,
                        'delta_elec': retail_T - feed_in_T,
                        'storage_dis_power': storage_dis_power / norm_fac * per_x_m2,
                        'storage_elec_out_tot': storage_elec_out_tot / norm_fac * per_x_m2,
                        'CAPEX_tot_storage': CAPEX_tot_storage,
                        'LCOS': CAPEX_tot_storage / storage_elec_out_tot if storage_elec_out_tot > 0 else 1e6,
                        'Insulation': U_h,
                        'ERA_roof_ratio': ERA_roof_ratio,
                        'H2 export': H2_export / norm_fac * per_x_m2,
                        'PV_elec_prod': local_prod,
                        'total_elec_needs': (local_prod - Elec_tot_to_Network + Elec_tot_from_Network) / norm_fac * per_x_m2,
                        'SS': (local_prod - Elec_tot_to_Network) / (local_prod - Elec_tot_to_Network + Elec_tot_from_Network) if local_prod > 0 else 0,
                        'SC': (local_prod - Elec_tot_to_Network) / local_prod if local_prod > 0 else None,
                        'Mean_to_network': Elec_tot_to_Network / 8760 * 1000 / norm_fac * per_x_m2,
                        'Mean_from_network': Elec_tot_from_Network / 8760 * 1000 / norm_fac * per_x_m2,
                        'Elec_tot_export': Elec_tot_to_Network / norm_fac * per_x_m2,
                        'Elec_tot_import': Elec_tot_from_Network / norm_fac * per_x_m2,
                        # ---- design metrics for the uncertainty analysis (absolute, not per-m2) ----
                        **design_metrics,
                    })

            except Exception as e:
                print(f"Error reading {r}: {e}")

        except FileNotFoundError:
            print(f"File missing: {r}")

    summary_df = pd.DataFrame(summary_data)

    # ---- derived quantities, same as your old Pareto/TOTEX script ----------
    # Note: TOTEX and GWP are already set directly by extract_design_metrics
    # (from df_Performance's 'Network' row), so they are NOT recomputed here.
    if not summary_df.empty:
        # CAPEX_fixed = total CAPEX minus every REGISTERED technology's CAPEX,
        # generically -- whatever isn't in tech_registry (e.g. PTES_conv)
        # automatically stays inside CAPEX_fixed, with no special-casing.
        tech_capex_cols = [spec['capex_metric'] for spec in tech_registry.values()]
        summary_df['CAPEX_fixed'] = summary_df['CAPEX'] - summary_df[tech_capex_cols].sum(axis=1)
        # Uses 'retail_elec'/'feed_in_elec' -- the actual tariffs read from the
        # scenario name via feed_in_pos/retail_pos -- not a placeholder default.
        summary_df['OPEX_fixed'] = np.round(
            summary_df['OPEX']
            - summary_df['Elec_import'] * summary_df['retail_elec'] * 1000
            + summary_df['Elec_export'] * summary_df['feed_in_elec'] * 1000,
            1,
        )

    return summary_df, all_results_list


# =============================================================================
# NORMALIZATION CONVENTION -- read this before changing anything below
# =============================================================================
#
# Two families of columns coexist in `summary_df`, and they are normalized
# DIFFERENTLY, on purpose:
#
# 1. The original KPI columns from `get_results` (lowercase: 'totex', 'opex',
#    'capex', 'CO2', 'rSOC_mult', 'Bat_mult', ...): these respect the
#    `norm_ERA` / `per_x_m2` arguments you pass to `get_results`, i.e. they
#    may already be divided by ERA_tot. Use them for plotting/reporting only.
#
# 2. The DESIGN columns (produced by `extract_design_metrics`, driven by
#    tech_registry, and everything derived from it: every technology's
#    size_metric/capex_metric/cinv1_key, plus 'Elec_import', 'Elec_export',
#    'OPEX', 'CAPEX', 'CAPEX_fixed', 'OPEX_fixed', 'GWP', 'TOTEX'): these are
#    ALWAYS kept absolute (extensive), regardless of `norm_ERA`/`per_x_m2`.
#    This is not an oversight -- it's required, because
#    `compute_uncertain_economics` combines them with intensive unit costs
#    (`cinv2` in CHF/kW, tariffs in CHF/kWh). Dividing a size or an energy
#    flow by ERA before that multiplication would silently give wrong CHF
#    totals.
#
# 'ERA_tot' is carried through as its own explicit column everywhere (never
# silently absorbed into a normalization), so you can always normalize any
# absolute output after the fact with `add_per_m2_columns` below, or per-row
# inside `normalize_uncertainty_results` via `normalize_by_ERA=True`.
# =============================================================================

def add_per_m2_columns(df, columns=None, era_col='ERA_tot', suffix='_per_m2', tech_registry=None):
    """
    Explicit, opt-in normalization step: adds `<col><suffix>` = df[col] / df[era_col]
    for each column in `columns`, without touching the original absolute columns.

    This is the ONLY place absolute economic/impact outputs get divided by
    floor area in this module (aside from the equivalent per-row step inside
    `normalize_uncertainty_results` when `normalize_by_ERA=True`). Call it
    whenever you want to compare designs of different ERA_tot on a per-m2
    basis.

    Parameters
    ----------
    df : DataFrame
        Must contain `era_col` and every column in `columns`.
    columns : list of str, optional
        Columns to normalize. Defaults to CAPEX/OPEX/TOTEX/GWP plus every
        technology's capex_metric from `tech_registry` (default
        DEFAULT_TECH_REGISTRY). Sizes and energy flows are NOT included by
        default -- pass them explicitly if you want capacity-per-m2 or
        energy-per-m2 columns.
    tech_registry : dict, optional
        Used only to build the default `columns` list -- ignored if you pass
        `columns` explicitly.
    """
    if columns is None:
        tech_registry = tech_registry or DEFAULT_TECH_REGISTRY
        columns = ['CAPEX', 'OPEX', 'TOTEX', 'GWP'] + [spec['capex_metric'] for spec in tech_registry.values()]

    missing = [c for c in columns + [era_col] if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for normalization: {missing}")

    df = df.copy()
    for col in columns:
        df[f"{col}{suffix}"] = df[col] / df[era_col]
    return df


# =============================================================================
# 3. Plotting helpers (unchanged)
# =============================================================================

def plot_summary(
    df,
    to_plot_y_axis='all',
    y_variable_to_normalize=None,
    to_plot_x_axis='elec_network_capacity',
    normalize_to=None,
    ylabel="",
    xlabel="",
    parametric_variable=None,
    legend_labels=None,
    savefig=None
):
    if to_plot_y_axis == 'all':
        y_columns = [col for col in df.columns if col not in ['scenario', to_plot_x_axis]]
    else:
        y_columns = [to_plot_y_axis] if isinstance(to_plot_y_axis, str) else to_plot_y_axis

    if normalize_to:
        norm_row = df[df['scenario'] == normalize_to]
        if norm_row.empty:
            raise ValueError(f"Normalization scenario '{normalize_to}' not found.")
        norm_values = norm_row.iloc[0]
        df = df.copy()
        for col in y_columns:
            df[col] = df[col] / norm_values[col]

    plt.figure(figsize=(10, 6))

    for col in y_columns:
        if parametric_variable:
            for p_val, group in df.groupby(parametric_variable[0]):
                group = group.sort_values(by=to_plot_x_axis)
                norm = group[y_variable_to_normalize] if y_variable_to_normalize else 1
                plt.plot(
                    group[to_plot_x_axis],
                    group[col] / norm,
                    marker='o',
                    label=f"{parametric_variable[1]} = {p_val} {parametric_variable[2]}"
                )
        else:
            if y_variable_to_normalize is None:
                y_variable_to_normalize = 1

            df = df.sort_values(by=to_plot_x_axis)
            plt.plot(
                df[to_plot_x_axis],
                df[col] / y_variable_to_normalize,
                marker='D',
                alpha=0.6,
            )

    plt.xlabel(xlabel, fontsize=14, fontweight='normal')
    plt.ylabel(ylabel, fontsize=14, fontweight='normal')
    if legend_labels:
        plt.legend(legend_labels, fontsize=12, facecolor=None, edgecolor=None, framealpha=0, loc='best')
    else:
        try:
            plt.legend(fontsize=12, facecolor=None, edgecolor=None, framealpha=0, loc='best')
        except Exception:
            pass
    plt.tight_layout()
    if savefig:
        plt.savefig('results/rSOC_results/' + savefig + '.png', dpi=300)
    plt.show()


def plot_heatmap_summary(
        df,
        kpi='rSOC_mult',
        y_variable_to_normalize=None,
        normalize_to=None,
        x_axis='retail_tariff',
        y_axis='feed_in_tariff',
        filter_contains="CH4",
        xlabel="",
        ylabel="",
        color_bar_label="",
        savefig=None
):
    df_filtered = df[df['scenario'].str.contains(filter_contains)]

    if normalize_to:
        norm_row = df[df['scenario'] == normalize_to]
        if norm_row.empty:
            raise ValueError(f"Normalization scenario '{normalize_to}' not found.")
        norm_val = norm_row.iloc[0][kpi]
        df_filtered = df_filtered.copy()
        df_filtered[kpi] = df_filtered[kpi] / norm_val

    if y_variable_to_normalize:
        df_filtered = df_filtered.copy()
        df_filtered[kpi] = df_filtered[kpi] / df_filtered[y_variable_to_normalize]

    pivot_table = df_filtered.pivot_table(index=y_axis, columns=x_axis, values=kpi, aggfunc='mean')
    pivot_table = pivot_table.sort_index(ascending=True).sort_index(axis=1, ascending=True)

    plt.figure(figsize=(10, 6))
    ax = sns.heatmap(
        pivot_table,
        annot=True,
        fmt=".2f",
        cmap="YlOrRd",
        cbar_kws={'label': color_bar_label},
        annot_kws={"size": 14, "weight": "normal", "color": "black"},
    )
    plt.xlabel(xlabel, fontsize=14, fontweight='normal', labelpad=10)
    plt.ylabel(ylabel, fontsize=14, fontweight='normal', labelpad=10)

    cbar = ax.collections[0].colorbar
    cbar.ax.yaxis.label.set_size(14)
    cbar.ax.yaxis.label.set_weight("normal")
    ax.tick_params(axis='both', labelsize=12)

    plt.tight_layout()
    if savefig:
        plt.savefig('results/rSOC_results/' + savefig + '.png', dpi=300)
    plt.show()


# =============================================================================
# 3b. Baseline-vs-uncertain plotting -- STEP 5, consumes the df_mc produced by
#     normalize_uncertainty_results (STEP 4). Works off `{col}_baseline` /
#     `{col}_perturbed` columns only, so it doesn't care which exact function
#     produced df_mc as long as those columns exist.
# =============================================================================

def summarize_uncertainty(df_mc, x_col='CAPEX', y_col='TOTEX', ci_inner=0.5, ci_outer=0.95):
    """
    Per-design summary statistics for `plot_uncertainty_band`.

    Expects df_mc as produced by `normalize_uncertainty_results` in this
    module, i.e. containing `{col}_baseline` and `{col}_perturbed` for both
    x_col and y_col (e.g. x_col='CAPEX' -> 'CAPEX_baseline', 'CAPEX_perturbed').

    Returns one row per design_id, sorted by ascending `x_baseline` (the
    deterministic x_col value) -- this replaces the old Pareto-front ordering
    now that designs are independent runs rather than points on a front.

    Columns returned: design_id, techno (if present), x_baseline, y_baseline,
    y_median, y_mean, y_low_{inner}, y_high_{inner}, y_low_{outer}, y_high_{outer}.
    """
    x_base_col, y_base_col = f"{x_col}_baseline", f"{y_col}_baseline"
    x_pert_col, y_pert_col = f"{x_col}_perturbed", f"{y_col}_perturbed"

    if x_col != 'CAPEX':
        x_base_col = x_col

    missing = [c for c in (x_base_col, y_base_col, y_pert_col) if c not in df_mc.columns]
    if missing:
        raise KeyError(
            f"df_mc is missing {missing}. Was it produced by this module's "
            "normalize_uncertainty_results (which names columns '{{col}}_baseline'/'{{col}}_perturbed')?"
        )

    inner_lbl, outer_lbl = int(round(ci_inner * 100)), int(round(ci_outer * 100))
    alpha_inner, alpha_outer = 1 - ci_inner, 1 - ci_outer

    rows = []
    for design_id, g in df_mc.groupby('design_id'):
        y = g[y_pert_col].values
        row = {
            'design_id': design_id,
            'x_baseline': g[x_base_col].iloc[0],
            'y_baseline': g[y_base_col].iloc[0],
            'y_median': np.median(y),
            'y_mean': np.mean(y),
            f'y_low_{inner_lbl}': np.quantile(y, alpha_inner / 2),
            f'y_high_{inner_lbl}': np.quantile(y, 1 - alpha_inner / 2),
            f'y_low_{outer_lbl}': np.quantile(y, alpha_outer / 2),
            f'y_high_{outer_lbl}': np.quantile(y, 1 - alpha_outer / 2),
        }
        if 'techno' in g.columns:
            row['techno'] = g['techno'].iloc[0]
        rows.append(row)

    return pd.DataFrame(rows).sort_values('x_baseline', ascending=True).reset_index(drop=True)


def plot_uncertainty_band(
    df_mc,
    x_col='CAPEX',
    y_col='TOTEX',
    statistical_metric = 'median',
    ci_inner=0.5,
    ci_outer=0.95,
    xlabel=None,
    ylabel=None,
    deterministic=False,
    baseline_label="Deterministic (baseline)",
    uncertain_label="Uncertain (median)",
    by_techno=None,
    figsize=(8, 5),
    fig_name=None,
):
    """
    Designs sorted by increasing baseline x_col (default: CAPEX), showing for
    y_col (default: TOTEX):
      - the deterministic baseline value (dashed line + markers), if
        `deterministic=True`
      - the Monte-Carlo median (solid line + markers, or per-techno markers if
        `by_techno` is given) -- "the real point"
      - the 50% CI band (ci_inner) in dark grey
      - the 95% CI band (ci_outer) in light grey

    `by_techno` : dict, optional
        Maps a 'techno' value (e.g. 'rSOC') to a matplotlib marker (e.g. 'h').
        If given, points are grouped and colored/marked by their 'techno'
        column instead of drawn as a single series -- requires df_mc to have
        a 'techno' column (present if get_results was given `techno_pos`).

    Returns (fig, ax, df_summary) -- df_summary is the per-design table from
    `summarize_uncertainty`, handy for further plots or for a table export.
    """
    if statistical_metric == 'median':
        y_KPI = 'y_median'
    elif statistical_metric == 'mean':
        y_KPI = 'y_mean'

    inner_lbl, outer_lbl = int(round(ci_inner * 100)), int(round(ci_outer * 100))
    df_summary = summarize_uncertainty(df_mc, x_col=x_col, y_col=y_col, ci_inner=ci_inner, ci_outer=ci_outer)

    x = df_summary['x_baseline']

    fig, ax = plt.subplots(figsize=figsize)

    # 95% CI -- light grey, drawn first (background)
    ax.fill_between(
        x, df_summary[f'y_low_{outer_lbl}'], df_summary[f'y_high_{outer_lbl}'],
        color="0.85", label=f"{outer_lbl}% CI"
    )
    # 50% CI -- dark grey, drawn on top
    ax.fill_between(
        x, df_summary[f'y_low_{inner_lbl}'], df_summary[f'y_high_{inner_lbl}'],
        color="0.55", label=f"{inner_lbl}% CI"
    )

    if deterministic:
        # Deterministic baseline
        ax.plot(x, df_summary['y_baseline'], linestyle="--", marker="o", color="#833d5e", lw=1.5, label=baseline_label)

    if by_techno is not None:
        techno_palette = {"PV-HP": "blue", "Batt": "green", "PTES": "red", "rSOC": "yellow"}
        for techno in list(by_techno.keys()):
            to_plot = df_summary[df_summary['techno'] == techno]
            ax.scatter(to_plot['x_baseline'], to_plot[y_KPI], marker=by_techno[techno],
                       color=techno_palette.get(techno, "grey"), label=f"{uncertain_label} ({techno})")
    else:
        # Monte-Carlo median (the actual computed point per design)
        ax.scatter(x, df_summary[y_KPI], marker='o', color="#2e4d7a", label=uncertain_label)
        for xi, yi in zip(x, df_summary[y_KPI]):
            ax.text(xi, yi, f"({xi:.2f},{yi:.2f})", ha='left', va='bottom')

    ax.set_xlabel(xlabel or f"{x_col} (baseline)")
    ax.set_ylabel(ylabel or y_col)
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)
    plt.tight_layout()

    if fig_name is not None:
        fig.savefig(fig_name, dpi=300)

    return fig, ax, df_summary


# =============================================================================
# 4. Uncertainty / Monte-Carlo engine
# =============================================================================

def annualized_capex(
    unit_cost_cinv1,
    unit_cost_cinv2,
    size,
    lifetime,
    project_lifetime=25,
    interest_rate=0.02
):
    """
    Vectorized annualized CAPEX including replacements.
    """
    unit_cost_cinv2 = np.asarray(unit_cost_cinv2, dtype=float)
    lifetime = np.asarray(lifetime, dtype=float)
    lifetime = np.maximum(lifetime, 1e-3)

    if size <= 0:
        return np.zeros_like(unit_cost_cinv2)

    initial_cost = unit_cost_cinv1 + unit_cost_cinv2 * size

    replacement_npv = np.zeros_like(unit_cost_cinv2)
    for i in range(len(unit_cost_cinv2)):
        replacement_years = np.arange(lifetime[i], project_lifetime, lifetime[i])
        for y in replacement_years:
            residual_fraction = min(1.0, (project_lifetime - y) / lifetime[i])
            replacement_npv[i] += initial_cost[i] * residual_fraction / (1 + interest_rate) ** y

    total_npv = initial_cost + replacement_npv

    crf = (interest_rate * (1 + interest_rate) ** project_lifetime) / ((1 + interest_rate) ** project_lifetime - 1)

    return total_npv * crf


def sample_clipped(rv, size, p_low, p_high, rng):
    samples = rv.rvs(size=size, random_state=rng)
    return np.clip(samples, p_low, p_high)


# =============================================================================
# 4a. STEP 2 -- sample the uncertain parameters (nothing else happens here)
# =============================================================================

def sample_uncertainty_draws(uncertainty_distributions, N_runs=1000, random_seed=42,
                              corr_factor=None, sweep_params=None):
    """
    STEP 2 of the pipeline: draw the uncertain parameters, and ONLY that --
    no cost formula is touched here. Inspect/plot the returned dataframe
    (histograms, `.describe()`, range checks) before moving on to
    `compute_uncertain_economics`.

    Per your choice, the SAME draws are used for every design (paired Monte
    Carlo): run #7 represents the same market scenario (same tariffs, same
    unit costs, same rSOC lifetime) for every design, so designs can be
    compared run-by-run, not just distribution-by-distribution. That's why
    this function does not take summary_df at all -- draws don't depend on
    the design.

    Generic loop, no hardcoded parameter names
    -------------------------------------------
    Every key in `uncertainty_distributions` is sampled the same way, in a
    single loop -- there's no per-parameter branch anywhere in this function,
    and the output column is named EXACTLY the same as the key in
    `uncertainty_distributions` (whatever that is -- e.g. straight from your
    Excel sheet). No renaming happens here.

    `corr_factor` (default: empty dict) maps a key to a multiplicative
    correction applied to its raw draw, e.g.
    `corr_factor={'rsoc_lifetime': 1000 / 8760}` to convert a raw draw to
    years. A key with no entry in `corr_factor` is used completely unmodified
    -- nothing is corrected unless you explicitly ask for it.

    When a correction IS applied for a key, BOTH the raw draw (`{key}_raw`)
    and the corrected value (`{key}`) are kept, so you can sanity-check the
    conversion. When no correction applies, only `{key}` is produced
    (identical to the raw draw).

    To add a new uncertain parameter: add it to `uncertainty_distributions`,
    and optionally give it an entry in `corr_factor` -- nothing else changes,
    and no column name is ever hardcoded downstream (see
    `compute_uncertain_economics`, which reads column names from
    `tech_registry`'s `cinv2_role`/`lifetime` entries).

    Bypass: choose which parameters are actually swept
    -----------------------------------------------------
    `sweep_params` (default None -> every key is swept, i.e. current
    behavior). Pass a list of keys to sample only those; every OTHER key in
    `uncertainty_distributions` is instead frozen at its distribution's
    median (`dist["rv"].median()`, clipped to [p_lower, p_upper]), repeated
    for all N_runs -- so downstream, that parameter contributes no
    variability, without touching `uncertainty_distributions` itself or any
    other part of the pipeline.

    Returns
    -------
    df_draws : DataFrame, one row per run_id, plus one (or two, if corrected)
    column(s) per key in `uncertainty_distributions`, named after that key.
    """
    if corr_factor is None:
        corr_factor = {}

    rng = np.random.default_rng(random_seed)
    columns = {"run_id": np.arange(N_runs)}

    for key, dist in uncertainty_distributions.items():
        if sweep_params is None or key in sweep_params:
            raw = sample_clipped(dist["rv"], N_runs, dist["p_lower"], dist["p_upper"], rng)
        else:
            median_val = np.clip(dist["rv"].median(), dist["p_lower"], dist["p_upper"])
            raw = np.full(N_runs, median_val)

        factor = corr_factor.get(key)
        if factor is not None:
            columns[f"{key}_raw"] = raw
            columns[key] = raw * factor
        else:
            columns[key] = raw

    return pd.DataFrame(columns)


# =============================================================================
# 4b. STEP 3 -- combine summary_df (absolute, baseline) with df_draws
#     (perturbed parameters, shared across designs) into the perturbed
#     economics. Still absolute here -- normalization is STEP 4, separate.
# =============================================================================

def compute_uncertain_economics(
    summary_df, df_draws, design_id_col='scenario',
    tech_registry=None,
    column_overrides=None, lifetime_overrides=None,
    passthrough_summary_cols=('techno', 'CAPEX_tot_storage'),
    project_lifetime=25, interest_rate=0.02,
):
    """
    STEP 3 of the pipeline: apply the SAME df_draws (from
    `sample_uncertainty_draws`) to every design in `summary_df` -- the
    DataFrame `get_results` already gives you, unmodified -- and compute the
    perturbed CAPEX/OPEX/TOTEX/GWP alongside each design's baseline
    (deterministic) values. Everything stays in ABSOLUTE terms here, so you
    can check the raw CHF/kgCO2 numbers before any per-m2 normalization
    happens (that's `normalize_uncertainty_results`).

    Every technology comes from `tech_registry`
    ---------------------------------------------
    There is no per-technology hardcoded block anywhere in this function --
    it loops over `tech_registry` (default DEFAULT_TECH_REGISTRY; pass the
    SAME registry you gave `get_results`). For each technology, its size and
    cinv1 are read from `summary_df` (via `size_metric`/`cinv1_key`), its
    cinv2 draw is read from `df_draws` (via `cinv2_role`, or an entry in
    `column_overrides` if your Excel sheet names it differently), and its
    lifetime is either a fixed constant or a swept `df_draws` column
    (whichever `tech_registry[tech]['lifetime']` specifies -- override for
    one call via `lifetime_overrides`).

    Any OTHER column present in df_draws (beyond what tech_registry needs)
    is also carried through into df_mc unmodified, under its own name, purely
    for traceability -- so adding an extra uncertain parameter you don't
    (yet) use in a cost formula doesn't require touching this function either.

    Reads directly off `summary_df` -- no separate design-prep step needed,
    since `get_results` already produces every column tech_registry requires.
    `design_id_col` (default 'scenario') identifies each row.
    `passthrough_summary_cols`: extra summary_df columns (beyond what
    tech_registry/DESIGN_COLUMNS need) to carry through into df_mc
    unmodified, e.g. 'techno' or 'CAPEX_tot_storage'.

    Returns
    -------
    df_mc : DataFrame, one row per (design_id, run_id), with:
    - design diagnostics: ERA_tot, Elec_import, Elec_export, CAPEX_fixed,
      OPEX_fixed, plus every technology's size/CAPEX/cinv1.
    - every column from df_draws, carried through unmodified.
    - for CAPEX, OPEX, TOTEX, GWP, and every technology's capex_metric:
      `{metric}_baseline_abs` (constant per design, from get_results) and
      `{metric}_perturbed_abs` (varies per run). No normalized (per-m2)
      columns yet -- that's `normalize_uncertainty_results`.
    """
    tech_registry = tech_registry or DEFAULT_TECH_REGISTRY
    column_overrides = column_overrides or {}
    lifetime_overrides = lifetime_overrides or {}
    resolve = lambda role: column_overrides.get(role, role)

    design_cols = _design_columns(tech_registry)
    missing_design_cols = [c for c in design_cols if c not in summary_df.columns] + (
        [design_id_col] if design_id_col not in summary_df.columns else []
    )
    if missing_design_cols:
        raise KeyError(
            f"summary_df is missing columns required for the uncertainty analysis: {missing_design_cols}. "
            "Make sure it was produced by get_results() with the SAME tech_registry."
        )
    bad_era = summary_df['ERA_tot'].isna() | (summary_df['ERA_tot'] <= 0)
    if bad_era.any():
        bad_ids = summary_df.loc[bad_era, design_id_col].tolist()
        print(f"Warning: non-positive or missing ERA_tot for designs {bad_ids}; "
              "per-m2 normalization will fail or be meaningless for these rows.")

    # Resolve every df_draws column needed, generically from tech_registry
    draw_col_lookup = {}
    for tech, spec in tech_registry.items():
        draw_col_lookup[f'{tech}.cinv2'] = resolve(spec['cinv2_role'])
        if isinstance(spec['lifetime'], str):
            draw_col_lookup[f'{tech}.lifetime'] = resolve(spec['lifetime'])
    draw_col_lookup['retail_tariff'] = resolve('electricity_retail')
    draw_col_lookup['feed_in_tariff'] = resolve('electricity_feed_in')

    missing = {k: v for k, v in draw_col_lookup.items() if v not in df_draws.columns}
    if missing:
        raise KeyError(
            f"df_draws is missing the following columns: {missing}. Either "
            "uncertainty_distributions/sample_uncertainty_draws wasn't given a "
            "matching key, or column_overrides doesn't match your actual column name."
        )

    N_runs = len(df_draws)
    retail_tariff_draws = df_draws[draw_col_lookup['retail_tariff']].values
    feed_in_tariff_draws = df_draws[draw_col_lookup['feed_in_tariff']].values
    # Every df_draws column, carried through unmodified -- fully generic,
    # no hardcoded names, whatever extra columns exist (e.g. a '_raw' column
    # from a corr_factor, or a parameter not used in any formula) pass through.
    passthrough_cols = {c: df_draws[c].values for c in df_draws.columns}

    all_results = []
    for _, row in summary_df.iterrows():
        design_id = row[design_id_col]
        elec_import = row["Elec_import"]
        elec_export = row["Elec_export"]
        capex_fixed = row["CAPEX_fixed"]
        opex_fixed = row["OPEX_fixed"]

        capex_perturbed_abs = np.full(N_runs, float(capex_fixed))
        tech_columns = {}

        # --- Generic per-technology CAPEX, driven ENTIRELY by tech_registry ---
        for tech, spec in tech_registry.items():
            size = row[spec['size_metric']]
            cinv1 = row[spec['cinv1_key']]
            cinv2_draws = df_draws[draw_col_lookup[f'{tech}.cinv2']].values

            lifetime_spec = lifetime_overrides.get(tech, spec['lifetime'])
            if isinstance(lifetime_spec, str):
                lifetime = df_draws[draw_col_lookup[f'{tech}.lifetime']].values
            else:
                lifetime = np.full(N_runs, lifetime_spec)

            tech_capex_perturbed = annualized_capex(
                unit_cost_cinv1=cinv1, unit_cost_cinv2=cinv2_draws,
                size=size, lifetime=lifetime,
                project_lifetime=project_lifetime, interest_rate=interest_rate
            )
            capex_perturbed_abs = capex_perturbed_abs + tech_capex_perturbed

            tech_columns[f"{spec['capex_metric']}_baseline_abs"] = np.repeat(row[spec['capex_metric']], N_runs)
            tech_columns[f"{spec['capex_metric']}_perturbed_abs"] = tech_capex_perturbed
            tech_columns[spec['size_metric']] = np.repeat(size, N_runs)
            tech_columns[spec['cinv1_key']] = np.repeat(cinv1, N_runs)

        # Same units convention as get_results' OPEX_fixed: tariff * 1000
        # (elec_import/export in MWh, tariff in CHF/kWh -> CHF).
        opex_perturbed_abs = (
            opex_fixed
            + elec_import * retail_tariff_draws * 1000
            - elec_export * feed_in_tariff_draws * 1000
        )
        totex_perturbed_abs = capex_perturbed_abs + opex_perturbed_abs
        # GWP isn't perturbed by any distribution here (kept constant per design);
        # tracked with the same baseline/perturbed pairing for a consistent API,
        # ready for the day a GWP uncertainty distribution is added.
        gwp_perturbed_abs = np.repeat(row["GWP"], N_runs)

        def pair(name, baseline_abs, perturbed_abs):
            return {
                f"{name}_baseline_abs": np.repeat(baseline_abs, N_runs),
                f"{name}_perturbed_abs": perturbed_abs,
            }

        columns = {
            "design_id": np.repeat(design_id, N_runs),
            "ERA_tot": np.repeat(row.get("ERA_tot", np.nan), N_runs),
            "Elec_import": np.repeat(elec_import, N_runs),
            "Elec_export": np.repeat(elec_export, N_runs),
            "CAPEX_fixed": np.repeat(capex_fixed, N_runs),
            "OPEX_fixed": np.repeat(opex_fixed, N_runs),
            # Every technology's size/CAPEX(baseline+perturbed)/cinv1
            **tech_columns,
            # Every df_draws column, whatever it's called
            **passthrough_cols,
        }
        for col in passthrough_summary_cols:
            if col in row.index and col not in columns:
                columns[col] = np.repeat(row[col], N_runs)

        columns.update(pair("CAPEX", row["CAPEX"], capex_perturbed_abs))
        columns.update(pair("OPEX", row["OPEX"], opex_perturbed_abs))
        columns.update(pair("TOTEX", row["TOTEX"], totex_perturbed_abs))
        columns.update(pair("GWP", row["GWP"], gwp_perturbed_abs))

        all_results.append(pd.DataFrame(columns))

    return pd.concat(all_results, ignore_index=True)


# =============================================================================
# 4c. STEP 4 -- normalize by ERA (explicit, opt-in, per-row)
# =============================================================================

def normalize_uncertainty_results(df_mc, metrics=None, era_col='ERA_tot', normalize_by_ERA=True,
                                   tech_registry=None):
    """
    STEP 4 of the pipeline: turn the absolute `{metric}_baseline_abs` /
    `{metric}_perturbed_abs` columns from `compute_uncertain_economics` into
    the `{metric}_baseline` / `{metric}_perturbed` columns used for plotting
    -- per m2 if `normalize_by_ERA=True` (using each row's OWN `era_col`,
    never a single global value), or identical to the `_abs` columns if
    `normalize_by_ERA=False`.

    The `_abs` columns are always left untouched, so you can always recover
    the absolute totals regardless of what you choose here.

    `metrics` defaults to CAPEX/OPEX/TOTEX/GWP plus every technology's
    capex_metric from `tech_registry` (default DEFAULT_TECH_REGISTRY) --
    derived, not hardcoded, so it never drifts out of sync with
    `compute_uncertain_economics`. Pass the SAME `tech_registry` you used
    upstream to stay consistent, or pass `metrics` explicitly to override.
    """
    if metrics is None:
        tech_registry = tech_registry or DEFAULT_TECH_REGISTRY
        metrics = ['CAPEX', 'OPEX', 'TOTEX', 'GWP'] + [spec['capex_metric'] for spec in tech_registry.values()]

    if normalize_by_ERA:
        if era_col not in df_mc.columns:
            raise KeyError(f"'{era_col}' not found in df_mc; cannot normalize.")
        bad = df_mc[era_col].isna() | (df_mc[era_col] <= 0)
        if bad.any():
            raise ValueError(f"{bad.sum()} rows have invalid {era_col} (<=0 or NaN); cannot normalize.")
        era = df_mc[era_col]
    else:
        era = 1

    df_mc = df_mc.copy()
    for m in metrics:
        base_abs_col, pert_abs_col = f"{m}_baseline_abs", f"{m}_perturbed_abs"
        if base_abs_col not in df_mc.columns or pert_abs_col not in df_mc.columns:
            raise KeyError(f"Missing {base_abs_col}/{pert_abs_col}; was df_mc produced by compute_uncertain_economics?")
        df_mc[f"{m}_baseline"] = df_mc[base_abs_col] / era
        df_mc[f"{m}_perturbed"] = df_mc[pert_abs_col] / era

    return df_mc