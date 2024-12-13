.. _sec_model:

Model
+++++

The energy hub concept is used to model an energy community where multi-energy carriers can supply
diverse end use demands through building-level equipment and district-level infrastructure optimally interconnected and operated.
For a delimited perimeter of buildings, REHO selects the optimal energy system configuration minimizing the specified objective function.
All the energy flows at building-level and district-level are then fully characterized by the model decision variables.

.. figure:: ../images/district.svg
   :align: center
   :name: district

   District-level energy hub model in REHO


Energy demands considered by the model are: thermal comfort (space heating and cooling), domestic hot water (DHW), domestic electricity, and mobility needs.
Domestic electricity, DHW, and mobility needs are generated using standardized profiles according to norms or measurements in a pre-processing step.
In contrast, the thermal comfort demand is modeled within the framework itself in order to include the control strategy of the energy management system and the possibility of a thermal renovation of the building.
This heating or cooling demand is impacted by factors such as the conductive heat losses through the building envelope, the heat capacity of the building and the heat gains from occupants, electric appliances and solar irradiation.
Furthermore, the energy demand associated with thermal comfort is characterized by the desired comfort temperature of the rooms, the nominal return and supply temperature of the heat distribution system and the control strategy of latter.

Heating and cooling requirements can be satisfied by energy conversion technologies (such as a heat pump, an electrical heater, a fuel cell, a gas boiler, an air conditioner...) or directly from a district heating infrastructure.
Energy can be stored in installed equipment (such as a battery or a water tank), or in the form of building thermal inertia.
Photovoltaic panels act as a renewable energy source.
The building-level energy system is interconnected to the energy distribution infrastructure of the district (electrical grid, natural gas grid, ...).

.. figure:: ../images/model.svg
   :align: center
   :name: fig-model

   REHO model architecture

.. figure:: ../images/building.png
   :width: 450
   :align: center
   :name: building

   Building-level energy hub in REHO


List of symbols
===========================

.. note::
    In the following, all decision variables of the model are denoted with **bold letters** to distinguish them from the parameters.

