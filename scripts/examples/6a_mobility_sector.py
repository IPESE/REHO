from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, nb_buildings=3)

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


    # SCENARIO 1
    scenario['name'] = 'totex_1'

    # Set parameters
    era = np.sum([qbuildings_data["buildings_data"][b]['ERA'] for b in qbuildings_data["buildings_data"]])
    parameters = {  "Population": era / 46, # here Population is scaled to the number of buildings being optimized (CH : 46m²/cap on average )
                    "DailyDist" : {"long" : 10,
                                   'short' : 26},
                }
                    # verifier que le fichier modalshares.csv est consistent avec les labels de DailyDist, dans ce cas les colonnes devraient être max_short, min_short, max_long, min_long

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids,parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobiasl")
    reho.single_optimization()

    # SCENARIO 2
    scenario['name'] = 'totex_EVchargingprofile'

    # Activate the constraint forcing the charging profile of electric vehicles. 
    scenario['specific'] = ['EV_chargingprofile1',"EV_chargingprofile2"]

    # Run optimization
    reho.scenario = scenario
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='6a')
