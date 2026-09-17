# Changelog

All notable changes to REHO are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and REHO follows [Semantic Versioning](https://semver.org/).

Entries are grouped by type of change (Added, Changed, Fixed, ...) and tagged with the area of the
codebase they affect, then sorted by those two columns. The **Breaking** column flags changes that
require action when upgrading: 🔴 breaks existing code, 🟠 still works today but is deprecated and
will break in a future release, 🟢 no action needed.

[added]: https://img.shields.io/badge/-Added-lightgrey
[changed]: https://img.shields.io/badge/-Changed-lightgrey
[deprecated]: https://img.shields.io/badge/-Deprecated-lightgrey
[removed]: https://img.shields.io/badge/-Removed-lightgrey
[fixed]: https://img.shields.io/badge/-Fixed-lightgrey
[security]: https://img.shields.io/badge/-Security-lightgrey

[model]: https://img.shields.io/badge/-Model-blue
[preprocessing]: https://img.shields.io/badge/-Preprocessing-green
[postprocessing]: https://img.shields.io/badge/-Postprocessing-orange
[plotting]: https://img.shields.io/badge/-Plotting-purple

[documentation]: https://img.shields.io/badge/-Documentation-yellow
[packaging]: https://img.shields.io/badge/-Packaging-lightblue

## [Unreleased]

Architecture and documentation overhaul, and the correction of two modelling errors that change
the results: the typical periods were shifted by one day, and the electrical heat gains ignored the
appliances. The refactoring itself leaves the results unchanged: run before and after, the compact,
building-scale and district-scale formulations produce identical output.

| Type                  | Category                          | Title | Description                                                                                                                                                                                        | Breaking |
|-----------------------|------------------------------------|------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------:|
| ![Added][added]       | ![Model][model]    | **Public API** | `from reho import REHO, QBuildingsReader, initialize_grids, initialize_units` now works. The names are resolved lazily, so `import reho` stays cheap. The old `from reho.model.reho import *` keeps working. | 🟢 |
| ![Added][added]       | ![Model][model]    | **`reho.model.options`** | The defaults of `method`, `scenario` and `DW_params` are declared as data, with a description for each option. The documentation tables are generated from them, so they cannot drift. | 🟢 |
| ![Added][added]       | ![Model][model]    | **Option validation** | An unknown option is now reported with the closest match (`'district_scale'` → did you mean `'district-scale'`?) instead of being silently ignored. Pass `strict=True` to raise instead. | 🟢 |
| ![Added][added]       | ![Model][model]    | **`reho.model.ampl_interface`** | AMPL session creation is in one place, and the technology → `.mod` mapping is a registry rather than an `if`/`elif` chain in two files. Adding a technology is now a one-line data change. | 🟢 |
| ![Added][added]       | ![Model][model]    | **`reho.logger`** | Central logging configuration. `configure_logging(level, enabled, ...)` replaces the scattered `print` calls; REHO no longer writes to stdout on import or from worker processes. | 🟢 |
| ![Added][added]       | ![Documentation][documentation]    | **Data reference** | New section documenting the inputs — every file of `reho/data/`: columns, units, provenance and known caveats — and the outputs — every `df_*` result DataFrame: index levels, columns, units, and when each is produced. | 🟢 |
| ![Added][added]       | ![Documentation][documentation]    | **API reference** | The Package structure page ends with the API reference, generated from the docstrings, which are rendered in full. | 🟢 |
| ![Added][added]       | ![Documentation][documentation]    | **Developer guide** | Replaces the Contribute page: how a run flows through the package, the coding conventions, recipes for adding a technology, an energy layer or an indicator, testing, documentation, and the contribution process. | 🟢 |
| ![Added][added]       | ![Packaging][packaging]    | **Continuous integration** | New `tests.yml` workflow running the offline test-suite on Python 3.11-3.13, the linter, the distribution build and the documentation build. | 🟢 |
| ![Added][added]       | ![Packaging][packaging]    | **Test-suite** | 132 offline tests covering options, paths, data integrity, the AMPL registries, the typical periods, the SIA profiles, the weights of the decomposition and several indicators — no license, solver, database or network needed. The tests that need them are marked `slow`, and `needs_ampl` or `needs_network`. `test_examples.py` now asserts on the exit code instead of always passing. | 🟢 |
| ![Changed][changed]   | ![Model][model]    | **Explicit imports** | The 26 `from x import *` inside the package are gone, and the example scripts import explicitly. The modules that were wildcard-imported keep an `__all__` so existing user scripts are unaffected. | 🟢 |
| ![Changed][changed]   | ![Model][model]    | **`reho.paths`** | No import-time side effects: it no longer loads `.env`, prints, or changes pandas' global display options. `reho.paths.path_to_clustering` and `path_to_configurations` are resolved against the working directory when read, rather than when `reho.paths` is imported. | 🟠 |
| ![Changed][changed]   | ![Model][model]    | **Infeasible problems** | `single_optimization` raises `RuntimeError` with a diagnostic message instead of calling `sys.exit`, which used to kill the interpreter of anything embedding REHO. | 🟠 |
| ![Changed][changed]   | ![Preprocessing][preprocessing]    | **Database failures** | `QBuildingsReader.establish_connection` raises `ConnectionError` instead of logging and returning a half-built reader that failed opaquely later. | 🟠 |
| ![Changed][changed]   | ![Preprocessing][preprocessing]    | **Typical-period cache** | The typical periods cached in `data/clustering/` are rebuilt when they were written by an earlier version of REHO, as recorded in `typical_periods_version.txt`, and a warning says so. A generation interrupted midway, which used to leave a directory later runs could not read, is redone too. | 🟢 |
| ![Changed][changed]   | ![Documentation][documentation]    | **Navigation** | Sections in the order Overview, Releases, Model, Data reference, Package structure, Developer guide and Getting started; Examples, Appendix and REHO-fm, which opens in a new tab, under More. | 🟢 |
| ![Removed][removed]   | ![Model][model]    | **Dynamic emission profiles** | The `use_dynamic_emission_profiles` option is removed, with everything that served it: the hourly emission matrix `reho/data/emissions/`, `reho.model.preprocessing.emissions_parser`, `reho.paths.path_to_emissions`, the unused `postcompute_average_emission` indicator and the `'E'` (emissions) clustering attribute. The option had been failing with a `KeyError` since the location data stopped building the profiles. Passing it now triggers the unknown-option warning, and the `'E'` attribute raises `ValueError`. | 🔴 |
| ![Fixed][fixed]       | ![Model][model]    | **`raise` of non-exceptions** | Seven places did `raise warnings.warn(...)` or `raise "a message"`, which raise `TypeError` instead of the intended error. They now raise a real exception with an actionable message. | 🟢 |
| ![Fixed][fixed]       | ![Model][model]    | **DHN temperature checks** | `if 'T_DHN_supply_cst' and 'T_DHN_return_cst' in parameters` reads as `if ('T_DHN_supply_cst') and (...)`: the first key was never checked. Four occurrences fixed. | 🟢 |
| ![Fixed][fixed]       | ![Model][model]    | **`cluster=None`** | `MasterProblem` crashed when no cluster was given, because the default was applied after the location data had already been read. | 🟢 |
| ![Fixed][fixed]       | ![Model][model]    | **Bare `except:`** | The 25 bare excepts are replaced by specific exceptions; they used to swallow `KeyboardInterrupt` and hide genuine errors. | 🟢 |
| ![Fixed][fixed]       | ![Model][model]    | **Initiation weights** | `get_beta_values` tested the objective after replacing it by `SP_obj_fct`, so when minimizing OPEX the initiation of the decomposition put its secondary weight on OPEX itself — a mere rescaling that proposed essentially the same configuration three times — instead of on CAPEX. It also removed the epsilon constraints from the scenario shared by the sub-problems: with `parallel_computation` disabled, every sub-problem initiated after the first put that weight on OPEX instead of on the constrained objective. District-scale results minimizing OPEX, such as the ends of a Pareto front, may change. | 🟢 |
| ![Fixed][fixed]       | ![Preprocessing][preprocessing]    | **Renovation over mixed periods** | A building spanning more construction periods than it has area ratios raised `IndexError`, because the padding computed a negative length. | 🟢 |
| ![Fixed][fixed]       | ![Preprocessing][preprocessing]    | **`sympy` shadowing** | A loop variable named `sp` shadowed the module-level `import sympy as sp` in `actors.py`. | 🟢 |
| ![Fixed][fixed]       | ![Preprocessing][preprocessing]    | **Delimiter detection** | `file_reader` inspected only the header line, so it misread files whose column names contain a comma (`sia2024_rooms_sia380_1.csv`). It now requires a delimiter to split every line consistently, and raises instead of returning `None` when a file cannot be parsed. | 🟢 |
| ![Fixed][fixed]       | ![Preprocessing][preprocessing]    | **Typical periods shifted by one day** | The K-medoids clustering numbered the medoid days from 0, while every place reading them counts from 1: each typical period took the weather and the date — hence the monthly and weekday SIA factors and the sun position — of the day before its medoid, which may belong to another cluster. The two extreme periods were dated one day early as well. The results change, and the cached typical periods are rebuilt. On the first two buildings of `scripts/examples/data/buildings.csv`, over three clusterings of the Geneva weather with the same medoids, the space-heating demand changed by −12% to +0.4% and the net operating cost by up to 5,900 CHF/y, and the results varied much less from one clustering to the next. | 🟢 |
| ![Fixed][fixed]       | ![Preprocessing][preprocessing]    | **Electrical heat gains** | The SIA 2024 profiles were unpacked in the wrong order, so the electrical heat gains came from the lighting and the additional (showroom) lighting instead of the lighting and the appliances: for housing, only the lighting — about 11% of the electricity use — produced heat gains. The electricity demand itself was right. The results change: on the first two buildings of `scripts/examples/data/buildings.csv`, the space-heating demand decreases by 6.6%. | 🟢 |
| ![Fixed][fixed]       | ![Preprocessing][preprocessing]    | **Periods from the same day** | `write_weather_files` told the periods apart by their day of the year, so an extreme period falling on the day of a typical period was merged with it. Periods are now told apart by position, and the date of a period uses the period duration instead of 24 hours. | 🟢 |
| ![Fixed][fixed]       | ![Preprocessing][preprocessing]    | **Retry policy** | `requests_retry_session` mounted its retry adapter twice on `https://` and never on `http://`. | 🟢 |
| ![Fixed][fixed]       | ![Postprocessing][postprocessing]    | **`extract_parameters`** | The option read every AMPL parameter and then discarded them. They are stored in `df_Parameters`, per building with the decomposition. A table too large for an xlsx sheet — `df_Parameters` of a district of more than about fifteen buildings — is left out of the xlsx export with a warning, where it used to make the whole export fail. | 🟢 |
| ![Fixed][fixed]       | ![Postprocessing][postprocessing]    | **Heat pump COP** | The COP of a building was that of the first heat pump listed for it, NaN when that one was not installed. It now combines all the heat pumps of the building. | 🟢 |
| ![Fixed][fixed]       | ![Postprocessing][postprocessing]    | **Sensitivity analysis** | `run_SA` never called `extract_results`, which moreover read the results as attributes and under another key: `objective_values` stayed empty and `calculate_SA` could not run. | 🟢 |
| ![Fixed][fixed]       | ![Plotting][plotting]    | **Monthly averages** | `monthly_average`, used by `plot_unit_monthly`, divided the total of each month by its number of hours minus one. | 🟢 |
| ![Fixed][fixed]       | ![Documentation][documentation]    | **Sphinx build** | From 84 warnings to zero, and the build now passes with `-W`. `docs/.venvdocs` was being scanned, every module was documented twice, and `conf.py` had a missing comma that silently merged two mocked imports. | 🟢 |
| ![Fixed][fixed]       | ![Packaging][packaging]    | **Package declarations** | `packages = ["reho"]` omitted every sub-package and the `package-data` key was `"REHO"`, which matches nothing; the wheel was only correct by accident, through setuptools-scm's file finder. | 🟢 |

## [v2.0.1]

| Type                  | Category                          | Title | Description                                                                                                                                                                                        | Breaking |
|-----------------------|------------------------------------|------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------:|
| ![Added][added]       | ![Postprocessing][postprocessing]    | **OSMOSE export** | Add `reho.model.postprocessing.osmose.get_osmose_streams`, which converts the buildings space heating, domestic hot water, and cooling demands of `df_Buildings_t` into a list of heat and cold streams, ready to be used in OSMOSE. Demands are grouped by service and temperature interval (supply and return temperatures within a given tolerance), for each scenario and Pareto step. Takes either the results dictionary or the path to a saved pickle. | 🟢 |
| ![Added][added]       | ![Postprocessing][postprocessing]    | **Cooling temperatures** | `df_Buildings_t` now also contains the cooling supply and return temperatures (`Tc_supply`, `Tc_return`), next to the heating ones. | 🟢 |
|  |  |  |  |  |
| ![Added][added]       | ![Model][model]    | **Renovation value recovery** | Added a `renovation_value_share` parameter, representing the share of renovation cost offset by the resulting increase in house value. | 🟢 |
| ![Changed][changed]   | ![Model][model]    | **Mobility** | Added a cost of mobility to the actors problem and simplified the mobility model. Removed the obligation to have an EV charger in the district when an ICE vehicle is present. `ebike.mod` was deleted along the way while `ElectricBike_district` stayed selectable, which broke examples `6a` and `6b`; the file is restored — flagged in case dropping electric bikes was in fact intended. | 🟢 |
| ![Changed][changed]   | ![Model][model]    | **Actors** | `Samples` is now a DataFrame instead of a `dict`, so it no longer breaks the result filtering and the xlsx export — a long-standing bug that made every actors run crash, unrelated to pandas 3.0. `Cost_travel` is written as a scalar, which pandas 3.0 requires. A warning is now logged when `Network_ext` is below the district peak demand: the decomposition initiation then caps grid use below that peak, and the sub-problems come back infeasible at the coldest hour without anything pointing at the network. | 🟢 |
| ![Fixed][fixed]       | ![Model][model]    | **Corrections** | Transmission of results from the sub-problem to the master problem: PV production, mobility extreme periods, and `df_Annuals`. Restored the `data_EUD` declarations in `master_problem.mod`, without which any scenario using the `DataHeat` unit (example `3l`) failed. Realigned the sensitivity analysis with the parameter format introduced by "Adapt SA for buildings data" — unit keys, the optional `units` group, and a `Pareto_ID` that no longer reads as a directory path when saving (example `4b`). | 🟢 |

## [v2.0.0]



| Type                  | Category                          | Title | Description                                                                                                                                                                                        | Breaking |
|-----------------------|------------------------------------|------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------:|
| ![Changed][changed]   | Global                  | **Packages migration** | Dropped support for pandas 1.x and 2.x; REHO now requires `pandas>=3.0.0`. Code relying on pre-3.0 pandas semantics (e.g. implicit downcasting, `DataFrame.append`, old `groupby`/`resample` defaults) will need to be updated before upgrading. | 🔴 |
| ![Changed][changed]   | Global                   | **Packages migration** | Dropped support for SQLAlchemy 1.x; REHO now requires `sqlalchemy>=2.0.0`. Any custom code building queries against `QBuildingsReader.tables` using the 1.x `select([...])` style must be updated to the 2.0 `select(...)` API. | 🔴 |
| ![Changed][changed]   | Global                    | **Packages migration** | Raised the minimum Python version from 3.9 to 3.11. Python 3.9 and 3.10 are no longer supported. | 🔴 |
| ![Changed][changed]   | Global                    | **Packages migration** | Unpinned numpy (`<2.0.0`) and geopandas (`<1.0.0`). Environments now resolve to numpy 2.x / geopandas 1.x by default; code depending on numpy 1.x or geopandas <1.0 behavior may break. | 🔴 |
| ![Fixed][fixed]       | Scripts                    | **Packages migration** | Various fixes to example scripts and the test runner for pandas 3.0. | 🟢 |
|  |  |  |  |  |
| ![Changed][changed]   | ![Preprocessing][preprocessing]    | **QBuildings access** | `QBuildingsReader.read_db` selection API changed:<br>1. Buildings are now selected through a single `filters` dictionary, e.g. `read_db({'transformers': 234})`, `read_db({'egid': 1009515})`, `read_db({'geometry': 'boundary.gpkg'})`.<br>2. Filters combine with a logical AND, so a transformer and an EGID can be given together.<br>3. The `district_boundary`, `district_id`, `egid`, and `id_building` keyword arguments are deprecated in favor of `filters`; they now raise a `DeprecationWarning` and will be removed in a future release. | 🟠  |
| ![Added][added]       | ![Preprocessing][preprocessing]    | **QBuildings access** | `QBuildingsReader.read_db` can now select buildings by `id_building`, and by an arbitrary `geometry` (a file path, WKT string, shapely geometry, or (Geo)DataFrame) via spatial intersection. | 🟢 |
|  |  |  |  |  |
| ![Added][added]       | ![Plotting][plotting]    | **Profiles** | Adding of a `plot_combined_profiles` that allows to combine different type of profiles to be mixed together, typically one by season. | 🟢 |
| ![Fixed][fixed]       | ![Plotting][plotting]    | **Plot fixes** | Correction in `plot_eud` and `plot_pareto`and `plot_pareto_by_objectives`. | 🟢 |
| ![Added][added]       | ![Preprocessing][preprocessing]    | **Reference scenario** | If the scenario name is `reference`, it activates a function where we build REHO with the units configuration (heating + dhw system and installed PVs) retrieved from QBuildings. | 🟢 |
| ![Changed][changed]       | ![Preprocessing][preprocessing]    | **Solar gains** | Change of re-calibration of solar gains and Uh when ERA < Footprint. | 🟢 |
| ![Changed][changed]       | ![Postprocessing][postprocessing]    | **Sensitivity analysis** | Add an option to do the sensitivity analysis in the buildings data as well as prices. | 🟠 |

### Migration notes

- If you pin `REHO<2.0` (once released) in your own project, your existing pandas 1.x/2.x and
  SQLAlchemy 1.x environment will keep working. Upgrading to `REHO>=2.0` requires upgrading
  pandas and SQLAlchemy alongside it — there is no dual-support release.
- Replace `reader.read_db(district_id=234, egid=[...])` with
  `reader.read_db({'transformers': 234, 'egid': [...]})`. The deprecated keyword form still works
  but now raises a `DeprecationWarning` and will be removed later.
