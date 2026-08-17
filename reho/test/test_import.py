import pytest


def test_import_reho_modules():
    modules = [
        'reho',
        'reho.model.reho',
        'reho.model.master_problem',
        'reho.model.sub_problem',
        'reho.model.actors_problem',
        'reho.model.infrastructure',
        'reho.model.preprocessing',
        'reho.model.postprocessing',
        'reho.plotting',
    ]

    for module in modules:
        try:
            __import__(module)
        except ImportError as e:
            pytest.fail(f"Importing {module} module failed: {e}")
