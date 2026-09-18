# Output

An optimization fills `reho.results`, a nested dictionary of pandas DataFrames:

```python
reho.results[scenario_name][pareto_id][dataframe_name]
```

- `scenario_name` is `scenario['name']`;
- `pareto_id` is `0` for a {meth}`~reho.model.reho.REHO.single_optimization`, and
  `1 … 2·nPareto+2` along a Pareto front, sorted by decreasing operating cost;
- `dataframe_name` is one of the `df_*` keys documented below.

```python
results = reho.results['totex'][0]
results['df_Unit']                      # what was installed, and at which capacity
results['df_Annuals']                   # yearly energy balance per layer
results['df_KPIs'].loc['Network']       # aggregated performance indicators
```

Which DataFrames are present depends on the `method` options — each section below
says when a frame is produced — and on the formulation: a district-scale run adds
the decomposition-specific frames of the master problem.

:::{admonition} Units convention
:class: note

Power in **kW**, energy in **kWh** unless the column name says `MWh`, costs in
**CHF/y** (investments are annualized, see `ANN_factor`), emissions in
**kgCO₂-eq/y**, temperatures in **°C**.
:::

---

## Design and performance

### `df_Performance`

The economic and environmental bottom line. Indexed by `Hub`: one row per building,
plus a `Network` row holding the district totals.

| Column | Unit | Meaning |
|---|---|---|
| `Costs_op` | CHF/y | Operating cost: energy bought minus energy sold |
| `Costs_inv` | CHF/y | **Annualized** investment cost of the units |
| `Costs_rep` | CHF/y | Annualized replacement cost of units whose lifetime is shorter than the horizon |
| `Costs_ins` | CHF/y | Annualized renovation cost (only with `method['renovation']`) |
| `Costs_grid_connection` | CHF/y | Fixed cost of the connections to the energy layers |
| `Costs_ft` | CHF/y | Thermal-comfort penalty. Should stay near zero; a large value means the system cannot hold the set-point temperature |
| `GWP_op` | kgCO₂/y | Operating emissions |
| `GWP_constr` | kgCO₂/y | Annualized embodied emissions of the units |
| `ANN_factor` | – | Annualization factor τ of the units, from their lifetime and the interest rate |
| `ANN_factor_ins` | – | Annualization factor of the renovation investment (longer horizon) |
| `EMOO_CAPEX`, `EMOO_OPEX`, `EMOO_TOTEX`, `EMOO_GWP`, `EMOO_grid` | mixed | Value of the epsilon constraints that were active |
| `Objective` | mixed | Value of the objective function, excluding the comfort penalty |

**CAPEX** = `Costs_inv` + `Costs_rep`; **OPEX** = `Costs_op` + `Costs_grid_connection`;
**TOTEX** = CAPEX + OPEX. All are already annualized, so they can be summed directly.

### `df_Unit`

One row per unit, whether installed or not. Indexed by `Unit`
(`<unit>_<building>` at the building scale, `<unit>_district` at the district scale).

| Column | Unit | Meaning |
|---|---|---|
| `Units_Use` | 0/1 | Whether the unit is installed |
| `Units_Mult` | `ref_unit` | Installed capacity, in the unit's own reference unit (kWth, kWh, m², ...) |
| `Costs_Unit_inv` | CHF/y | Annualized investment cost of that unit |
| `Costs_Unit_rep` | CHF/y | Annualized replacement cost |
| `GWP_Unit_constr` | kgCO₂/y | Annualized embodied emissions. Multiply by `lifetime` for the total |
| `lifetime` | y | Technical lifetime |
| `Units_Ext` | `ref_unit` | Pre-existing capacity that did not have to be bought |

### `df_Grid`

Capacity and reinforcement of the connection lines, indexed by `Hub` and `Layer`.

| Column | Unit | Meaning |
|---|---|---|
| `Capacity` | kW | Line capacity after reinforcement |
| `UseCapacity` | 0/1 | Whether the line was reinforced |
| `ReinforcementCost` | CHF | Investment cost of the reinforcement |
| `ReinforcementGWP` | kgCO₂ | Embodied emissions of the reinforcement |

### `df_Annuals`

Yearly energy balance, indexed by `Layer` and `Hub`. The `Hub` level mixes
buildings, units and the special value `Network`, which makes it the quickest way
to answer "how much electricity did the district import".

| Column | Unit | Meaning |
|---|---|---|
| `Demand_MWh` | MWh/y | Energy consumed from that layer |
| `Supply_MWh` | MWh/y | Energy supplied to that layer |

Beyond the energy carriers, the `Layer` level also carries the end-use services
(`SH`, `DHW`, `Cooling`) and the free gains (`HeatGains`, `SolarGains`), so the
demand side of the building can be read from the same frame.

### `df_Buildings`

The buildings' characteristics as they entered the optimization: `ERA`, `U_h`,
`SolarRoofArea`, `period`, `id_class`, the energy signatures, etc. — that is, the
`buildings_data` dictionary as a DataFrame, indexed by `Hub`. With
`method['renovation']`, `U_h` holds the *post-renovation* value chosen by the model.

