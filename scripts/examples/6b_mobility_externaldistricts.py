from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(transformer=3658, nb_buildings=2)

    # Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['EMOO'] = {}
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']

    parameters = {  "Population": 9,
                    "max_share_cars": 0.7,
                    "min_share_cars": 0.4,
                }
    
    set_indexed = {"Districts": [8538 ,13569]}

    # Load parameters representing external district demands and supply
    with open(f'data/mobility/6b_extdistrict_parameters.pickle', 'rb') as handle:
        parameters_extdistrict = pickle.load(handle)
    for param in parameters_extdistrict.keys():
        parameters[param] = parameters_extdistrict[param]

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids,district_data=True)

    # Set method options
    method = {'building-scale': True,
              'external_district' : True
              }
    # Run optimization
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids,parameters=parameters, cluster=cluster,set_indexed=set_indexed, scenario=scenario, method=method, solver="gurobiasl")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='6b')
