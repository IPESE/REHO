# Diverse configurations under uncertainty (branch `gengfu`)

Two generic functions on top of REHO:

| File | Function | What it does |
|---|---|---|
| `diverse_configs/generate_config.py` | `generate_config()` | Generates a pool of diverse district configurations (TOTEX optimum, SS maximum, MGA, SS targets, tariffs, technology sets, forced sizes), selects N diverse ones, re-runs each under 3 economic contexts with `fix_units` and returns the dataframe for the Monte-Carlo pipeline + figures. |
| `diverse_configs/challenge_configurations.py` | `challenge_configurations_under_uncertainty()` | Paired Monte Carlo on that dataframe: CAPEX-TOTEX median and 95 % interval, probabilistic ranking and blend of designs (score on TOTEX, SS, GU), regret, adaptability and lock-in. |

`diverse_configs/generate_config_test_LowRise10.ipynb` runs both on 10 Low-Rise buildings (Geneva weather).

## Setup

1. REHO of this branch = v2.2.0 + the `GWP_OP` objective (operational GWP only, used for the SS maximum).
   Install it from the repository root, and make sure no other `reho` is installed in the same environment:

   ```
   pip install --extra-index-url https://pypi.ampl.com -e .
   pip install seaborn            # needed by scripts/uncertainty_postprocess.py, not a REHO dependency
   ```

2. Solver: `generate_config()` uses Gurobi through AMPL by default (AMPL Gurobi module + licence).
   Without Gurobi, pass `reho_settings={'solver': 'highs'}` (much slower).

## Inputs used by the notebook

- `results/district_candidates_qbuildings.pickle`: buildings of the candidate districts (no QBuildings database connection needed)
- `../uncertainty/energy_storage_parameters.xlsx` + `energy_storage_distributions.py`: uncertainty distributions
- `../uncertainty_postprocess.py`: Monte-Carlo pipeline (`get_results`, `sample_uncertainty_draws`, `compute_uncertain_economics`)

## Run

Open the notebook in `diverse_configs/` and run it top to bottom. Results are written to
`diverse_configs/results/<district>10_gc_quick/` (not versioned); an interrupted run resumes where it stopped.
`QUICK = True` runs a reduced lever set (about 30 + 3N REHO optimisations).

Note: `scripts/` is in `.gitignore`; add changes to these files with `git add -f`.
