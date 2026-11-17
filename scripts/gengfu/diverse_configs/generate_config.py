"""
generate_config.py
==================

One generic function, ``generate_config()``, that turns ANY district + economic context into a small set of
diverse energy-system configurations, ready for the Monte-Carlo pipeline in ``scripts/uncertainty_postprocess.py``.

    Inputs                                   Outputs
    ------                                   -------
    district_id                              3 x N pickles  (design first, then operation context)
    uncertain_var_link   {var: KPI}          summary_df     (get_results() output, one row per design x context)
    KPIs_objective_link  {KPI: lever}        selection      (which designs were kept and why)
    n_max                'auto' | int | None figures        (diversity + uncertain-variable subplots, HTML)
    contexts             {name: {RT, FI}}

One call runs every step below. REHO results are saved as they are produced and reused when the function is called
again with the same out_dir (an interrupted run resumes where it stopped; nothing is ever overwritten):

    1. generate   TOTEX optimum + SS maximum, then every lever of KPIs_objective_link   -> pool_<lever>.pickle
    2. evaluate   every pool design re-run with fix_units at the reference context     -> pool_eval.pickle
                  (removes the operation bias of the levers: all KPIs are comparable)
    3. select     percent-based diversity selection (see select_configurations)        -> selection.pickle
    4. contexts   each selected design re-run with fix_units under every context       -> <district>_<ID>_<tech>_<ctx>_<RT>_<FI>.pickle
    5. summarize  get_results() on the 3 x N pickles + KPIs + figures                   -> summary_df.pickle, figures/*.html

Selection rule (all thresholds are SHARES OF THE DISTRICT'S OWN POOL RANGE, so they transfer to any district):
    a. every feature (KPIs + installed capacities) is min-max scaled to 0-100 % of the pool range
    b. near-duplicates: all features within dup_tol (5 %) -> keep the cheaper one
    c. must keep: TOTEX optimum + cheapest design of each storage technology set
    d. every feature range is split in n_bands (4 x 25 %); every non-empty band gets >= 1 design
    e. farthest-point fill
    f. N = smallest N >= n_min such that (d) holds, every feature covers >= min_range (95 %) of its range and the
       KS distance between selected and pool distributions is <= max_ks (0.25) for every feature.
    g. if an integer n_max < N: the n_max designs are re-chosen to cover the 4 KPIs as widely as possible (must keep,
       min and max of each KPI, every KPI band, farthest-point fill in KPI space); 'capped' = True, 'rule_met' may be False.

Not changed: REHO itself. Levers use only existing REHO options (EMOO_TOTEX, EMOO_GWP, enforce/exclude units,
Units_Fmin, tariffs, roof share). GU is a KPI only (no lever).
"""

import copy
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from reho.model.reho import *  # noqa: F401,F403  (REHO, infrastructure)

# =====================================================================================================================
# Defaults (override any of them through the function arguments)
# =====================================================================================================================

DEFAULT_CONTEXTS = {'attractive': {'RT': 0.20, 'FI': 0.15},
                    'baseline': {'RT': 0.30, 'FI': 0.10},
                    'harsh': {'RT': 0.04, 'FI': 0.02}}

# Which KPI each uncertain variable acts on (used for the "uncertain variable" subplots and kept in the outputs).
DEFAULT_UNCERTAIN_VAR_LINK = {'electricity_feed_in': 'el_export',      # keys = parameter ids of
                              'electricity_retail': 'el_import',       # scripts/uncertainty/energy_storage_parameters.xlsx
                              'battery_capex': 'Battery_district',
                              'rsoc_capex': 'rSOC_district',
                              'rsoc_lifetime': 'rSOC_district',
                              'ch4_tank_capex': 'CH4_storage_IP_district'}

# Which lever generates diversity for which KPI. Every lever is relative to the district (percent / per 1000 m2 ERA).
#   mga       : TOTEX <= TOTEX_opt + eps * |TOTEX_opt|, objectives push CAPEX down/up and SS up
#   ss_target : import fixed at a share of the way from the TOTEX optimum to the SS maximum
#   tariffs   : TOTEX optimum under other (RT, FI) pairs
#   tech_sets : storage technology sets (exclude units)
#   sizes     : forced minimum sizes [per 1000 m2 ERA] and reduced PV roof share
#   GU        : None -> KPI only, no lever
DEFAULT_KPIS_OBJECTIVE_LINK = {
    'TOTEX': {'lever': 'mga', 'eps': [0.1, 0.2, 0.3, 0.5, 1.0], 'objectives': ['CAPEX_min', 'CAPEX_max', 'SS_max']},
    'SS': {'lever': 'ss_target', 'fractions': [0.25, 0.50, 0.75]},
    'price': {'lever': 'tariffs', 'pairs': [(0.16, 0.056), (0.16, 0.083), (0.16, 0.124), (0.30, 0.056), (0.30, 0.07),
                                            (0.30, 0.124), (0.40, 0.056), (0.40, 0.07), (0.40, 0.10), (0.40, 0.124)]},
    'installed_capacity': {'lever': 'sizes', 'rSOC_district': [3, 6, 10, 15], 'Battery_district': [50, 100, 150],
                           'roof_share': [0.50, 0.75],
                           'tech_sets': ['no_storage', 'battery_only', 'rsoc_only']},
    'GU': None,
}

# Selection features: KPIs + installed capacities (water tanks / electric heaters ignored: negligible share).
DEFAULT_SELECTION = {'kpis': ['TOTEX', 'CAPEX', 'SS', 'GU'],
                     'capacities': ['PV', 'HeatPump_Air', 'Battery_district', 'rSOC_district', 'CH4_storage_IP_district'],
                     'dup_tol': 0.05, 'n_bands': 4, 'min_range': 0.95, 'max_ks': 0.25, 'n_min': 10}

# Technology costs at the MEDIANS of scripts/uncertainty/energy_storage_parameters.xlsx, converted exactly like the
# supervisor's Monte-Carlo pipeline (rSOC lifetime kh -> yr at full load 1000/8760; CH4 tank USD = CHF, corr 1), so the
# designs are generated with the same cost basis the uncertainty analysis perturbs. Use tech_from_distributions() to
# re-derive them when the Excel file changes.
RSOC_KH_TO_YR = 1000 / 8760
DEFAULT_TECH = {'Battery_district': {'Cost_inv2': 300.0},
                'rSOC_district': {'Cost_inv2': 1073.3, 'lifetime': 60.0 * RSOC_KH_TO_YR},   # 60 kh = 6.85 yr
                'CH4_storage_IP_district': {'Cost_inv2': 1.981}}


def tech_from_distributions(uncertainty_distributions, kh_to_yr=RSOC_KH_TO_YR):
    """DEFAULT_TECH from esd.build_distribution_dict(...) (medians), same conversions as the MC pipeline."""
    m = {k: float(v['median']) for k, v in uncertainty_distributions.items()}
    return {'Battery_district': {'Cost_inv2': m['battery_capex']},
            'rSOC_district': {'Cost_inv2': m['rsoc_capex'], 'lifetime': m['rsoc_lifetime'] * kh_to_yr},
            'CH4_storage_IP_district': {'Cost_inv2': m['ch4_tank_capex']}}


DEFAULT_REHO = {'cluster': {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24},
                'method': {'interperiod_storage': True, 'district-scale': True, 'parallel_computation': False,
                           'print_logs': False},
                'DW_params': {'max_iter': 2},
                'other_grids': {'Hydrogen': {'Cost_supply_cst': 0.45, 'Cost_demand_cst': 0.25}, 'Biomethane': {},
                                'CO2': {}, 'Heat': {'Cost_supply_cst': 0.15, 'Cost_demand_cst': 0.00}},
                'ss_objective': 'GWP_OP', 'solver': 'gurobi'}

