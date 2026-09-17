# Input

REHO ships with the reference data needed to run a Swiss case study out of the
box: technology catalogues, energy-layer tariffs and emission factors, building
norms, mobility profiles and a discretized sky dome. This page documents every
file: what it contains, in which units, and where it comes from.

The inputs that describe the case study itself — the buildings, read from
QBuildings or from a CSV file, and the weather — are presented in
{doc}`../getting_started`.

All these files live in `reho/data/` and are exposed through
{mod}`reho.paths`. Any of them can be replaced by a custom file — see
{ref}`using-your-own-data`.

:::{admonition} Units convention
:class: note

Unless stated otherwise: power in **kW**, energy in **kWh**, costs in **CHF**,
emissions in **kgCO₂-eq**, temperatures in **°C**, areas in **m²**, and
U-values in **kW/(m²·K)**.
:::

---

## `infrastructure/` — technologies and energy layers

The energy system is described by two kinds of objects: **layers** (the energy
carriers that can be exchanged with the outside world) and **units** (the
technologies that convert, store or transport energy between layers).

(tbl-layers-schema)=
### `layers.csv` — energy layers

Read by {func}`~reho.model.infrastructure.initialize_grids`. One row per energy
carrier. Semicolon-separated.

| Column | Unit | Meaning |
|---|---|---|
| `Grid` | – | Layer name, used as the key everywhere else (`Electricity`, `NaturalGas`, `Heat`, ...) |
| `ref_unit` | – | Unit in which the layer is accounted (`kWh`) |
| `Network_demand_connection` | – | Multiplier on the export connection capacity (×10⁶) |
| `Network_supply_connection` | – | Multiplier on the import connection capacity (×10⁶) |
| `Cost_demand_cst` | CHF/kWh | Price **received** when exporting to the network (feed-in tariff) |
| `Cost_supply_cst` | CHF/kWh | Price **paid** when importing from the network (retail tariff) |
| `GWP_demand_cst` | kgCO₂/kWh | Emissions avoided by exporting |
| `GWP_supply_cst` | kgCO₂/kWh | Emissions of imported energy |
| `Cost_connection` | CHF/y | Fixed cost of being connected to the layer |
| `Network_ext` | kW | Capacity of the connection to the external network |
| `ReinforcementOfNetwork` | kW | Available reinforcement steps, `/`-separated and increasing |
| `Cost_network_inv1`, `Cost_network_inv2` | CHF, CHF/kW | Fixed and specific investment cost of a reinforcement |
| `GWP_network_1`, `GWP_network_2` | kgCO₂, kgCO₂/kW | Fixed and specific embodied emissions of a reinforcement |
| `Network_lifetime` | y | Lifetime used to annualize the reinforcement investment |

:::{admonition} Why `Cost_supply_cst` ≥ `Cost_demand_cst`
:class: important

Buying energy must cost at least as much as selling it back. Otherwise the
optimizer discovers a money pump: import and immediately re-export, indefinitely.
The test-suite enforces this invariant
(`reho/test/test_data.py::TestLayers::test_supply_is_not_cheaper_than_demand`).
:::

Default values: {ref}`tbl-grid`.

(tbl-units-schema)=
### `building_units.csv`, `district_units.csv` — technology catalogue

Read by {func}`~reho.model.infrastructure.initialize_units`, via
{func}`~reho.model.infrastructure.prepare_units_df`. One row per technology.
Semicolon-separated; cells holding a list use `/` as separator.

| Column | Unit | Meaning |
|---|---|---|
| `Unit` | – | Unique name. At the building scale it is suffixed with the building (`PV` → `PV_Building1`) |
| `ref_unit` | – | Unit in which the size is expressed (`kWth`, `kWe`, `kWh`, `m2`, ...) |
| `Units_Fmin`, `Units_Fmax` | `ref_unit` | Minimum and maximum size when the unit is installed |
| `Cost_inv1` | CHF | Fixed investment cost, paid as soon as the unit is installed |
| `Cost_inv2` | CHF/`ref_unit` | Specific investment cost, proportional to the size |
| `GWP_unit1` | kgCO₂ | Fixed embodied emissions |
| `GWP_unit2` | kgCO₂/`ref_unit` | Specific embodied emissions |
| `lifetime` | y | Technical lifetime, used for annualization and replacement |
| `UnitOfType` | – | Technology family. **Must** match a key of {data}`~reho.model.ampl_interface.BUILDING_UNIT_MODELS` or {data}`~reho.model.ampl_interface.DISTRICT_UNIT_MODELS` |
| `UnitOfLayer` | – | Layers the unit connects to, `/`-separated. Includes `HeatCascade` for thermal units |
| `UnitOfService` | – | End-use services supplied: `DHW`, `SH`, `Cooling`, `rSOC_heat` |
| `StreamsOfUnit` | – | Heat-cascade streams: `h_ht`/`h_mt`/`h_lt` (hot) or `c_ht` (cold) |
| `Units_flowrate_in`, `Units_flowrate_out` | – | Layers the unit consumes from and supplies to |
| `stream_Tin`, `stream_Tout` | °C | Inlet and outlet temperature of each stream, in the order of `StreamsOfUnit` |
| `References` | – | Source of the cost and emission data, as a reStructuredText link |

