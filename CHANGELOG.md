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
