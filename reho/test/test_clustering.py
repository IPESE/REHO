import pytest
from reho.model.preprocessing.clustering import Clustering
from reho.model.preprocessing.weather import get_weather_data


@pytest.fixture
def qbuildings_data():
    return {'buildings_data': {'Building1': {'x': 2496193, 'y': 1114279, 'z': 402}}}


@pytest.fixture
def weather_data(qbuildings_data):
    return get_weather_data(qbuildings_data).reset_index(drop=True)


@pytest.fixture
def cluster():
    return {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}


def test_clustering(qbuildings_data, weather_data, cluster):
    cl = Clustering(data=weather_data, nb_clusters=[cluster['Periods']], period_duration=cluster['PeriodDuration'], options={"year-to-day": True, "extreme": []})
    cl.run_clustering()
