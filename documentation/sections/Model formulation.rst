.. _ch_estd:

Model formulation
+++++++++++++++++

.. caution ::
   TO BE DONE


Overview
========

The nomenclature explained in Section :ref:`ssec_nomenclature`

GL : I would add a big picture here representing the model and wrappers (pre/post and model).
I would then explain the link between the different models.

Folder structure:
-----------------

The software is divided into two parts - the AMPL part with all model constraints and the Python part with all data management (initialization and execution of the optimization). This means all unit models, the building model, and all objectives are written in the AMPL part. Then, everything is loaded using Python, the input data is set, and the desired constraints are selected or dropped. The following sections give an overview of where to find what. Open the repository and browse through it while you read this manual. You do not have to understand everything right away; you can always come back to this section.

Optimization model (AMPL)
~~~~~~~~~~~~~~~~~~~~~~~~~

All AMPL files are in the folder `ampl_model`.

Inside, you will find 5 files:

- `model.mod` contains the modeling of the energy system with the declaration of all parameters and variables, problem constraints (energy balance, mass balance, heat cascade, etc.). This is the core of the MILP model.
- `scenario.mod` contains the optimization objective functions, the epsilon constraints, and some specific constraints that can be enabled to model a particular scenario.
- `data_stream.mod` contains values that specify the operating temperatures of streams and energy conversion units.
- `data_stream_storage.mod` specifies the operating temperatures of the energy storage units.
- `master_problem.mod` contains the modeling of the problem for the decomposition approach.

And one folder `units` which contains the model files specific to each technology that can be used in the system. Three subfolders (`district_units`, `h2_units`, and `storage`) are used for easier classification.

Wrapper
~~~~~~~

The Python wrapper is used to work with the AMPL model. The whole program is based on the Python API for AMPL [amplpy](https://pypi.org/project/amplpy/). Therefore, the main purpose of the wrapper is generating data, processing it in a way so `amplpy` can use it, and retrieving the results afterward.

You will find 3 folders and 5 files in this directory. Let us start with the folders, listed in alphabetical order:

- `plotting` contains some shared scripts for plotting.
- `postprocessing` contains all scripts which are used to extract, save, and postprocess the output of the model:
  - `current_consumption` contains data used for comparing KPIs of different solutions; you don't need to pay attention to it, it will soon be integrated somewhere else.
  - `KPIs.py` calculates the KPIs resulting from the optimization.
  - `post_compute_decentralized_districts.py`
  - `save_results.py` is the function to save the results in a specified format (.csv, .pickle, .dat).
  - `write_results.py` to extract (using `amplpy`) the results from the AMPL model and pass it to Python (typically, using pandas dataframes) to be saved and/or further processed (e.g., plotted and printed). The class `REHOResults` is collecting main variables and parameters. If you want to access a value, you can check here which attribute you have to call in the result object. Assuming that you already have loaded your output file (cf `useful_functions`) and you would like to know the size of the units which are installed, a look into the main AMPL file `model.mod` reveals that the variable you need is called `Units_Mult`. You can then search for the variable in the result class in Python and realize that it is located in the dataframe called `df_Unit`.

- `preprocessing` contains various data and scripts which are used to access and manipulate data, to characterize the input of the model:
  - `elec_co2_emission` contains data characterizing the CO2 emissions related to electricity generated from the grid.
  - `electricityProfiles`
  - `EV_profiles` generates the electric vehicle electricity demand profile.
  - `loadProfiles` data and scripts to characterize the consumption profiles (domestic electricity or domestic hot water demand) or the presence profiles (for internal heat gains).
  - `QBuildings` data and scripts to extract information from the QBuildings database.
  - `SIA` contains parameters collected from Swiss Norms "SIA" which are used to distinguish between eight different building types in their usage and behavior.
  - `skydome` is used for PV orientation.
  - `units` contains different additional unit parameters.
  - `weatherData` contains the meteorological data (temperature and solar irradiance).
  - `data_generation.py` calculates the different profiles for assessing the demand of buildings. The building model for evaluating space heating demand is modeled in AMPL, but functions in this file provide necessary profiles such as SolarGain and HeatGain. It also calculates the need for domestic hot water (DHW) and electricity.

- `run` contains all the scripts and functions related to the optimization runs.
  - `examples` contains some basic examples to get started with the tool.
  - You can create specific subfolders here for your own case-studies (containing scripts, results, and figures). These will be ignored by the git versioning.

Regarding the files (also listed in alphabetical order for clarity):

- `compact_optimization.py` collects all the data input for the AMPL model, loads the AMPL model, sets the desired scenario, solves the optimization, extracts the results, and saves them.
- `config.py` where all important paths are collected.
- `district_decomposition.py` is applying a decomposition method on a district-scale energy system (i.e., containing multiple buildings). Is linked to the AMPL file `master_problem.mod`.
- `district_structure.py` contains the district class used to characterize the district under optimization. All the sets and parameters which are connected to (1) the buildings, (2) the units, and (3) the grids, are collected or initialized here.
- `reho.py` contains the reho class used to perform the single or multi-objective optimization.


Pre-processing
==============

I would list the wrappers used in pre here:
https://ipese-web.epfl.ch/lepour/reho_guidelines/structure.html#wrapper


Model
=====


Post processing
===============

I would list the wrappers used in post here:
https://ipese-web.epfl.ch/lepour/reho_guidelines/structure.html#wrapper


