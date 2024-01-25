Getting started
+++++++++++++++


Installation
============

REHO repository
---------------

Select a directory where you would like to have your files,
open the terminal/cmd in this folder and clone the `REHO repository <https://github.com/IPESE/REHO>`_ using the command:

.. code-block:: bash

   git clone https://github.com/IPESE/REHO.git


Important: As soon as everything is cloned, please check out your own branch (from branch master).
Go back to the terminal and run:

.. code-block:: bash

   git checkout -b your_branch_name

AMPL
----

As REHO is based on AMPL, it requires a licence of AMPL and at least one LP solver.

- The `AMPL Community Edition <https://ampl.com/ce/>`_ offers a free, full-powered AMPL license for personal, academic, and commercial-prototyping use.
- Gurobi is the default solver in REHO, but any LP solver is possible.

Plenty of text editors exist which feature AMPL. We recommend using `Sublime Text <https://www.sublimetext.com/>`_, which
provides the `AMPL Highlighting package <https://github.com/JackDunnNZ/sublime-ampl>`_.

Python
------

You will need `Python3 <https://www.python.org/downloads/>`_, just pick the latest version.
As IDE we recommend to use `PyCharm <https://www.jetbrains.com/pycharm/>`_, offering a free full-featured license for students.

First run of the model
----------------------

1. Open PyCharm, open a project and browse to the folder of the repository REHO. Do not accept the automatic virtual environment creation.
2. Go to File > Settings > Project: REHO to set up your Project Interpreter, click on the gear symbol and choose to add.
3. Add a new virtual environment (venv) and select as base interpreter your python.exe file of your python installation. Confirm with OK.
4. Install required Python packages. Open the Terminal tab (View > Tool Windows > Terminal) and type the command one by one:

.. code-block:: bash
   :caption: Installing Python packages

   pip install -r requirements.txt
   pipwin install -r requirements_win.txt

If `geopandas` fails to install, you might need to run:

.. code-block:: bash

   pip install geopandas

5. Choose the file scripts > examples > 3a_Read_csv.py and run the script.
If your installation is correct, you should receive the final message “Process finished with exit code 0”.
Sometimes, when running the model for the first time, you need to explicitly tell PyCharm to connect to the AMPL server by typing ampl in the PyCharm Terminal tab.

6. Create a new folder for your future work with REHO. Right click on the folder scripts in and create a New > Directory. You will use this folder to write and save your first scripts.


Run the model
=============

This section only provides a brief overview of REHO's capabilities, based on the few examples available in :code:`scripts/examples`.
These latter should allow you to get started with the tool and conduct your first optimizations.
For an exhaustive list of all input data parameters, please refer to :doc:`/sections/Input data` section.

Buildings information
---------------------

Each building needs to be characterised to estimate its energy demand, its renewable potential, and its sector coupling potential.
Such information about the buildings involved in the analysis can be provided to REHO in two ways:

1. By connecting to the `QBuildings database <https://ipese-web.epfl.ch/lepour/qbuildings/index.html>`_ ;
2. Or by reading CSV files.

QBuildings
~~~~~~~~~~

QBuildings is a GIS database for the characterization of the Swiss building stock from an energy point of view (end-use demand, buildings morphology, endogenous resources).
It is built by gathering different public databases and combining them with SIA norms.
It was initiated and developed by EPFL (Switzerland), within the Industrial Process and Energy Systems Engineering (IPESE) group.

REHO can connect to QBuildings and read the data it contains with the following code:

.. code-block:: bash

    reader = QBuildingsReader()             # load QBuildingsReader class
    reader.establish_connection('Suisse')   # connect to QBuildings database
    qbuildings_data = reader.read_db(transformer=3658, nb_buildings=2)      # read data

The two files implied in the process are:

- :code:`data/QBuildings/Suisse.ini` contains the login information to access the database
- :code:`model/preprocessing/QBuildings.py` contains the :code:`QBuildingsReader` class, with functions to access to database and extract specified information

*NB: Note that you need to be connected to EPFL network or VPN to access the database*

CSV files
~~~~~~~~~

The buildings information can also be provided through a CSV file, with the call:

.. code-block:: bash

    reader = QBuildingsReader()
    qbuildings_data = reader.read_csv(buildings_filename='buildings_example.csv', nb_buildings=2)

The CSV file must be located in the :code:`data/buildings/` folder.

Optimization scope
------------------

The value of REHO is to offer optimization of a specified territory at building-scale or district-scale.

Building-scale
~~~~~~~~~~~~~~

`1a_building-scale_totex.py` shows how to conduct a building-scale optimization, by setting:

.. code-block:: bash

    method = {'building-scale': True}

District-scale
~~~~~~~~~~~~~~

`2a_district-scale_totex.py` shows how to conduct a district-scale optimization, by setting:

