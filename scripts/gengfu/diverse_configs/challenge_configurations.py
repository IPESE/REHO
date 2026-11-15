"""
challenge_configurations_under_uncertainty()
============================================

Second function of the workflow (after generate_config):

    Inputs   uncertainty distributions            {id: {'rv', 'p_lower', 'p_upper'}}  (supervisor's xlsx)
             configuration dataframe              summary_df of generate_config(), index (design, context):
                                                  N designs x 3 operations (one per economic context)
    Outputs  1. CAPEX vs TOTEX plot, median and 95 % interval per design
             2. probabilistic ranking of the designs and the blend of designs (weights)
             3. low-regret decisions: regret, adaptability and lock-in of every design

Method (paired Monte Carlo, supervisor's scripts/uncertainty_postprocess.py, steps 2-4)
    The same R draws of the uncertain parameters are applied to every (design, operation) row, which gives
    TOTEX[d, o, r] in CHF/m2/yr. Per draw r:

        initial[d, r] = TOTEX[d, initial_operation, r]     operation planned at the reference context
        best[d, r]    = min_o TOTEX[d, o, r]               best of the available operations
        cost[d, r]    = TOTEX of the operation used in the draw (see Score) or mean_o TOTEX (operation='blend')
        optimum[r]    = min_d best[d, r]                   cheapest design with its cheapest operation

        adaptability[d, r] = initial - best      what re-optimising the operation recovers (>= 0)
        lock_in[d, r]      = best - optimum      what stays lost even with the best operation (>= 0)
        regret[d, r]       = cost - optimum

    Score (user 2026-11-15: the blend depends on TOTEX, SS and GU): in every draw each KPI is scaled over the
             designs to 0 (best of the draw) .. 1 (worst of the draw): TOTEX and GU lower is better, SS higher is
             better. score[d, r] = sum_k kpi_weights[k] * scaled_k[d, r]  (0 = best on every KPI).
             operation='best': all (design, operation) pairs are scored together and each design uses its
             best-scoring operation in that draw (TOTEX, SS, GU of that operation); operation='blend': mean of the
             three operations.
    Ranking: rank of score[d, r] among the designs in each draw -> P(rank), P(best), expected rank.
    Blend (main result, user 2026-11-14): weight of a design = share of the sampled contexts in which it has the
             best score, w_d = P(best_d). The blend's KPIs in draw r are sum_d w_d KPI[d, r].
    Blend (supplement): risk-averse weights from one LP over all draws, minimising
             (1 - lambda) * mean + lambda * CVaR_alpha of the blended score regret (score - best score of the draw),
             lambda from 0 to 1 (frontier).
"""

import copy
import os
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.optimize import linprog
from scipy.spatial import ConvexHull

from generate_config import BATTERY_DAILY_REGISTRY_ENTRY, TECH_COLOR   # daily battery registry entry, class colours

DEFAULT_CORR_FACTOR = {'rsoc_lifetime': 1000 / 8760}          # kh of operation -> years (supervisor's convention)
LAYOUT = dict(template='simple_white', font=dict(family='Arial'))


