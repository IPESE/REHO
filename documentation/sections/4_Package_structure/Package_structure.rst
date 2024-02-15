Package structure
+++++++++++++++++

.. autosummary::
    :recursive:
    :toctree: _autosummary

    reho

.. contents::
   :local:
   :depth: 5

.. toctree::
   :maxdepth: 5


.. warning::

    Section still under development.

    Focus on package structure and implementation

    Sequential approach : Preprocessing --> Optimization --> Postprocessing

    .. Top-down approach (reho.py --> district_decomposition.py --> compact_optimization.py --> infrastructure.py)


REHO exploits the benefits of two programming languages:

* **AMPL:** the core optimization model with the objectives, constraints, modeling equations (energy balance, mass balance, heating cascade, etc.)
* **Python:** the data management structure used for initialization of the model, execution of the optimization, and results retrieval). All the input and output data is passed to the AMPL model through `amplpy <https://pypi.org/project/amplpy/>`_, the Python API for AMPL.

.. _software_diagram:

.. figure:: images/diagram_package.svg

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

.. automodule:: reho.model

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
- `write_results.py`: extracts the results from the AMPL model and converts it to Python dictionary and pandas dataframes.


**preprocessing/**
------------------------

Prepares and manipulates the input of the optimization:

`clustering.py`
~~~~~~~~~~~~~~~~~~~~~~~

*Executes the data reduction for meteorological data.*

.. note::
    The meteo file provided are only the ones from the 6 meteo archetypes. Should we link every other location to these
    typical meteos if no meteo file is provided? This could be easily done as the transformer in QBuildings have
    the meteo_cluster.

`data_generation.py`
~~~~~~~~~~~~~~~~~~~~~~~

*Calculates the buildings domestic hot water (DHW) and domestic electricity profiles. Also generates the heat gains and solar gains profiles.*

.. caution::
    It seems the solar gain profiles relies on `skydome/typical_irradiation.csv` that is specific to Rolle.

.. automodule:: reho.model.preprocessing.data_generation
    :members: build_eud_profiles, solar_gains_profile

`electricity_prices.py`
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: reho.model.preprocessing.electricity_prices
    :members: get_prices_from_elcom_by_canton, get_prices_from_elcom_by_city, get_injection_prices, get_electricity_prices


`emission_matrix_parser.py`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Characterizes the CO2 emissions related to electricity generated from the grid.*

.. caution::
    It relies on `emissions/electricity_matrix_2019_reduced.csv`, is that ok?.

`EV_profile_generator.py`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Generates the electric vehicle electricity demand profiles.*

.. caution::
    Needs to be documented.

`QBuildings.py`
~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: reho.model.preprocessing.QBuildings.QBuildingsReader
    :members:

`sia_parser.py`
~~~~~~~~~~~~~~~~~~~~~~~

*Collects data from "SIA" Swiss Norms, which are used to distinguish between eight different building types in their usage and behavior.*

`skydome_input_parser.py`
~~~~~~~~~~~~~~~~~~~~~~~~~

*Used for PV orientation.*

.. caution::
    As for the solar heat gains, it relies on a skydome generated for Luise's case study. How to generalise it?

`weather.py`
~~~~~~~~~~~~~~~~~~~~~~~

*Generates the meteorological data (temperature and solar irradiance).*

.. automodule:: reho.model.preprocessing.weather
    :members: get_cluster_file_ID, generate_output_data, write_dat_files

*compact_optimization.py*
------------------------------

.. autoclass:: reho.model.compact_optimization.compact_optimization

*district_decomposition.py*
------------------------------

.. autoclass:: reho.model.district_decomposition.district_decomposition


*infrastructure.py*
------------------------------

*Characterizes all the sets and parameters which are connected to buildings, units and grids.*

The default values (ampl code), the inputs from the district structure (costs, fmax, fmin, …) and new parameters from the data folder.

.. caution::
    To be documented.

*reho.py*
------------------------------

.. autoclass:: reho.model.reho.reho
   :members: save_results


**plotting/**
==================

*Directory for plotting and visualization code.*

- `layout.csv`: the plotting relies on this file to get the *color* and the *labels* that characterize the units and the layers.
- `sia380_1.csv`: contains the translation of building's affectation in roman numbering to labels in the SIA 380/1 norm.

*plotting.py*
---------------

.. automodule:: reho.plotting.plotting
   :members: plot_actors, plot_performance, plot_sankey, sunburst_eud, unit_monthly_plot

**rainbow_plots/**
------------------

*Contains the scripts to generate rainbow plots for results generated by REHO.*

`sankey.py`
-----------

*Builds the dataframe to use to plot a sankey diagram from a **reho_results**.*

`yearly_profile_builder.py`
---------------------------

*Reconstructs a yearly profile from the clustering periods.*






*paths.py*
==================

*File for managing file paths and configurations.*