KEEP_UNITS = ['PV', 'HeatPump_Air', 'Battery_district', 'rSOC_district', 'CH4_storage_IP_district', 'WaterTankSH',
              'WaterTankDHW', 'ElectricalHeater_SH', 'ElectricalHeater_DHW', 'MTR_district', 'Compressor_IP_district',
              'CO2_storage_IP_district', 'ElectricalHeater_other_district']
RSOC_CHAIN = ['rSOC_district', 'MTR_district', 'Compressor_IP_district', 'CO2_storage_IP_district',
              'CH4_storage_IP_district']
TECH_SETS = {'no_storage': ['Battery_district'] + RSOC_CHAIN, 'battery_only': RSOC_CHAIN, 'rsoc_only': ['Battery_district']}
LOAD_UNITS = ['HeatPump_Air', 'ElectricalHeater_SH', 'ElectricalHeater_DHW', 'ElectricalHeater_other_district']
KPI_COLUMNS = ['TOTEX', 'CAPEX', 'OPEX', 'SS', 'GU', 'el_import', 'el_export']
CAPACITY_UNITS = ['PV', 'HeatPump_Air', 'ElectricalHeater_SH', 'ElectricalHeater_DHW', 'WaterTankSH', 'WaterTankDHW',
                  'Battery_district', 'rSOC_district', 'MTR_district', 'CH4_storage_IP_district']
SIZE_TOL = 1e-3
ANCHOR = ('anchor', 'totex_opt')                                           # key of the TOTEX optimum in pool_eval

# Daily battery (Battery_district) is NOT the seasonal Battery_IP of DEFAULT_TECH_REGISTRY -> own entry.
BATTERY_DAILY_REGISTRY_ENTRY = {'unit_pattern': 'Battery_district', 'size_metric': 'Battery_daily_size',
                                'capex_metric': 'Battery_daily_CAPEX', 'cinv1_key': 'battery_daily_cinv1',
                                'cinv1_default': 30000, 'cinv2_role': 'battery_capex', 'lifetime': 15.0}
# the xlsx has one Li-ion "Battery CAPEX" sheet -> the daily battery draws the same battery_capex column


# =====================================================================================================================
# Main function
# =====================================================================================================================

def generate_config(district_id, uncertain_var_link=None, KPIs_objective_link=None, n_max='auto', contexts=None, *,
                    out_dir, qb_file=None, qbuildings_data=None, buildings=None, seed=2026, weather=None,
                    reference_context='baseline', selection=None, tech=None, reho_settings=None,
                    uncertainty_distributions=None,
                    postprocess_dir=None):
    """Generate diverse configurations for one district and re-run them under several economic contexts.

    Parameters
    ----------
    district_id : str
        Name of the district (used in file names). Its buildings come from ``qbuildings_data`` (a REHO qbuildings dict)
        or, if not given, from ``qb_file`` (pickle {district_id: qbuildings_data}).
    buildings : None | list of egid | int
        Which buildings of the district to model. None = all; list = these egids (reproducible, recommended);
        int n = n buildings drawn at random with ``seed`` (the drawn egids are printed and saved in settings.pickle,
        copy them into a list for later runs).
    weather : dict, optional
        REHO ``cluster`` dict (weather location and typical days), e.g.
        {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24} (default).
    uncertain_var_link : dict {uncertain variable: KPI or capacity column}
        e.g. {'electricity_feed_in': 'el_export', 'rsoc_lifetime': 'rSOC_district'}. One subplot per entry shows that the
        selected designs differ in what the uncertainty acts on. Default DEFAULT_UNCERTAIN_VAR_LINK.
    KPIs_objective_link : dict {KPI: lever spec or None}
        Levers used to generate diversity (see DEFAULT_KPIS_OBJECTIVE_LINK). None = KPI evaluated only (e.g. GU).
    n_max : 'auto' | int | None
        'auto' -> smallest N meeting the coverage rule; int -> same rule, at most n_max; None -> no selection
        (all designs left after near-duplicate removal).
    contexts : dict {name: {'RT': .., 'FI': ..}}
        Economic contexts for the fix_units re-runs (operation bias). Default DEFAULT_CONTEXTS.
    qb_file, out_dir : str
        District pickle and output folder (created; existing pickles are reused, never overwritten).
    reference_context : str
        Context (key of ``contexts``) at which the pool is generated and compared.
    uncertainty_distributions : dict, optional
        esd.build_distribution_dict(...) output; if given, technology costs = its medians (tech_from_distributions).

    Returns
    -------
    Only the SELECTED designs appear in the outputs (the others are dropped inside the function and never re-run
    under the economic contexts):
    dict with 'cluster_table' (selected designs grouped by storage class, KPIs at the reference context),
    'files' (3 x N pickles), 'summary_df' (design x context, input of the Monte-Carlo pipeline),
    'uncertain_var_columns' ({uncertain variable: summary_df column}), 'selection' (rule report),
    'legend' (meaning of the design codes G0..G5), 'figures', 'get_results_kwargs'.
    """
    uncertain_var_link = uncertain_var_link or DEFAULT_UNCERTAIN_VAR_LINK
    levers = KPIs_objective_link or DEFAULT_KPIS_OBJECTIVE_LINK
    contexts = contexts or DEFAULT_CONTEXTS
    sel_cfg = {**DEFAULT_SELECTION, **(selection or {})}
    cfg = {**DEFAULT_REHO, **(reho_settings or {})}
    tech = tech or (tech_from_distributions(uncertainty_distributions) if uncertainty_distributions else DEFAULT_TECH)
    if reference_context not in contexts:
        raise ValueError(f'reference_context {reference_context!r} is not one of the contexts {list(contexts)}')
    known = set(KPI_COLUMNS) | set(CAPACITY_UNITS)
    bad = {u: k for u, k in uncertain_var_link.items() if k not in known}
    if bad:
        raise ValueError(f'uncertain_var_link points to unknown KPIs {bad}; available: {sorted(known)}')
    if weather:
        cfg['cluster'] = weather
    os.makedirs(os.path.join(out_dir, 'figures'), exist_ok=True)
    qbd = load_buildings(district_id, qb_file, qbuildings_data, buildings, seed)
    check_settings(out_dir, district_id, qbd, cfg, tech, contexts[reference_context])
    ctx = District(district_id, qbd, out_dir, contexts[reference_context], tech, cfg)
    out = {}

    # 1. generate the pool: TOTEX optimum, SS maximum, then every lever of KPIs_objective_link       (REHO)
    ctx.generate_pool(levers)

    # 2. evaluate every pool design with fix_units at the reference context -> comparable KPIs        (REHO)
    ctx.evaluate_pool()
    pool = ctx.load('pool_eval')
    T = pool_table(pool['results'], ctx.era, levers)
    failed = {k: m['error'] for k, m in pool['meta'].items() if 'error' in m}
    if failed:
        print(f'WARNING: {len(failed)} pool designs could not be evaluated and are left out:', failed)

    # 3. select N diverse configurations (percent-based rule)                                          (no REHO)
    features = sel_cfg['kpis'] + sel_cfg['capacities']
    sel = select_configurations(T, features, n_max=n_max, cap_features=sel_cfg['kpis'],
                                **{k: sel_cfg[k] for k in ('dup_tol', 'n_bands', 'min_range', 'max_ks', 'n_min')})
    ctx.dump('selection', sel)
    out['selection'] = sel
    out['cluster_table'] = cluster_table(T.loc[sel['selected']])          # selected only: cluster -> code -> KPIs
    out['legend'] = pd.DataFrame([{'generator': g, 'meaning': m} for g, m in GENERATOR_CODES.values()]).set_index('generator')

    # 4. re-run each selected design under every economic context with fix_units -> 3 x N pickles     (REHO)
    out['files'] = ctx.run_contexts(pool['results'], T.loc[sel['selected']], contexts)

    # 5. dataframe for the Monte-Carlo pipeline (get_results) + diversity figures                      (no REHO)
    out['summary_df'], out['get_results_kwargs'] = summarize(ctx, out['files'], T, postprocess_dir)
    out['uncertain_var_columns'] = {u: f'{k}_kpi' for u, k in uncertain_var_link.items()}   # columns of summary_df
    out['figures'] = make_figures(ctx, out['summary_df'], uncertain_var_link, reference_context)
    return out


