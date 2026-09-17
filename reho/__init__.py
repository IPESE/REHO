"""REHO - Renewable Energy Hub Optimizer.

A decision support tool for sustainable urban energy system planning, developed
at EPFL by the Industrial Process and Energy Systems Engineering (IPESE) group.

The objects a run script needs are re-exported here::

    from reho import REHO, QBuildingsReader, initialize_grids, initialize_units

    reader = QBuildingsReader()
    qbuildings_data = reader.read_csv("data/buildings.csv", nb_buildings=2)

    grids = initialize_grids()
    units = initialize_units(scenario={"exclude_units": []}, grids=grids)

    reho = REHO(qbuildings_data, units, grids,
                scenario={"Objective": "TOTEX", "name": "totex"},
                method={"building-scale": True})
    reho.single_optimization()
    reho.save_results(format=["xlsx", "pickle"], filename="my_run")

These names are resolved lazily (:pep:`562`), so ``import reho`` stays cheap: the
heavy scientific stack is only imported when one of them is actually used.

See also
--------
reho.model.reho.REHO : running an optimization.
reho.model.options : the ``method``, ``scenario`` and ``DW_params`` dictionaries.
reho.plotting.plotting : plotting the results.
"""

__all__ = [
    "ActorsModel",
    "Infrastructure",
    "MasterProblem",
    "QBuildingsReader",
    "REHO",
    "SubProblem",
    "configure_logging",
    "initialize_grids",
    "initialize_units",
]

#: Public name -> module that defines it, used by the lazy ``__getattr__`` below.
_LAZY_EXPORTS = {
    "ActorsModel": "reho.model.actors_problem",
    "Infrastructure": "reho.model.infrastructure",
    "MasterProblem": "reho.model.master_problem",
    "QBuildingsReader": "reho.model.preprocessing.QBuildings",
    "REHO": "reho.model.reho",
    "SubProblem": "reho.model.sub_problem",
    "configure_logging": "reho.logger",
    "initialize_grids": "reho.model.infrastructure",
    "initialize_units": "reho.model.infrastructure",
}


def __getattr__(name):
    try:
        module_name = _LAZY_EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None

    import importlib

    value = getattr(importlib.import_module(module_name), name)
    globals()[name] = value  # cache, so the lookup happens only once
    return value


def __dir__():
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