---

## Time-resolved results

All time-resolved frames are indexed by `Period` and `Time`: `Period` runs over the
typical periods of the clustering plus two extreme periods (coldest and warmest
hour of the year, one timestep each), and `Time` over the timesteps of a period.
`df_Time` and `df_Index` map them back to the calendar year.

### `df_Time`

Indexed by `Period`.

| Column | Unit | Meaning |
|---|---|---|
| `dp` | d | How many days of the year that typical period stands for. **Use it to weight any profile before summing it to a yearly value** |
| `TimeEnd` | – | Number of timesteps in the period |
| `dt` | h | Duration of one timestep |

```python
# Yearly total from an hourly profile
profile = results['df_Unit_t'].xs(('Electricity', 'PV_Building1'), level=('Layer', 'Unit'))
yearly_kWh = profile['Units_supply'].groupby('Period').sum().mul(results['df_Time'].dp).sum()
```

### `df_Index`

Indexed by `HourOfYear` (1…8760), with `PeriodOfYear` giving the typical period that
represents that hour. Produced when `method['save_data_input']` is enabled.

### `df_Weather`

`T_ext` [°C] and `Irr` [W/m²] for each timestep. Produced when
`method['save_data_input']` is enabled.

### `df_Unit_t`

Operation of every unit, indexed by `Layer`, `Unit`, `Period`, `Time`.

| Column | Unit | Meaning |
|---|---|---|
| `Units_demand` | kW | Power drawn from the layer |
| `Units_supply` | kW | Power delivered to the layer |
| `Units_curtailment` | kW | Power available but not used (typically PV) |
| `BAT_E_stored` | kWh | Battery state of charge |
| `EV_E_stored`, `EV_supply_travel`, `EV_demand_ext` | kWh, kW | Electric-vehicle state of charge, travel consumption, charging in another district |

With `method['save_timeseries'] = False`, only PV, battery and cogeneration rows are
kept, which keeps large studies manageable.

### `df_Grid_t`

Exchanges with the energy layers, indexed by `Layer`, `Hub`, `Period`, `Time`.
The `Hub` level holds one entry per building plus `Network`.

| Column | Unit | Meaning |
|---|---|---|
| `Grid_demand` | kW | Power exported to the layer |
| `Grid_supply` | kW | Power imported from the layer |
| `Cost_supply`, `Cost_demand` | CHF/kWh | Tariffs actually applied at that timestep |
| `GWP_supply`, `GWP_demand` | kgCO₂/kWh | Emission factors applied at that timestep |
| `Uncontrollable_load` | kW | Domestic electricity demand, which the model cannot shift |

### `df_Buildings_t`

State of each building, indexed by `Hub`, `Period`, `Time`.

| Column | Unit | Meaning |
|---|---|---|
| `Domestic_electricity` | kW | Electricity demand of appliances and lighting |
| `House_Q_DHW` | kW | Domestic hot water demand |
| `House_Q_heating`, `House_Q_cooling` | kW | Space heating and cooling delivered |
| `T_in` | °C | Indoor temperature |
| `Th_supply`, `Th_return` | °C | Supply and return temperature of the heating circuit |
| `Tc_supply`, `Tc_return` | °C | Same for the cooling circuit |
| `HeatGains` | kW | Internal gains from occupants and appliances |
| `SolarGains` | kW | Solar gains through the windows |

### `df_Streams_t`

Heat-cascade streams, indexed by `Stream`, `Service`, `Unit`, `Period`, `Time`.
Produced when `method['save_streams']` is enabled.

| Column | Unit | Meaning |
|---|---|---|
| `Streams_Q` | kW | Heat load of the stream |
| `Streams_Tin`, `Streams_Tout` | °C | Inlet and outlet temperature |
| `Streams_Mcp_kW/K` | kW/K | Heat-capacity flow rate |
| `dTmin` | K | Minimum approach temperature contribution |

This is the frame the pinch analysis and the composite curves are built from
({func}`~reho.plotting.plotting.plot_composite_curve`), and the one exported to
OSMOSE by {func}`~reho.model.postprocessing.osmose.get_osmose_streams`.

### `df_Interperiod`

State of charge of the seasonal storage units, indexed by unit and hour of the year
(not by typical period: that is the point of inter-period storage). Produced when
`method['interperiod_storage']` is enabled.

One column per storage variable that is not zero everywhere: `BAT_E_stored_IP` for the
batteries, `H2_stor_stored`, `CH4_stor_stored` and `CO2_stor_stored` for the gases, and
`PTES_E_Stored` for the pumped thermal storage.

Three more rows, indexed by `('storage info', ...)`, describe the gas storages and are
zero for the other technologies:

| Row | Unit | Meaning |
|---|---|---|
| `Volume` | m³ | Volume of the first storage unit of the gas |
| `Pressure` | bar | Pressure of the gas in that unit |
| `Compressibility factor` | - | Compressibility factor of the gas at that pressure |

---

## Key performance indicators

### `df_KPIs`

Indexed by `Hub`, with a `Network` row. Computed by
{func}`~reho.model.postprocessing.KPIs.calculate_KPIs`.

