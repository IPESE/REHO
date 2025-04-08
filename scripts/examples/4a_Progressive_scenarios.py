from reho.model.reho import *
from reho.plotting import plotting


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
    scenario['EMOO'] = {}
    scenario['specific'] = []

    # Set method options
    method = {'building-scale': True}

    # Set specific parameters
    parameters = {}

    # Scenario 1 Oil boiler
    scenario['name'] = 'Oil'
    scenario['exclude_units'] = ['ThermalSolar', 'HeatPump', 'ElectricalHeater', 'PV']
    scenario['enforce_units'] = []
    grids = infrastructure.initialize_grids({'Electricity': {}, 'Oil': {}})
    units = infrastructure.initialize_units(scenario, grids)

    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Scenario 2 HP + PV
    scenario['name'] = 'HP + PV'
    scenario['exclude_units'] = ['ThermalSolar', 'OIL_Boiler']
    scenario['enforce_units'] = []
    units = infrastructure.initialize_units(scenario, grids)

    reho.scenario = scenario
    reho.units = units
    reho.infrastructure = infrastructure.Infrastructure(qbuildings_data, units, grids)
    reho.build_infrastructure_SP()
    for b in qbuildings_data['buildings_data']:
        reho.buildings_data[b]['Th_supply_0'] = 45
        reho.buildings_data[b]['Th_return_0'] = 35
    reho.single_optimization()

    # Scenario 3 EV
    scenario['name'] = 'EV'
    scenario['exclude_units'] = ['ThermalSolar', 'OIL_Boiler', 'Bike_district', 'ICE_district', 'ElectricBike_district']
    scenario['enforce_units'] = ['EV_district']

    grids = infrastructure.initialize_grids({'Electricity': {}, 'Oil': {}, 'Gasoline': {}, 'Mobility': {}})
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    reho.scenario = scenario
    reho.units = units
    reho.infrastructure = infrastructure.Infrastructure(qbuildings_data, units, grids)
    reho.build_infrastructure_SP()
    reho.single_optimization()

    # Scenario 4 ICT
    scenario['name'] = 'ICT'
    scenario['exclude_units'] = ['ThermalSolar', 'OIL_Boiler', 'Bike_district', 'ICE_district', 'ElectricBike_district', 'DataHeat_SH']
    scenario['enforce_units'] = ['EV_district', 'DataHeat_DHW']

    grids = infrastructure.initialize_grids({'Electricity': {}, 'Oil': {}, 'Gasoline': {}, 'Mobility': {},
                                             'Data': {"Cost_demand_cst": 1, "GWP_demand_cst": 0}})
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    reho.scenario = scenario
    reho.units = units
    reho.infrastructure = infrastructure.Infrastructure(qbuildings_data, units, grids)
    reho.build_infrastructure_SP()
    reho.single_optimization()

    # Scenario 5 Isolation
    scenario['name'] = 'Isolation'
    for b in qbuildings_data['buildings_data']:
        reho.buildings_data[b]['U_h'] = 0.4 * qbuildings_data['buildings_data'][b]['U_h']

    reho.scenario = scenario
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='4a')

    # Additional data
    era = reho.results['Oil'][0]['df_Buildings'].ERA.sum()

    # Gasoline avoided costs = EV_consumption * 4 (efficiency ratio ICE/EV) * gasoline_price
    gasoline_price = 0.24  # CHF/kWh
    gasoline_gwp = 0.32  # kgCO2/kWh
    EV_consumption = reho.results['EV'][0]['df_Annuals'].loc[("Electricity", "EV_charger_district"), "Demand_MWh"] - reho.results['EV'][0]['df_Annuals'].loc[("Electricity", "EV_charger_district"), "Supply_MWh"]
    gasoline_cost = 1000 * EV_consumption * 4 * gasoline_price / era
    gasoline_impact = 1000 * EV_consumption * 4 * gasoline_gwp / era

    # ICT avoided costs = ICT_consumption * 1.3 (mean PUE for Switzerland) * electricity_price
    electricity_price = 0.33  # CHF/kWh
    electricity_gwp = 0.13  # kgCO2/kWh
    ict_cost = 1000 * reho.results['ICT'][0]['df_Annuals'].loc[("Data", "Network"), "Demand_MWh"] * 1.3 * electricity_price / era
    ict_impact = 1000 * reho.results['ICT'][0]['df_Annuals'].loc[("Data", "Network"), "Demand_MWh"] * 1.3 * electricity_gwp / era

    # Isolation costs and impact
    isolation_cost = 5.4  # CHF/m2/yr (already annualized for 50 years)
    isolation_impact = 0.076  # kgCO2/m2/yr (already annualized for 50 years)

    additional_costs = {'mobility': [gasoline_cost, gasoline_cost, 0, 0, 0],
                        'ict': [ict_cost, ict_cost, ict_cost, 0, 0],
                        'isolation': [0, 0, 0, 0, isolation_cost]}
    additional_costs['no_ict_profit'] = False  # data processing profits can be included in the costs or not

    additional_gwp = {'mobility': [gasoline_impact, gasoline_impact, 0, 0, 0],
                      'ict': [ict_impact, ict_impact, ict_impact, 0, 0],
                      'isolation': [0, 0, 0, 0, isolation_impact]}

    # Plot results
    plotting.plot_performance(reho.results, plot='costs', per_m2=True, additional_costs=additional_costs, title="Economical performance").show()
    plotting.plot_performance(reho.results, plot='gwp', per_m2=True, additional_gwp=additional_gwp, title="Environmental performance").show()
