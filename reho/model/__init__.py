"""Optimization model: problem formulation, pre-processing and post-processing.

- :mod:`reho.model.reho` - user-facing entry point (:class:`~reho.model.reho.REHO`).
- :mod:`reho.model.master_problem` / :mod:`reho.model.sub_problem` - the two levels
  of the Dantzig-Wolfe decomposition.
- :mod:`reho.model.infrastructure` - units, layers and grids of the energy system.
- :mod:`reho.model.options` - the ``method``, ``scenario`` and ``DW_params`` dictionaries.
- :mod:`reho.model.ampl_interface` - AMPL sessions and the technology model registries.
- ``ampl_model/`` - the AMPL files that hold the MILP formulation itself.
- :mod:`reho.model.preprocessing` / :mod:`reho.model.postprocessing` - inputs and results.
"""
