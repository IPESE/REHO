from reho.model.reho import *
import time

if __name__ == '__main__':
    # Start time
    start_time = time.time()
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    #qbuildings_data = reader.read_db(district_id=234, egid=['1017073/1017074', '1017109', '1017079', '1030377/1030380'])
    #qbuildings_data = reader.read_db(district_id=16922, nb_buildings=1000)
    qbuildings_data = reader.read_db(district_id=118, nb_buildings=5)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 12, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    #scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['exclude_units']=[]
    scenario['enforce_units'] = []

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Set method options
    method = {'district-scale': True}
    DW_params = {'max_iter': 4}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, DW_params=DW_params, solver="gurobiasl")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='2a118')
    # End time
    end_time = time.time()

    # Calculate elapsed time
    elapsed_time = end_time - start_time
    print(f"Elapsed time: {elapsed_time:.4f} seconds")
