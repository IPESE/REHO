from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(district_id=234, nb_buildings=2)

    # Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['EMOO'] = {}
    scenario['exclude_units'] = [ 'NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids,district_data=True)    

    # Set method options
    method = {'building-scale': True}


    # SCENARIO 1: Flexible charging profile
    scenario['name'] = 'totex'

    # Set parameters
    era = np.sum([qbuildings_data["buildings_data"][b]['ERA'] for b in qbuildings_data["buildings_data"]])
    parameters = {"Population": era / 46} # 46m²/person on average

    parameters['DailyDist'], modal_split = EV_gen.mobility_demand_from_WP1data(36, nbins=2) # 36 km/day/person, 2 categories of distance (D0 : short and D1 : long)

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids,parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobiasl")
    reho.modal_split = modal_split
    reho.single_optimization()

    # SCENARIO 2: Fixed charging profile
    scenario['name'] = 'totex_profile'

    # Activate the constraint forcing the charging profile of electric vehicles. 
    scenario['specific'] = ['EV_chargingprofile1', "EV_chargingprofile2"]

    # Run optimization
    reho.scenario = scenario
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='6a')
