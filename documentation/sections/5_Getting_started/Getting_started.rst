Getting started
++++++++++++++++

Installation
============

REHO package
------------

.. code-block:: bash

   pip install --extra-index-url https://pypi.ampl.com REHO

REHO repository
---------------

Select a directory where you would like to have your files,
open the terminal/cmd in this folder and clone the `REHO repository <https://github.com/IPESE/REHO>`_ using the command:

.. code-block:: bash

   git clone https://github.com/IPESE/REHO.git

Python
------

You will need `Python3 <https://www.python.org/downloads/>`_, just pick the latest version.
As IDE we recommend to use `PyCharm <https://www.jetbrains.com/pycharm/>`_, offering a free full-featured license for students.

AMPL
----

As REHO is based on AMPL, it requires a licence of AMPL and at least one LP solver.

- The `AMPL Community Edition <https://ampl.com/ce/>`_ offers a free, full-powered AMPL license for personal, academic, and commercial-prototyping use.
- Gurobi is the default solver in REHO, but any LP solver is possible.

Plenty of text editors exist which feature AMPL. We recommend using `Sublime Text <https://www.sublimetext.com/>`_, which
provides the `AMPL Highlighting package <https://github.com/JackDunnNZ/sublime-ampl>`_.



Setup environment
----------------------

Important: As soon as everything is cloned, please check out your own branch (from branch master).
Go back to the terminal and run:

.. code-block:: bash

   git checkout -b your_branch_name

1. Open PyCharm, open a project and browse to the folder of the repository REHO. Do not accept the automatic virtual environment creation.
2. Go to File > Settings > Project: REHO to set up your Project Interpreter, click on the gear symbol and choose to add.
3. Add a new virtual environment (venv) and select as base interpreter your python.exe file of your python installation. Confirm with OK.
4. Install required Python packages. Open the Terminal tab (View > Tool Windows > Terminal) and type the command one by one:

.. code-block:: bash

   pip install -r requirements.txt
   pipwin install -r requirements_win.txt

If `geopandas` fails to install, you might need to run:

.. code-block:: bash

   pip install geopandas

5. Choose the file scripts > examples > 3a_Read_csv.py and run the script.
If your installation is correct, you should receive the final message “Process finished with exit code 0”.
Sometimes, when running the model for the first time, you need to explicitly tell PyCharm to connect to the AMPL server by typing ampl in the PyCharm Terminal tab.

6. Create a new folder for your future work with REHO. Right click on the folder scripts in and create a New > Directory. You will use this folder to write and save your first scripts.


Running REHO
============

This section only provides a brief overview of REHO's capabilities, based on a basic script example.
This latter should allow you to get started with the tool and conduct your first optimizations.

.. code-block:: python

    from reho.model.reho import *
    from reho.plotting import plotting

    # Set building parameters
    reader = QBuildingsReader()
    qbuildings_data = reader.read_csv(buildings_filename='buildings_example.csv', nb_buildings=3)

    # Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['EMOO'] = {}
    scenario['specific'] = []
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['ThermalSolar', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Set method options
    method = {'building-scale': True}

    # Run optimization
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['pickle'], filename='totex')

    # Plot energy flows
    plotting.plot_sankey(reho.results['totex'][0], label='EN_long', color='ColorPastel').show()


Set building parameters
---------------------------

Each building needs to be characterised to estimate its energy demand, its renewable potential, and its sector coupling potential.
Such information about the buildings involved in the analysis can be provided to REHO in two ways:

1. By connecting to the `QBuildings database <https://ipese-web.epfl.ch/lepour/qbuildings/index.html>`_ ;
2. Or by reading CSV files.

QBuildings
~~~~~~~~~~~~~~~~~

QBuildings is a GIS database for the characterization of the Swiss building stock from an energy point of view (end-use demand, buildings morphology, endogenous resources).
It is built by gathering different public databases and combining them with SIA norms.
It was initiated and developed by EPFL (Switzerland), within the Industrial Process and Energy Systems Engineering (IPESE) group.

REHO can connect to QBuildings and read the data it contains with the following code:

.. code-block:: python

    reader = QBuildingsReader()             # load QBuildingsReader class
    reader.establish_connection('Suisse')   # connect to QBuildings database
    qbuildings_data = reader.read_db(transformer=3658, nb_buildings=2)      # read data

The two files implied in the process are:

- :code:`data/QBuildings/Suisse.ini` contains the login information to access the database
- :code:`model/preprocessing/QBuildings.py` contains the :code:`QBuildingsReader` class, with functions to access to database and extract specified information

*NB: Note that you need to be connected to EPFL network or VPN to access the database*

CSV files
~~~~~~~~~~~~~~~~~

The buildings information can also be provided through a CSV file, with the call:

.. code-block:: python

    reader = QBuildingsReader()
    qbuildings_data = reader.read_csv(buildings_filename='buildings_example.csv', nb_buildings=2)

The CSV file must be located in the :code:`data/buildings/` folder.


Select weather data
-----------------------