.. code-block:: bash

    method = {'district-scale': True}

Multi-objective optimization
----------------------------

REHO offers single or multi-objective optimization. The objective function can be specified in the :code:`scenario` dictionary:

.. code-block:: bash

    scenario['Objective'] = 'TOTEX'     # select an objective function as defined in ampl_model/scenario.mod

.. code-block:: bash

    scenario['Objective'] = ['OPEX', 'CAPEX']   # for multi-objective optimization two objectives need to be specified

This :code:`scenario` dictionary can also be used to specify epsilon constraints (:code:`EMOO`) or additional constraints (:code:`specific`).

Epsilon constraints
~~~~~~~~~~~~~~~~~~~

The key :code:`EMOO` allows to add an epsilon constraint on some objective:

.. code-block:: bash

    scenario['EMOO'] = {EMOO_opex: 16}     # select an epsilon constraint as defined in ampl_model/scenario.mod

This is used to limit another objective when performing multi-objective optimization.
In this example, the maximal allowed OPEX value is set to 16 [CHF/m2/y].
You can find a list of possible epsilon constraints in :code:`scenario.mod`.

Specific constraints
~~~~~~~~~~~~~~~~~~~~

In :code:`scenario` the key :code:`specific` allows to provide a list of specific constraints that can be activated:

.. code-block:: bash

    scenario['specific'] = ["enforce_PV_max"]      # enforce the entire roof surface to be covered with PV panels


Pareto curves
~~~~~~~~~~~~~

:code:`1b_building-scale_Pareto.py` and :code:`2b_district-scale_Pareto.py` show how to obtain an OPEX-CAPEX Pareto front,
at building-scale or district-scale respectively.

.. code-block:: bash

    scenario['nPareto'] = 2

The parameter :code:`nPareto` indicates the number of intermediate points for each objective.
The total number of optimizations will be :code:``2 + 2 * nPareto`` (2 extreme points plus 2 times a discretized interval of :code:`nPareto` points.

Methods
-------

You can use different methodology options in REHO, specified in the :code:`method` dictionary:

.. code-block:: bash

    method = {'use_pv_orientation': True, 'use_facades': False, 'district-scale': True}

This example will enable PV orientation and PV on facades.
The methods available are listed in :code:`compact_optimization.initialize_default_methods`.

Weather
-------

Yearly weather data has to be clustered to typical days. The :code:`cluster` dictionary contains the weather information:

.. code-block:: bash

    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

Where:

- 'Location' can be chosen among the files available in :code:`data/weather/hour`
- 'Attributes' indicates the features among which the clustering is applied (I refers to Irradiance, T to Temperature, and W to Weekday)
- 'Periods' relates to desired number of typical days
- 'PeriodDuration' the typical period duration (24h is the default choice, corresponding to a typical day)


Infrastructure
--------------

Initializing the energy system structure is done with the :code:`infrastructure` class.

Grids
~~~~~

Grids are initialized with:

.. code-block:: bash

    grids = infrastructure.initialize_grids(file="grids.csv")


Where the file :code:`grids.csv` located in :code:`preprocessing/parameters/` directory contains the default parameters such as energy tariffs and carbon content.

To use custom prices, there are two options:

1. Provide another CSV file to the :code:`initialize_grids()` function:

.. code-block:: bash

    grids = infrastructure.initialize_grids(file="custom_grids.csv")

Where :code:`"custom_grids.csv"` has to be located in :code:`preprocessing/parameters/`.

2. Use the :code:`Cost_supply_cst` and :code:`Cost_demand_cst` parameters in the :code:`initialize_grids()` function:

.. code-block:: bash

    grids = infrastructure.initialize_grids({
        'Electricity': {'Cost_supply_cst': 0.30, 'Cost_demand_cst': 0.18},
        'Oil': {'Cost_supply_cst': 0.16}
    })

In this example, new supply and demand costs for electricity, and a new supply cost oil are specified.


Units
~~~~~

Units are initialized with:

.. code-block:: bash

    scenario['exclude_units'] = ['Battery', 'HeatPump_Geothermal']
    scenario['enforce_units'] = ['HeatPump_Air']
    units = infrastructure.initialize_units(scenario, grids, building_data="building_units.csv")

Where:

- 'exclude_units' is a list containing the units excluded from the available options
- 'enforce_units' is a list containing the units forced to be installed
- :code:`grids` is the dictionary formerly returned by :code:`initialize_grids()`
- "building_units.csv" located in :code:`preprocessing/parameters/` contains the default parameters for units characteristics (specific cost, LCA indicators...)

District units can be enabled with the boolean argument :code:`district_units`:

.. code-block:: bash

    units = infrastructure.initialize_units(scenario, grids, building_data, district_data="district_units.csv", district_units=True)

Here "district_units.csv" contains the default parameters for district-size units.



