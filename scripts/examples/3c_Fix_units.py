from reho.model.reho import *
from reho.model.preprocessing.QBuildings import QBuildingsReader


if __name__ == '__main__':

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(3658, nb_buildings=1)

    # Set specific parameters
    parameters = {}

    # Select clustering file
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Choose energy system structure options
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration', 'DataHeat_DHW', 'OIL_Boiler', 'DHN_hex', 'HeatPump_DHN']
    scenario['enforce_units'] = []

    method = {}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids=grids)

    # Run optimization
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Run new optimization with the capacity of PV and electrical heater being fixed by the sizes of the first optimization
    reho.df_fix_Units = reho.results['totex'][0]["df_Unit"]                    # load data on the capacity of units
    reho.fix_units_list = ['PV', 'ElectricalHeater_DHW', 'ElectricalHeater_SH']   # select the ones being fixed
    reho.scenario['Objective'] = 'CAPEX'
    reho.scenario['name'] = 'fixed'
    reho.method['fix_units'] = True                                               # select the method fixing the unit sizes
    reho.single_optimization()

    # Save results
    SR.save_results(reho, save=['xlsx', 'pickle'], filename='3c')
