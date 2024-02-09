Releases
++++++++

How to cite
===========

.. caution::
   TO DO

Related works
=====================

.. grid:: 1 2 1 2

    .. grid-item::

        :bdg-primary:`Serves as basis for the model`

    .. grid-item::

        :bdg-secondary:`Produced using the model`

    .. grid-item::

        :octicon:`mortar-board` Academic publications

    .. grid-item::

        :octicon:`organization` Student projects


Thesis
~~~~~~~~~~~~~~~~~~~~~~~~
The two following thesis have been published in relation with REHO and provides detailed insights on the optimization tool.

.. dropdown:: :bdg-primary:`REHO basis` *On the Role of Districts as Renewable Energy Hubs, Middelhauve*   :cite:p:`middelhauveRoleDistrictsRenewable2022`
    :icon: mortar-board

    Presents the energy hub concept and extends it to the district level. The thesis describes the use of PV orientations and problem decomposition.


.. dropdown:: :bdg-primary:`REHO basis` *Model-based sizing of building energy systems with renewable sources, Stadler*   :cite:p:`stadlerModelbasedSizingBuilding2019`
    :icon: mortar-board

    Presents the building energy system modelization and serves as a basis for the AMPL model.


Journal and conference papers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Journal and conference papers provide the methodology on specific aspects of REHO.

.. dropdown:: :bdg-primary:`REHO basis` *Decomposition Strategy for Districts as Renewable Energy Hubs, Middelhauve* :cite:p:`middelhauve2022decomposition`
    :icon: mortar-board

    Presents the decomposition algorithm used for district-scale optimization.


.. dropdown:: :bdg-primary:`REHO basis` *Potential of Photovoltaic Panels on Building Envelopes for Decentralized District Energy Systems, Middelhauve*   :cite:p:`middelhauve2021potential`
    :icon: mortar-board

    Presents the model for the consideration of PV panels orientation on the roofs and facades of the buildings.


.. dropdown:: :bdg-secondary:`Uses REHO` *From Local Energy Communities Towards National Energy System: A Grid-Aware Techno-Economic Analysis, Terrier* :cite:p:`terrierLocalEnergyCommunities2023`
    :icon: mortar-board

    Presents a analysis over the decision-making trends within energy communities and their integration in the national energy infrastructure.


.. dropdown:: :bdg-secondary:`Uses REHO` *Clustering and typification of urban districts for Energy System Modelling, Loustau* :cite:p:`loustauClusteringTypificationUrban2023`
    :icon: mortar-board

    Presents a methodology to identify district types in a regional or national territory to optimize them with REHO. Allows to extrapolate REHO results at larger scale.

.. dropdown:: :bdg-secondary:`REHO basis` *Contribution of Model Predictive Control in the Integration of Renewable Energy Sources within the Built Environment, Stadler* :cite:p:`stadlerMPC2018`
    :icon: mortar-board

    Presents the model predictive control of building energy systems and a methodology to identify typical climatic zones in Switzerland.


Student projects
~~~~~~~~~~~~~~~~~~~~~~~~

Several master projects have been carried out using REHO. While the reports did not follow peer-review from a journal, they present various applications of REHO.

.. dropdown:: :bdg-primary:`REHO basis` *Intégration du service de refroidissement dans REHO, Aviolat* :cite:p:`aviolatIntegrationServiceRefroidissement2023`
    :icon: organization

    Presents the integration of the cooling service in the model. **French**

.. dropdown:: :bdg-primary:`REHO basis` *Demand Aggregation in a District Energy System Perspective, Lacorte* :cite:p:`lacorteDemandAggregationDistrict`
    :icon: organization

    Presents the modelling of long-term storage technologies.

.. dropdown:: :bdg-primary:`REHO basis` *Contribution of Storage Technologies to Renewable Energy Hubs, Mathieu* :cite:p:`mathieuContributionStorageTechnologies`
    :icon: organization

    Presents the modelling of long-term storage technologies.

.. dropdown:: :bdg-secondary:`Uses REHO` *Techno-Economic Study of Local Energy Community in the Canton of Geneva, Suermondt* :cite:p:`suermondtTechnoeconomicStudyLocal2023`
    :icon: organization

    Presents a case study on a district-scale optimization in Geneva.



License
=======


Copyright (C) <2021-2023> <Ecole Polytechnique Fédérale de Lausanne (EPFL), Switzerland>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License. You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

Code versions
==============

REHO is available as an open-source and collaborative Python library.

It is deployed as a PyPI package (https://pypi.org/project/REHO/) and can be installed with:

.. code-block:: bash

   pip install REHO

The developer version can be accessed from its GitHub repository (https://github.com/IPESE/REHO) and installed with:

.. code-block:: bash

   git clone https://github.com/IPESE/REHO.git