.. tab-set::

    .. tab-item:: Variables

        +------------------------------+-------------------------------------------------+-------------------------+
        | :math:`\boldsymbol{C}`       | cost                                            | :math:`\text{currency}` |
        +------------------------------+-------------------------------------------------+-------------------------+
        | :math:`\boldsymbol{E}`       | electricity                                     | :math:`kW(h)`           |
        +------------------------------+-------------------------------------------------+-------------------------+
        | :math:`\boldsymbol{G}`       | global warming potential                        | :math:`kg_{CO_2, eq}`   |
        +------------------------------+-------------------------------------------------+-------------------------+
        | :math:`\boldsymbol{H}`       | natural gas or fresh water                      | :math:`kW(h)`           |
        +------------------------------+-------------------------------------------------+-------------------------+
        | :math:`\boldsymbol{Q}`       | thermal energy                                  | :math:`kWh`             |
        +------------------------------+-------------------------------------------------+-------------------------+
        | :math:`\boldsymbol{R}`       | residual heat                                   | :math:`kWh`             |
        +------------------------------+-------------------------------------------------+-------------------------+
        | :math:`\boldsymbol{T}`       | temperature                                     | :math:`K`               |
        +------------------------------+-------------------------------------------------+-------------------------+
        | :math:`\boldsymbol{f}`       | sizing variable                                 | :math:`\diamondsuit`    |
        +------------------------------+-------------------------------------------------+-------------------------+
        | :math:`\boldsymbol{\lambda}` | decomposition decision variable, master problem | :math:`-`               |
        +------------------------------+-------------------------------------------------+-------------------------+
        | :math:`\boldsymbol{y}`       | decision variable, binary                       | :math:`-`               |
        +------------------------------+-------------------------------------------------+-------------------------+

    .. tab-item:: Parameters

            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`A`         | area                                     | :math:`m^2`                          |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`C`         | heat capacity coefficient                | :math:`kW/m^2K`                      |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`F`         | bound of validity range of unit sizes    | :math:`\diamondsuit`                 |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`\Phi`      | specific heat gain                       | :math:`kW/m^2`                       |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`Q`         | thermal power                            | :math:`kW`                           |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`T`         | temperature                              | :math:`K`                            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`U`         | heat transfer coefficient                | :math:`kW/m^2K`                      |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`V`         | volume                                   | :math:`m^3`                          |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`\alpha`    | azimuth angle                            | :math:`^{\circ}`                     |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`\beta`     | limiting angle                           | :math:`^{\circ}`                     |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`c`         | energy tariff                            | :math:`\text{currency}/kWh`          |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`c_p`       | specific heat capacity                   | :math:`kJ/(kgK)`                     |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`d`         | distance                                 | :math:`m`                            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`d_p`       | frequency of periods per year            | :math:`d/yr`                         |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`d_t`       | frequency of timesteps per period        | :math:`h/d`                          |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`e`         | electric power                           | :math:`kW/m^2`                       |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`\epsilon`  | elevation angle                          | :math:`^{\circ}`                     |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`\nu`       | efficiency                               | :math:`-`                            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`f_{b,r}`   | spatial fraction of a room in a building | :math:`-`                            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`f^s`       | solar factor                             | :math:`-`                            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`fû`        | usage factor                             | :math:`-`                            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`g`         | global warming potential streams         | :math:`kg_{CO_2, eq}/kWh`            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`\gamma`    | tilt angle                               | :math:`^{\circ}`                     |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`g^{glass}` | ratio of glass per facades               | :math:`-`                            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`h`         | height                                   | :math:`m`                            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`i`         | interest rate                            | :math:`-`                            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`i^{cl}`    | fixed investment cost                    | :math:`\text{currency}`              |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`i^{c2}`    | continuous investment cost               | :math:`\text{currency}/\diamondsuit` |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`i^{g1}`    | fixed impact factor                      | :math:`kg_{CO_2, eq}`                |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`i^{g2}`    | continuous impact factor                 | :math:`kg_{CO_2, eq}/ \diamondsuit`  |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`irr`       | irradiation density                      | :math:`kWh/m^2`                      |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`l`         | lifetime                                 | :math:`yr`                           |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`m`         | mass                                     | :math:`kg`                           |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`n`         | project horizon                          | :math:`yr`                           |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`pd`        | period duration                          | :math:`h`                            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`\phi`      | solar gain fraction                      | :math:`kW/m^2`                       |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`q`         | thermal power                            | :math:`kW/m^2`                       |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`\rho`      | density                                  | :math:`kg/m^3`                       |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`s`         | shading factor                           | :math:`-`                            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`x`         | coordinate, pointing east                | :math:`-`                            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`y`         | coordinate, pointing north               | :math:`-`                            |
            +-------------------+------------------------------------------+--------------------------------------+
            | :math:`z`         | coordinate, pointing to zenith           | :math:`-`                            |
            +-------------------+------------------------------------------+--------------------------------------+

    .. tab-item:: Dual variables

        +-----------------+-------------------------------------------------------+
        | :math:`[\beta]` | epsilon constraint for multi objective   optimization |
        +-----------------+-------------------------------------------------------+
        | :math:`[\mu]`   | incentive to change design proposal                   |
        +-----------------+-------------------------------------------------------+
        | :math:`[\pi]`   | cost or global warming potential of electricity       |
        +-----------------+-------------------------------------------------------+

    .. tab-item:: Superscripts

        +-----------+-------------------------------+
        | A         | appliances                    |
        +-----------+-------------------------------+
        | B         | building                      |
        +-----------+-------------------------------+
        | L         | light                         |
        +-----------+-------------------------------+
        | P         | people                        |
        +-----------+-------------------------------+
        | bat       | bateobatle                    |
        +-----------+-------------------------------+
        | bes       | bes                           |
        +-----------+-------------------------------+
        | cap       | cap                           |
        +-----------+-------------------------------+
        | chp       | chp                           |
        +-----------+-------------------------------+
        | cw        | cw                            |
        +-----------+-------------------------------+
        | :math:`-` | demand                        |
        +-----------+-------------------------------+
        | dhw       | domestic hot water            |
        +-----------+-------------------------------+
        | el        | electricity                   |
        +-----------+-------------------------------+
        | ERA       | enery reference area          |
        +-----------+-------------------------------+
        | ext       | external                      |
        +-----------+-------------------------------+
        | gain      | heat gain                     |
        +-----------+-------------------------------+
        | ghi       | global horizontal irradiation |
        +-----------+-------------------------------+
        | gr        | grid                          |
        +-----------+-------------------------------+
        | hp        | heat pump                     |
        +-----------+-------------------------------+
        | int       | internal                      |
        +-----------+-------------------------------+
        | inv       | investment                    |
        +-----------+-------------------------------+
        | irr       | irradiation                   |
        +-----------+-------------------------------+
        | max       | maximum                       |
        +-----------+-------------------------------+
        | min       | minimum                       |
        +-----------+-------------------------------+
        | net       | netto                         |
        +-----------+-------------------------------+
        | ng        | natural gas                   |
        +-----------+-------------------------------+
        | op        | operation                     |
        +-----------+-------------------------------+
        | pv        | photovoltaic panel            |
        +-----------+-------------------------------+
        | r         | return                        |
        +-----------+-------------------------------+
        | ref       | reference                     |
        +-----------+-------------------------------+
        | rep       | replacement                   |
        +-----------+-------------------------------+
        | s         | supply                        |
        +-----------+-------------------------------+
        | SH        | space heating                 |
        +-----------+-------------------------------+
        | stat      | static                        |
        +-----------+-------------------------------+
        | :math:`+` | supply                        |
        +-----------+-------------------------------+
        | tot       | total                         |
        +-----------+-------------------------------+
        | TR        | transformer                   |
        +-----------+-------------------------------+

    .. tab-item:: Indexes

        +------------+-----------------------------------+
        | 0          | nominal state                     |
        +------------+-----------------------------------+
        | II         | ref. to 1st law of thermodynamics |
        +------------+-----------------------------------+
        | II         | ref. to 2nd law of thermodynamics |
        +------------+-----------------------------------+
        | :math:`b`  | building                          |
        +------------+-----------------------------------+
        | :math:`f`  | facades                           |
        +------------+-----------------------------------+
        | :math:`i`  | iteration                         |
        +------------+-----------------------------------+
        | :math:`k`  | temperature interval              |
        +------------+-----------------------------------+
        | :math:`l`  | linearization interval            |
        +------------+-----------------------------------+
        | :math:`p`  | period                            |
        +------------+-----------------------------------+
        | :math:`pt` | patch                             |
        +------------+-----------------------------------+
        | :math:`r`  | replacement                       |
        +------------+-----------------------------------+
        | :math:`t`  | timestep                          |
        +------------+-----------------------------------+
        | :math:`u`  | unit                              |
        +------------+-----------------------------------+

    .. tab-item:: Sets

        +-------------+------------------------------+
        | :math:`A`   | azimuth angles               |
        +-------------+------------------------------+
        | :math:`B`   | buildings                    |
        +-------------+------------------------------+
        | :math:`F`   | facades                      |
        +-------------+------------------------------+
        | :math:`I`   | iterations                   |
        +-------------+------------------------------+
        | :math:`K`   | temperature levels           |
        +-------------+------------------------------+
        | :math:`L`   | linearization intervals      |
        +-------------+------------------------------+
        | :math:`O`   | orientations                 |
        +-------------+------------------------------+
        | :math:`P`   | typical periods              |
        +-------------+------------------------------+
        | :math:`R`   | roofs                        |
        +-------------+------------------------------+
        | :math:`S`   | skydome patches              |
        +-------------+------------------------------+
        | :math:`T`   | timesteps                    |
        +-------------+------------------------------+
        | :math:`U`   | units                        |
        +-------------+------------------------------+
        | :math:`U_r` | units that need replacements |
        +-------------+------------------------------+
        | :math:`Y`   | tilt angles                  |
        +-------------+------------------------------+





