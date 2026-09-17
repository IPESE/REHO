"""Tests for the AMPL technology registries.

These check the consistency between the Python registries, the AMPL files on disk
and the units declared in the CSV data, without needing an AMPL license: a typo in
a ``.mod`` file name or a technology added to the data but never wired into the
model is caught here rather than at solve time.
"""

import os

import pytest

from reho.model.ampl_interface import (
    BUILDING_UNIT_MODELS,
    DISTRICT_UNIT_MODELS,
    INTERPERIOD_BUILDING_UNIT_MODELS,
    INTERPERIOD_DISTRICT_UNIT_MODELS,
    _REGISTRY_DIRECTORIES,
)
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
                      "actors_problem.mod", "actors_mobility.mod", "data_stream.dat"]:
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
