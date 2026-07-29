# Getting started

::::{grid} 1 2 2 2
:gutter: 4

:::{grid-item-card} Part-Time User? 😎
:class-card: install-card
:columns: 12 12 6 6
:padding: 3

REHO is available as a [PyPI package](https://pypi.org/project/REHO/) and can be installed via pip with:

+++

```bash
pip install --extra-index-url https://pypi.ampl.com REHO
```
:::

:::{grid-item-card} Talented Developer? 🏄
:class-card: install-card
:columns: 12 12 6 6
:padding: 3

Full code can be accessed from the [REHO repository](https://github.com/IPESE/REHO) and project cloned using the command:

+++

```bash
git clone https://github.com/IPESE/REHO.git
```
:::
::::

## Prerequisites

### Python 3

You will need [Python3](https://www.python.org/downloads/). REHO is compatible with Python 3.9 and above.

As IDE we recommend to use [PyCharm](https://www.jetbrains.com/pycharm/), but [Visual Studio Code](https://code.visualstudio.com/) (VS Code) is also a good choice.


### AMPL

#### AMPL syntax

For most convenient use, we recommend using a text editor that supports AMPL syntax highlighting. As PyCharm does not currently provide an extension for AMPL syntax, we suggest using a different editor for AMPL files such as [Sublime Text](https://www.sublimetext.com/), with its [AMPL Highlighting package](https://github.com/JackDunnNZ/sublime-ampl). VS Code in turn features several extensions for AMPL.

For a quick introduction to AMPL syntax, please refer to [AMPL Resources - Quick introduction](https://dev.ampl.com/ampl/introduction.html).

#### AMPL install and license

As REHO is based on AMPL, it requires AMPL to be installed with a license. There are two main options:

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} Option 1: AMPL for Python
:padding: 3

AMPL developed `amplpy`, its python wrapper. In REHO, it is installed by default. A user only has to provide a license.

You can use the free [AMPL Community Edition](https://ampl.com/ce/). This AMPL license is full-sized and full-featured for personal, academic, and commercial-prototyping use. Since 2023, there are no more restrictions on the number of variables or constraints one can use. This Community Edition operates on a cloud license, requiring an internet connection to function.

+++

Follow the installation steps in AMPL website to request your license. Once you have it, it must be activated in your project terminal:

```bash
python -m amplpy.modules activate <license-uuid>
```
:::

:::{grid-item-card} Option 2: Install AMPL on your computer
:padding: 3

You already have an AMPL license (standard or custom license for research, teaching, business, consultant), you have installed AMPL and you know the path of your installation.

+++

You need to provide the path to your license file in a `.env` file located at the root of your project, and containing the following line:

```bash
AMPL_PATH="path_to_your_license"
```
:::
::::

:::{note}
You do not strictly need to install AMPL on your machine, as AMPL modules will be automatically installed in your environment with REHO. However, you will need to either activate your cloud license or provide your local license path. Come back to this section after you have installed REHO, either from PyPI or from source, to set up your license accordingly.

Additional information and support can be found in the `amplpy` library documentation ([AMPL Python API](https://amplpy.ampl.com/en/latest/)).
:::


:::{warning} Running code from VS Code or Terminal
Running scripts from VS Code or from a standalone terminal may lead to path issues, either when importing the REHO module or when providing the path to `.env`.
Please refer to the issue raised in [REHO/Issues/Relative Path in VS Code](https://github.com/IPESE/REHO/issues/13).
:::



#### Solver

REHO requires at least one linear programming solver.

The requirements already specify the installation of the [HiGHS](https://highs.dev/) solver, which is chosen by default when performing an optimization.

However, you have the possibility to install other open-source or licensed solvers, and specify them in the `REHO(solver="...")` class constructor. The [Gurobi](https://www.gurobi.com/) solver works particularly well with REHO, with a calculation time reduced by a factor of 3 compared to HiGHS.
Is it available with an academic license. If you are using *AMPL for Python* and want to use Gurobi, please do in the project terminal:

```bash
python -m amplpy.modules install gurobi
```

Please refer to [AMPL Modules for Python](https://dev.ampl.com/ampl/python/modules.html) page further insights about AMPL solvers available.


### PostgreSQL

For large-scale applications, REHO can be connected to relational database management systems. The [QBuildings database](https://qbuildings.epfl.ch/) used as a reference for the input to REHO is built with PostgreSQL.

More specifically, the [psycopg2](https://pypi.org/project/psycopg2/) library is used to connect to the database and execute queries in Python. This library is already included in the REHO requirements but is known to cause some issues, as some prerequisites are frequently missing (i.e. the PostgreSQL package and Python development tools).

:::{note}
For Windows users, the binary wheel `psycopg2-binary` is already specified in REHO requirements so this should no longer be an issue.
:::

For Linux and Mac users, 2 options are suggested:

**Option 1: Install the wheel `psycopg2-binary` instead**

```bash
pip install psycopg2-binary
```

**Option 2: Install prerequisites for `psycopg2` from source**

::::{grid} 1 2 2 2
:gutter: 4

:::{grid-item-card} Linux users
:class-card: install-card
:columns: 12 12 6 6
:padding: 3

```bash
sudo apt install python3-dev libpq-dev
```
:::

:::{grid-item-card} Mac users
:class-card: install-card
:columns: 12 12 6 6
:padding: 3

```bash
brew install postgresql
```
:::
::::

You may refer to the discussion [How to install psycopg2 with "pip" on Python?](https://stackoverflow.com/questions/5420789/how-to-install-psycopg2-with-pip-on-python/5450183#5450183) for additional support.


## Installation

### From PyPI

#### Command

Select the project root containing a Python environment and install the latest stable release of REHO with:

```bash
pip install --extra-index-url https://pypi.ampl.com REHO
```

#### Checking proper installation

Entry points allow to verify the proper installation of REHO:

```bash
reho-test-import
```

```bash
reho-test-run
```

If your installation is correct, you should:

- See the results of the optimizations in the terminal.
- See files appear in the newly created subfolders `data/clustering/` and `results/` and `figures/`.
- Have an overview of a Sankey diagram in your web browser.

```bash
reho-download-examples
```

This command will download files from the `scripts/examples/` folder from the [repository](https://github.com/IPESE/REHO/tree/main/scripts/examples), and copy them locally in the working directory.

Finally, the folder `reho/test/` contains several scripts written with pytest, allowing to check for REHO functionalities.

### From source

#### Command

Select your project directory and clone the REHO repository with:

```bash
git clone https://github.com/IPESE/REHO.git
```

:::{warning}
The REHO repository can be forked or cloned depending on the intended use. If you simply clone the repository do not forget to check out your own branch from the `main`.
:::

#### Requirements

Please include a `venv` at the project root folder and install dependencies with:

```bash
pip install -r requirements.txt
```


#### Checking proper installation

Run any of the files in `reho/test/` or `scripts/examples/` folders.

If your installation is correct, each run should end with *"Process finished with exit code 0"*.
Some scripts will also render some results in your web browser and open different tabs showing the outcome of your optimization.

:::{warning}
In `scripts/examples/`, the solver is always explicitly set to Gurobi to reduce calculation time. But you can simply remove the `REHO(solver="gurobi")` argument and the open-source solver HiGHS will be used by default instead.
:::


#### Git tracking

You will also see some files appear in some newly created subfolders such as `data/clustering/`, `results/` and `figures/`. These are not git-tracked. But all the other Python files in `scripts/examples/` are git-tracked.

You should then be careful to not modify the content of these files.

However, for your future work and own case-studies with REHO, you can create any additional subfolders in `scripts/`. These will be ignored by the git versioning.


## Running REHO

The following paragraphs describe the content of `reho/test/test_run.py` and `reho/test/test_plot.py`. These latter should allow you to get started with the tool and conduct your first optimizations.

```{literalinclude} ../../reho/test/test_run.py
:language: python
```

```{literalinclude} ../../reho/test/test_plot.py
:language: python
```

### Set building parameters

Each building needs to be characterized to estimate its energy demand, its renewable potential, and its sector coupling potential.
Such information about the buildings involved in the analysis can be provided to REHO in two different ways:

1. By connecting to the [QBuildings database](https://qbuildings.epfl.ch/);
2. By reading CSV files.

#### QBuildings

QBuildings is a GIS database for the characterization of the Swiss building stock from an energy point of view (end-use demand, buildings morphology, endogenous resources).
It is built by gathering different public databases and combining them with SIA norms.
It was initiated and developed by EPFL (Switzerland), within the Industrial Process and Energy Systems Engineering (IPESE) group.

REHO can connect to QBuildings and read the data it contains with the following code:

```python
reader = QBuildingsReader()                             # load QBuildingsReader class
reader.establish_connection('Geneva')                   # connect to QBuildings database
qbuildings_data = reader.read_db({'egid': 1009515})      # read data, filtered by {layer: value}
```

See {meth}`reho.model.preprocessing.QBuildings.QBuildingsReader.read_db` for further description.


#### CSV files

The buildings information can also be provided through a CSV file, with the call:

```python
reader = QBuildingsReader()
qbuildings_data = reader.read_csv(buildings_filename='data/buildings.csv', nb_buildings=2)
```

See {meth}`reho.model.preprocessing.QBuildings.QBuildingsReader.read_csv` for further description.

:::{warning}
To work properly, the .csv given should contain the same fields as the ones defined in QBuildings.

The order does not matter. It can be helpful to explore the files `scripts/examples/data/buildings.csv`,
`scripts/examples/data/roofs.csv` and `scripts/examples/data/facades.csv`.
:::

#### Buildings input data

:::{dropdown} List of buildings parameters
:icon: list-unordered

(tbl-csv-buildings)=
**Table of mandatory buildings parameters**

| Parameters | Description | Example |
|:--|:--|:--|
| id_class | Building's class, from {ref}`tbl-sia380`. If several, separate them with `/` | I/II/I |
| ratio | Share of the ERA attributed to each id_class. If one class should be 1, else should follow the order of the id_class | 0.4/0.25/0.35 |
| status | From SIA2024, characterize the electricity consumption in REHO. Put 'standard' by default. | standard |
| area_era_m2 | Energetic Reference Area | 279.4 |
| area_facade_m2 | Area of vertical facades | 348 |
| area_roof_solar_m2 | Roof area suitable for solar panels installation. See [Sonnendach](https://www.bfe.admin.ch/bfe/en/home/supply/statistics-and-geodata/geoinformation/geodata/solar-energy/suitability-of-roofs-for-use-of-solar-energy.html) | 148.3 |
| height_m | Height up to the last ceiling. Use to determine shadowing in *use_facades*. | 12.83 |
| thermal_transmittance_signature_kW_m2_K | Averaged conductance | 0.00202 |
| thermal_specific_capacity_Wh_m2_K | Thermal inertia | 119.4 |
| temperature_interior_C | Target temperature to reach | 20.0 |
| temperature_cooling_supply_C | | 12.0 |
| temperature_cooling_return_C | | 17.0 |
| temperature_heating_supply_C | | 65.0 |
| temperature_heating_return_C | | 50.0 |
:::

:::{dropdown} List of roofs parameters
:icon: list-unordered

(tbl-csv-roofs)=
**Table of mandatory roofs parameters**

| Parameters | Description | Example |
|:--|:--|:--|
| tilt | Inclination of the roof, in degree | 30 |
| azimuth | Orientation of the roof, in degree | 12 |
| id_roof | Unique identifier | 1 |
| area_roof_solar_m2 | Surface suitable for solar panels | 210.3 |
| id_building | Use to identify to which building the roof belongs | 10 |
:::

:::{dropdown} List of facades parameters
:icon: list-unordered

(tbl-csv-facades)=
**Table of mandatory facades parameters**

| Parameters | Description | Example |
|:--|:--|:--|
| azimuth | Orientation of the facade, in degree | 12 |
| id_facade | Unique identifier | 1 |
| area_facade_solar_m2 | Surface suitable for solar panels | 145.6 |
| id_building | Use to identify to which building the facade belongs | 10 |
| cx | Coordinate x of the facade centroid | 2592822.33 |
| cy | Coordinate y of the facade centroid | 2592809.46 |
| geometry | Geometry of the facade, useful if centroid is not available. Should be in *wkb* or *wkt* format. | `MULTILINESTRING ((2592822 1120151, 2592809 1120182))` |
:::

### Select weather data

Based on the building's coordinates, REHO automatically connects to the PVGIS database (using the [pvlib](https://pvlib-python.readthedocs.io/en/stable/) library) to extract annual weather data.

Yearly weather data is then clustered into typical days. The `cluster` dictionary contains the clustering specifications:

```python
cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}
```

Where:

- `'Location'` will be the name of the directory where clustering files are written.
- `'Attributes'` indicates the features among which the clustering is applied (T refers to Temperature, I to Irradiance, and W to Weekday).
- `'Periods'` relates to the desired number of typical periods.
- `'PeriodDuration'` is the typical period duration (24h is the default choice, corresponding to a typical day).

:::{note}
`scripts/examples/3f_Custom_profiles.py` shows how to provide custom weather data.
:::

### Set scenario

#### Objective function

REHO offers single or multi-objective optimization. The objective function can be specified in the `scenario` dictionary:

```python
scenario['Objective'] = 'TOTEX'     # select an objective function as defined in ampl_model/scenario.mod
```

```python
scenario['Objective'] = ['OPEX', 'CAPEX']   # for multi-objective optimization two objectives need to be specified
```

This `scenario` dictionary can also be used to specify epsilon constraints (`EMOO`) or additional constraints (`specific`).

#### Epsilon constraints

The key `EMOO` allows to add an epsilon constraint on some objective:

```python
scenario['EMOO'] = {EMOO_opex: 16}     # select an epsilon constraint as defined in ampl_model/scenario.mod
```

This is used to limit another objective when performing multi-objective optimization.
In this example, the maximal allowed OPEX value is set to 16 [CHF/m2/y].
You can find a list of possible epsilon constraints in `scenario.mod`.

#### Specific constraints

In `scenario` the key `specific` allows to provide a list of specific constraints that can be activated:

```python
scenario['specific'] = ["enforce_PV_max"]      # enforce the entire roof surface to be covered with PV panels
```

#### Pareto curves

To generate a Pareto front, 2 objective functions need to be specified:

```python
scenario['Objective'] = ['OPEX', 'CAPEX']  # for multi-objective optimization two objectives are needed
```

The number of intermediate points for each objective is specified with:

```python
scenario['nPareto'] = 2  # number of points per objective
```

The total number of optimizations will be `2 + 2 * nPareto` (2 extreme points plus 2 times a discretized interval of `nPareto` points.

:::{note}
Examples `1b_building-scale_Pareto.py` and `2b_district-scale_Pareto.py` can be run to obtain an OPEX-CAPEX Pareto front, at building-scale or district-scale respectively.
:::


### Initialize available units and grids

Initializing the energy system structure is done with the {class}`reho.model.infrastructure.infrastructure` class.

Default values for units and grids are proposed, but any parameters can be adapted through providing customized .csv files.

#### Grids

Grids are initialized with:

```python
grids = infrastructure.initialize_grids(file="reho/data/infratructure/layers.csv")
```

Where the file `layers.csv` contains the default parameters for the different energy layers available.

To use custom prices, there are two options:

1. Provide another .csv file to the `initialize_grids()` function:

```python
grids = infrastructure.initialize_grids(file="my_custom_layers.csv")
```

2. Use the `Cost_supply_cst` and `Cost_demand_cst` parameters in the `initialize_grids()` function:

```python
grids = infrastructure.initialize_grids({
    'Electricity': {'Cost_supply_cst': 0.30, 'Cost_demand_cst': 0.18},
    'Oil': {'Cost_supply_cst': 0.16}
})
```

In this example, new supply and demand costs for electricity, and a new supply cost oil are specified.

For further explanation, see {func}`reho.model.infrastructure.initialize_grids`.

#### Units

Units are initialized with:

```python
scenario['exclude_units'] = ['ThermalSolar']
scenario['enforce_units'] = ['HeatPump_Air']
units = infrastructure.initialize_units(scenario, grids, building_data="reho/data/infratructure/building_units.csv")
```

Where:

- `scenario['exclude_units']` is a list containing the units excluded from the available technologies.
- `scenario['enforce_units']` is a list containing the units forced to be installed.
    - The unit name has to match the *Unit* column of `building_units.csv`.
    - If you do not want to exclude or enforce any unit, give empty lists.
- `grids` is the dictionary formerly returned by `initialize_grids()`.
- `building_units.csv` contains the default specifications for units (cost, carbon footprint...).

District units can be enabled with the argument `district_data`:

```python
units = infrastructure.initialize_units(scenario, grids, building_data, district_data="district_units.csv")
```

Here `district_units.csv` contains the default parameters for district-size units.

### Set method options

You can use different methodology options in REHO, specified in the `method` dictionary.
The methods available are listed in {ref}`tbl-methods`.

(tbl-methods)=
```{csv-table} List of the available methods in REHO
:file: ../data/methods.csv
:header-rows: 1
:delim: ;
:class: longtable
```

#### Optimization scope

The value of REHO is to offer optimization of a specified territory at building-scale or district-scale.

Conduct a building-scale optimization, by setting:

```python
method = {'building-scale': True}
```


Conduct a district-scale optimization, by setting:

```python
method = {'district-scale': True}
```


#### PV orientation and PV on facades

These lines of code will enable PV orientation and PV on facades:

```python
reader = QBuildingsReader(load_roofs=True, load_facades=True)
reader.establish_connection('Suisse')
qbuildings_data = reader.read_db({'transformers': 3658}, nb_buildings=2)
method = {'use_pv_orientation': True, 'use_facades': True, 'district-scale': True}
```


:::{warning}
As the roofs and facades data are required, `load_roofs` and `load_facades` have been set to `True` in the reader a priori.
:::


### Run optimization

The `reho` instance is initialized with:

```python
reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="highs")
```

One or several optimization(s) can then be conducted:

```python
reho.single_optimization()
```

```python
reho.generate_pareto_curve()
```


### Save results

At the end of the optimization process, the results are written in `reho.results`, a dictionary indexed on `Scn_ID` and `Pareto_ID`.

These results can be saved as a `.pickle` or `.xlsx` file with:

```python
reho.save_results(format=['pickle', 'xlsx'], filename='test_results')
```


### Read results

Saved results can be accessed with:

```python
results = pd.read_pickle('test_results.pickle')
```

And browsing through `Scn_ID` and `Pareto_ID` with:

```python
Scn_ID = list(results.keys())
Pareto_ID = list(results[Scn_ID[0]].keys())
df_Results = results[Scn_ID[0]][Pareto_ID[0]]
```

Where `df_Results` corresponds to the output of one single-optimization, and is a dictionary containing the following dataframes: `df_Performance`, `df_Annuals`, `df_Buildings`, `df_Unit`, `df_Unit_t`, `df_Grid_t`, `df_Buildings_t`, `df_Time`, `df_Weather`, `df_Index`, `df_KPIs`, `df_Economics`.

Refer to {mod}`reho.model.postprocessing.write_results` for more information about the content of these dataframes.

### Plot results

REHO embeds predefined plotting functions to visualize results, such as:

```python
# Performance plot : Costs and Global Warming Potential
plotting.plot_performance(results, plot='costs', indexed_on='Scn_ID', filename="figures/performance_costs").show()
plotting.plot_performance(results, plot='gwp', indexed_on='Scn_ID', filename="figures/performance_gwp").show()

# Sankey diagram
plotting.plot_sankey(results['totex'][0], label='EN_long', color='ColorPastel').show()
```

Refer to {mod}`reho.plotting.plotting` for more details and other plotting functions.
