from reho.model.reho import *
import datetime

if __name__ == '__main__':
    date = datetime.datetime.now().strftime("%d_%H%M")
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(transformer=3658, nb_buildings=10) #3112

    # Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['EMOO'] = {}
    scenario['specific'] = []
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    parameters = {'Population': 20}

    # Set method options
    method = {'building-scale': True}
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario,
                method=method, parameters=parameters, solver="baron")

    # Set specific parameters
    # reho.parameters['TransformerCapacity'] = np.array([1e6, 1e6, 0, 1e6])  # TODO : robustesse of mobility Network
    # reho.parameters['Mode_Speed'] = {'Bike2_district': 20}
    # reho.parameters['DailyDist'] = 9

    # reho.parameters.update(EV_gen.scenario_profiles_temp(cluster))

    # Other params 
    # Mobility demand profile can be changed in the csv file data/mobility/dailyprofiles.csv + function get_demand_profiles

    # Run optimization
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='Mob')
    reho.save_mobility_results(filename = f"3f_mobility{date}")

    # # getting parameters for iteration
    print(reho.results_MP["totex"][0][0]["df_Dual_t"]["pi"].xs("Electricity"))
