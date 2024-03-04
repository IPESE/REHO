Examples
++++++++

This section provides a brief overview of REHO's capabilities based on a few scripts examples
(available in https://github.com/IPESE/REHO/tree/main/scripts/examples).

These examples should allow you to test the various features of the tool.

You can create specific subfolders in the `scripts` directory for your own case-studies.
The content there (code, results, and figures) will be ignored by the git versioning.

1. Building-scale
--------------------

Single-optimization
====================================
.. literalinclude:: ../../scripts/examples/1a_building-scale_totex.py
   :language: python

Pareto curve
====================================
.. literalinclude:: ../../scripts/examples/1b_building-scale_Pareto.py
   :language: python

2. District-scale
--------------------

Single-optimization
====================================
.. literalinclude:: ../../scripts/examples/2a_district-scale_totex.py
   :language: python

Pareto curve
====================================
.. literalinclude:: ../../scripts/examples/2b_district-scale_Pareto.py
   :language: python

3. Various features
--------------------

Buildings as .csv files
====================================
.. literalinclude:: ../../scripts/examples/3a_Read_csv.py
   :language: python

Stochastic profiles for EUD
====================================
.. literalinclude:: ../../scripts/examples/3b_Stochastic_profiles.py
   :language: python

Fix units size
====================================
.. literalinclude:: ../../scripts/examples/3c_Fix_units.py
   :language: python

Change heat pump temperature
====================================
.. literalinclude:: ../../scripts/examples/3d_HP_T_source.py
   :language: python

Add other energy layers
====================================
.. literalinclude:: ../../scripts/examples/3e_Layers.py
   :language: python

Include electric vehicles
====================================
.. literalinclude:: ../../scripts/examples/3f_EVs.py
   :language: python

Integrate a district heating network
====================================
.. literalinclude:: ../../scripts/examples/3g_DHN.py
   :language: python

Connect to ELCOM database for electricity prices
===========================================================
.. literalinclude:: ../../scripts/examples/3h_Electricity_prices.py
   :language: python

Progressive integrated system
====================================
.. literalinclude:: ../../scripts/examples/4a_Progressive_scenarios.py
   :language: python

.. literalinclude:: ../../scripts/examples/4b_Progressive_scenarios_csv.py
   :language: python

Include photovoltaics on facades
====================================
.. literalinclude:: ../../scripts/examples/5a_Facades.py
   :language: python



