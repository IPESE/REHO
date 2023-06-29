
.. _app:bestd_data:

Input Data
++++++++++

.. caution ::
   UNDER CONSTRUCTION

Input files overview
====================

.. caution ::
   EXPLAIN OVERALL STRUCTURE

There are several input files in the REHO framework, each serving a specific purpose:

1. **Building Information File**:
   This file contains information about the buildings involved in the analysis. It will allow REHO to estimate the energy demand, renewable energy potential and allow sector coupling.

2. **Scenario Files**:
   These files define the scenario for the analysis, such as carbon neutral building, forbidden technologies, feed-in tariff...

3. **Model Input Files**:
   These files provide the necessary inputs for the REHO model, which are the model parameters and objective function settings.

Figure: Overview of Data Files in the REHO Framework
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. figure:: /images/reho_input_files.png
   :alt: Overview of data files in the REHO framework.
   :name: fig:reho_data_files

   Overview of data files in the REHO framework.

In the following sections, we will describe each data file in detail and explain its purpose.

Building Information File
=========================


.. caution ::
   To the attention of FEDECOM partners: this section details the data that needs to be collected.

List of data
------------

Table :ref:`tab:reho_data_in_buildings` summarises all the parameters needed. In the following,
the parameters are regrouped by purpose and will be detailed. The tables account for four information:
(i) parameters' name,
(ii) description,
(iii) if it is mandatory,
(iv) example of value.
All parameters are not mandatory for the model. Indeed, some can be substituted by a template if not available,
such as the number of people living in the building or KPIs used to verify the consistency of the method. Thus, this column
uses 3 labels: mandatory, additional and KPIs.

.. table:: List of data from buildings
   :name: tab:reho_data_in_buildings

   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |               Parameters               |   Description                 |    example of value  | Need?       |          Regourped (TBD)     |
   +========================================+===============================+======================+=============+==============================+
   |               push_test                | Construction period           |     1946-1960        | additional  |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |               class                    | Type of utilisation           |     Residential      | additional  |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |            area_era_m2                 | Floor area                    |        279.0         | mandatory   |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |          area_facade_m2                | area of vertical facades      | 348.5                | mandatory   |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |       area_facade_solar_m2             | same but facing south???      | 348.5                | additional  |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |         area_roof_solar_m2             | corrected area facing sun     | 148.3                | mandatory   |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |              height_m                  | Height of the building        | 12.83                | additional  |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   | energy_heating_signature_kWh_y         | Yearly space heating demand   | 33280                | KPIs        |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   | energy_hotwater_signature_kWh_y        | Yearly sanitary water demand  | 2464                 | KPIs        |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |  thermal_transmittance_signature       | Thermal inertia               |        0.00202       | mandatory   |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |             id_class                   | ???                           |          II          | mandatory   |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |    thermal_specific_capacity_Wh_m2_K   | expected consumption (EPB)    | 119.4                | mandatory   |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |           energy_el_kWh_y              | Yearly electricity demand     | 5835.5               | KPIs        |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |            capita_cap                  | Number of users of the buildin|  15.2                | additional  |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |               ratio                    | ???                           |         1.0          | mandatory   |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |              status                    | ???                           | ['existing'          | mandatory   |                              |
   |                                        |                               | 'existing']          |             |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |     temperature_cooling_supply_C       |                               |         12.0         | mandatory   |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |     temperature_cooling_return_C       |                               |         17.0         | mandatory   |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |    temperature_heating_supply_C        |                               |         65.0         | mandatory   |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |    temperature_heating_return_C        |                               |         50.0         | mandatory   |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |       temperature_interior_C           | Target temperature to reach   |         20.0         | mandatory   |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+

Description of data
-------------------

The parameters presented in Table :ref:`tab:reho_data_in_buildings` can be regrouped in three: Geometry, heating and EPB.
Each of these groups are detailed with their parameters hereafter.

Geometry of the building
~~~~~~~~~~~~~~~~~~~~~~~~

Following Figure
illustrates the different geometry related parameters.

.. figure:: /images/reho_facades_and_roof.png
   :alt: Ilustration of geometry parameters (to be improved).
   :name: fig:reho_facades_and_roofs

   Ilustration of geometry parameters (to be improved).

The geometry is mainly defined by distances. On a building, we have floor, facades and roofs.
The era (*area_era_m2*) is the floor area, usually estimated as the ground floor area times the number of floors.
The facade area (*area_facade_m2*) is the area of all the facade including the area with windows.
The additional parameter *area_facade_solar_m2* accounts for the facade facing the sun (e.g. oriented south in Belgium).
The roof area available for solar is taken in parameter *area_roof_solar*, it estimates the equivalent area (in m2)
of PV that can be installed with the optimal inclinaison (**to be verified**). 


Scenario Files
==============

.. caution ::
   TO BE POPULATED BY UCLouvain
   TO BE CHECKED BY DORSAN

   Here, we detail the content of files in wrapper-amplpy/run/examples/results/.
   E.G. '7a_Read_csv.py'.
   This section should have the exhaustive list of parameters that can be defined in this file.


TO BE DONE

Model Input Files
=================

.. caution ::
   TO BE POPULATED BY UCLouvain

The pre-processing of REHO gives a list of inputs for the model. The following will detail it (to be done).
