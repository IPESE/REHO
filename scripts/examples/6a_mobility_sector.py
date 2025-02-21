from reho.model.reho import *
from reho.plotting import plotting

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
    scenario['exclude_units'] = ['NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    # Set method options
    method = {'building-scale': True}

    # SCENARIO 1: Flexible charging profile
    scenario['name'] = 'totex'

    # Set parameters
    era = np.sum([qbuildings_data["buildings_data"][b]['ERA'] for b in qbuildings_data["buildings_data"]])

    # here Population is scaled to the number of buildings being optimized (CH : 46m²/cap on average )
    # 35 km/cap/day, 2 categories of distance (D0 : short and D1 : long)
    parameters = {"Population": era / 46, "DailyDist": {'D0': 25, 'D1': 10}}

    # min max share for each mobility mode and each distance
    modal_split = pd.DataFrame({"min_D0": [0, 0, 0.4, 0.3], "max_D0": [0.1, 0.3, 0.7, 0.7],
                                "min_D1": [0, 0.2, 0.4, 0.3], "max_D1": [0, 0.4, 0.7, 0.7]},
                               index=['MD', 'PT', 'cars', 'EV_district'])

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobiasl")
    reho.modal_split = modal_split # give modal_split as attribute
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

    # Plot results
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()