Inputs
===========================

For the application of REHO, the energy hub description needs to contain - as highlighted by :ref:`fig-model` :

- the *End Use Demands (EUDs)*, from the meteorological data and the buildings characteristics,
- the resources to which it has access to provide those *EUDs*, namely the grids,
- the equipments that can be used to convert those resources into the required services.


End use demand profiles
---------------------------------

:cite:t:`middelhauveRoleDistrictsRenewable2022` - Section 1.2

The *EUDs* profiles to be determined are:

- The demand profile for domestic hot water
- The demand profile for domestic electricity
- The demand profile for space heating computed with:
    - The internal heat gains from occupancy,
    - The internal heat gains from electric appliances,
    - The heat exchange with the exterior,
    - The solar gains from the irradiance,
- The demand profile for mobility. 

.. admonition:: Statistical profiles

    When real data is not available, the profiles can be estimated using statistical data.

    In the case of REHO, the consumption profiles are computed from statistical data on buildings characteristics,
    combined with weather data.

Buildings characteristics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The buildings are defined by their usage type, their morphology, and their heating performance.

Usage
"""""""""

Usage is defined by the building category (I to XII) from `SIA 380/1:2016 <https://shop.sia.ch/collection%20des%20normes/architecte/380-1_2016_f/F/Product>`_.
It defines, combined with `SIA 2024:2015 <https://shop.sia.ch/collection%20des%20normes/architecte/2024_2021_f/F/Product>`_,
the statistical profiles for each category in terms of occupation, lighting and hot water demand.

These profiles are generally specific to each room type and usage.

.. dropdown:: List of SIA 380/1 categories
    :icon: home

    .. table::
        :name: tbl-sia380

        +------+-----------------------+
        | I    | Collective housing    |
        +------+-----------------------+
        | II   | Individual housing    |
        +------+-----------------------+
        | III  | Administrative        |
        +------+-----------------------+
        | IV   | School                |
        +------+-----------------------+
        | V    | Commercial            |
        +------+-----------------------+
        | VI   | Restaurant            |
        +------+-----------------------+
        | VII  | Gathering places      |
        +------+-----------------------+
        | VIII | Hospital              |
        +------+-----------------------+
        | IX   | Industry              |
        +------+-----------------------+
        | X    | Shed, warehouse       |
        +------+-----------------------+
        | XI   | Sports facilities     |
        +------+-----------------------+
        | XII  | Covered swimming-pool |
        +------+-----------------------+
        | XIII | Other                 |
        +------+-----------------------+


Morphology
""""""""""""""""""""""

- Energy reference area (ERA) :math:`A_{ERA} [m^2]`
- Roof surfaces :math:`A_{roofs} [m^2]`
- Facades surfaces :math:`A_{facades} [m^2]`
- Glass fraction :math:`g^{glass} [-]`