def challenge_configurations_under_uncertainty(uncertainty_distributions, configurations, *, n_runs=1000, seed=42,
                                               operation='best', initial_operation='baseline', kpi_weights=None,
                                               alpha=0.9, n_frontier=11,
                                               tech_registry=None, corr_factor=None, out_dir=None,
                                               postprocess_dir=None):
    """
    Parameters
    ----------
    uncertainty_distributions : dict
        {parameter id: {'rv': scipy frozen distribution, 'p_lower': float, 'p_upper': float}}.
    configurations : DataFrame
        summary_df of generate_config(): one row per (design, context), index levels 'design' and 'context'.
    n_runs, seed : Monte-Carlo size and seed (same draws for every design).
    operation : 'best' or 'blend'
        How the operations of one design are used in each draw: the one with the best score, or their mean.
    initial_operation : str
        Context whose operation is the planned one (reference for adaptability).
    kpi_weights : dict
        Weight of each KPI in the score that ranks and blends the designs (normalised to sum 1).
        Default {'TOTEX': 1/3, 'SS': 1/3, 'GU': 1/3}.
    alpha : float in [0, 1)
        CVaR level of the blend optimisation (share of the best draws left out of the tail).
    n_frontier : int
        Number of blends on the mean-regret / CVaR-regret frontier (risk weight lambda from 0 to 1).
    tech_registry, corr_factor : passed to the supervisor's pipeline (defaults: registry + daily battery,
        rSOC lifetime kh -> yr).
    out_dir : folder for the figures (HTML) and the summary table (pickle); None = nothing written.
    postprocess_dir : folder of uncertainty_postprocess.py if it is not on sys.path.

    Returns
    -------
    dict with
        'summary'           one row per design: CAPEX / TOTEX median and 95 % interval, P(best), expected rank,
                            blend weight, regret, adaptability, lock-in (mean and 95th percentile)
        'rank_probability'  design x rank table, P(design has this rank)
        'weights'           blend weights (sum 1): share of the draws in which each design has the best score
        'weights_cvar'      supplement: risk-averse blend weights, minimum CVaR_alpha of the score regret (lambda = 1)
        'frontier'          blends from minimum mean regret (lambda 0) to minimum CVaR (lambda 1): lambda, mean
                            and CVaR of the blended regret, weight of every design
        'low_regret'        the decisions: min mean regret, min 95th-percentile regret, blend and its regret
        'per_draw'          design x draw tables: cost (TOTEX), SS, GU, score, regret, adaptability, lock_in, capex;
                            blend: TOTEX / SS / GU of the blend per draw
        'draws'             the sampled uncertain parameters
        'figures'           {'capex_totex', 'capex_totex_cloud', 'ranking', 'regret'} plotly figures
    """
    if operation not in ('best', 'blend'):
        raise ValueError("operation must be 'best' or 'blend'")
    kw = pd.Series(kpi_weights or {'TOTEX': 1 / 3, 'SS': 1 / 3, 'GU': 1 / 3}, dtype=float)
    if not set(kw.index) <= {'TOTEX', 'SS', 'GU'} or (kw < 0).any() or kw.sum() <= 0:
        raise ValueError("kpi_weights: non-negative weights for 'TOTEX', 'SS', 'GU'")
    kw = (kw / kw.sum()).reindex(['TOTEX', 'SS', 'GU'], fill_value=0)
    if postprocess_dir:
        sys.path.insert(0, postprocess_dir)
    from uncertainty_postprocess import (DEFAULT_TECH_REGISTRY, compute_uncertain_economics,
                                         normalize_uncertainty_results, sample_uncertainty_draws)
    registry = tech_registry or {**copy.deepcopy(DEFAULT_TECH_REGISTRY), 'battery_daily': BATTERY_DAILY_REGISTRY_ENTRY}

    # ---- 1. Monte Carlo: TOTEX[d, o, r] and CAPEX[d, r], per m2 ERA ------------------------------------------------
    cfg, designs, operations = _complete_designs(configurations, initial_operation)
    draws = sample_uncertainty_draws(uncertainty_distributions, N_runs=n_runs, random_seed=seed,
                                     corr_factor=DEFAULT_CORR_FACTOR if corr_factor is None else corr_factor)
    mc = compute_uncertain_economics(cfg.reset_index(), draws, tech_registry=registry)
    mc = normalize_uncertainty_results(mc, tech_registry=registry, normalize_by_ERA=True)
    shape = (len(designs), len(operations), n_runs)           # mc rows follow cfg rows, n_runs each
    totex = mc['TOTEX_perturbed'].to_numpy().reshape(shape)
    capex = mc['CAPEX_perturbed'].to_numpy().reshape(shape)[:, operations.index(initial_operation)]

    # ---- 2. operation used in each draw and multi-KPI score (every KPI scaled per draw to 0 = best .. 1 = worst) --
    ss_do, gu_do = (np.repeat(cfg[f'{k}_kpi'].to_numpy().reshape(shape[:2])[:, :, None], n_runs, axis=2)
                    for k in ('SS', 'GU'))
    score_of = lambda t, s_, g, axis_shape: sum(
        kw[k] * _scale(v.reshape(-1, n_runs), low) for k, v, low in
        (('TOTEX', t, True), ('SS', s_, False), ('GU', g, True))).reshape(axis_shape)
    if operation == 'best':           # all (design, operation) pairs scored together, best-scoring one per design
        score_do = score_of(totex, ss_do, gu_do, shape)
        op = score_do.argmin(axis=1)[:, None]
        cost, ss, gu = (np.take_along_axis(a, op, axis=1)[:, 0] for a in (totex, ss_do, gu_do))
        score = score_do.min(axis=1)
    else:                             # mean of the operations
        cost, ss, gu = totex.mean(axis=1), ss_do.mean(axis=1), gu_do.mean(axis=1)
        score = score_of(cost, ss, gu, shape[::2])
    score_regret = score - score.min(axis=0)

    # ---- 3. cost-based regret, adaptability and lock-in ------------------------------------------------------------
    initial = totex[:, operations.index(initial_operation)]
    best = totex.min(axis=1)
    optimum = best.min(axis=0)
    regret, adaptability, lock_in = cost - optimum, initial - best, best - optimum

    # ---- 4. probabilistic ranking and blend ------------------------------------------------------------------------
    rank = score.argsort(axis=0).argsort(axis=0)              # 0 = best score of the draw
    rank_probability = pd.DataFrame((rank[:, None, :] == np.arange(len(designs))[None, :, None]).mean(axis=2),
                                    index=designs, columns=pd.RangeIndex(1, len(designs) + 1, name='rank'))
    weights = rank_probability[1].rename('weight')                      # main blend: P(best score)
    frontier = pd.DataFrame([_blend(score_regret, alpha, lam) for lam in np.linspace(0, 1, n_frontier)],
                            columns=['lambda', 'regret_mean', 'regret_cvar'] + designs)
    weights_cvar = frontier.iloc[-1][designs].rename('weight_cvar').astype(float)   # supplement: lambda = 1
    w = weights.to_numpy()
    blend = pd.DataFrame({'TOTEX': w @ cost, 'SS': w @ ss, 'GU': w @ gu}, index=draws['run_id'])
    blend_regret = w @ regret

    # ---- 5. summary table, decisions, figures ----------------------------------------------------------------------
    q = lambda a, p: np.quantile(a, p, axis=1)
    summary = pd.DataFrame({
        'tech_set': cfg.xs(initial_operation, level='context')['tech_set'].reindex(designs).to_numpy(),
        'CAPEX_median': np.median(capex, axis=1), 'CAPEX_lo95': q(capex, .025), 'CAPEX_hi95': q(capex, .975),
        'TOTEX_median': np.median(cost, axis=1), 'TOTEX_lo95': q(cost, .025), 'TOTEX_hi95': q(cost, .975),
        'SS_median': np.median(ss, axis=1), 'GU_median': np.median(gu, axis=1),
        'score_mean': score.mean(axis=1), 'score_regret_mean': score_regret.mean(axis=1),
        'score_regret_cvar': [_cvar(r, alpha) for r in score_regret],
        'P_best': weights.to_numpy(), 'expected_rank': rank.mean(axis=1) + 1,
        'weight': weights.to_numpy(), 'weight_cvar': weights_cvar.to_numpy(),
        'regret_mean': regret.mean(axis=1), 'regret_p95': q(regret, .95),
        'adaptability_mean': adaptability.mean(axis=1), 'adaptability_p95': q(adaptability, .95),
        'lock_in_mean': lock_in.mean(axis=1), 'lock_in_p95': q(lock_in, .95),
    }, index=pd.Index(designs, name='design')).sort_values('expected_rank')
    nonzero = lambda v: v[v > 1e-3].sort_values(ascending=False).round(3).to_dict()
    low_regret = {'min_mean_regret': summary['regret_mean'].idxmin(), 'min_p95_regret': summary['regret_p95'].idxmin(),
                  'kpi_weights': kw.round(3).to_dict(), 'blend': nonzero(weights),
                  **{f'blend_{k}_median': float(blend[k].median()) for k in blend},
                  'blend_regret_mean': float(blend_regret.mean()),
                  'blend_regret_p95': float(np.quantile(blend_regret, .95)),
                  'blend_cvar': nonzero(weights_cvar)}

    frame = lambda a: pd.DataFrame(a, index=pd.Index(designs, name='design'), columns=draws['run_id'])
    per_draw = {k: frame(v) for k, v in (('cost', cost), ('SS', ss), ('GU', gu), ('score', score), ('regret', regret),
                                          ('adaptability', adaptability), ('lock_in', lock_in), ('capex', capex))}
    per_draw['blend'] = blend
    out = {'summary': summary, 'rank_probability': rank_probability, 'weights': weights, 'weights_cvar': weights_cvar,
           'frontier': frontier, 'low_regret': low_regret, 'per_draw': per_draw, 'draws': draws,
           'figures': _figures(summary, per_draw, kw, operation, initial_operation, n_runs)}
    if out_dir:
        os.makedirs(os.path.join(out_dir, 'figures'), exist_ok=True)
        summary.to_pickle(os.path.join(out_dir, f'challenge_summary_{operation}.pickle'))
        for name, fig in out['figures'].items():
            fig.write_html(os.path.join(out_dir, 'figures', f'challenge_{name}_{operation}.html'))
    return out


