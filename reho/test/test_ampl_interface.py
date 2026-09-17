"""Tests for the AMPL technology registries.

These check the consistency between the Python registries, the AMPL files on disk
and the units declared in the CSV data, without needing an AMPL license: a typo in
a ``.mod`` file name or a technology added to the data but never wired into the
model is caught here rather than at solve time.
"""

import os
import re

import pandas as pd
import pytest

from reho.model.ampl_interface import (
    BUILDING_UNIT_MODELS,
    DISTRICT_UNIT_MODELS,
    INTERPERIOD_BUILDING_UNIT_MODELS,
    INTERPERIOD_DISTRICT_UNIT_MODELS,
    _REGISTRY_DIRECTORIES,
)
from reho.model.sub_problem import MODEL_STREAMS_TEMPERATURE, _building_timesteps
from reho.paths import file_reader, path_to_ampl_model, path_to_infrastructure, path_to_units

REGISTRIES = {
    "BUILDING_UNIT_MODELS": BUILDING_UNIT_MODELS,
    "DISTRICT_UNIT_MODELS": DISTRICT_UNIT_MODELS,
    "INTERPERIOD_BUILDING_UNIT_MODELS": INTERPERIOD_BUILDING_UNIT_MODELS,
    "INTERPERIOD_DISTRICT_UNIT_MODELS": INTERPERIOD_DISTRICT_UNIT_MODELS,
}


def _registered_files(registry):
    for key, files in registry.items():
        for file_name in [files] if isinstance(files, str) else files:
            yield key, file_name


@pytest.mark.parametrize("name", sorted(REGISTRIES))
def test_registered_model_files_exist(name):
    registry = REGISTRIES[name]
    directory = _REGISTRY_DIRECTORIES[id(registry)]
    for key, file_name in _registered_files(registry):
        assert os.path.isfile(os.path.join(directory, file_name)), \
            f"{name}[{key!r}] points at {file_name}, which does not exist in {directory}"


def test_core_model_files_exist():
    for file_name in ["sub_problem.mod", "master_problem.mod", "scenario.mod",
                      "actors_problem.mod", "actors_mobility.mod"]:
        assert os.path.isfile(os.path.join(path_to_ampl_model, file_name))


def test_pv_variants_exist():
    # PV has two formulations, selected by method['use_pv_orientation'].
    for file_name in ["pv.mod", "pv_orientation.mod"]:
        assert os.path.isfile(os.path.join(path_to_units, file_name))


def test_every_building_unit_type_has_a_model():
    """Each ``UnitOfType`` of building_units.csv must be modelled by a ``.mod`` file."""
    units = file_reader(os.path.join(path_to_infrastructure, "building_units.csv"))
    known = set(BUILDING_UNIT_MODELS) | set(INTERPERIOD_BUILDING_UNIT_MODELS)
    # DHN_pipes is declared as a unit but modelled together with DHN_hex.
    known |= {"DHN_pipes"}
    missing = sorted(set(units["UnitOfType"]) - known)
    assert not missing, f"These building unit types have no registered AMPL model: {missing}"


def test_every_district_unit_has_a_model():
    """Each district unit must be modelled, or reuse a building-scale model."""
    units = file_reader(os.path.join(path_to_infrastructure, "district_units.csv"))
    known = set(DISTRICT_UNIT_MODELS) | set(INTERPERIOD_DISTRICT_UNIT_MODELS)
    # Handled outside the registries: the district battery reuses battery.mod, the EV
    # charger and the mobility modes are declared by mobility.mod / evehicle.mod, and
    # DHN pipes by dhn.mod when the network is enabled.
    known |= {"Battery_district", "EV_charger_district", "DHN_pipes_district"}
    missing = sorted(set(units["Unit"]) - known)
    assert not missing, f"These district units have no registered AMPL model: {missing}"


def test_registry_keys_are_unique_across_scales():
    """A key must not mean two different things in two registries."""
    building = set(BUILDING_UNIT_MODELS) | set(INTERPERIOD_BUILDING_UNIT_MODELS)
    district = set(DISTRICT_UNIT_MODELS) | set(INTERPERIOD_DISTRICT_UNIT_MODELS)
    assert not building & district


def test_model_stream_temperatures_are_parameters_of_the_model():
    """The streams whose temperatures the model computes point at parameters it declares."""
    models = ""
    for directory, file_name in [(path_to_ampl_model, "sub_problem.mod"), (path_to_units, "heatstorage.mod")]:
        with open(os.path.join(directory, file_name)) as model:
            models += model.read()
    for stream, parameters in MODEL_STREAMS_TEMPERATURE.items():
        for parameter in parameters:
            assert re.search(rf"\bparam {parameter}\{{", models), f"{stream}: {parameter} is not a parameter of the model"


def test_stream_temperatures_are_spread_over_the_timesteps():
    index = pd.MultiIndex.from_tuples([(1, 1), (1, 2), (2, 1)], names=["Period", "Time"])
    per_timestep = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0, 60.0], index=pd.MultiIndex.from_tuples(
        [(house, period, time) for house in ["Building1", "Building2"] for period, time in index], names=["House", "Period", "Time"]))
    per_period = pd.Series([7.0, 8.0], index=pd.MultiIndex.from_tuples([("Building1", 1), ("Building1", 2)], names=["House", "Period"]))
    network = pd.Series([1.0, 2.0, 3.0], index=index)

    assert list(_building_timesteps(per_timestep, "Building2", index)) == [40.0, 50.0, 60.0]
    assert list(_building_timesteps(per_period, "Building1", index)) == [7.0, 7.0, 8.0]
    assert list(_building_timesteps(network, "Building1", index)) == [1.0, 2.0, 3.0]
    with pytest.raises(ValueError):
        _building_timesteps(per_period.iloc[:1], "Building1", index)
