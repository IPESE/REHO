import pytest


def test_import_reho_module():
    try:
        import reho.model.reho
    except ImportError as e:
        pytest.fail(f"Importing reho.model.reho module failed: {e}")


def test_import_plotting_module():
    try:
        import reho.plotting
    except ImportError as e:
        pytest.fail(f"Importing reho.plotting module failed: {e}")


def test_import_reho_package():
    try:
        import reho
    except ImportError as e:
        pytest.fail(f"Importing reho package failed: {e}")
