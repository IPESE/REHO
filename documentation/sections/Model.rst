.. _sec_model:

Model
+++++

.. caution ::
   Work in progress

Structure
=========

The software is divided into two parts, written respectively in AMPL and Python:

* **Energy model:** the AMPL part with the model objectives, constraints, modelling equations (energy balance, mass balance, heating cascade, etc.)
* **Wrapper:** the Python part with all data management (initialization, execution and results retrieval of the optimization)

.. figure:: /images/reho_input_files_V2.png
   :alt: Overview of model structure including pre and post processing.
   :name: fig:reho_overview

The figure :numref:`fig:reho_overview` illustrates how the code is structured with its pre and post processing wrappers.

The `model` folder contains 3 folders and 4 files.

Folders:

- `preprocessing`: prepares and manipulates the input of the optimization
- `ampl_model`: core of the optimization model (model objectives, constraints, modelling equations)
- `postprocessing`: extracts, saves, and postprocesses the output of the optimization

Files:

- `reho.py`: performs the single or multi-objective optimization
- `infrastructure.py`: characterizes all the sets and parameters which are connected to buildings, units and grids
- `compact_optimization.py`: collects all the data input, loads the AMPL model, solves the optimization
- `district_decomposition.py`: applies a decomposition method for a district-scale optimization (related to the AMPL file `master_problem.mod`)


.. caution::

   TODO:
   Explain how the code works as a flow chart with a big picture representing the model and wrappers (pre/post and model).

   This section should give an overview of the wrappers and code. The code should give all the parameters, variables and SET used in the model.
   The numerical values and sources should be given in the data appendix.


Energy model
============

.. caution::
   TODO:
   The code needs to be modified to the same nomenclature as EnergyScope: SET, Variables and parameters.
   The name of some parameters could be changed to the same as EnergyScope: Units_Mult_1 (F), Units_Fmin (fmax), ...

All AMPL files are in the folder `model > ampl_model`.
`
Inside, you will find 5 files:

- `model.mod` contains the modelling of the energy system with the declaration of all parameters and variables, problem constraints (energy balance, mass balance, heat cascade, etc.). This is the core of the MILP model.
- `master_problem.mod` contains the modeling of the problem for the decomposition approach.
- `scenario.mod` contains the optimization objective functions, the epsilon constraints, and some specific constraints that can be enabled to model a particular scenario.
- `data_stream.dat` contains values that specify the operating temperatures of streams and energy conversion units.
- `data_stream_storage.dat` specifies the operating temperatures of the energy storage units.

And one folder `units` which contains the model files specific to each technology that can be used in the system.
Three subfolders (`district_units`, `h2_units`, and `storage`) are used for easier classification.

Unit model
--------------

.. caution::

   TODO:
   Detail what is accounted in a typical 'unit.mod' file

Building model
--------------

.. caution::

   TODO:
   Detail what is accounted in the file 'model.mod'

District model:
---------------

.. caution::

   TODO:
   Detail what is accounted in the file 'master_problem.mod'


Wrapper
=======

The wrapper is based on the Python API for AMPL [amplpy](https://pypi.org/project/amplpy/).
Therefore, the main purpose of the wrapper is generating data, processing it in a way so `amplpy` can use it, and retrieving the results afterward.

REHO class
----------

.. caution::

   TODO:
   Detail what is accounted in the file `reho.py`


Infrastructure class
--------------------

.. caution::

   TODO:
   Detail what is accounted in the file `infrastructure.py`

Compact optimization
--------------------

.. caution::

   TODO:
   Detail what is accounted in the file `compact_optimization.py`

District decomposition
----------------------

.. caution::

   TODO:
   Detail what is accounted in the file `district_decomposition.py`


Preprocessing
-------------

  - `clustering.py` executes the data reduction for meteorological data.
  - `data_generation.py`: calculates the buildings domestic hot water (DHW) and domestic electricity profiles. Also generates the heat gains and solar gains profiles.
  - `electricity_profile_parser.py`: characterizes the electricity consumption profiles.
  - `emission_matrix_parser.py`: characterizes the CO2 emissions related to electricity generated from the grid.
  - `EV_profile_generator.py`: generates the electric vehicle electricity demand profiles.
  - `QBuildings.py`: connects and extract information from the QBuildings database.
  - `sia_parser.py`: collects data from "SIA" Swiss Norms, which are used to distinguish between eight different building types in their usage and behavior.
  - `skydome_input_parser.py`: used for PV orientation.
  - `weather.py`: generates the meteorological data (temperature and solar irradiance).

Postprocessing
--------------

Files:
  - `KPIs.py`: calculates the KPIs resulting from the optimization.
  - `post_compute_decentralized_districts.py`: manipulates results to have consistency between the building-scale and district-scale optimizations.
  - `save_results.py`: saves the results in a specified format (.csv, .pickle).
  - `write_results.py`: extracts the results from the AMPL model and converts it to Python dictionary and pandas dataframes).


REHOResults
~~~~~~~~~~~

The class `REHOResults` is collecting main variables and parameters.
If you want to access a value, you can check here which attribute you have to call in the result object.
Assuming that you already have loaded your output file (cf `useful_functions`) and you would like to know the size of the units which are installed,
a look into the main AMPL file `model.mod` reveals that the variable you need is called `Units_Mult`.
You can then search for the variable in the result class in Python and realize that it is located in the dataframe called `df_Unit`.

Scripts
=======

`scripts` contains all the scripts and functions related to the optimization runs

`examples` contains some basic examples to get started with the tool.
You can create specific subfolders here for your own case-studies (containing scripts, results, and figures).
These will be ignored by the git versioning.

Examples
~~~~~~~~

List of examples.

Plotting
=======

`plotting` contains some shared scripts for plotting.



