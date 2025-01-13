from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, egid=['1017073/1017074', '1017109', '1017079', '1030377/1030380'])

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    # Set method options
    method = {'building-scale': True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Run a new optimization with the capacity of PV and electrical heater fixed with the size of the first optimization
    reho.df_fix_Units = reho.results['totex'][0]["df_Unit"]  # load data on the capacity of units
    reho.fix_units_list = ['PV', 'ElectricalHeater_DHW', 'ElectricalHeater_SH']  # select the ones being fixed
    reho.scenario['Objective'] = 'CAPEX'
    reho.scenario['name'] = 'fixed'
    reho.method['fix_units'] = True  # select the method fixing the unit sizes
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='3h')