A unit is only offered to the optimizer when **all** of its `UnitOfLayer` entries
are among the initialized grids. Declaring a `Hydrogen` unit without initializing
the `Hydrogen` layer silently drops the unit — which is the intended behaviour,
and the reason the layer list must be complete before
{func}`~reho.model.infrastructure.initialize_units` is called.

Default values: {ref}`tbl-building-units-csv` and {ref}`tbl-district-units-csv`.

### `building_units_IP.csv`, `district_units_IP.csv` — inter-period storage

Same schema. These technologies are only loaded when `method['interperiod_storage']`
is enabled: their state of charge is chained across typical periods, which makes
seasonal storage representable.

### `development.csv` — technologies under development

Same schema, not loaded by default. Holds formulations that are being validated
(pit thermal energy storage, latent heat storage) and whose `.mod` files live in
`ampl_model/units/development/`. Not part of the supported model.

### `HP_parameters.csv`, `AC_parameters.csv` — part-load performance

Performance maps of heat pumps and air conditioners, read by
{func}`~reho.model.infrastructure.read_performance_map`. Semicolon-separated, indexed by
sink and source temperature: the two index columns are named after the AMPL sets they
fill.

| Column | Unit | Meaning |
|---|---|---|
| `HP_Tsink` / `AC_Tsink` | °C | Sink temperature — what the unit delivers |
| `HP_Tsource` / `AC_Tsource` | °C | Source temperature — what the unit draws from |
| `HP_Eta_nominal` / `AC_Eta_nominal` | – | Second-law efficiency, i.e. the fraction of the Carnot COP achieved |
| `HP_Pmax_nominal` / `AC_Pmax_nominal` | – | Maximum power as a fraction of the nominal size |

The actual source temperature seen by a unit is deduced from its **name**:
`HeatPump_Air` follows the ambient temperature, `HeatPump_Lake` and
`HeatPump_Geothermal` use the constants of
{data}`~reho.model.sub_problem.DEFAULT_HP_SOURCE_TEMPERATURES`, and `HeatPump_DHN`
follows the network temperature. Any other source must be declared through
`parameters['T_source']`.

### `U_values.csv` — thermal envelope per construction period

| Column | Unit | Meaning |
|---|---|---|
| `period` | – | Construction period, matching the `period` field of QBuildings |
| `U_facade`, `U_footprint`, `U_roof`, `U_window` | kW/(m²·K) | U-value of the existing envelope |
| `U_required_facade`, ... | kW/(m²·K) | U-value reached after renovating that element |

:::{admonition} Known data issue
:class: warning

For several construction periods the post-renovation value is *higher* (worse)
than the existing one — the facade for every period up to 2000, and the roof for
1981–2000. Renovating those elements would degrade the envelope.
{func}`~reho.model.preprocessing.renovation.U_h_renovation` currently masks this
by forcing a {data}`~reho.model.preprocessing.renovation.MIN_UH_IMPROVEMENT`
improvement, so a renovation scenario over an affected building stock produces an
improvement that the data does not actually support. The test
`test_data.py::test_renovation_targets_improve_on_the_existing_envelope` documents
the inconsistency as an expected failure; it should be resolved by revising the
reference values.
:::

### `renovation.csv` — renovation costs and embodied emissions

Comma-separated (unlike the other infrastructure files). Indexed by
`year` (construction period, with its own naming — see
{data}`~reho.model.preprocessing.renovation.CONSTRUCTION_PERIOD_TO_RENOVATION_PERIOD`)
and `element` (`facade`, `roof`, `footprint`, `window`).

| Column | Unit | Meaning |
|---|---|---|
| `cost[CHF/m2]` | CHF/m² | Investment cost of renovating one square metre of that element |
| `GWP kg CO2/m2` | kgCO₂/m² | Embodied emissions of the same |

Costs are multiplied by
{data}`~reho.model.preprocessing.renovation.RENOVATION_COST_FACTOR` to reach their
VAT-inclusive, present-day value.

---

## `SIA/` — Swiss building norms

