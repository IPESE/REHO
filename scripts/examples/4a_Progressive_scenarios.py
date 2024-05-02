from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(transformer=3658, nb_buildings=1)

    # Select weather data
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
    scenario['exclude_units'] = ['ThermalSolar', 'HeatPump', 'ElectricalHeater', 'PV', 'DataHeat']
    scenario['enforce_units'] = []
    grids = infrastructure.initialize_grids({'Electricity': {}, 'Oil': {}, 'Data': {}})
    units = infrastructure.initialize_units(scenario, grids)

    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # SCENARIO 2 HP + PV #
    scenario['name'] = 'HP + PV'
    scenario['exclude_units'] = ['ThermalSolar', 'OIL_Boiler', 'DataHeat']
    scenario['enforce_units'] = ['HeatPump_Geothermal']
    units = infrastructure.initialize_units(scenario, grids)

    reho.scenario = scenario
    reho.units = units
    reho.infrastructure = infrastructure.infrastructure(qbuildings_data, units, grids)
    reho.buildings_data['Building1']['temperature_heating_supply_C'] = 42
    reho.buildings_data['Building1']['temperature_heating_return_C'] = 34
    reho.single_optimization()

    # SCENARIO 3 EV  #
    scenario['name'] = 'EV'
    scenario['exclude_units'] = ['ThermalSolar', 'OIL_Boiler', 'DataHeat']
    scenario['enforce_units'] = ['EV_district']
    units = infrastructure.initialize_units(scenario, grids, district_data=True)
    reho.parameters['n_vehicles'] = 6

    reho.scenario = scenario
    reho.units = units
    reho.infrastructure = infrastructure.infrastructure(qbuildings_data, units, grids)
    reho.single_optimization()

    # SCENARIO 4 Data #
    scenario['name'] = 'Data'
    scenario['exclude_units'] = ['ThermalSolar', 'OIL_Boiler', 'DataHeat_SH']
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    reho.scenario = scenario
    reho.units = units
    reho.infrastructure = infrastructure.infrastructure(qbuildings_data, units, grids)
    reho.single_optimization()

    # SCENARIO 5 PV + HP + isolation #
    scenario['name'] = 'Isolation'
    reho.buildings_data['Building1']['U_h'] = 0.5 * qbuildings_data['buildings_data']['Building1']['U_h']

    reho.scenario = scenario
    reho.single_optimization()

    # Save results
    reho.save_results(format=['pickle'], filename='4a')
