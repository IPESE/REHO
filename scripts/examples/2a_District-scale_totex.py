from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader(load_roofs=True)
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(transformer=290, nb_buildings=10)

    # Select clustering options for weather data
    cluster = {'Location': 'Lugano', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)
    parameters = {"TransformerCapacity": np.array([12.12*3, 1e8])}

    # Set method options
    method = {"district-scale": True, "print_logs": True, "refurbishment": False, "include_all_solutions": False,
              'use_pv_orientation': True, 'use_facades': False, "use_dynamic_emission_profiles": True,
              "save_streams": False, "save_timeseries": False, "save_data_input": False}
    DW_params = {'max_iter': 16}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, DW_params=DW_params, solver="gurobi", parameters=parameters)
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'save_all'], filename='Sc0_290_FINAL')