# =====================================================================================================================
# District: REHO runs (steps 1, 2, 4)
# =====================================================================================================================

def load_buildings(district_id, qb_file=None, qbuildings_data=None, buildings=None, seed=2026):
    """qbuildings dict restricted to the chosen buildings, renumbered Building1..n in egid order (reproducible)."""
    if qbuildings_data is None:
        if qb_file is None:
            raise ValueError('give qbuildings_data or qb_file')
        with open(qb_file, 'rb') as fh:
            qbuildings_data = pickle.load(fh)[district_id]
    qbd = copy.deepcopy(qbuildings_data)
    by_egid = {str(b['egid']): b for b in qbd['buildings_data'].values()}
    if buildings is None:
        egids = sorted(by_egid)
    elif isinstance(buildings, int):
        egids = sorted(np.random.default_rng(seed).choice(sorted(by_egid), size=buildings, replace=False).tolist())
        print(f'{buildings} buildings drawn with seed {seed}: buildings={egids}')
    else:
        egids = [str(e) for e in buildings]
        missing = [e for e in egids if e not in by_egid]
        if missing:
            raise ValueError(f'egids not in district {district_id}: {missing}')
    qbd['buildings_data'] = {f'Building{i + 1}': by_egid[e] for i, e in enumerate(egids)}
    return qbd


def check_settings(out_dir, district_id, qbd, cfg, tech, ref):
    """out_dir belongs to ONE set of inputs: refuse to reuse its pickles if buildings / weather / costs changed."""
    now = {'district': district_id, 'egids': [str(b['egid']) for b in qbd['buildings_data'].values()],
           'cluster': cfg['cluster'], 'tech': tech, 'reference_context': ref, 'DW_params': cfg['DW_params']}
    f = os.path.join(out_dir, 'settings.pickle')
    if os.path.exists(f):
        old = pickle.load(open(f, 'rb'))
        diff = [k for k in now if old.get(k) != now[k]]
        if diff:
            raise ValueError(f'{out_dir} was made with other inputs ({diff}); use a new out_dir')
    else:
        with open(f, 'wb') as fh:
            pickle.dump(now, fh)


