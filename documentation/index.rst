.. REHO documentation master file

.. to build :
..      cd documentation
..      make html

Renewable Energy Hub Optimizer
==============================

Renewable Energy Hub Optimizer (REHO) is a decision support tool for sustainable urban energy system planning.

It is developed by EPFL (Switzerland), within the Industrial Process and Energy Systems Engineering (IPESE) group.

REHO simultaneously addresses the optimal design and operation of capacities, catering to multi-objective
considerations across economic, environmental, and efficiency criteria. Its MILP framework, multi-objective
optimization, multi-scale adaptability, consideration of diverse end-use demands, and multi-energy integration drive
informed decision-making for renewable energy deployment in urban areas.

This documentation introduces REHO and highlights its key features and contributions to the field of
sustainable energy system planning.

.. figure:: images/district_documentation.svg


Contents
=========

.. grid::

   .. grid-item-card:: :octicon:`home` Overview
      :link: sections/1_Overview.html

      Start with a quick summary of what is REHO and what it can do.

.. grid::

    .. grid-item-card:: :octicon:`book` Model
        :link: sections/3_Model.html

        Describes the mathematical formulation behind the REHO model.

    .. grid-item-card:: :octicon:`package` Package structure
        :link: sections/4_Package_structure.html

        Describes the content of the REHO package, with a description of functions you will come to use.

.. grid::

   .. grid-item-card:: :octicon:`rocket` Getting started
        :link: sections/5_Getting_started.html

        Check out how to install and run REHO on your machine, setting up different configurations.

   .. grid-item-card:: :octicon:`code-review` Examples
        :link: sections/6_Examples.html

        Still not sure how you should use REHO? Here are examples that include various features.

.. grid::

   .. grid-item-card:: :octicon:`git-branch` Releases
        :link: sections/2_Releases.html

        Find here the code versions, the license, how to cite and the list of the related works.

.. toctree::
   :maxdepth: 1
   :hidden:

   sections/1_Overview
   sections/2_Releases
   sections/3_Model
   sections/4_Package_structure
   sections/5_Getting_started
   sections/6_Examples
   sections/7_Contribute
   sections/Appendix


.. Indices and tables
   ==================
   * :ref:`genindex`
   * :ref:`modindex`
   * :ref:`search`

Downloading REHO
=======================

.. grid::

    .. grid-item-card:: Part-Time User? 😎
        :padding: 3

        REHO is available as a `PyPI package <https://pypi.org/project/REHO/>`__
        and can be installed via pip with:

        ++++++++++++++++++++++

        .. code-block:: bash

            pip install --extra-index-url https://pypi.ampl.com REHO

.. grid::

    .. grid-item-card:: Talented Developer? 🏄

        REHO is an open-source and collaborative Python library.
        Full code can be accessed from the `REHO repository <https://github.com/IPESE/REHO>`__ and project cloned using the command:

        ++++

        .. code-block:: bash

            git clone https://github.com/IPESE/REHO.git


Main contributors
=================

.. image:: images/logos/ipese-logo-black.svg
   :width: 600
   :height: 150
   :align: right
   :class: only-light

.. image:: images/logos/ipese-logo-white.svg
   :width: 600
   :height: 150
   :align: right
   :class: only-dark

* Dorsan **Lepour** (2020-...)
* Joseph **Loustau** (2022-2024)
* Cédric **Terrier** (2021-...)
