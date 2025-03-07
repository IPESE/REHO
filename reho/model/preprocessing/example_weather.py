from reho.model.reho import *
from reho.model.preprocessing.weather import *
if __name__ == '__main__':

    reader = QBuildingsReader()
    reader.establish_connection('Suisse')  # connect to QBuildings database
    #qbuildings_data = reader.read_db(district_id=5, egid=['2034144/2034143/2749579/2034146/2034145'])
    qbuildings_data = reader.read_db(district_id=7306, nb_buildings=1000)

    Attributes = ['Text', 'Irr']
    nb_clusters = [12, 24, 36, 48]

    df_annual = get_weather_data(qbuildings_data).reset_index(drop=True)
    df_annual = df_annual[Attributes]

    cl = Clustering(data=df_annual, nb_clusters=nb_clusters, period_duration=24, options={"year-to-day": True, "extreme": []})
    cl.run_clustering()

    plot_cluster_KPI_separate(cl.kpis_clu, save_fig=False)
    plot_LDC(cl, save_fig=False)