class District:
    def __init__(self, district_id, qbd, out_dir, ref, tech, cfg):
        self.qb = qbd
        self.id, self.out_dir, self.ref, self.tech, self.cfg = district_id, out_dir, ref, tech, cfg
        self.era = sum(b['ERA'] for b in self.qb['buildings_data'].values())
        files = ['building_units.csv', 'building_units_IP.csv', 'district_units.csv', 'district_units_IP.csv']
        all_units = {u for f in files for u in
                     pd.read_csv(os.path.join(infrastructure.path_to_infrastructure, f), sep=';')['Unit']}
        self.exclude = sorted(all_units - set(KEEP_UNITS))

    # ---------------------------------------------------------------- files
    def path(self, name):
        return os.path.join(self.out_dir, f'{name}.pickle')

    def load(self, name):
        p = self.path(name)
        return pickle.load(open(p, 'rb')) if os.path.exists(p) else {'results': {}, 'meta': {}}

    def dump(self, name, obj):
        with open(self.path(name), 'wb') as fh:
            pickle.dump(obj, fh)

    # ---------------------------------------------------------------- REHO inputs
    def build_inputs(self, scenario, rt, fi, ss_mode=False, zero_unit_gwp=False, fmin=None):
        grids = infrastructure.initialize_grids({'Electricity': {'Cost_supply_cst': rt, 'Cost_demand_cst': fi},
                                                 **copy.deepcopy(self.cfg['other_grids'])})
        grids['Electricity']['Network_capacity_existing'] = 1e6          # unlimited grid
        if ss_mode:                                                        # SS runs: no credit for exports,
            for layer in grids:                                            # heat import never replaces electricity
                grids[layer]['GWP_demand_cst'] = 0.0
            if 'Heat' in grids:
                grids['Heat']['GWP_supply_cst'] = 1e3
        units = infrastructure.initialize_units(scenario, grids, district_data=True, interperiod_data='district')
        present = {r['Unit'] for r in units['district_units']}
        missing = [u for u in ('rSOC_district', 'MTR_district')
                   if u not in present and u not in scenario.get('exclude_units', [])]
        assert not missing, f'units dropped by REHO (missing layer?): {missing}'
        for g in ('building_units', 'district_units'):
            for r in units[g]:
                r.update(self.tech.get(r['Unit'], {}))
                if fmin and r['Unit'] in fmin:
                    r['Units_Fmin'] = fmin[r['Unit']]
                if zero_unit_gwp:
                    r.update(GWP_unit1=0.0, GWP_unit2=0.0)
        return grids, units

    def make_reho(self, name, objective, rt=None, fi=None, exclude=(), enforce=(), emoo=None, fix=None,
                  roof_share=1.0, **inp):
        rt = self.ref['RT'] if rt is None else rt
        fi = self.ref['FI'] if fi is None else fi
        scenario = {'Objective': objective, 'name': name, 'exclude_units': self.exclude + list(exclude),
                    'enforce_units': list(enforce), 'EMOO': {'EMOO_grid': 0, **(emoo or {})}}
        grids, units = self.build_inputs(scenario, rt, fi, **inp)
        m = {**copy.deepcopy(self.cfg['method']), 'include_all_solutions': True}
        if fix is not None:
            m['fix_units'] = True
        qbd = copy.deepcopy(self.qb)
        for b in qbd['buildings_data'].values():
            b['SolarRoofArea'] *= roof_share
        reho = REHO(qbuildings_data=qbd, units=units, grids=grids, cluster=self.cfg['cluster'], scenario=scenario,
                    method=m, DW_params=self.cfg['DW_params'], solver=self.cfg['solver'])
        if fix is not None:
            reho.df_fix_Units = fix
        return reho

    def solve(self, store, key, reho, name, info):
        """Solve the scenario set on reho, store under key, write the store pickle at once (crash-safe)."""
        d = self.load(store)
        t0 = pd.Timestamp.now()
        try:
            reho.single_optimization()
            d['results'][key] = reho.results[name][0]
            d['meta'][key] = {**info, 'runtime': str(pd.Timestamp.now() - t0)}
        except Exception as e:                                            # keep going, record the failure
            d['meta'][key] = {**info, 'error': repr(e)[:300]}
        self.dump(store, d)
        print(store, key, d['meta'][key])

    # ---------------------------------------------------------------- step 1: generate
    def generate_pool(self, levers):
        st = 'pool_anchor'
        if 'totex_opt' not in self.load(st)['results']:
            self.solve(st, 'totex_opt', self.make_reho('totex_opt', 'TOTEX'), 'totex_opt', {'lever': 'anchor'})
        if 'ss_max' not in self.load(st)['results']:
            self.solve(st, 'ss_max', self.make_reho('ss_max', self.cfg['ss_objective'], ss_mode=True), 'ss_max',
                       {'lever': 'anchor'})
        anchors, meta = self.load(st)['results'], self.load(st)['meta']
        if not {'totex_opt', 'ss_max'} <= set(anchors):
            raise RuntimeError(f'anchor runs failed, nothing else can be generated: {meta}')
        ref, ssm = anchors['totex_opt'], anchors['ss_max']
        p = ref['df_Performance'].loc['Network']
        totex_opt = (p['Costs_inv'] + p['Costs_op']) / self.era           # what EMOO_TOTEX bounds
        # MGA slack = eps x |TOTEX_opt|: still a relaxation when TOTEX_opt <= 0 (high feed-in tariff / large export)
        slack = abs(totex_opt)
        if slack < 1.0:
            print(f'WARNING: |TOTEX_opt| = {slack:.3f} CHF/m2/yr is very small, the MGA slack eps x |TOTEX_opt| is narrow')
        imp = lambda r: 1000 * r['df_Annuals'].xs('Network', level='Hub').loc['Electricity', 'Supply_MWh']

        for kpi, spec in levers.items():
            if not spec:
                continue                                                   # KPI only (e.g. GU)
            st, done = f'pool_{kpi}', set(self.load(f'pool_{kpi}')['results'])
            lever = spec['lever']
            if lever == 'mga':
                obj = {'CAPEX_min': 'CAPEX', 'CAPEX_max': 'OPEX', 'SS_max': self.cfg['ss_objective']}
                todo = [(e, o) for e in spec['eps'] for o in spec['objectives'] if (e, o) not in done]
                if todo:
                    reho = self.make_reho('mga_ref', 'TOTEX', ss_mode=True)
                    reho.single_optimization()                             # anchor columns for the band runs
                    for e, o in todo:
                        name = f'mga_{e:g}_{o}'
                        reho.scenario.update(name=name, Objective=obj[o],
                                             EMOO={'EMOO_grid': 0, 'EMOO_TOTEX': totex_opt + e * slack})
                        self.solve(st, (e, o), reho, name, {'lever': lever, 'eps_share': e, 'objective': o})
            elif lever == 'ss_target':
                f_el = self.build_inputs({'exclude_units': [], 'enforce_units': []}, **self._p())[0][
                    'Electricity']['GWP_supply_cst']
                for fr in spec['fractions']:
                    if fr in done:
                        continue
                    target = imp(ref) + fr * (imp(ssm) - imp(ref))
                    name = f'ss_{int(100 * fr)}'
                    reho = self.make_reho(name, 'TOTEX', ss_mode=True, zero_unit_gwp=True,
                                          emoo={'EMOO_GWP': f_el * target / self.era})
                    self.solve(st, fr, reho, name, {'lever': lever, 'import_target_MWh': target / 1000})
            elif lever == 'tariffs':
                for rt, fi in spec['pairs']:
                    if (rt, fi) in done or (rt, fi) == (self.ref['RT'], self.ref['FI']):
                        continue
                    name = f'price_RT{rt}_FI{fi}'
                    self.solve(st, (rt, fi), self.make_reho(name, 'TOTEX', rt=rt, fi=fi), name,
                               {'lever': lever, 'RT': rt, 'FI': fi})
            elif lever == 'sizes':
                runs = {f'tech_{t}': dict(exclude=TECH_SETS[t]) for t in spec.get('tech_sets', [])}
                for s in spec.get('rSOC_district', []):
                    runs[f'rsoc_{s}'] = dict(enforce=['rSOC_district'], fmin={'rSOC_district': s * self.era / 1000})
                for s in spec.get('Battery_district', []):
                    runs[f'battery_{s}'] = dict(exclude=RSOC_CHAIN, enforce=['Battery_district'],
                                                fmin={'Battery_district': s * self.era / 1000})
                for f in spec.get('roof_share', []):
                    runs[f'roof_{int(100 * f)}'] = dict(roof_share=f)
                for k, v in runs.items():
                    if k not in done:
                        self.solve(st, k, self.make_reho(k, 'TOTEX', **v), k, {'lever': lever, **v})
            else:
                raise ValueError(f'unknown lever {lever!r} for KPI {kpi!r}')

    def _p(self):
        return {'rt': self.ref['RT'], 'fi': self.ref['FI']}

    # ---------------------------------------------------------------- step 2: evaluate (operation bias)
    def evaluate_pool(self):
        """Every pool design re-run with fix_units, TOTEX objective, reference context -> comparable KPIs."""
        designs = {}
        for f in sorted(os.listdir(self.out_dir)):
            m = re.fullmatch(r'pool_(?!eval)(.+)\.pickle', f)
            if m:
                for k, r in self.load(f'pool_{m.group(1)}')['results'].items():
                    designs[(m.group(1), str(k))] = r
        done = set(self.load('pool_eval')['results'])
        for key, res in designs.items():
            if key not in done:
                name = 'eval_' + re.sub(r'\W+', '_', '_'.join(key))
                self.solve('pool_eval', key, self.make_reho(name, 'TOTEX', fix=fix_table(res)), name,
                           {'lever': key[0], 'design': key[1]})

    # ---------------------------------------------------------------- step 4: contexts
    def context_name(self, design_id, tech_set, ctx, c):
        # positions for get_results: techno_pos=2, retail_pos=4, feed_in_pos=5
        return f"{_clean(self.id)}_{design_id}_{tech_set}_{_clean(ctx)}_{c['RT']}_{c['FI']}"

    def context_files(self, Tsel, contexts):
        rows = [dict(design=i, context=k, RT=c['RT'], FI=c['FI'],
                     file=self.context_name(i, Tsel.loc[i, 'tech_short'], k, c)) for i in Tsel.index
                for k, c in contexts.items()]
        return pd.DataFrame(rows).set_index(['design', 'context'])           # design first, then context

    def run_contexts(self, pool_results, Tsel, contexts):
        files = self.context_files(Tsel, contexts)
        for (i, k), row in files.iterrows():
            f = os.path.join(self.out_dir, row['file'] + '.pickle')
            if os.path.exists(f):
                continue
            try:
                reho = self.make_reho(row['file'], 'TOTEX', rt=row['RT'], fi=row['FI'],
                                      fix=fix_table(pool_results[Tsel.loc[i, 'key']]))
                reho.single_optimization()
                with open(f, 'wb') as fh:                                   # get_results layout {name: {0: result}}
                    pickle.dump({row['file']: {0: reho.results[row['file']][0]}}, fh)
                print('context run ->', f)
            except Exception as e:                                          # keep going; reported by summarize()
                print('context run FAILED', row['file'], repr(e)[:300])
        return files


def fix_table(res):
    du = res['df_Unit'][['Units_Mult', 'Units_Use']].copy()
    used = (du['Units_Mult'] > SIZE_TOL) & (du['Units_Use'] > 0.5)
    du.loc[~used, ['Units_Mult', 'Units_Use']] = 0
    du.loc[used, 'Units_Use'] = 1
    return du


# =====================================================================================================================
# KPIs
# =====================================================================================================================

