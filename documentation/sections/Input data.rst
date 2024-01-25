
.. _app:bestd_data:

Input data
++++++++++

.. caution ::
   [To be removed]

   Please, update the information in the shared document available at:
   'shared drive <https://docs.google.com/spreadsheets/d/1lK5Zz9cD4d12runQ_tiUMjtU2Dq7QNZ07eLt0lUs5aw/edit?usp=sharing>`_
   Tekniker will lead the collect.

Input files overview
====================

There are several input files in the REHO framework, each serving a specific purpose:

1. **Building Information File**:
   This file contains information about the buildings involved in the analysis. It will allow REHO to estimate the energy demand, renewable energy potential and allow sector coupling.

2. **Scenario File**:
   This file defines the scenario used by the model. It accounts for information such as carbon neutral building, forbidden technologies, feed-in tariff...

3. **Model Input File**:
   This file provides the necessary inputs for the REHO model. It is generated based on
   pre-processing of the framework.

.. figure:: /images/reho_input_files_V2.png
   :alt: Overview of data files in the REHO framework.
   :name: fig:reho_data_files

   Overview of data files in the REHO framework. (NB for developers: the Scenario csv is in the form of a py code. Adaptation will be required to either translate the csv content in the py or keep the .py. Anyway, the documnetation should list the parameters within the *scenario* file).

In the following sections, we will describe each data file in detail to explain each parameter meaning and purpose.

.. _sec:data:building_info:

Building Information File
=========================

.. caution ::
   To the attention of FEDECOM partners: this section details the data that needs to be collected.


This file gives all the details of the building accounted in the community.
Each building needs to be characterised to estimate its energy demand, its renewable and sector coupling potential.
The pre processing of the REHO framework allows these estimation based on data listed in :numref:`Table %s <tab:reho_data_in_buildings>` (see Section :ref:`sec_model`).

:numref:`Table %s <tab:reho_data_in_buildings>` lists the 21 parameters used to define a building.
To ease the understanding, these parameters are regrouped in four categories:
- Geometry: are the parameters representing the geometry of the building (e.g. area of roof available for solar panels).
- Usage: are the paraemters characterising the usage of the building (e.g. number of units or affectation).
- Heating technique: are the parameters characterising the type of heating technique (e.g. floor heating)
- Energy Performance Building (EPB): are the parameters that describes the heat and electricity performance of the building (e.g. its insulation or appliances age)

The 21 parameters don't have the same importance for the framework.
Some are **mandatory** and cannot be omitted. Others (**additional**) will be substituted by templates if not given. Template usually use average values for a region, and are thus less accurate than using the real value.
The last category is **KPIs** and regroup the parameters that are used to verify the consistency of the pre-processing framework.

:numref:`Table %s <tab:reho_data_in_buildings>` also account for a building example.
The example is a building with three units.
The first occupies 40% of the floor area, is used as a commerce and with modern appliances.
The second occupies 25% of the floor area, is used as a residence and uses old appliances (light bulbs, old fridges, ...)
The third occupies 35% of the floor area, is used as a residence and uses normal appliances.
The building has a centralised heating and cooling system.

