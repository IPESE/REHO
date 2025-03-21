from joblib.testing import param

from reho.model.reho import *
from reho.plotting import plotting
from reho.model.preprocessing.clustering import Clustering
from data_centre_profiles import data_centre_profile
from pathlib import Path
import numpy as np



if __name__ == '__main__':
    # Set path to CSV buildings data
    buildings_filename = str(Path.cwd() / 'data' / 'EPFL_3.csv')

    # Set building parameters
    reader = QBuildingsReader()
    n_house = 1  # 53 buildings in total
    qbuildings_data = reader.read_csv(buildings_filename=buildings_filename, nb_buildings=n_house)

    # Select clustering options for weather data, with custom profiles
    custom_weather_profile = str(Path.cwd() / 'data' / 'profiles' / 'pully_v2.csv')

    # Select clustering options for weather data
    cluster = {'custom_weather': custom_weather_profile,
               'Location': 'Pully',
               'Attributes': ['T', 'I', 'E', 'D'],
               'Periods': 10,
               'PeriodDuration': 24}

    # Cluster data center load profile
    # attributes_cluster_DL = ['Irr', 'Text', 'Weekday', 'DataLoad']
    # df_annual = weather.read_custom_weather(custom_weather_profile)
    # df_annual = df_annual['attributes_cluster_DL']
    # cl = Clustering(data=df_annual, nb_clusters=[10], option={"year-to-day": True, "extreme": []}, pd=24)
    # cl.run_clustering()
    # val_cls = weather.generate_output_data(cl, attributes_cluster_DL, "Pully")
    # data_centre_heat_profile = data_centre_profile(val_cls)
    data_centre_heat_profile = pd.read_csv(str(Path.cwd() / 'data' / 'clustering' / 'DL_Pully_10_24_T_I_E_D.dat'), header=None).to_numpy()

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'GWP'
    scenario['name'] = 'GWP'
    scenario['exclude_units'] = ['HeatPump_Geothermal','HeatPump_Air','HeatPump_Lake','HeatPump_Anergy','HeatPump_DHN', 'ElectricalHeater_SH', 'ThermalSolar'] #'OIL_Boiler',  'NG_Boiler','HeatPump_Air', 'HeatPump_Lake''HeatPump_Anergy''DataHeatSH', #['ThermalSolar', 'Battery', 'NG_Boiler']
    scenario['enforce_units'] = ['ORC_EPFL_district']
    scenario["specific"] = ['enforce_PV_max'] #'enforce_DHN'

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {"Cost_demand_cst": 0.08, "Cost_supply_cst": 0.08},
                                             'Heat': {"Cost_demand_cst": 0.0001, "Cost_supply_cst": 0.0002,  "GWP_supply_cst": 0}})

    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    parameters = {'n_vehicles': np.array([0.0]),
                  'T_DHN_supply_cst': np.repeat(70.0, n_house),
                  'T_DHN_return_cst': np.repeat(60.0, n_house),
                  'TransformerCapacity_heat_t': data_centre_heat_profile}

    # Set method options
    method = {'building-scale': True,
              'save_stream_t': True,
              'use_dynamic_emission_profiles': True,
              'save_streams': True,
              'ORC_all_the_time': False}
    #DW_params = {'max_iter': 2}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, parameters=parameters,
                scenario=scenario, method=method, solver="gurobi") #DW_params=DW_params if district-scale: True
    reho.single_optimization()

    # Save results
    filename = "EPFL_ORC"
    reho.save_results(format=['xlsx', 'pickle'], filename=filename)

    # Plot results
    # plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long',
    #                            title="Economical performance").show()
    #
    # plotting.plot_performance(reho.results, plot='gwp', indexed_on='Scn_ID', label='EN_long',
    #                            title="GWP performance").show()

    plotting.plot_sankey_1(reho.results[scenario['name']][0], label='EN_long', color='ColorPastel').show()

