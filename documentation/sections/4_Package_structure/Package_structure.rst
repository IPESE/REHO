Package structure
+++++++++++++++++

.. caution::

    Focus on package structure and implementation

    .. Top-down approach (reho.py --> district_decomposition.py --> compact_optimization.py --> infrastructure.py)

    .. Or sequential approach Preprocessing --> Optimization --> Postprocessing

REHO exploits the benefits of two programming languages:

* **AMPL:** the core optimization model with the objectives, constraints, modeling equations (energy balance, mass balance, heating cascade, etc.)
* **Python:** the data management structure used for initialization of the model, execution of the optimization, and results retrieval). All the input and output data is passed to the AMPL model through `amplpy <https://pypi.org/project/amplpy/>`_, the Python API for AMPL.

.. _software_diagram:

.. figure:: images/software_diagram.svg

   Diagram of the REHO architecture


:ref:`software_diagram` illustrates REHO architecture, which can be distinguished into three parts:

* **Preprocessing:** generation of end use demand energy profiles + characterization of equipment and resources
* **Optimization:** MILP Dantzig-Wolfe decomposition algorithm with the master problem (MP) and subproblems (SPs)
* **Postprocessing:** list of energy system configurations and related KPIs


**data/**
==================

Directory for data-related files.

- **electricity/**
- **emissions/**
- **parameters/**
- **QBuildings/**
- **SIA/**
- **skydome/**
- **weather/**


**model/**
==================

Directory for model-related code.

**ampl_model/**
---------------------

Core of the optimization model (model objectives, constraints, modelling equations), containing all AMPL files:

- **units/** contains the model files specific to each technology that can be used in the system. Three subfolders (`district_units`, `h2_units`, and `storage`) are used for easier classification.
- `data_stream.dat` contains values that specify the operating temperatures of streams and energy conversion units.
- `data_stream_storage.dat` specifies the operating temperatures of the energy storage units.
- `master_problem.mod` contains the modeling of the problem for the decomposition approach.
- `model.mod` contains the modelling of the energy system with the declaration of all parameters and variables, problem constraints (energy balance, mass balance, heat cascade, etc.). This is the core of the MILP model.
- `scenario.mod` contains the optimization objective functions, the epsilon constraints, and some specific constraints that can be enabled to model a particular scenario.

**postprocessing/**
-----------------------

Extracts and postprocesses the output of the optimization:

- `KPIs.py`: calculates the KPIs resulting from the optimization.
- `post_compute_decentralized_districts.py`: manipulates results to have consistency between the building-scale and district-scale optimizations.
- `write_results.py`: extracts the results from the AMPL model and converts it to Python dictionary and pandas dataframes).


**preprocessing/**
------------------------

Prepares and manipulates the input of the optimization:

- `clustering.py` executes the data reduction for meteorological data.
- `data_generation.py`: calculates the buildings domestic hot water (DHW) and domestic electricity profiles. Also generates the heat gains and solar gains profiles.
- `electricity_prices.py`: queries the electricity retail prices from the ELCOM database.
- `electricity_profile_parser.py`: characterizes the electricity consumption profiles.
- `emission_matrix_parser.py`: characterizes the CO2 emissions related to electricity generated from the grid.
- `EV_profile_generator.py`: generates the electric vehicle electricity demand profiles.
- `QBuildings.py`: connects and extract information from the QBuildings database.
- `sia_parser.py`: collects data from "SIA" Swiss Norms, which are used to distinguish between eight different building types in their usage and behavior.
- `skydome_input_parser.py`: used for PV orientation.
- `weather.py`: generates the meteorological data (temperature and solar irradiance).


*compact_optimization.py*
------------------------------

Collects all the data input and sends it an AMPL model, solves the optimization

*district_decomposition.py*
------------------------------

Applies the decomposition method

*infrastructure.py*
------------------------------

Characterizes all the sets and parameters which are connected to buildings, units and grids

*reho.py*
------------------------------

Performs the single or multi-objective optimization

- `save_results`: saves the results in a specified format (.csv, .pickle).


**plotting/**
==================

Directory for plotting and visualization code.

- `layout.csv`
- `plotting.py`
- **rainbow_plots/**
- `sankey.py`
- `sia380_1.csv`
- `yearly_profile_builder.py`

.. automodule:: reho.plotting.plotting
   :members:
   :exclude-members: monthly_heat_balance



*paths.py*
==================

File for managing file paths and configurations.