Heating performance
""""""""""""""""""""""

- Year of construction or renovation
- Quality of thermal envelope
    - Overall heat transfer coefficient :math:`U_{h} [kW/K/m^2]`
    - Heat capacity coefficient :math:`C_{h} [Wh/K/m^2]`
- Temperatures of supply and return for heating system :math:`T_{h,supply}-T_{h,return} [°C]`
- Temperatures of supply and return for cooling system :math:`T_{c,supply}-T_{c,return} [°C]`
- Reference indoor temperature :math:`T_{in} [°C]`

The heating technique is maily measured in degrees Celsius. In building we have heating and cooling system.
They include supply and return temperatures for both heating and cooling.
The supply and return temperatures for cooling are captured by *temperature_cooling_supply_C* and *temperature_cooling_return_C*, respectively.
Similarly, the parameters *temperature_heating_supply_C* and *temperature_heating_return_C* represent the corresponding temperatures for the heating system.
The target temperature to be reached inside the building is defined by the parameter *temperature_interior_C*.

Weather data
~~~~~~~~~~~~~~~~~~~~~~~~
To calculate energy demand profiles the outdoor ambient temperature global irradiation for the region in study are necessary.

- Outdoor ambient temperature (yearly profile) :math:`T_{out} [°C]`
- Global horizontal irradiation (yearly profile) :math:`Irr_{out} [°C]`

Data reduction
"""""""""""""""""""

The hourly timesteps of a typical annual profile, leads to 8760 data points per year.
This leads, together with the complexity of the model, to computationally untraceable models.
Reducing the size of the data representing the energy demand of the renewable energy hub and weather conditions is required.
The aggregation of timeseries to typical periods is specifically popular, as patterns occur naturally in the supply and demand of energy, which arise in the time dimension through hourly, daily and seasonal cycles.
The k-medoids clustering algorithm is used in REHO. Typical days are identified based on two variables: global irradiation and ambient temperature.

*NB: Extreme periods are also considered, but only for the design of the capacities.*


Grids
---------------------------------

In the REHO model, a grid is characterized by the energy carrier it transports and its specifications.

Energy layers
~~~~~~~~~~~~~~~~~~~~~~~~

Seven energy carriers are considered in REHO, namely:

- Electricity,
- Natural gas,
- Oil,
- District heat,
- Fossil fuel,
- Mobility (service expressed in pkm),
- Data (ICT service).

These layers are modeled through parameters that can be changed in the model:

- Import and export tariffs,
- Carbon content,
- Environmental impact (detailed LCA characterization).

.. _List of LCA criteria:

.. dropdown:: List of LCA criteria
    :icon: globe

    - Land use
    - Human toxicity
    - Water pollutants
    - (to be completed)

    .. caution:: Complete list of LCA

They can be set as constant through the year or specified at an hourly resolution.

Specifications
~~~~~~~~~~~~~~~~~~~~~~~~

Cost, environmental impact, maximal capacity for district imports and exports

.. Are they internal costs?


Equipments
---------------------------------

The model has to choose between several energy conversion and energy storage technologies that can be installed to answer
the *EUDs*.

The units are parametrized by:

- Specific cost (fixed and variable costs, valid for a limited range :math:`f_{min}` - :math:`f_{max}`)
- Environmental impact (= grey energy encompassing the manufacturing of the unit, and distributed over the lifetime of the unit, see `List of LCA criteria`_)
- Thermodynamics properties (efficiency, temperature of operation)

Building-level units
~~~~~~~~~~~~~~~~~~~~~~~~

.. table:: Overview of building-level units in REHO: Input and output streams, the reference unit of each technology
    :name: tbl-building-units

    +---------------------------------+---------------------------+-------------------+----------------+
    | Technology                      | Input stream              | Output stream     | Reference unit |
    +=================================+===========================+===================+================+
    | Energy conversion technologies  |                           |                   |                |
    +---------------------------------+---------------------------+-------------------+----------------+
    | gas boiler                      | natural gas               | heat              |  $$kW_{th}$$   |
    +---------------------------------+---------------------------+-------------------+----------------+
    | heat pump                       | ambient heat, electricity | heat              |   $$kW_{e}$$   |
    +---------------------------------+---------------------------+-------------------+----------------+
    | electrical heater SH            | electricity               | heat              |  $$kW_{th}$$   |
    +---------------------------------+---------------------------+-------------------+----------------+
    | electrical heater DHW           | electricity               | heat              |  $$kW_{th}$$   |
    +---------------------------------+---------------------------+-------------------+----------------+
    | PV panel                        | solar irradiation         | electricity       |   $$kW_{p}$$   |
    +---------------------------------+---------------------------+-------------------+----------------+
    | cogeneration                    | natural gas               | electricity, heat |   $$kW_{e}$$   |
    +---------------------------------+---------------------------+-------------------+----------------+
    | Storage technologies            |                           |                   |                |
    +---------------------------------+---------------------------+-------------------+----------------+
    | thermal storage SH              | heat                      | heat              |    $$m^3$$     |
    +---------------------------------+---------------------------+-------------------+----------------+
    | thermal storage DHW             | heat                      | heat              |    $$m^3$$     |
    +---------------------------------+---------------------------+-------------------+----------------+
    | battery                         | electricity               | electricity       |    $$kWh$$     |
    +---------------------------------+---------------------------+-------------------+----------------+

District-level units
~~~~~~~~~~~~~~~~~~~~~~~~

The units cannot be used at the building-scale.

.. table:: Overview of district-level units in REHO: Input and output streams, the reference unit of each technology
    :name: tbl-district-units

+------------------------------------------+---------------------------+------------------------+----------------+
| Technology                               | Input stream              | Output stream          | Reference unit |
+------------------------------------------+---------------------------+------------------------+----------------+
| Energy conversion technologies           |                           |                        |                |
+------------------------------------------+---------------------------+------------------------+----------------+
| gas boiler                               | natural gas               | heat                   |  $$kW_{th}$$   |
+------------------------------------------+---------------------------+------------------------+----------------+
| geothermal heat pump                     | ambient heat, electricity | heat                   |   $$kW_{e}$$   |
+------------------------------------------+---------------------------+------------------------+----------------+
| district heating network                 | heat                      | heat                   |  $$kW_{th}$$   |
+------------------------------------------+---------------------------+------------------------+----------------+
| cogeneration                             | natural gas               | electricity, heat      |   $$kW_{e}$$   |
+------------------------------------------+---------------------------+------------------------+----------------+
| Electricity storage technologies         |                           |                        |                |
+------------------------------------------+---------------------------+------------------------+----------------+
| EV charger                               | electricity*              | electricity*           |     $$kWh$$    |
+------------------------------------------+---------------------------+------------------------+----------------+
| electrical vehicle                       | electricity*              | electricity*, mobility |     $$kWh$$    |
+------------------------------------------+---------------------------+------------------------+----------------+
| ICE vehicle (internal combustion engine) | fossil fuel               | mobility               |    $$unit$$    |
+------------------------------------------+---------------------------+------------------------+----------------+
| bike                                     |                           | mobility               |    $$unit$$    |
+------------------------------------------+---------------------------+------------------------+----------------+
| electric bike                            | electricity               | mobility               |    $$unit$$    |
+------------------------------------------+---------------------------+------------------------+----------------+
| battery                                  | electricity               | electricity            |    $$kWh$$     |
+------------------------------------------+---------------------------+------------------------+----------------+

.. note::
    EVs are not directly connected to the Layer *electricity*.  Rather, intermediate variables representing the exchanges between EVs and charging stations are used, and the import of electricity from the Grid to charge the vehicles can be observed through the EV charger demand :math:`\boldsymbol{\sum_{u \in EVcharger}\dot{E}_{u,p,t}^{-}` (see :ref:`fig-mob1`). 

Model
===========================

Objective functions
---------------------------------

:cite:t:`middelhauveRoleDistrictsRenewable2022` - *Section 1.2.4*

REHO can optimize energy hubs considering economic indicators (minimizing operational expenses, capital expenses, total expenses) or
environmental indicators (global warming potential).

As objectives can be generally competing, the problem can be approached using a *Multi-Objective Optimization (MOO)* approach.
MOO is implemented using the :math:`\epsilon`-constraint method to generate Pareto curves.

Annual operating expenses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::
    \boldsymbol{C^{op}_b} =  \sum_{l \in \text{L}} \sum_{p \in \text{P}} \sum_{t \in \text{T}} \left(  c^{l, +}_{p,t} \cdot \boldsymbol{ \dot{E}^{gr,+}_{b,l,p,t} } -  c^{l,-}_{p,t}\cdot \boldsymbol{ \dot{E}^{gr,-}_{b,l,p,t} } \right) \cdot d_t \cdot d_p  \quad \forall b \in  \text{B}

Annual capital expenses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::
    \begin{align}
         \boldsymbol{C^{cap}_b} &=   \frac{i(1+i)}{(1+i)^n -1} \cdot \left(\boldsymbol{C^{inv}_b } +  \boldsymbol{C^{rep}_b } \right) \label{eq_ch1:Ccap}\\
         \boldsymbol{C^{inv}_b }&= \sum_{u \in \text{U}}   b_{u} \cdot \left( i^{c1}_{u} \cdot \boldsymbol{y_{b,u}} + i^{c2}_{u} \cdot \boldsymbol{f_{b,u}} \right) \label{eq_ch1:Cinv}\\
         \boldsymbol{C^{rep}_b} &=   \sum_{u \in \text{U}}  \sum_{r \in \text{R}}  \frac{1}{\left( 1 + i \right)^{r \cdot l_u}}  \cdot \left( i^{c1}_{u} \cdot \boldsymbol{y_{b,u}} + i^{c2}_{u} \cdot \boldsymbol{f_{b,u}} \right)   \quad \forall b \in  \text{B} \label{eq_ch1:Crep}
    \end{align}

Annual total expenses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::
    \boldsymbol{C^{tot}_b} =  \boldsymbol{C^{cap}_b} +  \boldsymbol{C^{op}_b} \quad \forall b \in \text{B}


Global warming potential
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::
    \boldsymbol{G^{op}_b} = \sum_{l \in \text{L}} \sum_{p \in \text{P}} \sum_{t\in \text{T}}  \left( g^{l,+}_{p,t} \cdot \boldsymbol{\dot{E}^{gr,+}_{b,l,p,t}} - g^{l,-}_{p,t} \cdot \boldsymbol{\dot{E}^{gr,-}_{b,l,p,t}} \right) \cdot d_p \cdot d_t \quad \forall b \in  \text{B}

.. math::
    \boldsymbol{G^{bes}_b }= \sum_{u \in \text{U}}  \frac{1}{l_u}\cdot   \left( i^{g1}_u \cdot \boldsymbol{y_{b,u}} + i^{g2}_u\cdot \boldsymbol{f_{b,u}} \right) \quad \forall b \in \text{B}

.. math::
    \boldsymbol{G^{tot}_b} = \boldsymbol{G^{bes}_b} +  \boldsymbol{G^{op}_b} \quad \forall b \in \text{B}

Building-level constraints
---------------------------------


Sizing constraints
~~~~~~~~~~~~~~~~~~~~~~~~

Upper and lower bounds for unit installations are necessary for identifying the validity range for the linearization of the cost function of the unit.

The main equation for sizing and scheduling problem units are described by:

.. math::
    \begin{align}
    \boldsymbol{y_{b,u}}  \cdot  F_u^{min}  &\leq  \boldsymbol{f_{b,u}} \leq \boldsymbol{y_{b,u}}  \cdot  F_u^{max}   \\
    \boldsymbol{f_{b,u,p,t}} &\leq  \boldsymbol{f_{b,u}}\\
    \boldsymbol{y_{b,u,p,t}} &\leq  \boldsymbol{y_{b,u}}\\
    & \quad \forall b \in  \text{B} \quad \forall u \in  \text{U}  \quad \forall p \in  \text{P} \quad \forall t\in  \text{T} \nonumber
    \end{align}


Energy balance
~~~~~~~~~~~~~~~~~~~~~~~~

The energy system of the building includes all the different unit technologies that are used to fulfil the building's energy demand.

.. math::
    \begin{align}
    \boldsymbol{\dot{E}_{b,p,t}^{gr,+}}  +  \sum_{u \in \text{U}} \boldsymbol{ \dot{E}_{b,u,p,t}^{+}} &= \boldsymbol{\dot{E}_{b,p,t}^{gr,-}}+ \sum_{u \in \text{U}} \boldsymbol{\dot{E}_{b,u,p,t}^{-}} + \dot{E}_{b, p, t}^{B,-} \label{eq_ch1:Ebalance}  \\
    \boldsymbol{\dot{H}_{b,p,t}^{gr,+}}  &=  \sum_{u \in \text{U}} \boldsymbol{\dot{H}_{b,u,p,t}^{-}}  \qquad  \qquad \quad \forall b \in  \text{B} \quad \forall p \in  \text{P} \quad \forall t\in  \text{T} \label{eq_ch1:Hbalance}
    \end{align}

Heat cascade
~~~~~~~~~~~~~~~~~~~~~~~~

.. math::
    \begin{align}
    \boldsymbol{\dot{R}_{k,b,p,t} }- \boldsymbol{ \dot{R}_{k+1,b,p,t}}  &=  \sum_{u_h \in \text{S}_h} \boldsymbol{\dot{Q}_{u_h,k,b,p,t}^{-}}- \sum_{u_c \in \text{S}_c} \boldsymbol{\dot{Q}_{u_c,k,b,p,t}^{+}} \label{eq_ch1:heatK1}\\
    \boldsymbol{\dot{R}_{1,b,p,t}}&= \boldsymbol{\dot{R}_{n_k+1,b,p,t}} = 0  \qquad \qquad  \forall k \in  \text{K} \quad \forall b \in  \text{B} \quad \forall p \in  \text{P} \quad \forall t\in  \text{T} \label{eq_ch1:heatK2}
    \end{align}

Thermal comfort
~~~~~~~~~~~~~~~~~~~~~~~~

The general form of the SH demand can be expressed by the first order dynamic model of buildings:

.. math::
    \boldsymbol{\dot{Q}_{b,p,t}^{SH}} = \dot{Q}_{b,p,t}^{gain} - U_{b}^{h}  \cdot A^{ERA}_b \cdot (\boldsymbol{T^{int}_{b,p,t}} - T^{ext}_{p,t}) - C^h_b \cdot A^{ERA}_b \cdot (\boldsymbol{T^{int}_{b,p,t+1}} - \boldsymbol{T^{int}_{b,p,t}})  \quad \forall b \in  \text{B} \quad \forall p \in  \text{P} \quad \forall t\in  \text{T}


Where heat gains are constituted by:

.. math::
    \dot{Q}^{gain}_{b,p,t}  = \dot{Q}^{int}_{b,p,t} + \dot{Q}^{irr}_{b,p,t}\quad \forall b \in  \text{B} \quad \forall p \in  \text{P} \quad \forall t\in  \text{T}

With internal heat gains calculated based on SIA 2024:2015 and include the rooms usage:

.. math::
    \dot{Q}^{int}_{b,p,t}  = A^{net}_b \cdot \sum_{r \in Rooms} f_{b,r} \cdot f^{u}_{r,p}  \cdot (\Phi^{P}_{r,p,t} + \Phi^{A+L}_{r,p,t}) \quad \forall b \in  \text{B} \quad \forall p \in  \text{P} \quad \forall t\in  \text{T}

And solar heat gains proportional to the global irradiation, through a solar gain coefficient:

:cite:t:`middelhauveRoleDistrictsRenewable2022` - *Section 3.2.4 Solar heat gains*

.. math::
    \dot{Q}^{irr}_{b,p,t}  = A^{ERA}_b \cdot \phi^{irr} \cdot \dot{irr}^{ghi}_{b,p,t} \quad \forall b \in  \text{B} \quad \forall p \in  \text{P} \quad \forall t\in  \text{T}


.. note::
    The internal building temperature :math:`T_{int}` is considered as a variable to be optimized.
    This allows the building heat capacity to work as an additional, free thermal storage for the building energy system, thus making it possible to use available surplus electricity, which was generated onsite.

**Penalty costs**

Clearly, comfort should also be taken into account: this is achieved through the introduction of a penalty cost in the optimization problem objective at each hour when the indoor temperature exceeds pre-defined bounds.
These penalty costs are deduced in a post-computing step.

Domestic hot water
~~~~~~~~~~~~~~~~~~~~~~~~

.. math::
    {Q}^{dhw,-}_{b} = A^{net}_b \cdot \sum_{r \in Rooms} f_{b,r}\cdot f^{u}_{r,p} \cdot V^{dhw,ref}_{r}  \cdot \frac{n^{ref}}{A^{net}_r}\cdot c_p^{dhw} \cdot \rho^{dhw} ( T^{dhw} - T^{cw})  \quad \forall b \in  \text{B}

Domestic electricity
~~~~~~~~~~~~~~~~~~~~~~~~


.. math::
    \dot{E}^{B}_{b,p,t}  = A^{net}_b \cdot \sum_{r \in Rooms} f_{b,r} \cdot f^{u}_{r,p}  \cdot  \dot{e}^{A+L}_{r,p,t} \quad \forall b \in  \text{B} \quad \forall p \in  \text{P} \quad \forall t\in  \text{T}

Storage
~~~~~~~~~~~~~~~~~~~~~~~~

Cyclic constraints are imposed both on the indoor temperature and on thermal and electrical energy storage systems, to ensure the the state is reset to its initial status at the end of each period.

A tank for domestic hot water is mandatory, and one for space heating is possible – generally helps to increase the self-consumption of PV + HP combination.

District-level constraints
---------------------------------

Decomposition algorithm (Dantzig-Wolfe) to break down the energy community into a master problem (transformer perspective) and one subproblem for each building ones.
The obtained solution is an approximation of the compact formulation (= solving all the buildings simultaneously, exponential computational complexity) but has a linear computational complexity.

Configuration selection
~~~~~~~~~~~~~~~~~~~~~~~~

.. math::
    \begin{align}
       0 \leq  \boldsymbol{\lambda_{i,b}} & \leq 1   \quad \forall i \in \text{I}, \quad \forall b \in \text{B}  \label{eq_ch4:convex_1}\\
        \sum_{i \in \text{I}}  \boldsymbol{\lambda_{i,b}} &= 1 \quad \forall b \in \text{B} \quad \backsim [\mu_b] \label{eq_ch4:convex_2}\
    \end{align}

.. math::
    \sum_{i \in \text{I}} \sum_{b \in \text{B}} \boldsymbol{\lambda_{i,b}} \cdot    \left(  \dot{E}^{gr,+}_{i,b,p,t}  -   \dot{E}^{gr,-}_{i,b,p,t} \right)  \cdot d_p \cdot d_t  = \boldsymbol{E^{TR,+}_{p,t}} - \boldsymbol{ E^{TR,-}_{p,t} }\quad \forall p \in \text{P}, \quad \forall t \in \text{T} \quad \backsim [\pi_{p,t}]

.. math::
    \boldsymbol{C^{el}} =  \sum_{p \in \text{P}} \sum_{t \in \text{T}}  \left(  c^{el, +}_{p,t} \cdot  \boldsymbol{E^{TR,+}_{p,t}}  -  c^{el,-}_{p,t}\cdot \boldsymbol{ E^{TR,-}_{p,t}} \right)

.. math::
    \boldsymbol{G^{el}} = \sum_{p \in \text{P}} \sum_{t\in \text{T}}  \left( g^{el}_{p,t} \cdot \boldsymbol{E^{TR,+}_{p,t}} - g^{el}_{p,t} \cdot \boldsymbol{E^{TR,-}_{p,t}}  \right)

.. math::
    \begin{align}
        \boldsymbol{C^{op}} &=  \boldsymbol{C^{el}} + \sum_{i \in \text{I}} \sum_{b \in \text{B}} \boldsymbol{\lambda_{i,b}} \cdot  C^{gas}_{i,b} \label{eq_ch4:opex}  \\
        \boldsymbol{C^{cap}} &=  \sum_{i \in \text{I}} \sum_{b \in \text{B}} \boldsymbol{\lambda_{i,b}} \cdot  C^{cap}_{i,b} \label{eq_ch4:capex} \\
        \boldsymbol{C^{tot}} &=    \boldsymbol{C^{cap}} +  \boldsymbol{C^{op}} \label{eq_ch4:totex}\\
        \boldsymbol{G^{tot}} &=    \boldsymbol{G^{el}} +   \sum_{i \in \text{I}} \sum_{b \in \text{B}} \boldsymbol{\lambda_{i,b}} \cdot  \left(G^{gas}_{i,b} + G^{bes}_{i,b}    \right) \label{eq_ch4:GWP}
    \end{align}

.. math::
    \begin{align}
        &\boldsymbol{TOTEX} = \boldsymbol{OPEX} + \boldsymbol{CAPEX}
        \label{totex}\\
        &\boldsymbol{OPEX} = \sum_{\substack{l\in L}} c^+_l \cdot \boldsymbol{E^{net, +}_l} -c^-_l \cdot \boldsymbol{E^{net, -}_l}
    	\label{opex}\\
    	&\boldsymbol{CAPEX} = \frac{i(1+i)}{(1+i)^n-1}(\boldsymbol{C^{inv}}+\boldsymbol{C^{rep}})
        \label{capex}\\
        &\boldsymbol{C^{inv}} = \sum_{\substack{u\in U}}b_u\cdot(i^{c1}_u\cdot \boldsymbol{y_u}+i^{c2}_u\cdot \boldsymbol{f_u})
        \label{cinv}\\
        &\boldsymbol{C^{rep}} = \sum_{\substack{u\in U}}\sum_{\substack{r\in R}}\frac{1}{(1+i)^{r\cdot l_u}}\cdot(i^{c1}_u\cdot \boldsymbol{y_u}+i^{c2}_u\cdot \boldsymbol{f_u})
        \label{crep}
    \end{align}

Grid capacity
~~~~~~~~~~~~~~~~~~~~~~~~

The maximum capacity of the local low-voltage transformer is considered.
The electricity export and the import is constrained within the feasibility range of the transformer.

.. _network:

.. figure:: ../images/network.svg
   :align: center

   Energy flows and network constraints in REHO


:ref:`network` distinguishes the:

- Grid = energy flows within the district boundary
- Network = exchanges with the district exterior, through the interface (transformer perspective)

.. math::
        \begin{align}
            &\sum_{b \in \text{B}}   (\boldsymbol{\dot{E}^{gr,+}_{b,l,p,t}} - \boldsymbol{\dot{E}^{gr,-}_{b,l,p,t}})  \cdot d_p \cdot d_t  = \boldsymbol{E^{net,+}_{l,p,t}} - \boldsymbol{ E^{net,-}_{l,p,t} }         \qquad \forall l, p, t \in \text{L, P, T}
            \label{grid constraints}\\
            &\boldsymbol{\dot{E}^{net,\pm}_{l,p,t}}  \leq  \dot{E}^{net, max}_l \qquad \forall l, p, t \in \text{L, P, T}
            \label{Transformer max}
        \end{align}

Outputs
===========================


Decision variables
----------------------------------

- Installed capacities for building-level and district-level units
- Operation time throughout a year

These fully characterize the energy flows at building-level and district-level, as well as the financial flows (investments + operational costs).

Key performance indicators
----------------------------------

The KPIs are divided in four subgroups: Environmental, economical, technical and security indicators.
For more information on how to calculate the KPIs presented below, please refer to :cite:t:`middelhauveRoleDistrictsRenewable2022` - *Section 1.2.5 Key performance indicators*.



Notes on the mobility sector
==============================

The Layer *Mobility* differs slightly from the other Layers in REHO as this energy carrier is expressed in passenger-kilometers ($pkm$) rather than $kWh$. 
The mobility demand is represented through an hourly passenger-kilometer ($pkm$) profile for each typical day, similarly to the other end-use demand profiles. 
The transport units represented in the model include EVs, ICEs, bikes, electric bikes and public transport. 

The model can optimize between the different transport modes. However, it is for now recommended to constrain the modal share using the variables min_share and max_share, as the optimization based on cost does not reflect typical usage of the different transport modes. The `FSO reports <https://www.are.admin.ch/are/fr/home/mobilite/bases-et-donnees/mrmt.html>`_ can be used to find suitable modal split data. 

Electric vehicles (EVs)
----------------------------------
EVs are modelled as a district-level unit (see table :ref:`tbl-district-units`). This conversion unit supplies mobility by transforming electricity, but note that in the model, the unit is not directly connected to the electricity Layer
TBF

Co-optimization
----------------------------------
Multiple districts can be optimized together in order to calculate EV charging exchanges between districts. 
This feature can be used to conduct analyses on EV fleets at the city scale.  
Example 6c demonstrates how to use this feature.