Yearly weather data has to be clustered to typical days. The :code:`cluster` dictionary contains the weather information:

.. code-block:: python

    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

Where:

- 'Location' can be chosen among the files available in :code:`data/weather/hour`
- 'Attributes' indicates the features among which the clustering is applied (I refers to Irradiance, T to Temperature, and W to Weekday)
- 'Periods' relates to desired number of typical days
- 'PeriodDuration' the typical period duration (24h is the default choice, corresponding to a typical day)

Set scenario
-----------------------

Objective function
~~~~~~~~~~~~~~~~~~~

REHO offers single or multi-objective optimization. The objective function can be specified in the :code:`scenario` dictionary:

.. code-block:: python

    scenario['Objective'] = 'TOTEX'     # select an objective function as defined in ampl_model/scenario.mod

.. code-block:: python

    scenario['Objective'] = ['OPEX', 'CAPEX']   # for multi-objective optimization two objectives need to be specified

This :code:`scenario` dictionary can also be used to specify epsilon constraints (:code:`EMOO`) or additional constraints (:code:`specific`).

Epsilon constraints
~~~~~~~~~~~~~~~~~~~

The key :code:`EMOO` allows to add an epsilon constraint on some objective:

.. code-block:: python

    scenario['EMOO'] = {EMOO_opex: 16}     # select an epsilon constraint as defined in ampl_model/scenario.mod

This is used to limit another objective when performing multi-objective optimization.
In this example, the maximal allowed OPEX value is set to 16 [CHF/m2/y].
You can find a list of possible epsilon constraints in :code:`scenario.mod`.

Specific constraints
~~~~~~~~~~~~~~~~~~~~

In :code:`scenario` the key :code:`specific` allows to provide a list of specific constraints that can be activated:

.. code-block:: python

    scenario['specific'] = ["enforce_PV_max"]      # enforce the entire roof surface to be covered with PV panels

Pareto curves
~~~~~~~~~~~~~

:code:`1b_building-scale_Pareto.py` and :code:`2b_district-scale_Pareto.py` show how to obtain an OPEX-CAPEX Pareto front,
at building-scale or district-scale respectively.

.. code-block:: python

    scenario['nPareto'] = 2

