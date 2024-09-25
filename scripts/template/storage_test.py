from reho.model.reho import *
from reho.plotting import plotting
from reho.model.preprocessing.clustering import Clustering

if __name__ == '__main__':

    # Set building parameters
    # you can as well define your district from a csv file instead of reading the database
    reader = QBuildingsReader()
    n_house = 1
    qbuildings_data = reader.read_csv(buildings_filename='/Users/ravi/REHO/scripts/template/data/EPFL_2.csv', nb_buildings= n_house)

    # Select weather data
    cluster = {'Location': 'Pully', 'Attributes': ['I', 'T','E','D'], 'Periods': 10, 'PeriodDuration': 24}


    scenario = dict()
    scenario['Objective'] = 'GWP'
    scenario['name'] = 'gwp'
    scenario['exclude_units'] = [] #'OIL_Boiler',  'NG_Boiler','HeatPump_Air', 'HeatPump_Lake''HeatPump_Anergy''DataHeatSH',

    #
    #
    scenario['enforce_units'] = ['Battery_interperiod'] #'HeatPump_Geothermal_district','DHN_out_district','Battery_district','PV_district',
    scenario["specific"] = []

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {"Cost_demand_cst": 0.08, "Cost_supply_cst": 0.08},
                                            "Heat": {"Cost_demand_cst": 0.0001, "Cost_supply_cst": 0.0002,  "GWP_supply_cst": 0}})  #'NaturalGas': {"Cost_demand_cst": 0.01, "Cost_supply_cst": 0.10},
                                                                                                                #"Data": {"Cost_demand_cst": 0.0001, "Cost_supply_cst": 0.0002}}

    units = infrastructure.initialize_units(scenario, grids, district_data= True, storage_data= True)

    parameters = {'n_vehicles': np.array([0.0]), 'T_DHN_supply_cst': np.repeat(70.0, n_house),'T_DHN_return_cst': np.repeat(60.0, n_house)} #, 'Network_supply_heat': np.array([0.0])

    # Set method options
    method = {'building-scale': True,'save_stream_t': True, 'use_dynamic_emission_profiles': True, 'save_streams': True, 'use_Storage_Interperiod': True} #, 'use_pv_orientation': True
    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units,parameters=parameters, grids=grids, cluster=cluster, scenario=scenario, method=method, solver ='gurobi') #parameters=parameters,
    reho.single_optimization()
    # Save results
    filename='storage_test'
    reho.save_results(format=['xlsx', 'pickle'], filename=filename)
    plotting.plot_sankey_1(reho.results['gwp'][0], label='EN_long', color='ColorPastel').show()