def grid_usage(res):
    """GU = peak / dp-weighted mean of hourly district consumption on the typical days.
    Consumption = domestic electricity + heat pumps + electric heaters (storage and PV excluded)."""
    dp = res['df_Time']['dp']
    if isinstance(dp.index, pd.MultiIndex):
        dp = dp.groupby(level=0).first()
    el = res['df_Grid_t'].xs('Electricity', level='Layer')
    dom = el.drop('Network', level='Hub')['Uncontrollable_load'].groupby(level=['Period', 'Time']).sum()
    ut = res['df_Unit_t'].xs('Electricity', level='Layer')['Units_demand'].reset_index()
    ut['Unit'] = ut['Unit'].str.replace(r'_Building\d+$', '', regex=True)
    load = dom.add(ut[ut['Unit'].isin(LOAD_UNITS)].groupby(['Period', 'Time'])['Units_demand'].sum(),
                   fill_value=0).astype(float)
    load = load[load.index.get_level_values('Period').map(dp) > 0]
    w = np.asarray(load.index.get_level_values('Period').map(dp), dtype=float)
    mean = (load.to_numpy() * w).sum() / w.sum()
    return {'GU': load.max() / mean, 'P_load_peak_kW': load.max(), 'E_load_MWh': (load.to_numpy() * w).sum() / 1000}


def sizes(res):
    du = res['df_Unit']
    du = du[(du['Units_Mult'] > SIZE_TOL) & (du['Units_Use'] > 0.5)]['Units_Mult']
    return du.groupby([re.sub(r'_Building\d+$', '', u) for u in du.index]).sum()


def kpis(res, era):
    """Per m2 ERA (costs, energy) and per 1000 m2 ERA (installed capacities)."""
    p = res['df_Performance'].loc['Network']
    net = res['df_Annuals'].xs('Network', level='Hub')
    s = sizes(res).reindex(CAPACITY_UNITS, fill_value=0) / era * 1000
    return {'TOTEX': (p['Costs_inv'] + p['Costs_op'] + p['Costs_ft']) / era, 'CAPEX': p['Costs_inv'] / era,
            'OPEX': p['Costs_op'] / era, 'comfort_penalty': p['Costs_ft'] / era,
            'SS': 100 * res['df_KPIs'].loc['Network', 'SS'],
            'el_import': 1000 * net.loc['Electricity', 'Supply_MWh'] / era,
            'el_export': 1000 * net.loc['Electricity', 'Demand_MWh'] / era, **grid_usage(res), **s.to_dict()}


STORAGE_CLASSES = ['none', 'battery', 'rsoc', 'battery+rsoc']        # class (colour, order) = installed storage set


def tech_set(row):
    """(name, storage class). Name = installed technologies among PV, HP, battery, rSOC (size > 0), e.g.
    'PV+HP+battery', 'HP (no storage)', 'grid only'; class = storage set only (file names, colours, order)."""
    has = {k: row.get(c, 0) > SIZE_TOL for k, c in (('PV', 'PV'), ('HP', 'HeatPump_Air'), ('battery', 'Battery_district'),
                                                    ('rSOC', 'rSOC_district'))}
    name = '+'.join(k for k, v in has.items() if v)
    if not (has['battery'] or has['rSOC']):
        name = f'{name} (no storage)' if name else 'grid only'
    return name, {(False, False): 'none', (True, False): 'battery', (False, True): 'rsoc',
                  (True, True): 'battery+rsoc'}[(has['battery'], has['rSOC'])]


def storage_class(name):
    """Storage class of a technology-set name made by tech_set()."""
    b, r = 'battery' in name, 'rSOC' in name
    return {(False, False): 'none', (True, False): 'battery', (False, True): 'rsoc', (True, True): 'battery+rsoc'}[(b, r)]


def class_order(names):
    """Technology-set names sorted by storage class, then name."""
    return sorted(dict.fromkeys(names), key=lambda n: (STORAGE_CLASSES.index(storage_class(n)), n))


# Design codes: G<generator>-<nn>, numbered in the order of the lever specification (stable for the same inputs).
GENERATOR_CODES = {'anchor': ('G0', 'Anchors: TOTEX optimum and SS maximum'),
                   'tariffs': ('G1', 'TOTEX optimum under other retail / feed-in tariffs'),
                   'mga': ('G2', 'MGA: TOTEX <= TOTEX_opt + eps x |TOTEX_opt|, then min CAPEX / max CAPEX / max SS'),
                   'ss_target': ('G3', 'Grid import fixed between the TOTEX optimum (0 %) and the SS maximum (100 %)'),
                   'tech_sets': ('G4', 'TOTEX optimum with a restricted storage technology set'),
                   'sizes': ('G5', 'TOTEX optimum with a forced minimum size or a reduced PV roof share')}


def design_codes(levers):
    """{pool key: (code, description)} built from KPIs_objective_link, in specification order."""
    rows = [(ANCHOR, 'anchor', 'TOTEX optimum'), (('anchor', 'ss_max'), 'anchor', 'SS maximum')]
    for kpi, spec in levers.items():
        if not spec:
            continue
        lv = spec['lever']
        if lv == 'mga':
            rows += [((kpi, str((e, o))), lv, f'eps {e:.0%}, {o}') for e in spec['eps'] for o in spec['objectives']]
        elif lv == 'ss_target':
            rows += [((kpi, str(f)), lv, f'import at {f:.0%} of the way to SS max') for f in spec['fractions']]
        elif lv == 'tariffs':
            rows += [((kpi, str((rt, fi))), lv, f'RT {rt} / FI {fi}') for rt, fi in spec['pairs']]
        elif lv == 'sizes':
            rows += [((kpi, f'tech_{t}'), 'tech_sets', t.replace('_', ' ')) for t in spec.get('tech_sets', [])]
            rows += [((kpi, f'rsoc_{v}'), lv, f'rSOC >= {v} kW/1000 m2') for v in spec.get('rSOC_district', [])]
            rows += [((kpi, f'battery_{v}'), lv, f'battery >= {v} kWh/1000 m2, no rSOC')
                     for v in spec.get('Battery_district', [])]
            rows += [((kpi, f'roof_{int(100 * f)}'), lv, f'PV roof share {f:.0%}') for f in spec.get('roof_share', [])]
    out, count = {}, {}
    for key, lv, desc in rows:
        g = GENERATOR_CODES[lv][0]
        count[g] = count.get(g, 0) + 1
        out[key] = (f'{g}-{count[g]:02d}', desc)
    return out


def _clean(s):
    return re.sub(r'[^0-9A-Za-z.+]+', '-', str(s)).strip('-')


def pool_table(results, era, levers):
    """One row per evaluated design. Index = design code (G<generator>-<nn>), 'description' says what it is,
    'tech_set' names the installed technologies (e.g. PV+HP+battery); its cluster is the storage set (tech_short)."""
    if ANCHOR not in results:
        raise RuntimeError('the TOTEX optimum could not be evaluated: check the errors printed during generation.')
    codes = design_codes(levers)
    keys = list(results)
    T = pd.DataFrame.from_dict({k: kpis(results[k], era) for k in keys}, orient='index')
    T.index = pd.Index(keys, tupleize_cols=False)
    T['key'] = pd.Series(keys, index=T.index, dtype=object)
    T['description'] = [codes.get(k, ('', f'{k[0]}: {k[1]}'))[1] for k in keys]
    T[['tech_set', 'tech_short']] = T.apply(lambda r: pd.Series(tech_set(r)), axis=1)
    T['dTOTEX'] = T['TOTEX'] - T.loc[[ANCHOR], 'TOTEX'].iloc[0]
    T['is_anchor'] = [k == ANCHOR for k in keys]
    extra = iter(range(1, len(keys) + 1))
    T.index = [codes[k][0] if k in codes else f'GX-{next(extra):02d}' for k in keys]
    assert T.index.is_unique, 'design codes are not unique'
    return T.loc[sorted(T.index)]