def _complete_designs(configurations, initial_operation):
    """Rows ordered design -> operation, keeping only the designs that have every operation."""
    idx = configurations.index
    designs, operations = (list(dict.fromkeys(idx.get_level_values(n))) for n in ('design', 'context'))
    if initial_operation not in operations:
        raise ValueError(f'initial_operation {initial_operation!r} is not one of {operations}')
    full = [d for d in designs if all((d, o) in idx for o in operations)]
    if len(full) < len(designs):
        print('WARNING: designs without all operations are left out:', sorted(set(designs) - set(full)))
    return configurations.loc[pd.MultiIndex.from_product([full, operations], names=['design', 'context'])], full, operations


def _scale(v, low_is_best):
    """Per draw (column), scale over the designs to 0 = best .. 1 = worst; 0 when all designs are equal."""
    lo, hi = v.min(axis=0), v.max(axis=0)
    span = np.where(hi - lo > 1e-12, hi - lo, np.inf)
    return (v - lo) / span if low_is_best else (hi - v) / span


def _cvar(x, alpha):
    """Mean of the worst (1 - alpha) share of x."""
    return np.sort(x)[int(np.floor(alpha * len(x))):].mean()


def _blend(regret, alpha, lam):
    """Blend weights minimising (1 - lam) * mean + lam * CVaR_alpha of the blended regret (Rockafellar-Uryasev LP).
    Variables [w (D), t, u (R)]: min (1-lam) w.mean_regret + lam (t + sum(u) / ((1-alpha) R))
    s.t. u_r >= w.regret_r - t, u >= 0, w >= 0, sum w = 1. Returns [lam, mean, CVaR, w...]."""
    D, R = regret.shape
    c = np.r_[(1 - lam) * regret.mean(axis=1), lam, np.full(R, lam / ((1 - alpha) * R))]
    A_ub = np.hstack([regret.T, -np.ones((R, 1)), -np.eye(R)])
    res = linprog(c, A_ub=A_ub, b_ub=np.zeros(R), A_eq=np.r_[np.ones(D), 0, np.zeros(R)][None, :], b_eq=[1],
                  bounds=[(0, None)] * D + [(None, None)] + [(0, None)] * R, method='highs')
    if not res.success:
        raise RuntimeError(f'blend optimisation failed: {res.message}')
    w = np.clip(res.x[:D], 0, None)
    w[w < 1e-4] = 0
    w /= w.sum()
    b = w @ regret
    return [lam, b.mean(), _cvar(b, alpha), *w]


