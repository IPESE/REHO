from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')

    districts = [ 3658,3112,277, 7724,8538, 13569, 13219,13228]
    for tr in districts:
        qbuildings_data = reader.read_db(transformer=tr, nb_buildings=2)

        # Select weather data
        cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

        # Set scenario
        scenario = dict()
        scenario['Objective'] = 'TOTEX'
        scenario['name'] = 'totex'
        scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
        scenario['enforce_units'] = []

        # Initialize available units and grids
        grids = infrastructure.initialize_grids()
        units = infrastructure.initialize_units(scenario, grids)

        # Set method options
        method = {'district-scale': True}
        DW_params = {'max_iter': 2}

        # Run optimization
        rehovar = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, DW_params=DW_params, solver="gurobiasl")
        rehovar.single_optimization()

        # Save results
        rehovar.save_results(format=['save_all', 'pickle'], filename=f'main_stable_REHO_2buil_{tr}')
