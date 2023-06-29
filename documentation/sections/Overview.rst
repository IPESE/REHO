Overview
++++++++
.. _label_sec_overview:


:Version: |version| (|release|)
:Date: |today|
:Version main developer: Dorsan Lepour (EPFL)
:Short summary: **todo**

.. caution ::
   TO BE COMPLETED


Features
========

Strengths of the model
----------------------

Weaknesses of the model
---------------------------

Nomenclature
============
.. _ssec_nomenclature:

Nomenclature
------------

The following nomenclature is used to characterize the different optimization approaches and the solutions they generate.

- **Centralized vs Decentralized:** is used to characterize the solution generated for the energy system. A very centralized energy system relies on a few capacities of very large size (hydro dams, thermal power plants), whereas a very decentralized one relies on many small units distributed over the territory (PV, domestic batteries, etc.).

- **Building-scale vs District-scale:** a building-scale optimization treats all the considered buildings independently, i.e. each of them is optimized regardless of the presence of the others. In contrast, a district-scale optimization considers the whole building stock as being able to interact, and exploits the synergies of the overall system defined by the buildings to be optimized.

- **Compact vs Decomposed:** This is only related to the district-scale optimization. The compact optimization solves the problem for all the buildings simultaneously ("true" solution, but exponential computational complexity), while the decomposed optimization solves the problem by applying a decomposition algorithm (Dantzig-Wolfe) to break down the problem into a master one (transformer perspective) and slaves ones (each building). The obtained solution is an approximation, but has a linear computational complexity.

There are three different groups of examples, one concerning each of the approaches:

- Decentralized = building-scale (buildings are optimized independently and sequentially)
- Centralized = district-scale, compact (all the buildings are optimized simultaneously)
- Decomposed = district-scale, with decomposition relaxation (buildings are optimized inter-dependently, but not simultaneously. There is a master problem for the district perspective, and one subproblem defined for each building)

This nomenclature is valid both for single optimization or a multi-objective optimization (Pareto front).