"""
Energy Storage Parameter Distribution Estimator
================================================
Reads ALL parameter definitions (ranges, distribution type, min/max)
directly from  energy_storage_parameters.xlsx  — edit the Excel file
to add literature sources or change distribution settings, then re-run.

Usage:
    python energy_storage_distributions.py
    # optional: python energy_storage_distributions.py path/to/other.xlsx

Outputs:
    energy_storage_distributions.png   — 2×3 panel figure
    (summary statistics printed to console)

Excel structure expected per sheet
───────────────────────────────────
Row 1  : title  (e.g. "Battery Investment Cost  [CHF/kWh]")
Row 2  : description (free text, ignored here)
Row 3  : blank
Row 4  : column headers  → cols A-G:
           Source | Year | Range | Min | Max | Notes | URL
Rows 5…: one literature source per row  (ends at first blank Source cell)

After a blank row, a "Distribution assumptions" block:
  "Recommended distribution"  → value in col B  (Normal/Uniform/Triangular/Log-normal)
  "Suggested Min"             → value in col B
  "Suggested Max"             → value in col B
  (optional) "Mode / peak"    → value in col B   (used for Triangular)

──────────────────────────────────────────────────────────────────────
CHANGE LOG (uncertainty-vs-hard-limits update)
──────────────────────────────────────────────────────────────────────
"Suggested Min" / "Suggested Max" are treated as HARD LITERATURE LIMITS
(i.e. effectively the 100% interval), not a soft ~95% band. Concretely:

1. Bug fix: the old code checked `mean is np.nan` / `std is np.nan` to
   decide whether to auto-derive them. Since these fields are actually
   initialised to `None` (not the float `np.nan`), that check was always
   False, so any Normal-distribution sheet WITHOUT an explicit
   "Suggested Mean"/"Suggested Std" (e.g. Battery CAPEX) silently ended
   up with mean=None, std=None and would crash downstream. Fixed to
   check `is None`.

2. Auto-derived std (Normal distributions with no explicit std given)
   used to assume p_min/p_max = symmetric 95% interval
   (std = (p_max - p_min) / (2 * z_0.975)). It now assumes p_min/p_max
   are hard bounds that should only be exceeded by ~0.1% of the mass on
   the MOST CONSTRAINED side (i.e. whichever of mean-p_min / p_max-mean
   is smaller): std = min(mean - p_min, p_max - mean) / z_0.999. This
   makes std strictly subordinate to (less "impacting" than) the
   literature min/max — it can no longer imply a spread that blows past
   the hard bounds on its tighter side. The looser side is free to carry
   a longer, less probable tail (useful for genuinely skewed parameters).
   This only changes sheets where std is NOT explicitly given; explicit
   "Suggested Std dev" values (e.g. rSOC CAPEX, deliberately wide to
   express a heavy right tail) are left untouched — the shape stays
   exactly as you tuned it.

3. Plotting (`make_figure`): the literature min/max are now drawn as
   solid red vertical lines ("Literature hard limit"), and the plotted
   curve / shaded interval are clipped to stop at those bounds — even
   if the underlying continuous distribution (e.g. a wide log-normal)
   would mathematically extend past them. This mirrors what
   `sample_clipped()` already enforces on drawn samples, so the figure
   now honestly reflects what the Monte Carlo actually produces (e.g.
   rSOC CAPEX no longer visually implies mass near 100 CHF/kW when the
   floor is 700).

4. `build_distribution_dict`: `p_lower` / `p_upper` (which
   `sample_uncertainty_draws` feeds straight into `sample_clipped()` as
   the clip bounds) used to be `rv.ppf(percentiles)` — e.g. the
   statistical 2.5%/97.5% quantiles — NOT the literature hard bounds.
   For rSOC CAPEX that meant samples were actually being clipped to
   ~237–2824 CHF/kW, not the intended 700–2500 hard limits. `p_lower` /
   `p_upper` now equal the literature `p_min` / `p_max` directly, so
   sampling truly respects the hard limits. The old percentile-based
   values are preserved separately as `ci_lower` / `ci_upper` for
   reporting.
"""

import sys
import re
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import pandas as pd
from scipy import stats
from pathlib import Path