TABLE_COLUMNS = {'TOTEX': 'TOTEX [CHF/m2/yr]', 'CAPEX': 'CAPEX [CHF/m2/yr]', 'OPEX': 'OPEX [CHF/m2/yr]',
                 'SS': 'SS [%]', 'GU': 'GU [-]', 'el_import': 'Import [kWh/m2/yr]', 'el_export': 'Export [kWh/m2/yr]',
                 'PV': 'PV [kW/1000m2]', 'HeatPump_Air': 'HP [kW/1000m2]', 'Battery_district': 'Battery [kWh/1000m2]',
                 'rSOC_district': 'rSOC [kW/1000m2]', 'CH4_storage_IP_district': 'CH4 storage [kWh/1000m2]'}


def cluster_table(T):
    """Designs grouped by storage class (cluster) -> design code, with KPIs and installed capacities."""
    d = T[['tech_set', 'description'] + list(TABLE_COLUMNS)].rename(columns=TABLE_COLUMNS)
    d['tech_set'] = pd.Categorical(d['tech_set'], class_order(d['tech_set']), ordered=True)
    d = d.rename_axis('design').reset_index().sort_values(['tech_set', 'design'])
    return d.rename(columns={'tech_set': 'cluster'}).set_index(['cluster', 'design'])


# =====================================================================================================================
# Stage 3: selection (pure pandas, no REHO)
# =====================================================================================================================

def _ks(a, b):
    v = np.sort(np.r_[a, b])
    return np.abs(np.searchsorted(np.sort(a), v, 'right') / len(a) - np.searchsorted(np.sort(b), v, 'right') / len(b)).max()


def select_configurations(T, features, n_max='auto', dup_tol=0.05, n_bands=4, min_range=0.95, max_ks=0.25, n_min=10,
                          cap_features=None, cost_col='TOTEX', group_col='tech_set', anchor_col='is_anchor'):
    """Percent-based diversity selection. Returns {'selected', 'dropped_duplicates', 'report', 'n_auto', 'capped', 'rule'}.

    If the rule needs more designs than an integer n_max (n_auto > n_max), the n_max designs are NOT the first n_max of
    the rule's order; they are re-chosen to cover cap_features (default: the KPIs TOTEX, CAPEX, SS, GU) as widely as
    possible: must-keep designs, then the min and max design of every cap feature (100 % range), then every band of the
    cap features, then farthest-point fill in the cap-feature space.
    """
    F = T[features].astype(float)
    X = (F - F.min()) / (F.max() - F.min()).replace(0, 1)                # share of the pool range
    keep, dup = [], {}
    anchor = T.index[T[anchor_col].astype(bool)][0]
    order = [anchor] + [i for i in T[cost_col].sort_values(kind='stable').index if i != anchor]   # ties: lower code
    for i in order:                                                        # b. near-duplicates: anchor, then cheaper first
        j = next((j for j in keep if (X.loc[i] - X.loc[j]).abs().max() < dup_tol), None)
        if j is None:
            keep.append(i)
        else:
            dup[i] = j
    Xc = X.loc[keep]
    band = np.minimum((Xc * n_bands).astype(int), n_bands - 1)
    cells = {i: {(f, band.loc[i, f]) for f in features} for i in keep}
    need = set().union(*cells.values())
    must = [anchor]                                                        # c. TOTEX optimum
    for _, g in T.loc[keep].groupby(group_col):                            #    + cheapest per technology set
        if not set(must) & set(g.index):
            must.append(T.loc[g.index, cost_col].idxmin())
    dist = lambda i, S: min(np.linalg.norm(Xc.loc[i] - Xc.loc[j]) for j in S)

    def pick(n):
        sel, cov = list(must), set().union(*(cells[i] for i in must))
        while cov != need and len(sel) < n:                                # d. band coverage
            best = max((i for i in keep if i not in sel), key=lambda i: (len(cells[i] - cov), dist(i, sel)))
            sel.append(best)
            cov |= cells[best]
        while len(sel) < n:                                                # e. farthest-point fill
            sel.append(max((i for i in keep if i not in sel), key=lambda i: dist(i, sel)))
        return sel

    def pick_capped(n, feats):                                              # n_max < n_auto: widest cover of feats
        Xk = Xc[feats]
        dk = lambda i, S: min(np.linalg.norm(Xk.loc[i] - Xk.loc[j]) for j in S)
        sel = list(must)
        for f in feats:                                                     # extremes -> 100 % range of every feat
            for i in (Xk[f].idxmin(), Xk[f].idxmax()):
                if i not in sel and len(sel) < n:
                    sel.append(i)
        ck = {i: {(f, band.loc[i, f]) for f in feats} for i in keep}
        need_k, cov = set().union(*ck.values()), set().union(*(ck[i] for i in sel))
        while cov != need_k and len(sel) < n:                               # every band of every feat
            best = max((i for i in keep if i not in sel), key=lambda i: (len(ck[i] - cov), dk(i, sel)))
            sel.append(best)
            cov |= ck[best]
        while len(sel) < n:                                                 # farthest point in the feat space
            sel.append(max((i for i in keep if i not in sel), key=lambda i: dk(i, sel)))
        return sel

    def report(sel):
        rows = []
        for f in features:
            s, p = F.loc[sel, f], F.loc[keep, f]
            rng = p.max() - p.min()
            rows.append({'feature': f, 'range_cov_%': 100 * (s.max() - s.min()) / rng if rng else 100.0,
                         'bands': f"{len({band.loc[i, f] for i in sel})}/{band[f].nunique()}",
                         'bands_ok': {band.loc[i, f] for i in sel} == set(band[f]), 'KS': _ks(s.values, p.values)})
        return pd.DataFrame(rows).set_index('feature')

    ok = lambda r: r['bands_ok'].all() and (r['range_cov_%'] >= 100 * min_range - 1e-9).all() and (r['KS'] <= max_ks).all()
    cap_features = [f for f in (cap_features or features) if f in features]
    capped = False
    if n_max is None:
        sel, n_auto = keep, None
    else:
        hi = len(keep) if n_max == 'auto' else min(max(int(n_max), len(must)), len(keep))
        n_auto = next((n for n in range(max(n_min, len(must)), len(keep) + 1) if ok(report(pick(n)))), len(keep))
        capped = n_auto > hi
        sel = pick_capped(hi, cap_features) if capped else pick(n_auto)
    return {'selected': sel, 'n_pool': len(T), 'dropped_duplicates': dup, 'report': report(sel), 'n_auto': n_auto,
            'capped': capped,                                            # True: n_max < n_auto, chosen on cap_features
            'rule_met': bool(ok(report(sel))),                           # False if n_max is too small for the rule
            'rule': dict(features=features, dup_tol=dup_tol, n_bands=n_bands, min_range=min_range, max_ks=max_ks,
                         n_min=n_min, n_max=n_max, cap_features=cap_features)}


# =====================================================================================================================
# Stage 5: summary for the Monte-Carlo pipeline + figures
# =====================================================================================================================

