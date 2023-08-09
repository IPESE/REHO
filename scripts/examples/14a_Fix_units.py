from model.reho import *
from model.preprocessing.QBuildings import QBuildingsReader


if __name__ == '__main__':

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse-old')
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
    grids = structure.initialize_grids()
    units = structure.initialize_units(scenario, grids=grids)

    # Run optimization
    reho_model = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method)
    reho_model.single_optimization()

    # Run new optimization with the capacity of PV and electrical heater being fixed by the sizes of the first optimization
    reho_model.df_fix_Units = reho_model.results['totex'][0].df_Unit                    # load data on the capacity of units
    reho_model.fix_units_list = ['PV', 'ElectricalHeater_DHW', 'ElectricalHeater_SH']   # select the ones being fixed
    reho_model.scenario['Objective'] = 'CAPEX'
    reho_model.scenario['name'] = 'fixed'
    reho_model.method['fix_units'] = True                                               # select the method fixing the unit sizes
    reho_model.single_optimization()

    # Save results
    SR.save_results(reho_model, save=['xlsx', 'pickle'], filename='14a')