def _clean(val):
    """Return stripped string or None for blank/NaN cells."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return str(val).strip()


def load_parameters(xlsx_path: str, DIST_ALIASES: dict) -> list:

    xl = pd.ExcelFile(xlsx_path)

    parameters = []

    for sheet_name in xl.sheet_names:

        df = xl.parse(sheet_name, header=None)

        # --------------------------------------------------------------
        # Title
        # --------------------------------------------------------------

        title_raw = _clean(df.iloc[0, 0]) or sheet_name

        m = re.search(r"\[(.+?)\]", title_raw)

        unit = m.group(1).strip() if m else ""

        label = re.sub(r"\s*\[.+?\]", "", title_raw).strip()

        # --------------------------------------------------------------
        # Header row
        # --------------------------------------------------------------

        header_row = None

        for i, row in df.iterrows():

            if _clean(row.iloc[0]) == "Source":

                header_row = i
                break

        if header_row is None:
            continue

        # --------------------------------------------------------------
        # Literature ranges
        # --------------------------------------------------------------

        lit_ranges = []

        for i in range(header_row + 1, len(df)):

            row = df.iloc[i]

            src = _clean(row.iloc[0])

            if not src:
                break

            try:
                lo = float(row.iloc[3])
                hi = float(row.iloc[4])

            except (ValueError, TypeError):
                continue

            lit_ranges.append((lo, hi, src))

        # --------------------------------------------------------------
        # Distribution assumptions
        # --------------------------------------------------------------

        dist_type = "normal"

        p_min = None
        p_max = None

        mean = None
        std = None

        mode = None

        for i in range(header_row + 1, len(df)):

            row = df.iloc[i]

            key = (_clean(row.iloc[0]) or "").lower()

            val = row.iloc[1]

            if "recommended distribution" in key:

                raw = (_clean(val) or "").lower()

                dist_type = DIST_ALIASES.get(raw, "normal")

            elif "suggested min" in key:

                cleaned = _clean(val)
                if cleaned is not None:
                    try:
                        p_min = float(cleaned)
                    except ValueError:
                        pass

            elif "suggested max" in key:

                cleaned = _clean(val)
                if cleaned is not None:
                    try:
                        p_max = float(cleaned)
                    except ValueError:
                        pass

            elif "suggested mean" in key:

                cleaned = _clean(val)
                if cleaned is not None:
                    try:
                        mean = float(cleaned)
                    except ValueError:
                        pass

            elif "suggested std" in key:

                cleaned = _clean(val)
                if cleaned is not None:
                    try:
                        std = float(cleaned)
                    except ValueError:
                        pass

            elif "mode" in key or "peak" in key:

                cleaned = _clean(val)
                if cleaned is not None:
                    try:
                        mode = float(cleaned)
                    except ValueError:
                        pass

        # --------------------------------------------------------------
        # Fallback from literature
        # --------------------------------------------------------------

        if p_min is None and lit_ranges:
            p_min = min(lo for lo, _, _ in lit_ranges)

        if p_max is None and lit_ranges:
            p_max = max(hi for _, hi, _ in lit_ranges)

        if p_min is None or p_max is None:
            continue

        # --------------------------------------------------------------
        # Infer normal parameters.
        #
        # p_min / p_max are treated as HARD literature limits (~100%
        # interval), not a soft 95% band. When std isn't given explicitly,
        # we derive it from whichever side (mean-p_min or p_max-mean) is
        # tighter, pinning THAT side to the one-sided 99.9th percentile
        # (z_0.999 ≈ 3.09). This keeps std subordinate to the literature
        # bounds instead of the old symmetric 95% assumption
        # (std = (p_max - p_min) / (2*z_0.975)), which could push
        # meaningful probability mass past the stated min/max.
        # --------------------------------------------------------------

        if dist_type == "normal":

            if mean is None:
                mean = (p_min + p_max) / 2

            if std is None:

                z999 = stats.norm.ppf(0.999)  # one-sided 99.9%

                half_lower = mean - p_min
                half_upper = p_max - mean

                most_constrained_half = min(half_lower, half_upper)

                std = most_constrained_half / z999

        # --------------------------------------------------------------
        # Non-normal distributions:
        # require explicit mean/std
        # --------------------------------------------------------------

        else:

            if mean is None or std is None:

                raise ValueError(
                    f"{sheet_name}: "
                    f"non-normal distributions require "
                    f"'Suggested Mean' and 'Suggested Std'"
                )

        # --------------------------------------------------------------
        # Default triangular mode
        # --------------------------------------------------------------

        if mode is None:
            mode = mean

        # --------------------------------------------------------------

        param_id = re.sub(
            r"[^a-z0-9]+",
            "_",
            sheet_name.lower()
        ).strip("_")

        parameters.append({

            "id": param_id,
            "label": label,
            "unit": unit,

            "dist": dist_type,

            "p_min": p_min,
            "p_max": p_max,

            "mean": mean,
            "std": std,

            "mode": mode,

            "lit_ranges": lit_ranges,
        })

    return parameters


def _build_rv(p):
    """Build the scipy frozen random variable for a parameter dict."""

    dist = p["dist"]

    mean = p["mean"]
    std = p["std"]

    p_min = p["p_min"]
    p_max = p["p_max"]

    mode = p["mode"]

    # --------------------------------------------------------------
    # NORMAL
    # --------------------------------------------------------------

    if dist == "normal":

        rv = stats.norm(
            loc=mean,
            scale=std
        )

    # --------------------------------------------------------------
    # UNIFORM
    # --------------------------------------------------------------

    elif dist == "uniform":

        rv = stats.uniform(
            loc=p_min,
            scale=p_max - p_min
        )

    # --------------------------------------------------------------
    # TRIANGULAR
    # --------------------------------------------------------------

    elif dist == "triangular":

        c = (mode - p_min) / (p_max - p_min)

        rv = stats.triang(
            c=c,
            loc=p_min,
            scale=p_max - p_min
        )

    # --------------------------------------------------------------
    # LOGNORMAL
    # --------------------------------------------------------------

    elif dist == "lognormal":

        variance = std**2

        sigma_ln = np.sqrt(
            np.log(
                1 + variance / mean**2
            )
        )

        mu_ln = (
            np.log(mean)
            - sigma_ln**2 / 2
        )

        rv = stats.lognorm(
            s=sigma_ln,
            scale=np.exp(mu_ln)
        )

    else:

        raise ValueError(
            f"Unknown distribution: {dist}"
        )

    return rv


def make_figure(
    parameters: list,
    out_path: str = "energy_storage_distributions.pdf",
    show_literature_samples: bool = True,
    percentiles=(0.025, 0.975)
):

    def build_distribution(p):
        return _build_rv(p)

    def draw_vline_to_pdf(
            ax,
            x0,
            rv,
            pdf_max,
            color="black",
            lw=1.0,
            linestyle="-",
            label=None
    ):

        y0 = rv.pdf(x0) / pdf_max

        ax.plot(
            [x0, x0],
            [0, y0],
            color=color,
            lw=lw,
            linestyle=linestyle,
            label=label
        )
    # ------------------------------------------------------------------
    # Figure layout
    # ------------------------------------------------------------------

    n = len(parameters)

    nc = 3
    nr = (n + nc - 1) // nc

    fig = plt.figure(
        figsize=(5 * nc, 5 * nr)
    )

    gs = gridspec.GridSpec(
        nr,
        nc,
        figure=fig,
        hspace=0.38,
        wspace=0.30,
        left=0.07,
        right=0.98,
        top=0.92,
        bottom=0.08
    )

    #fig.suptitle(
    #    "Energy Storage Parameter Distributions",
    #    fontsize=14,
    #    fontweight="bold"
    #)

    # ------------------------------------------------------------------
    # Plot each parameter
    # ------------------------------------------------------------------

    for idx, p in enumerate(parameters):

        ax = fig.add_subplot(
            gs[idx // nc, idx % nc]
        )

        rv = build_distribution(p)

        p_min = p["p_min"]
        p_max = p["p_max"]

        # --------------------------------------------------------------
        # X grid — clipped to the literature hard limits.
        #
        # Even if the underlying continuous distribution (e.g. a wide
        # log-normal deliberately set up for a heavy right tail) has
        # mathematical support beyond [p_min, p_max], we never draw the
        # curve / shading there: sample_clipped() already prevents any
        # actual Monte Carlo draw from leaving this range, so showing
        # probability mass outside it on the plot would be misleading.
        # --------------------------------------------------------------

        x_lo = max(rv.ppf(0.001), p_min)
        x_hi = min(rv.ppf(0.999), p_max)

        x = np.linspace(
            x_lo,
            x_hi,
            1000
        )

        pdf = rv.pdf(x)

        # Normalize to max = 1
        pdf_norm = pdf / np.max(pdf)

        # --------------------------------------------------------------
        # Statistics
        # --------------------------------------------------------------

        mean = rv.mean()

        median = rv.median()

        # Percentile markers, clamped into the hard-limit range (if the
        # requested percentile falls outside p_min/p_max, the hard limit
        # itself is the more honest marker — the tail is truncated there).
        plb = np.clip(rv.ppf(percentiles[0]), p_min, p_max)

        pub = np.clip(rv.ppf(percentiles[1]), p_min, p_max)

        # --------------------------------------------------------------
        # Shaded percentile region
        # --------------------------------------------------------------

        mask = (
            (x >= plb)
            & (x <= pub)
        )

        interval_label = (
            f"{int((percentiles[1]-percentiles[0])*100)}% interval"
        )

        ax.fill_between(
            x[mask],
            pdf_norm[mask],
            0,
            color="#2e4d7a",
            alpha=0.30,
            label=interval_label
        )

        # --------------------------------------------------------------
        # Distribution curve
        # --------------------------------------------------------------

        ax.plot(
            x,
            pdf_norm,
            color="#2e4d7a",
            lw=2
        )

        # --------------------------------------------------------------
        # Median (main indicator)
        # --------------------------------------------------------------

        draw_vline_to_pdf(
            ax=ax,
            x0=median,
            rv=rv,
            pdf_max=np.max(pdf),
            color="black",
            lw=1.6,
            linestyle="-",
            label="Median"
        )

        # --------------------------------------------------------------
        # Mean (secondary indicator)
        # --------------------------------------------------------------

        draw_vline_to_pdf(
            ax=ax,
            x0=mean,
            rv=rv,
            pdf_max=np.max(pdf),
            color="black",
            lw=1.2,
            linestyle=":",
            label="Mean"
        )

        # --------------------------------------------------------------
        # Lower percentile
        # --------------------------------------------------------------

        draw_vline_to_pdf(
            ax=ax,
            x0=plb,
            rv=rv,
            pdf_max=np.max(pdf),
            color="black",
            lw=1.0,
            linestyle="--"
        )

        # --------------------------------------------------------------
        # Upper percentile
        # --------------------------------------------------------------

        draw_vline_to_pdf(
            ax=ax,
            x0=pub,
            rv=rv,
            pdf_max=np.max(pdf),
            color="black",
            lw=1.0,
            linestyle="--",
            label="P5–P95"
        )

        # --------------------------------------------------------------
        # Literature hard limits (min/max) — always drawn, full height,
        # in red, so it's visually unambiguous these are hard cutoffs
        # (matching what sample_clipped() enforces on the actual draws),
        # not just another statistical percentile.
        # --------------------------------------------------------------

        ax.axvline(
            p_min,
            color="red",
            lw=1.4,
            linestyle="-",
            alpha=0.85,
            zorder=5,
            label="Literature hard limit"
        )

        ax.axvline(
            p_max,
            color="red",
            lw=1.4,
            linestyle="-",
            alpha=0.85,
            zorder=5
        )

        if show_literature_samples:

            y0 = 0.04

            for i, (lo, hi, _) in enumerate(
                p["lit_ranges"]
            ):

                yy = y0 + 0.025 * i

                ax.plot(
                    [lo, hi],
                    [yy, yy],
                    color="0.45",
                    lw=2,
                    solid_capstyle="butt"
                )

        # --------------------------------------------------------------
        # Labels
        # --------------------------------------------------------------

        ax.set_title(
            p["label"],
            fontsize=12,
            fontweight="bold"
        )

        ax.set_xlabel(
            p["unit"],
            fontsize=12
        )

        ax.set_ylabel(
            "Relative likelihood",
            fontsize=12
        )

        # --------------------------------------------------------------
        # Y axis
        # --------------------------------------------------------------

        ax.set_ylim(0, 1.08)

        ax.set_yticks(
            np.linspace(0, 1, 6)
        )

        # --------------------------------------------------------------
        # Grid
        # --------------------------------------------------------------

        ax.grid(
            alpha=0.15,
            linestyle="--",
            linewidth=0.5
        )

        # --------------------------------------------------------------
        # Cosmetics
        # --------------------------------------------------------------

        ax.tick_params(
            labelsize=10
        )

        ax.spines["top"].set_visible(False)

        ax.spines["right"].set_visible(False)

        # --------------------------------------------------------------
        # Legend
        # --------------------------------------------------------------

        ax.legend(
            fontsize=10,
            frameon=False,
            loc="upper right",
            bbox_to_anchor=(0.98, 1.02)
        )

    # ------------------------------------------------------------------
    # Save figure
    # ------------------------------------------------------------------

    plt.savefig(
        out_path,
        bbox_inches="tight"
    )

    print(f"Figure saved → {out_path}")

    return fig


def build_distribution_dict(parameters, percentiles):

    distributions = {}

    for p in parameters:

        rv = _build_rv(p)

        distributions[p["id"]] = {

            "rv": rv,

            "label": p["label"],

            "unit": p["unit"],

            "distribution": p["dist"],

            "mean": rv.mean(),

            "median": rv.median(),

            "std": rv.std(),

            # Hard literature limits — this is what sample_clipped() should
            # (and now does) use to bound actual Monte Carlo draws, so the
            # samples can never fall outside the literature-stated range.
            "p_lower": p["p_min"],

            "p_upper": p["p_max"],

            # Kept for reference/reporting: the purely statistical
            # quantiles of the fitted distribution (may fall outside
            # p_min/p_max for deliberately wide/skewed fits, e.g. a
            # heavy-tailed log-normal — that's expected and is exactly
            # why sampling clips to p_lower/p_upper instead of these).
            "ci_lower": rv.ppf(percentiles[0]),

            "ci_upper": rv.ppf(percentiles[1]),
        }

    return distributions