.. caution::
   Describe the example (a building with 3 units inside: a service and 2 dwellings + give characteristics (status, ...)

.. TODO: Add units in table (cf https://ipese-web.epfl.ch/lepour/qbuildings/index.html)

.. table:: List of data from buildings
   :name: tab:reho_data_in_buildings

   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |               Parameters               |   Description                 |    example of value  | Need?       |          Regourped (TBD)     |
   +========================================+===============================+======================+=============+==============================+
   |            area_era_m2                 | Floor area                    |        279           | mandatory   |    geometry                  |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |          area_facade_m2                | area of vertical facades      | 348                  | mandatory   |    geometry                  |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |          area_windows_m2               | area of vertical windows      | 80                   | mandatory   |    geometry                  |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |       area_facade_solar_m2             | for BIPV                      | 105                  | additional  |    geometry                  |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |         area_roof_solar_m2             | corrected area facing sun     | 148.3                | mandatory   |    geometry                  |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |              height_m                  | Height up to the last ceiling | 12.83                | additional  |    geometry                  |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |               period                   | Construction period           |     1946-1960        | additional  |   EPB                        |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   | energy_heating_signature_kWh_y         | Yearly space heating demand   | 33280                | KPIs        |   EPB                        |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   | energy_hotwater_signature_kWh_y        | Yearly sanitary water demand  | 2464                 | KPIs        |   EPB                        |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |thermal_transmittance_signature_kW_m2_K | Averaged conductance          |        0.00202       | mandatory   |   EPB                        |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |    thermal_specific_capacity_Wh_m2_K   | Thermal inertia               | 119.4                | mandatory   |   EPB                        |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |           energy_el_kWh_y              | Yearly electricity demand     | 5835.5               | KPIs        |   EPB                        |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |               class                    | Type of utilisation           |   ['Commercial',     | mandatory   |  usage                       |
   |                                        |                               |    'Residential',    |             |                              |
   |                                        |                               |    'Residential']    |             |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |            capita_cap                  | # Users of the building       |  15.2                | additional  |  usage                       |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |               ratio                    | living space share            | [0.4, 0.25, 0.35]    | mandatory   |  usage                       |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |              status                    | Electrical appliances         | ['low', 'high' ,     | mandatory   |  usage                       |
   |                                        | consumption                   | 'medium']            |             |                              |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |     temperature_cooling_supply_C       |                               |         12.0         | mandatory   |  Heating technique           |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |     temperature_cooling_return_C       |                               |         17.0         | mandatory   |  Heating technique           |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |    temperature_heating_supply_C        |                               |         65.0         | mandatory   |  Heating technique           |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |    temperature_heating_return_C        |                               |         50.0         | mandatory   |  Heating technique           |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+
   |       temperature_interior_C           | Target temperature to reach   |         20.0         | mandatory   |  Heating technique           |
   +----------------------------------------+-------------------------------+----------------------+-------------+------------------------------+

Description of data
-------------------

The parameters presented in Table :ref:`tab:reho_data_in_buildings` can be regrouped in four categories: Usage, Geometry, Heating technique and EPB.
Each of these groups are detailed with their parameters hereafter.

Geometry of the building
~~~~~~~~~~~~~~~~~~~~~~~~
.. caution::
   The following must be added to the table:
   - area_windows_m2

   The description of the parameters must be extended

Following Figure
illustrates the different geometry related parameters.

.. figure:: /images/house_patron_1_V2.png
   :alt: Ilustration of geometry parameters (to be improved).
   :name: fig:reho_facades_and_roofs

   Ilustration of geometry parameters


.. figure:: /images/house_patron_2_V2.png
   :alt: Ilustration of geometry parameters (to be improved).
   :name: fig:reho_facades_and_roofs_2

   Ilustration of geometry parameters



.. figure:: /images/house_patron_3_V2.png
   :alt: Ilustration of geometry parameters (to be improved).
   :name: fig:reho_facades_and_roofs_3

   Ilustration of geometry parameters

The geometry is mainly defined by distances (in meters). On a building, we have floor, facades and roofs.
The era (*area_era_m2*) is the floor area, usually estimated as the ground floor area times the number of floors.
The facade area (*area_facade_m2*) is the area of all the facade including the area with windows.
The additional parameter *area_facade_solar_m2* accounts for the facade facing the sun (e.g. oriented south in Belgium).
The roof area available for solar is taken in parameter *area_roof_solar*, it estimates the equivalent area (in m2)
of PV that can be installed with the optimal inclinaison (**to be verified**).


Usage
~~~~~

.. caution:: TO DO : - check and validate the decription.




.. figure:: /images/multi_homes.png
   :alt: Ilustration of usage parameters (to be improved).
   :name: fig:usage

   Illustration of two different building with different usage.
   The house is a single home with one family living there. It has old electrical appliances.
   The other building is has two units. The ground floor has a commercial activity over 80m2. The floor has a dwellings
   over 120m2 (thus it uses 60% of the space while the commercial uses 40%).

Usage parameters concentrate on how is the building used and who is using the building.
The user capacity (*capita_cap*) indicates the number of users in the building, influencing energy consumption (**to be verified**).
The era share (*ratio*) is a significant indicator as it differentiates the proportion of living space in the building allocated to different activities or functions.
For instance, the building in our example, with a ground floor store and two similar apartments, have a ratio of [0.4,0.3,0.3].
The electrical appliances status (*status*) indicates the consumption levels of electrical appliances, which could be high, medium, or low.
The type of the building (*class*) indicates the type of utilization of the as describe in the table below
These variables permit the model to accurately comprehend and estimate the patterns of energy usage.

Type of buildings
^^^^^^^^^^^^^^^^^^^^

- Collective housing
- Individual housing
- Administrative
- School
- Commercial
- Restaurant
- Hospital
- Industry
- Shed warehouse
- Sport facilities
- Covered swimming pool
- Gathering places
- Other


Energy Performance of the Building (EPB)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. caution:: TO DO : - check and validate the decription.

The Energy Performance of Buildings (*EPB*) characterize the energy consumption and efficiency of the building.
Notably, the construction period (*period*) can indicate the energy efficiency standards in place during the period of construction.
The thermal transmittance signature (*thermal_transmittance_signature_kW_m2_K*) represents the average conductance of the building, indicating the rate of heat transfer based on its isolation.
On the other hand, the thermal specific capacity (thermal_specific_capacity_Wh_m2_K) provides information on the building's thermal inertia, i.e., the time it takes for the building to adjust its internal temperature to changes in the external temperature.
The demands for space heating (*energy_heating_signature_kWh_y*), sanitary water (*energy_hotwater_signature_kWh_y*), and electricity (*energy_el_kWh_y*) are defined on a yearly basis.

Heating technique
~~~~~~~~~~~~~~~~~

.. caution:: TO DO : - check and validate the decription.
   - Add a table with differnt technologies and usual supply and return temperatures


.. figure:: /images/heating_V3.png
   :alt: Ilustration of heating technique parameters (to be improved).
   :name: fig:heating

   Illustration of different heating techniques and associated parameters.
   Interior temperature must be 18°C in winter (*temperature_interior_C*). Depending on the technologies
   the *temperature_heating_supply* (red) and *temperature_heating_return* (blue) differs.

.. figure:: /images/cooling_V3.png
   :alt: Ilustration of heating technique parameters (to be improved).
   :name: fig:cooling

   Illustration of a cooling technique and associated parameters.
   Interior temperature must be 25°C in summer (*temperature_interior_C*). Depending on the technologies
   the *temperature_cooling_supply* (red) and *temperature_cooling_return* (blue) differs.

The heating technique is maily measured in degrees Celsius. In building we have heating and cooling system.
They include supply and return temperatures for both heating and cooling.
The supply and return temperatures for cooling are captured by *temperature_cooling_supply_C* and *temperature_cooling_return_C*, respectively.
Similarly, the parameters *temperature_heating_supply_C* and *temperature_heating_return_C* represent the corresponding temperatures for the heating system.
The target temperature to be reached inside the building is defined by the parameter *temperature_interior_C*.
Understanding these parameters will assist in understanding the heating and cooling characteristics of the building and areas where there may be room for improvement.
