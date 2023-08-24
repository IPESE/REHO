.. REHO documentation master file,

The REHO model
==============

Renewable Energy Hub Optimizer (REHO) is a decision support tool for the optimization of buildings according to economic, environmental and efficiency criteria.

It is developed by EPFL (Switzerland), within the Industrial Process and Energy Systems Engineering (IPESE) group.

The purpose of REHO is to optimize energy systems at the building-scale or the district-scale,
considering simultaneously the optimal design as well as optimal scheduling of capacities.
It allows investigating the deployment of energy harvesting and energy storage capacities to ensure the energy balance of a specified territory,
through multi-objective optimization and KPIs parametric studies.

It exploits the benefits of two programming languages: AMPL and Python.

* The core optimization model is written in AMPL: objectives, constraints, modelling equations (energy balance, mass balance, heating cascade, etc.).
* All the input and output data is passed to the model through a Python wrapper. This data management structure is used for initialization of the optimization model, execution, and results retrieval.


Downloading REHO
=======================

The public version of REHO can be downloaded in the Releases section or from its github repository (using the Clone or Download button on the right side of the screen): https://github.com/Renewable-Energy-Hub-Optimizer/REHO_model

Main contributors
=================

* Dorsan **Lepour**
* Joseph **Loustau**
* Luise **Middelhauve**
* Paul **Stadler**
* Cédric **Terrier**

There are many other developers making this model a community!
You will meet them (and their work) in :doc:`/sections/Releases` section.


Contents
=========

.. toctree::
   :maxdepth: 1

   sections/Overview
   sections/Releases
   sections/Getting started
   sections/Model
   sections/Input data
   sections/Bibliography

.. Indices and tables
   ==================
   * :ref:`genindex`
   * :ref:`modindex`
   * :ref:`search`

