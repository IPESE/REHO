"""Tests for the default values and the validation of the option dictionaries."""

import pytest

from reho.model.options import (
    DEFAULT_DW_PARAMS,
    DEFAULT_METHODS,
    DEFAULT_SCENARIO,
    METHOD_DESCRIPTIONS,
    initialise_DW_params,
    initialize_default_methods,
    initialize_default_scenario,
)


class TestMethods:
    def test_defaults_are_complete(self):
        method = initialize_default_methods({})
        assert set(method) == set(DEFAULT_METHODS)

    def test_none_is_accepted(self):
        assert initialize_default_methods(None)["print_logs"] is True

    def test_user_values_win(self):
        assert initialize_default_methods({"print_logs": False})["print_logs"] is False

    def test_building_scale_implies_district_scale(self):
        # The building-scale approach reuses the decomposition with a single MP iteration.
        method = initialize_default_methods({"building-scale": True})
        assert method["district-scale"] is True
        assert method["include_all_solutions"] is False

    def test_actors_problem_implies_district_scale(self):
        method = initialize_default_methods({"actors_problem": True})
        assert method["district-scale"] is True
        assert method["include_all_solutions"] is True

    def test_unknown_option_warns_with_a_suggestion(self):
        with pytest.warns(UserWarning, match="district-scale"):
            initialize_default_methods({"district_scale": True})

    def test_unknown_option_raises_in_strict_mode(self):
        with pytest.raises(KeyError):
            initialize_default_methods({"not_an_option": 1}, strict=True)

    def test_every_option_is_documented(self):
        assert set(METHOD_DESCRIPTIONS) == set(DEFAULT_METHODS)


class TestScenario:
    def test_defaults_are_complete(self):
        scenario = initialize_default_scenario({})
        assert set(scenario) == set(DEFAULT_SCENARIO)
        assert scenario["EMOO"] == {"EMOO_grid": 0.0}

    def test_caller_dictionary_is_not_mutated(self):
        # Walking a Pareto front adds epsilon constraints to scenario['EMOO']; that
        # must not leak back into the script's own dictionary.
        original = {"Objective": "TOTEX", "EMOO": {}}
        completed = initialize_default_scenario(original)
        completed["EMOO"]["EMOO_CAPEX"] = 42
        assert original["EMOO"] == {}

    def test_n_pareto_is_accepted(self):
        scenario = initialize_default_scenario({"nPareto": 3})
        assert scenario["nPareto"] == 3

    def test_unknown_key_warns(self):
        with pytest.warns(UserWarning, match="Objective"):
            initialize_default_scenario({"Objectif": "TOTEX"})


class TestDWParams:
    def test_defaults_and_derived_values(self):
        cluster = {"Periods": 10, "PeriodDuration": 24}
        buildings = {"Building1": {}, "Building2": {}}
        params = initialise_DW_params({}, cluster, buildings)

        assert params["max_iter"] == DEFAULT_DW_PARAMS["max_iter"]
        assert params["n_houses"] == 2
        # Two extreme periods are appended to the typical ones.
        assert params["timesteps"] == 10 * 24 + 2

    def test_building_scale_forces_a_single_iteration(self):
        params = initialise_DW_params({"max_iter": 15}, building_scale=True)
        assert params["max_iter"] == 1

    def test_unknown_key_warns(self):
        with pytest.warns(UserWarning):
            initialise_DW_params({"max_iterations": 4})
