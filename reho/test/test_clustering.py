import pytest
from reho.model.preprocessing.weather import *


@pytest.fixture
def qbuildings_data():
    return {'buildings_data': {'Building1': {'x': 2496193, 'y': 1114279, 'z': 402}}}


@pytest.fixture
def weather_data(qbuildings_data):
    return get_weather_data(qbuildings_data).reset_index(drop=True)


def test_clustering(weather_data):
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': [2, 4, 6, 8, 10, 12], 'PeriodDuration': 24}

    attributes = []
    if 'T' in cluster['Attributes']:
        attributes.append('Text')
    if 'I' in cluster['Attributes']:
        attributes.append('Irr')
    if 'W' in cluster['Attributes']:
        attributes.append('Weekday')
    if 'E' in cluster['Attributes']:
        attributes.append('Emissions')

    cl = Clustering(data=weather_data[attributes], nb_clusters=cluster['Periods'], period_duration=cluster['PeriodDuration'],
                    options={"year-to-day": True, "extreme": []})
    cl.run_clustering()

    plot_cluster_KPI_separate(cl.kpis_clu)
    plot_LDC(cl)


def test_write_weather_files(qbuildings_data):
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}
    generate_weather_data(cluster, qbuildings_data)