Source of the end-use demand profiles, via
{mod}`~reho.model.preprocessing.sia_parser` and
{mod}`~reho.model.preprocessing.buildings_profiles`.

| File | Content |
|---|---|
| `sia2024_data.xlsx` | SIA 2024 norm: for each room type, the occupancy, appliance, lighting and domestic-hot-water profiles, and their yearly totals. Three sheets are read: `profiles`, `calculs`, `data`. |
| `sia2024_rooms_sia380_1.csv` | Share of each SIA 2024 room type in each SIA 380/1 building affectation. Rows are room types, columns are affectations, cells are area shares summing to 1 per column. |
| `b_value_floor.csv` | Reduction factor *b* applied to the floor heat loss, as a function of the footprint U-value (rows) and of the building's compactness (columns). |

A building's demand profile is therefore the composition of three things: its
affectation class (which room mix), the SIA 2024 norm (which profile per room),
and its own yearly energy signature read from QBuildings (which magnitude).

---

## `skydome/` — sky discretization for the oriented PV model

Used when `method['use_pv_orientation']` is enabled, to compute the irradiance
received by an arbitrarily oriented surface.

| File | Content |
|---|---|
| `skydome.csv` | The 145 sky patches: area, cartesian coordinates, azimuth and elevation, and the pre-computed sines and cosines the AMPL model needs. |
| `skyPatchesAreas.csv` | Area of each patch [mm²], in patch order. |
| `skyPatchesCenPts.csv` | Cartesian coordinates of each patch centre. |
| `normalized_irradiance.csv` | Normalized irradiance of each patch, per hour of the year. |
| `total_irradiation.csv` | Absolute irradiance of each patch, per hour of the year [W/m²]. One column per patch, plus `time`. |

---

## `mobility/` — travel demand and vehicle availability

| File | Content |
|---|---|
| `dailyprofiles.csv` | Hourly profiles, one column per `<quantity><daytype>_<variant>` combination: travel demand, electric-vehicle plug-in and plug-out availability, and activity shares. |
| `dailyprofiles_metadata.csv` | Label, description and source of every column of the above. **The place to look when a profile name is unclear.** |

Day types are `wdy` (weekday) and `wnd` (weekend); the `_def` variant is the
default used when no profile exists for a specific travel distance. See
{ref}`tbl-dailyprofiles` for the full metadata table.

---

## `elcom/` — electricity price lookup

`correspondance_table_municipality_operator.csv` maps each Swiss municipality
(`id_city`, `commune`) to its distribution system operator (`id_operator`,
`operator`). {mod}`~reho.model.preprocessing.electricity_prices` uses it to query
the [ELCOM](https://www.strompreis.elcom.admin.ch/) API for the retail and
injection tariffs that apply to a given case study.

---

## `actor/` — socio-economic data of the actors model

| File | Content |
|---|---|
| `income_percentile.csv` | Swiss income distribution: cumulative share of the population and the corresponding annual income [CHF/y]. |
| `rent_proportion.csv` | Share of a household's budget spent on rent, energy and mobility, per income bracket [CHF/month]. Used to derive the maximum rent a tenant can afford. |

---

## `QBuildings/` — database connection profiles

`Geneva.ini` and `Suisse.ini` hold the host, port, database name and read-only
credentials of the [QBuildings](https://qbuildings.epfl.ch/) instances. They are
consumed by
{meth}`QBuildingsReader.establish_connection <reho.model.preprocessing.QBuildings.QBuildingsReader.establish_connection>`.
No personal credential is involved: the accounts are public and read-only.

---

(using-your-own-data)=
## Using your own data

Every reference file can be replaced without touching the package. The two most
common cases:

```python
from reho import initialize_grids, initialize_units

# Custom technology catalogue and energy layers
grids = initialize_grids({'Electricity': {}, 'NaturalGas': {}}, file="my_layers.csv")
units = initialize_units(scenario, grids,
                         building_data="my_building_units.csv",
                         district_data="my_district_units.csv")
```

Keep the column names of the default files: they are the contract between the CSV
and {func}`~reho.model.infrastructure.prepare_units_df`. The unit *names* are free,
but `UnitOfType` must be one of the modelled families, otherwise the technology has
no equations attached to it and is silently ignored.

Tariffs can also be overridden per layer without any file:

```python
grids = initialize_grids({'Electricity': {'Cost_supply_cst': 0.28,
                                          'Cost_demand_cst': 0.12},
                          'NaturalGas': {'Cost_supply_cst': 0.16}})
```

To check a custom catalogue before running a full optimization, point the data
test-suite at it:

```bash
pytest reho/test/test_data.py -q
```