def _region95(x, y):
    """Outline of the 95 % of the draws closest to the median (Mahalanobis distance): convex hull, or a
    segment when the draws lie on a line (e.g. CAPEX fixed for designs without uncertain technologies)."""
    P = np.c_[x, y]
    D = P - np.median(P, axis=0)
    d2 = np.einsum('ij,jk,ik->i', D, np.linalg.pinv(np.cov(P.T)), D)
    K = P[d2 <= np.quantile(d2, 0.95)]
    try:
        h = ConvexHull(K)
        v = np.r_[h.vertices, h.vertices[:1]]
        return K[v, 0], K[v, 1]
    except Exception:                                       # degenerate (collinear) cloud
        i = np.argsort(K[:, 1])
        return K[i[[0, -1]], 0], K[i[[0, -1]], 1]


def _figures(summary, per_draw, kw, operation, initial_operation, n_runs):
    s = summary
    kpi_frames = {'TOTEX': per_draw['cost'], 'SS': per_draw['SS'], 'GU': per_draw['GU']}
    capex_frame, blend = per_draw['capex'], per_draw['blend']
    op_text = 'best operation per draw' if operation == 'best' else 'mean of the operations'
    figs = {}

    def class_traces(fig, x, y, err_x, err_y):
        for ts, g in s.groupby('tech_set', sort=False):
            fig.add_trace(go.Scatter(
                x=g[x], y=g[y], mode='markers+text', text=g.index, textposition='top right', name=ts, legendgroup=ts,
                marker=dict(size=10, color=TECH_COLOR.get(ts, '#444'), line=dict(color='black', width=0.5)),
                error_x=dict(type='data', symmetric=False, array=g[err_x[1]] - g[x], arrayminus=g[x] - g[err_x[0]],
                             thickness=1),
                error_y=dict(type='data', symmetric=False, array=g[err_y[1]] - g[y], arrayminus=g[y] - g[err_y[0]],
                             thickness=1),
                hovertemplate='%{text}<br>x %{x:.2f}<br>y %{y:.2f}<extra></extra>'))

    # 1a. CAPEX vs TOTEX: median and 95 % interval of each axis
    fig = go.Figure()
    class_traces(fig, 'CAPEX_median', 'TOTEX_median', ('CAPEX_lo95', 'CAPEX_hi95'), ('TOTEX_lo95', 'TOTEX_hi95'))
    fig.update_layout(**LAYOUT, width=1000, height=650, xaxis_title='CAPEX [CHF/m²/yr]', yaxis_title='TOTEX [CHF/m²/yr]',
                      title=f'CAPEX vs TOTEX under uncertainty: median and 95 % interval ({n_runs} draws, {op_text})')
    figs['capex_totex'] = fig

    # 1b. CAPEX vs TOTEX: every draw as a point, the region holding 95 % of the draws, and the median
    fig = go.Figure()
    for d, row in s.iterrows():
        c = TECH_COLOR.get(row['tech_set'], '#444')
        x, y = capex_frame.loc[d].to_numpy(), kpi_frames['TOTEX'].loc[d].to_numpy()
        fig.add_trace(go.Scattergl(x=x, y=y, mode='markers', marker=dict(size=3, color=c, opacity=0.15),
                                   legendgroup=row['tech_set'], showlegend=False, hoverinfo='skip'))
        hx, hy = _region95(x, y)
        fig.add_trace(go.Scatter(x=hx, y=hy, mode='lines', fill='toself', fillcolor=c, opacity=0.25,
                                 line=dict(color=c, width=1), legendgroup=row['tech_set'], showlegend=False,
                                 hoverinfo='skip'))
    for ts, g in s.groupby('tech_set', sort=False):
        fig.add_trace(go.Scatter(x=g['CAPEX_median'], y=g['TOTEX_median'], mode='markers+text', text=g.index,
                                 textposition='top right', name=ts, legendgroup=ts,
                                 marker=dict(size=10, color=TECH_COLOR.get(ts, '#444'), line=dict(color='black', width=1)),
                                 hovertemplate='%{text}<br>CAPEX %{x:.2f}<br>TOTEX %{y:.2f}<extra>median</extra>'))
    fig.update_layout(**LAYOUT, width=1000, height=650, xaxis_title='CAPEX [CHF/m²/yr]', yaxis_title='TOTEX [CHF/m²/yr]',
                      title=f'CAPEX vs TOTEX under uncertainty ({n_runs} draws, {op_text})<br><sub>dots = draws, '
                            f'shaded = region holding 95 % of the draws, large marker = median</sub>')
    figs['capex_totex_cloud'] = fig

    # 2. probabilistic ranking and blend (main result): weight = P(best score) | TOTEX, SS, GU
    #    of every design and of the blend, one row per design (sorted by expected rank), blend on top
    order = list(s.index)
    blend_label = 'BLEND'
    rows = [blend_label] + order                                      # top to bottom
    kw_text = ', '.join(f'{k} {v:.0%}' for k, v in kw.items() if v > 0)
    units = {'TOTEX': 'TOTEX [CHF/m²/yr]', 'SS': 'SS [%]', 'GU': 'GU [-]'}
    fig = make_subplots(rows=1, cols=4, column_widths=[0.16, 0.3, 0.27, 0.27], shared_yaxes=True,
                        horizontal_spacing=0.025,
                        subplot_titles=['Blend weight = P(best score)', units['TOTEX'] + ' (box)',
                                        units['SS'] + ' (dot area = share of draws)',
                                        units['GU'] + ' (dot area = share of draws)'])
    fig.add_trace(go.Bar(y=[blend_label], x=[0], orientation='h', showlegend=False, hoverinfo='skip'), row=1, col=1)
    w = s['weight']
    fig.add_trace(go.Bar(y=order, x=w, orientation='h', showlegend=False, text=[f'{v:.0%}' if v > 0.005 else ''
                                                                               for v in w], textposition='outside',
                         marker_color=[TECH_COLOR.get(t, '#444') for t in s['tech_set']],
                         hovertemplate='%{y}: %{x:.1%}<extra></extra>'), row=1, col=1)
    # TOTEX varies continuously over the draws -> box; SS and GU only take the values of the operations used ->
    # one dot per value, area = share of the draws
    series = lambda k: [(d, kpi_frames[k].loc[d].to_numpy(), TECH_COLOR.get(s.loc[d, 'tech_set'], '#444'))
                        for d in order] + [(blend_label, blend[k].to_numpy(), 'black')]
    for d, v, c in series('TOTEX'):
        fig.add_trace(go.Box(x=v, y=[d] * len(v), orientation='h', name=d, showlegend=False, boxpoints=False,
                             marker_color=c, line=dict(width=2 if d == blend_label else 1)), row=1, col=2)
    for j, (k, nd) in enumerate((('SS', 1), ('GU', 2)), start=3):
        for d, v, c in series(k):
            share = pd.Series(v.round(nd)).value_counts(normalize=True)
            fig.add_trace(go.Scatter(x=share.index, y=[d] * len(share), mode='markers', showlegend=False,
                                     marker=dict(size=4 + 18 * np.sqrt(share.to_numpy()), color=c, opacity=0.8,
                                                 line=dict(color='black', width=0.5)),
                                     customdata=share.to_numpy(),
                                     hovertemplate=f'{d}: %{{x}} in %{{customdata:.0%}} of the draws<extra></extra>'),
                          row=1, col=j)
    mix = ' + '.join(f'{v:.0%} {d}' for d, v in w.sort_values(ascending=False).items() if v > 0.005)
    for ts in dict.fromkeys(s['tech_set']):                          # legend: technology classes
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', name=ts,
                                 marker=dict(size=10, symbol='square', color=TECH_COLOR.get(ts, '#444'))), row=1, col=1)
    fig.update_yaxes(categoryorder='array', categoryarray=rows[::-1])
    fig.update_xaxes(tickformat='.0%', range=[0, min(1, 1.35 * w.max())], row=1, col=1)
    fig.update_layout(**LAYOUT, width=1400, height=170 + 30 * len(rows),
                      legend=dict(orientation='h', x=0.5, y=-0.12),
                      title=f'Probabilistic ranking and blend on TOTEX, SS and GU ({n_runs} sampled contexts, {op_text}; '
                            f'score weights {kw_text})<br>BLEND = {mix}', margin=dict(t=120))
    figs['ranking'] = fig

    # 3. adaptability vs lock-in (mean, whisker to the 95th percentile)
    fig = go.Figure()
    class_traces(fig, 'adaptability_mean', 'lock_in_mean', ('adaptability_mean', 'adaptability_p95'),
                 ('lock_in_mean', 'lock_in_p95'))
    fig.update_layout(**LAYOUT, width=950, height=600,
                      xaxis_title=f'Adaptability: {initial_operation} operation − best operation [CHF/m²/yr]',
                      yaxis_title='Lock-in: best operation − best design [CHF/m²/yr]',
                      title='Adaptability vs lock-in of each design: mean, whisker to the 95th percentile')
    figs['regret'] = fig
    return figs