def summarize(ctx, files, T, postprocess_dir=None):
    """Runs get_results() of scripts/uncertainty_postprocess.py on the 3 x N pickles and adds our KPIs."""
    if postprocess_dir:
        sys.path.insert(0, postprocess_dir)
    from uncertainty_postprocess import DEFAULT_TECH_REGISTRY, get_results
    registry = {**copy.deepcopy(DEFAULT_TECH_REGISTRY), 'battery_daily': BATTERY_DAILY_REGISTRY_ENTRY}
    exists = files['file'].map(lambda f: os.path.exists(os.path.join(ctx.out_dir, f + '.pickle')))
    if not exists.all():
        print(f'WARNING: {(~exists).sum()} of {len(files)} context runs are missing:', list(files.index[~exists]))
    files = files[exists]
    kw = dict(results_folder=ctx.out_dir, all_results=list(files['file']), techno_pos=2, retail_pos=4, feed_in_pos=5,
              tech_registry=registry)
    summary_df, _ = get_results(**kw)
    # get_results names each row '<file>__<scenario key>': index by the file name to attach design / context / KPIs
    summary_df = summary_df.set_index(summary_df['scenario'].str.split('__').str[0])
    assert summary_df.index.is_unique and set(summary_df.index) == set(files['file']), 'get_results rows do not match files'
    extra = {}
    for (d, c), row in files.iterrows():
        res = pickle.load(open(os.path.join(ctx.out_dir, row['file'] + '.pickle'), 'rb'))[row['file']][0]
        extra[row['file']] = {'design': d, 'context': c, 'tech_set': T.loc[d, 'tech_set'],
                              **{f'{k}_kpi': v for k, v in kpis(res, ctx.era).items()}}
    summary_df = summary_df.join(pd.DataFrame.from_dict(extra, orient='index'))
    order = {d: i for i, d in enumerate(dict.fromkeys(files.index.get_level_values('design')))}
    summary_df = (summary_df.assign(_o=summary_df['design'].map(order)).sort_values(['_o', 'context']).drop(columns='_o')
                  .set_index(['design', 'context']))                       # design first, then operation context
    summary_df.to_pickle(os.path.join(ctx.out_dir, 'summary_df.pickle'))
    return summary_df, kw


CLASS_COLOR = {'none': '#7f7f7f', 'battery': '#1f77b4', 'rsoc': '#2ca02c', 'battery+rsoc': '#d62728'}


class _TechColor(dict):
    """TECH_COLOR[name] = colour of the storage class of any technology-set name (PV / HP may be absent)."""
    def __missing__(self, name):
        return CLASS_COLOR[storage_class(name)]

    def get(self, name, default=None):
        try:
            return self[name]
        except KeyError:
            return default


TECH_COLOR = _TechColor()
CTX_SYMBOL = {'attractive': 'triangle-up', 'baseline': 'circle', 'harsh': 'triangle-down'}
SYMBOLS = ['circle', 'triangle-up', 'triangle-down', 'square', 'diamond', 'cross', 'x', 'star', 'pentagon', 'hexagon']
PATTERNS = ['/', '', '.', 'x', '+', '\\', '-', '|']


def context_styles(contexts):
    """{context: marker symbol} and {context: bar pattern} for ANY number / names of contexts (known names keep theirs)."""
    free = iter([m for m in SYMBOLS if m not in CTX_SYMBOL.values()] + SYMBOLS * 3)
    sym = {c: CTX_SYMBOL.get(c) or next(free) for c in contexts}
    pat = {c: PATTERNS[i % len(PATTERNS)] for i, c in enumerate(contexts)}
    return sym, pat
LABEL = {'TOTEX': 'TOTEX [CHF/m²/yr]', 'CAPEX': 'CAPEX [CHF/m²/yr]', 'SS': 'Self-sufficiency [%]', 'GU': 'GU [-]',
         'el_import': 'Import [kWh/m²/yr]', 'el_export': 'Export [kWh/m²/yr]', 'PV': 'PV [kW/1000 m²]',
         'HeatPump_Air': 'Heat pump [kW/1000 m²]', 'Battery_district': 'Daily battery [kWh/1000 m²]',
         'rSOC_district': 'rSOC [kW/1000 m²]', 'CH4_storage_IP_district': 'CH4 storage [kWh/1000 m²]'}


UNCERTAIN_LABEL = {'electricity_feed_in': 'feed-in tariff', 'electricity_retail': 'retail tariff',
                   'battery_capex': 'battery cost', 'rsoc_capex': 'rSOC cost', 'rsoc_lifetime': 'rSOC lifetime',
                   'ch4_tank_capex': 'CH4 tank cost'}


def totex_bars(res_cls, penalty, title):
    """REHO plot_performance(plot='costs', per m2) for {design: {0: result}}, plus the comfort penalty on the OPEX bar."""
    from reho.plotting import plotting
    fig = plotting.plot_performance(res_cls, plot='costs', indexed_on='Scn_ID', label='EN_long', per_m2=True,
                                    add_annotation=False)
    x2 = [i + 1 / 3 for i in range(len(res_cls))]
    fig.add_trace(go.Bar(name='Comfort penalty', x=x2, y=penalty, marker_color='#d62728', width=1 / 3,
                         legendgroup='group2', showlegend=True,
                         hovertemplate='<b>Comfort penalty</b><br>Costs: %{y:.2f} CHF/m²/y'))
    for tr in fig.data:                       # TOTEX bar includes the penalty
        if tr.name == 'TOTEX':
            tr.y = np.asarray(tr.y, dtype=float) + penalty
    # penalty stacked on the OPEX bar, drawn before REHO's thin TOTEX bar (which must stay on top)
    data, pen_tr = list(fig.data[:-1]), fig.data[-1]
    last_opex = max(i for i, tr in enumerate(data) if tr.legendgroup == 'group2')
    fig.data = tuple(data[:last_opex + 1] + [pen_tr] + data[last_opex + 1:])
    pad = max(0, (4 - len(res_cls)) / 2)      # few configurations: keep the bars narrow
    fig.update_xaxes(range=[-0.5 - pad, len(res_cls) - 0.5 + pad])
    fig.update_layout(template='simple_white', font=dict(family='Arial'), width=max(900, 70 * len(res_cls) + 300),
                      height=600, title=title)
    return fig


