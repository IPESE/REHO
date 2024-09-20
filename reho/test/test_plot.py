import os
import pandas as pd
import pytest
from reho.test.test_run import test_run
from reho.plotting import plotting


@pytest.fixture(scope="module", autouse=True)
def generate_test_results():
    if not os.path.exists('results/test_results.pickle'):
        test_run(save_results=True)


@pytest.fixture(scope="module")
def results():
    return pd.read_pickle('results/test_results.pickle')


def test_plot_performance(results):
    try:
        plotting.plot_performance(results, plot='costs', indexed_on='Scn_ID', title="Economical performance").show()
        plotting.plot_performance(results, plot='gwp', indexed_on='Scn_ID', title="Environmental performance").show()
        plotting.plot_performance(results, plot='combined', indexed_on='Scn_ID', title="Combined performance (Economical + Environmental)").show()
    except ImportError as e:
        pytest.fail(f"plot_performance failed: {e}")


def test_plot_expenses(results):
    try:
        plotting.plot_expenses(results, plot='costs', indexed_on='Scn_ID', title="Costs and Revenues").show()
    except ImportError as e:
        pytest.fail(f"plot_expenses failed: {e}")


def test_plot_sankey(results):
    try:
        plotting.plot_sankey(results['totex'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()
    except ImportError as e:
        pytest.fail(f"plot_sankey failed: {e}")


def test_plot_eud(results):
    try:
        plotting.plot_eud(results, label='EN_long', title="End-use demands").show()
    except ImportError as e:
        pytest.fail(f"plot_eud failed: {e}")


def test_plot_profiles(results):
    try:
        units_to_plot = ['ElectricalHeater', 'HeatPump', 'PV', 'NG_Boiler']
        plotting.plot_profiles(results['totex'][0], units_to_plot, label='EN_long', color='ColorPastel', resolution='weekly',
                               title="Energy profiles with a weekly moving average").show()
    except ImportError as e:
        pytest.fail(f"plot_profiles failed: {e}")


def all_plots(results):
    try:
        test_plot_performance(results)
        test_plot_expenses(results)
        test_plot_sankey(results)
        test_plot_eud(results)
        test_plot_profiles(results)
    except ImportError as e:
        pytest.fail(f"Plotting failed: {e}")
