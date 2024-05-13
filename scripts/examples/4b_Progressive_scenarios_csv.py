from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    qbuildings_data = reader.read_csv(buildings_filename='../template/data/buildings.csv', nb_buildings=1)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['EMOO'] = {}
    scenario['specific'] = []

    # Set method options
    method = {'building-scale': True}

    # Set specific parameters
    parameters = {}

    # SCENARIO 1 Oil boiler #
    scenario['name'] = 'Oil'
    scenario['exclude_units'] = ['DHN_hex', 'ThermalSolar', 'HeatPump', 'PV', 'WOOD_Stove', 'DataHeat']
    scenario['enforce_units'] = ['OIL_Boiler']

    grids = infrastructure.initialize_grids({'Electricity': {}, 'Oil': {}, 'Wood': {}, 'Heat': {}, 'Data': {}})
    units = infrastructure.initialize_units(scenario, grids)

    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method,
                solver="gurobi")
    reho.single_optimization()

    # SCENARIO 2 Wood stove #
    scenario['name'] = 'Wood'
    scenario['exclude_units'] = ['DHN_hex', 'ThermalSolar', 'HeatPump', 'PV', 'OIL_Boiler', 'DataHeat']
    scenario['enforce_units'] = ['WOOD_Stove']
    units = infrastructure.initialize_units(scenario, grids)

    reho.scenario = scenario
    reho.units = units
    reho.infrastructure = infrastructure.Infrastructure(qbuildings_data, units, grids)
    reho.single_optimization()

    # SCENARIO 3 Electrical Heater #
    scenario['name'] = 'ElectricalHeater'
    scenario['exclude_units'] = ['ThermalSolar', 'HeatPump', 'PV', 'OIL_Boiler', 'WOOD_Stove', 'DataHeat']
    scenario['enforce_units'] = []
    units = infrastructure.initialize_units(scenario, grids)

    reho.scenario = scenario
    reho.units = units
    reho.infrastructure = infrastructure.Infrastructure(qbuildings_data, units, grids)
    reho.single_optimization()

    # SCENARIO 4 HP + PV #
    scenario['name'] = 'HP'
    scenario['exclude_units'] = ['ThermalSolar', 'OIL_Boiler', 'WOOD_Stove', 'DataHeat']
    scenario['enforce_units'] = []
    units = infrastructure.initialize_units(scenario, grids)

    reho.scenario = scenario
    reho.units = units
    reho.infrastructure = infrastructure.Infrastructure(qbuildings_data, units, grids)
    reho.single_optimization()

    # SCENARIO 5 EV #
    scenario['name'] = 'EV'
    scenario['exclude_units'] = ['ThermalSolar', 'OIL_Boiler', 'WOOD_Stove', 'DataHeat']
    scenario['enforce_units'] = ['EV_district']
    units = infrastructure.initialize_units(scenario, grids, district_data=True)
    reho.parameters['n_vehicles'] = 2

    reho.scenario = scenario
    reho.units = units
    reho.infrastructure = infrastructure.Infrastructure(qbuildings_data, units, grids)
    reho.single_optimization()

    # SCENARIO 6 Data #
    scenario['name'] = 'Data'
    scenario['exclude_units'] = ['ThermalSolar', 'NG_Boiler', 'OIL_Boiler', 'WOOD_Stove', 'DataHeat_SH']
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    reho.scenario = scenario
    reho.units = units
    reho.infrastructure = infrastructure.Infrastructure(qbuildings_data, units, grids)
    reho.single_optimization()

    # Save results
    reho.save_results(format=['pickle'], filename='4b')