| Column | Unit | Meaning |
|---|---|---|
| `opex_m2` | CHF/m²/y | Operating cost per unit of energy reference area (ERA) |
| `capex_m2` | CHF/m²/y | Annualized investment cost per unit of ERA |
| `cost_rep_m2` | CHF/m²/y | Annualized replacement cost per unit of ERA |
| `cost_ft_m2` | CHF/m²/y | Thermal-comfort penalty per unit of ERA |
| `AR` | CHF/m²/y | Annual value of the electricity produced on site: export revenues plus the purchases avoided by self-consumption |
| `LCoE1`, `LCoE2` | CHF/kWh | Levelized cost of the locally produced electricity, with and without the grid supply |
| `SC` | – | Self-consumption: share of the locally produced electricity consumed on site |
| `SS` | – | Self-sufficiency: share of the electricity demand covered by local production |
| `PVP` | – | PV penetration: local PV production relative to the electricity demand |
| `PVC` | – | PV curtailment: share of the PV potential that could not be used |
| `GMs`, `GMd` | – | Grid multiple in supply and demand: peak over average exchange within a period |
| `GUs`, `GUd` | – | Grid utilization: peak exchange relative to the district's peak uncontrollable load |
| `gwp_op_m2`, `gwp_constr_m2`, `gwp_tot_m2` | kgCO₂/m²/y | Operating, embodied and total emissions per unit of ERA |
| `COP` | – | Annual coefficient of performance of the building's heat pumps together, and of all the heat pumps on the `Network` row |
| `PIR` | – | Profit-to-investment ratio of the owners (actors formulation only) |
| `Rent_Budget_Ratio` | – | Expense of the renters over their maximum expense (actors formulation only) |

`GMs`/`GMd` measure how *peaky* the exchange profile is, and `GUs`/`GUd` how large
the peak is relative to what the grid already has to carry: a value above 1 means
the energy system makes the connection's job harder than the buildings' own
uncontrollable demand does.

### `df_Economics`

Costs and emissions broken down by item, feeding
{func}`~reho.plotting.plotting.plot_performance` and
{func}`~reho.plotting.plotting.plot_expenses`. Rows are indexed by `Perf_type`
(`costs` / `impact`) and `Hub`; columns are grouped by `Category`: `operation`
(imports, exports and curtailment of each layer, and the costs avoided by local
electricity) and `investment` (annualized investment and replacement costs, and
embodied emissions, of each unit). See
{func}`~reho.model.postprocessing.KPIs.build_df_Economics`.

### `df_Metadata`

Provenance of the run: the REHO version, the date, the `scenario`, `method` and
`cluster` dictionaries, and the source and date of the buildings data. Written into
every exported file, so a result can always be traced back to the configuration
that produced it.

### `df_Parameters`

Every parameter passed to AMPL, for debugging: one row per value in column `Value`,
indexed by `Parameter` and `Index` — the position of the value in the parameter, as
comma-separated text, empty for a scalar. With the decomposition, a first index level
`house` tells the building of the sub-problem. Produced when
`method['extract_parameters']` is enabled. It holds tens of thousands of rows per
building — about 70,000 in the examples, with ten typical days — so beyond some fifteen
buildings it no longer fits in an xlsx sheet and is only kept in the pickle format.

---

## District-scale specific frames

These come from the master problem and appear with `method['district-scale']`.
They are mostly of interest when investigating the convergence of the
decomposition — see {doc}`../model/district`.

| Name | Index | Content |
|---|---|---|
| `df_DW` | `FeasibleSolution`, `Hub` | λ: the weight given to each candidate configuration. A value of 1 means the configuration was selected |
| `df_District` | `Hub` | Costs and emissions of each building and of the district (`Network`) |
| `df_District_t` | `Layer`, `Period`, `Time` | Network exchanges at the district level |
| `df_Dual` | `Hub` | μ: dual of the convexity constraint, i.e. the value of one more configuration for that building |
| `df_Dual_t` | `Layer`, `Period`, `Time` | π and π_GWP: the price signals sent back to the sub-problems |
| `df_beta` | objective | β: dual values of the epsilon constraints on the objectives, whose opposites weight those objectives in the next sub-problems |

The actors formulation adds `df_Actors`, `df_Actors_tariff`, `df_Actors_expense`,
`df_Actors_dual` and `Samples` — see {doc}`../model/actors`.

---

## Saving and reloading

```python
reho.save_results(format=['pickle', 'xlsx'], filename='my_run')
```

- **pickle** (`results/my_run.pickle`) stores the whole `results` dictionary and is
  the format to use to keep working in Python.
- **xlsx** (`results/my_run_<scenario><pareto>.xlsx`) writes one sheet per
  DataFrame, for inspection or for sharing with people who do not run Python.
  Rows that are entirely zero are dropped unless `filter=False`.
- `format=['save_all']` pickles the whole `REHO` object, including the inputs and
  the decomposition history. Larger, but reproducible.

```python
import pandas as pd
results = pd.read_pickle('results/my_run.pickle')
results['totex'][0]['df_Performance']
```
