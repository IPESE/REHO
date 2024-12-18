from reho.model.reho import *

if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, nb_buildings=6)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    grids["Electricity"]["ReinforcementOfNetwork"] = np.array([100, 1000]) # available capacities of networks [Electricity, NaturalGas]
    parameters = {'Network_ext': np.array([100, 1000])} # existing capacities of networks [Electricity, NaturalGas]

    # Set method options
    method = {'district-scale': True}
    DW_params = {'max_iter': 4}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, parameters=parameters, method=method, DW_params=DW_params, solver="gurobiasl")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='3j')
