import matplotlib
import pytest
from perfectdays import get_typical_periods

from perfectdays.api.reho import generate_weather_data

# Downloads the weather from PVGIS.
pytestmark = [pytest.mark.slow, pytest.mark.needs_network]

matplotlib.use("Agg")


@pytest.fixture
def qbuildings_data():
    return {'buildings_data': {'Building1': {'x': 2496193, 'y': 1114279, 'z': 402}}}


def test_clustering_quality():
    # Geneva, through PVGIS so that no Swiss grid is needed
    _, quality = get_typical_periods(46.21, 6.14, periods=10, source="pvgis", clustering_evaluation=True,
                                     k_range=[2, 4, 6, 8, 10, 12])
    for figure in (quality.kpis.plot(), quality.stability.plot(), quality.plot_ldc()):
        assert figure.axes


def test_write_weather_files(qbuildings_data, tmp_path):
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}
    typical_periods = generate_weather_data(cluster, qbuildings_data, str(tmp_path))
    assert typical_periods.n_periods == 10
    assert (tmp_path / "timestamp.csv").exists()