The parameter :code:`nPareto` indicates the number of intermediate points for each objective.
The total number of optimizations will be :code:``2 + 2 * nPareto`` (2 extreme points plus 2 times a discretized interval of :code:`nPareto` points.


Initialize available units and grids
-------------------------------------------

Initializing the energy system structure is done with the :code:`infrastructure` class.

Grids
~~~~~

Grids are initialized with:

.. code-block:: python

    grids = infrastructure.initialize_grids(file="grids.csv")


Where the file :code:`grids.csv` located in :code:`preprocessing/parameters/` directory contains the default parameters
for the different energy layers available.

To use custom prices, there are two options:

1. Provide another CSV file to the :code:`initialize_grids()` function:

.. code-block:: python

    grids = infrastructure.initialize_grids(file="custom_grids.csv")

Where :code:`"custom_grids.csv"` has to be located in :code:`preprocessing/parameters/`.

2. Use the :code:`Cost_supply_cst` and :code:`Cost_demand_cst` parameters in the :code:`initialize_grids()` function:

.. code-block:: python

    grids = infrastructure.initialize_grids({
        'Electricity': {'Cost_supply_cst': 0.30, 'Cost_demand_cst': 0.18},
        'Oil': {'Cost_supply_cst': 0.16}
    })

In this example, new supply and demand costs for electricity, and a new supply cost oil are specified.


Units
~~~~~

Units are initialized with:

.. code-block:: python

    scenario['exclude_units'] = ['Battery', 'HeatPump_Geothermal']
    scenario['enforce_units'] = ['HeatPump_Air']
    units = infrastructure.initialize_units(scenario, grids, building_data="building_units.csv")

Where:

- 'exclude_units' is a list containing the units excluded from the available technologies
- 'enforce_units' is a list containing the units forced to be installed
    - You have to use the `UnitOfType` field from the function `infrastructure.return_building_units`
    - If you don't want to exclude or enforce any unit, give empty lists.
- :code:`grids` is the dictionary formerly returned by :code:`initialize_grids()`
- "building_units.csv" located in :code:`preprocessing/parameters/` contains the default parameters for units characteristics (specific cost, LCA indicators...)



District units can be enabled with the boolean argument :code:`district_units`:

.. code-block:: python

    units = infrastructure.initialize_units(scenario, grids, building_data, district_data="district_units.csv", district_units=True)

Here "district_units.csv" contains the default parameters for district-size units.

Set method options
-----------------------

You can use different methodology options in REHO, specified in the :code:`method` dictionary.
The methods available are listed in :ref:`tbl-methods`.

.. table:: List of the available methods in REHO
    :name: tbl-methods

    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | Method name                   | Description                                                                                                                                                                                                                                                                                                                 | Default behavior |                     Reference                    |
    +===============================+=============================================================================================================================================================================================================================================================================================================================+==================+==================================================+
    |                                                                                                                                                                                                          *Solar methods*                                                                                                                                                                                                          |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | use_facades                   | Allows to consider the facades for PV panels installation                                                                                                                                                                                                                                                                   |       False      | :cite:t:`middelhauve2021potential`               |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | use_pv_orientation            | Considers the orientation for the solar potential estimation, including a shadow model from neighbor buildings                                                                                                                                                                                                              |       False      |                                                  |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    |                                                                                                                                                                                                       *Optimization methods*                                                                                                                                                                                                      |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | building-scale                | Optimizes by considering than each building is an independent system                                                                                                                                                                                                                                                        |       False      | :cite:t:`stadlerModelbasedSizingBuilding2019`    |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | district-scale                | Optimizes by allowing exchanges between buildings and the use of district units                                                                                                                                                                                                                                             |       False      | :cite:t:`middelhauveRoleDistrictsRenewable2022`  |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | parallel_computation          | Allows to solve sub-problems in parallel                                                                                                                                                                                                                                                                                    |       True       | :cite:t:`terrierOptimalDesignOperation2021`      |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | switch_off_second_objective   |                                                                                                                                                                                                                                                                                                                             |       False      |                                                  |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    |                                                                                                                                                                                                             *Profiles*                                                                                                                                                                                                            |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | include_stochasticity         | Includes variability among SIA typical consumption profiles                                                                                                                                                                                                                                                                 |       False      | :cite:t:`lacorteDemandAggregationDistrict`       |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | sd_stochasticity              | If include_stochasticity is True, allows to specify a list [sd_consumption, sd_timeshift] to choose the variability in 1-consumption and 2-moment of the consumption                                                                                                                                                        |       None       |                                                  |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | use_dynamic_emission_profiles | Uses hourly values for electricity GWP                                                                                                                                                                                                                                                                                      |       False      |                                                  |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | read_electricity_profiles     | Allows to replace SIA consumption profiles by a given one for electricity                                                                                                                                                                                                                                                   |       False      |                                                  |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    |                                                                                                                                                                                                          *Export options*                                                                                                                                                                                                         |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | include_all_solutions         | For a district-scale optimization, gives the results from the SPs                                                                                                                                                                                                                                                           |       False      |                                                  |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | save_stream_t                 | Adds in the results file the heat cascade streams between units by timesteps                                                                                                                                                                                                                                                |       False      |                                                  |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | save_lca                      | dds in the results file the impact in terms of LCA indicators by units, hubs and energy carriers                                                                                                                                                                                                                            |       False      |                                                  |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | extract_parameters            |                                                                                                                                                                                                                                                                                                                             |       False      |                                                  |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    |                                                                                                                                                                                                              *Others*                                                                                                                                                                                                             |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | actors_cost                   | Changes the MP to solve: instead of considering the district as a single entity to optimize, different stakeholders portfolios are considered where the objective function is the minimization of the costs for one particular actor, while the costs of the other actors are constrained with parameterized epsilon values |       False      |             [Granacher et al., 2024]_            |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | DHN_CO2                       |                                                                                                                                                                                                                                                                                                                             |       False      |                                                  |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+
    | use_Storage_Interperiod       | Allows the usage of long-term storage units                                                                                                                                                                                                                                                                                 |       False      | :cite:t:`mathieuContributionStorageTechnologies` |
    +-------------------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------+--------------------------------------------------+

Optimization scope
~~~~~~~~~~~~~~~~~~~~~~~~

The value of REHO is to offer optimization of a specified territory at building-scale or district-scale.


Conduct a building-scale optimization, by setting:

.. code-block:: python

    method = {'building-scale': True}


Conduct a district-scale optimization, by setting:

.. code-block:: python

    method = {'district-scale': True}


PV orientation and PV on facades
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This line of code will enable PV orientation and PV on facades:

.. code-block:: python

    method = {'use_pv_orientation': True, 'use_facades': False, 'district-scale': True}




Run optimization
-----------------------

Once `reho` instance has been properly initialized as :code:`reho(qbuildings_data, units, grids, cluster, scenario, method, solver)`, optimization can be conducted.

.. code-block:: python

    reho.single_optimization()

.. code-block:: python

    reho.generate_pareto_curve()


Save results
-----------------------

Results are saved in a `reho.results` dictionary and indexed on `Scn_ID` and `Pareto_ID`.
If you want to access a value, you can check here which attribute you have to call in the `df_Results` dataframe.

Assuming that you already have loaded your output file and you would like to know the size of the units which are installed,
a look into the main AMPL file `model.mod` reveals that the variable you need is called `Units_Mult`.
You can then search for the variable in the result class in Python and realize that it is located in the dataframe called `df_Unit`.

Plot energy flows
-----------------------

Plotting directly with `reho.results`

.. code-block:: python

    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long').show()
    plotting.plot_performance(reho.results, plot='gwp', indexed_on='Scn_ID', label='EN_long').show()
    plotting.plot_sankey(reho.results['totex'][0], label='EN_long', color='ColorPastel').show()