"""Tests for the replacement costs of the units.

The offline tests check that the sub-problem and the master problem charge the replacements the same
way, and that the costs of a building add up those of its units. The slow one evaluates the formula of
the model with AMPL and compares it with an independent computation.
"""

import os
import re

import pytest

from reho.paths import path_to_ampl_model


def _model(file_name):
    with open(os.path.join(path_to_ampl_model, file_name)) as model:
        return model.read()


def _replacement_formula(file_name):
    """Right-hand side of the Costs_Unit_replacement constraint, with its whitespace normalised."""
    match = re.search(r"subject to Costs_Unit_replacement\{.*?\}\s*:\s*Costs_Unit_rep\[u\]\s*=(.*?);", _model(file_name), re.S)
    assert match, f"Costs_Unit_replacement not found in {file_name}"
    return " ".join(match.group(1).split())


def _reference(lifetime, n_years=25, i_rate=0.02):
    """Replacement cost of one unit of investment, from a walk through the horizon.

    The unit is bought again each time its lifetime ends before the horizon, and each purchase is charged
    for the share of its lifetime spent within the horizon, discounted to the present.
    """
    cost, start = 0.0, lifetime
    while start < n_years - 1e-9:
        cost += min(1.0, (n_years - start) / lifetime) / (1 + i_rate) ** start
        start += lifetime
    return cost


def test_the_sub_problem_and_the_master_problem_replace_units_alike():
    assert _replacement_formula("sub_problem.mod") == _replacement_formula("master_problem.mod")


def test_the_replacement_costs_of_a_building_add_up_those_of_its_units():
    # The master problem receives the costs of each building from Costs_House_rep.
    match = re.search(r"subject to Costs_House_replacement\{h in House\}\s*:\s*(.*?);", _model("sub_problem.mod"), re.S)
    assert match
    assert " ".join(match.group(1).split()) == "Costs_House_rep[h] = sum{u in UnitsOfHouse[h]} Costs_Unit_rep[u]"


@pytest.mark.parametrize("lifetime, expected", [(25, 0.0), (30, 0.0), (60, 0.0), (15, (10 / 15) / 1.02**15)])
def test_reference_replacement_costs(lifetime, expected):
    assert _reference(lifetime) == pytest.approx(expected)


@pytest.mark.slow
@pytest.mark.needs_ampl
def test_the_model_charges_the_replacements_like_the_reference():
    from reho.model.ampl_interface import create_ampl_session

    lifetimes = [5, 7.5, 8, 10, 12, 15, 20, 25, 30, 60]
    formula = _replacement_formula("sub_problem.mod").replace("Costs_Unit_inv[u]", "1")
    ampl = create_ampl_session("highs", print_logs=False)
    ampl.eval(f"""
        set Units;
        param n_years default 25;
        param i_rate default 0.02;
        param lifetime{{u in Units}};
        param replacement{{u in Units}} := {formula};
    """)
    names = [f"unit{i}" for i in range(len(lifetimes))]
    ampl.getSet("Units").setValues(names)
    ampl.getParameter("lifetime").setValues(dict(zip(names, lifetimes, strict=True)))
    for name, lifetime in zip(names, lifetimes, strict=True):
        assert ampl.getParameter("replacement").get(name) == pytest.approx(_reference(lifetime), abs=1e-12), lifetime
