.. REHO documentation master file,

The REHO model
==============
The Renewable Energy Hub Optimize (REHO) an open-source [... **todo**]


REHO is developed by EPFL (Switzerland), Industrial Process and Energy Systems Engineering (IPESE) group .
This documentation introduces the *core* model REHO ... **TODO**

Introduction
============
The purpose of the Renewable Energy Hub Optimizer (REHO) tool is to optimize energy systems at building-scale or district-scale, considering simultaneously the optimal design as well as optimal scheduling of capacities. It allows investigating the deployment of energy harvesting and energy storage capacities to ensure the energy balance of a specified territory, through multi-objective optimization and KPIs parametric studies.

It exploits the benefits of two programming languages: AMPL and Python.

* The core optimization model is written in AMPL: objectives, constraints, modeling equations (energy balance, mass balance, heating cascade, etc.). This is the result of the PhD thesis of Paul Stadler (2019).
* All the input and output data is passed to the model through a Python wrapper. This data management structure is used for initialization of the optimization model, execution, and results retrieval. It was developed by Luise Middelhauve during her PhD thesis (2022).

This model is still under construction.

Downloading REHO
=======================

.. caution::
   The code is not yet shared. **Todo**


Main contributors
=================

* Dorsan **Lepour**: **todo**

There are many other developers making this model a community!
You will meet them (and their work) in :doc:`/sections/Releases` section.


Contents
=========

.. toctree::
   :maxdepth: 1

   sections/Overview
   sections/Releases
   sections/Getting started
   sections/Model formulation
   sections/Input Data
   sections/Bibliography

.. Indices and tables
   ==================
   * :ref:`genindex`
   * :ref:`modindex`
   * :ref:`search`

