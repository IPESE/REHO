"""The actors problem of examples 8a and 8b, on two buildings.

The master problem of the actors is where the numbers of the model are the furthest apart - yearly
costs of a building against subsidies and tariffs - and where a coefficient out of scale made the
presolve of the solver report a feasible problem as infeasible. These runs guard that.
"""

import pytest

import reho.model.preprocessing.actors as actors
from reho.model.actors_problem import ActorsModel
from reho.model.infrastructure import initialize_grids, initialize_units
from reho.model.preprocessing.QBuildings import QBuildingsReader

# Reads the QBuildings database, downloads the weather and solves a problem.
pytestmark = [pytest.mark.slow, pytest.mark.needs_ampl, pytest.mark.needs_network]

CLUSTER = {"Location": "Geneva", "Attributes": ["T", "I", "W"], "Periods": 10, "PeriodDuration": 24}


def build_model(specific, max_iter):
    reader = QBuildingsReader(load_roofs=True, load_facades=True, correct_Uh=True)
    reader.establish_connection("Geneva")
    qbuildings_data = reader.read_db({"transformers": 234}, nb_buildings=2)

    scenario = {"Objective": "TOTEX", "EMOO": {}, "name": "actors", "specific": specific,
                "exclude_units": ["ThermalSolar", "NG_Cogeneration", "Battery"], "enforce_units": []}
    method = {"actors_problem": True, "renovation": ["window/facade/roof/footprint"], "include_all_solutions": True,
              "save_streams": False, "save_timeseries": False, "print_logs": False, "parallel_computation": False}
    grids = initialize_grids()
    units = initialize_units(scenario, grids)
    return ActorsModel(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=dict(CLUSTER),
                       scenario=scenario, method=method, DW_params={"max_iter": max_iter}, solver="highs"), qbuildings_data


def results_of(model):
    return next(iter(next(iter(model.results.values())).values()))


def test_actors_problem_with_the_rents_of_the_buildings_compared():
    """Example 8a: the rents per m2 of the buildings stay within 20% of each other."""
    model, qbuildings_data = build_model(["no_ElectricalHeater_without_HP", "Owner_Link_Subsidy_to_renovation",
                                          "Renter_noSub", "Rent_fix_absolute"], max_iter=2)
    model.parameters["renter_expense_max"] = actors.generate_renter_expense_max(method="absolute", qbuildings_data=qbuildings_data, income=70000)
    model.sample_actors_epsilon(bounds={"Owners": [0.0, 0.0], "Utility": [0.0, 0.0]}, n_samples=1, ins_target=[0])
    model.actor_decomposition_optimization()

    performance = results_of(model)["df_Performance"]
    assert (performance.loc[model.infrastructure.House, "renter_expense"] > 0).all(), "the renters pay nothing"


def test_the_renter_expenses_of_the_baseline_are_what_they_pay_today():
    """Example 8b: the expenses the renters may not exceed come from the existing system."""
    model, _ = build_model(["no_ElectricalHeater_without_HP", "Owner_Link_Subsidy_to_renovation",
                            "Renter_noSub", "Rent_fix_increase"], max_iter=2)
    expenses = actors.generate_renter_expense_max(method="increase", reho_model=model)

    assert list(expenses.columns) == ["renter_expense_max"]
    assert (expenses["renter_expense_max"] > 0).all(), "the baseline leaves nothing for the renters to pay"