def make_figures(ctx, summary_df, uncertain_var_link, reference_context='baseline'):
    """Selected designs only. Colour = technology class (cluster), symbol = economic context."""
    figs = {}
    d = summary_df.reset_index()
    d['tech_set'] = pd.Categorical(d['tech_set'], class_order(d['tech_set']), ordered=True)
    d = d.sort_values(['tech_set', 'design'])
    ctx_symbol, ctx_pattern = context_styles(list(dict.fromkeys(summary_df.index.get_level_values('context'))))

    def add(fig, x, y, row, col, first, data=None):
        for (ts, c), g in (d if data is None else data).groupby(['tech_set', 'context'], observed=True):
            fig.add_trace(go.Scatter(x=x(g), y=g[y], mode='markers', name=f'{ts} | {c}', legendgroup=f'{ts}|{c}',
                                     showlegend=first, text=g['design'],
                                     hovertemplate='%{text}<br>x %{x}<br>y %{y:.2f}<extra></extra>',
                                     marker=dict(color=TECH_COLOR[ts], symbol=ctx_symbol[c], size=10,
                                                 line=dict(color='black', width=0.5))), row=row, col=col)

    # 1. KPIs (y) against CAPEX (x) under every context
    ys = ['TOTEX', 'SS', 'GU']
    fig = make_subplots(rows=1, cols=3, horizontal_spacing=0.07)
    for j, y in enumerate(ys):
        add(fig, lambda g: g['CAPEX_kpi'], f'{y}_kpi', 1, j + 1, j == 0)
        fig.update_xaxes(title_text=LABEL['CAPEX'], row=1, col=j + 1)
        fig.update_yaxes(title_text=LABEL[y], row=1, col=j + 1)
    fig.update_layout(template='simple_white', font=dict(family='Arial'), width=1400, height=620,
                      legend=dict(orientation='h', y=-0.22, x=0, font=dict(size=11)),
                      title=f'{ctx.id}: KPIs of the selected designs under each economic context '
                            f'(colour = technology class, symbol = context)')
    figs['kpis_vs_capex'] = fig

    # 2. range of KPIs and installed capacities per technology class (reference context: capacities are fixed by
    #    the design, so they are the same in every context)
    ref = d[d['context'] == reference_context].copy()
    ref['tech_set'] = ref['tech_set'].astype(str)
    classes = class_order(ref['tech_set'])
    ypos = {t: len(classes) - 1 - i for i, t in enumerate(classes)}
    jitter = pd.Series(np.random.default_rng(0).uniform(-0.15, 0.15, len(ref)), index=ref.index)
    panels = [('SS', 'Self-sufficiency [%]', 1), ('GU', 'GU, consumption peak / mean [-]', 1),
              ('TOTEX', LABEL['TOTEX'], 1), ('CAPEX', LABEL['CAPEX'], 1), ('PV', LABEL['PV'], 1),
              ('HeatPump_Air', LABEL['HeatPump_Air'], 1), ('Battery_district', LABEL['Battery_district'], 1),
              ('rSOC_district', LABEL['rSOC_district'], 1), ('CH4_storage_IP_district', 'CH4 storage [MWh/1000 m²]', 1e-3)]
    panels = [p for p in panels if f'{p[0]}_kpi' in ref.columns]
    fig = make_subplots(rows=(len(panels) + 2) // 3, cols=3, shared_yaxes=True, subplot_titles=[p[1] for p in panels],
                        horizontal_spacing=0.04, vertical_spacing=0.1)
    for n, (k, _, f) in enumerate(panels):
        r, c = n // 3 + 1, n % 3 + 1
        for ts in classes:
            g = ref[ref['tech_set'] == ts]
            v = g[f'{k}_kpi'] * f
            fig.add_trace(go.Scatter(x=[v.min(), v.max()], y=[ypos[ts]] * 2, mode='lines', hoverinfo='skip',
                                     showlegend=False, line=dict(color=TECH_COLOR[ts], width=9), opacity=0.25),
                          row=r, col=c)
            fig.add_trace(go.Scatter(x=v, y=ypos[ts] + jitter[g.index], mode='markers', name=f'{ts} ({len(g)})',
                                     legendgroup=ts, showlegend=(n == 0), text=g['design'],
                                     hovertemplate='%{text}: %{x:.2f}<extra></extra>',
                                     marker=dict(size=8, color=TECH_COLOR[ts], line=dict(color='black', width=0.4))),
                          row=r, col=c)
    fig.update_yaxes(tickvals=list(ypos.values()), ticktext=list(ypos.keys()), range=[-0.6, len(classes) - 0.4])
    fig.update_xaxes(showgrid=True, gridcolor='#eee')
    fig.update_layout(template='simple_white', font=dict(family='Arial'), width=1300,
                      height=280 * ((len(panels) + 2) // 3) + 70, showlegend=False,
                      title=f'{ctx.id}: range of KPIs and installed capacities per technology class '
                            f'({len(ref)} selected configurations, {reference_context} context)')
    figs['indicator_ranges'] = fig

    # 3. one figure, all selected designs: REHO cost template (CAPEX left / OPEX right / thin TOTEX), grouped by
    #    technology class (shaded band + label), sorted by CAPEX inside each class, reference context.
    #    REHO leaves the comfort penalty (Costs_ft) out of df_Economics: added as its own block.
    g = ref.assign(_c=ref['tech_set'].map({t: i for i, t in enumerate(classes)})).sort_values(['_c', 'CAPEX_kpi'])
    res_all = {}
    for _, row in g.iterrows():
        file = row['scenario'].split('__')[0]
        res_all[row['design']] = {0: pickle.load(open(os.path.join(ctx.out_dir, file + '.pickle'), 'rb'))[file][0]}
    fig = totex_bars(res_all, g['comfort_penalty_kpi'].to_numpy(),
                     f'{ctx.id}: CAPEX (left) / OPEX (right) / TOTEX (thin) per selected configuration, '
                     f'{reference_context} context')
    x0 = 0
    for ts in classes:
        n_ts = int((g['tech_set'] == ts).sum())
        fig.add_vrect(x0=x0 - 0.25, x1=x0 + n_ts - 1 + 0.6, fillcolor=TECH_COLOR[ts], opacity=0.12, line_width=0,
                      layer='below', annotation_text=ts, annotation_position='top',
                      annotation=dict(font=dict(color=TECH_COLOR[ts], size=12)))
        x0 += n_ts
    fig.update_yaxes(title_text='Costs [CHF/m²/yr]')
    figs['totex_bars'] = fig

    # 4. one bar subplot per entry of uncertain_var_link: what each uncertain variable acts on, per selected design.
    #    Designs grouped by technology class (shaded band, colour); operation results (import, export, SS, ...) as
    #    one bar per context side by side (pattern); capacities are fixed by the design -> one bar (reference context).
    order = list(dict.fromkeys(g['design']))                                # class, then CAPEX (as the TOTEX bars)
    colour = {r['design']: TECH_COLOR[r['tech_set']] for _, r in g.iterrows()}
    links = list(uncertain_var_link.items())
    n_rows = (len(links) + 1) // 2
    fig = make_subplots(rows=n_rows, cols=2, horizontal_spacing=0.08, vertical_spacing=0.16,
                        subplot_titles=[f'{UNCERTAIN_LABEL.get(u, u)} → {LABEL.get(k, k)}' for u, k in links])
    for n, (u, k) in enumerate(links):
        row, col = n // 2 + 1, n % 2 + 1
        data = ref if k in CAPACITY_UNITS else d
        for c, gc in data.groupby('context', sort=False):
            v = gc.set_index('design')[f'{k}_kpi'].reindex(order)
            fig.add_trace(go.Bar(x=order, y=v, name=c, legendgroup=c, showlegend=False, offsetgroup=c,
                                 marker=dict(color=[colour[o] for o in order], line=dict(color='black', width=0.5),
                                             pattern=dict(shape=ctx_pattern[c] if k not in CAPACITY_UNITS else '',
                                                          fillmode='overlay', fgcolor='black', size=5)),
                                 hovertemplate=f'%{{x}} ({c}): %{{y:.2f}}<extra></extra>'), row=row, col=col)
        x0 = 0
        for ts in classes:                                                  # shaded band per technology class
            n_ts = int((g['tech_set'] == ts).sum())
            fig.add_vrect(x0=x0 - 0.5, x1=x0 + n_ts - 0.5, fillcolor=TECH_COLOR[ts], opacity=0.08, line_width=0,
                          layer='below', row=row, col=col)
            x0 += n_ts
        fig.update_xaxes(categoryorder='array', categoryarray=order, tickangle=-45, row=row, col=col)
        fig.update_yaxes(title_text=LABEL.get(k, k), row=row, col=col)
    for ts in classes:                                                      # legend: classes (colour), contexts (pattern)
        fig.add_trace(go.Bar(x=[None], y=[None], name=ts, marker_color=TECH_COLOR[ts], legendgroup='class',
                             legendgrouptitle_text='technology class'), row=1, col=1)
    for c, p_ in ctx_pattern.items():
        fig.add_trace(go.Bar(x=[None], y=[None], name=c, legendgroup='context', legendgrouptitle_text='context',
                             marker=dict(color='white', line=dict(color='black', width=0.5),
                                         pattern=dict(shape=p_, fgcolor='black', size=5))), row=1, col=1)
    fig.update_layout(template='simple_white', font=dict(family='Arial'), width=1300, height=340 * n_rows + 120,
                      barmode='group', bargap=0.2, bargroupgap=0.05, legend=dict(orientation='h', y=-0.1, x=0),
                      title=f'{ctx.id}: what each uncertain variable acts on, per selected configuration '
                            f'(operation results: one bar per context; capacities: {reference_context})')
    figs['uncertain_var_link'] = fig

    for name, f in figs.items():
        f.write_html(os.path.join(ctx.out_dir, 'figures', f'{name}.html'))
    return figs
