from reho import QBuildingsReader, REHO, initialize_grids, initialize_units
from reho.plotting import plotting

if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db({'transformers': 5, 'egid': ['2034144/2034143/2749579/2034146/2034145']})

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ["FC", "ETZ", "Battery_IP", "Battery", "HeatPump_Geothermal"]
    scenario['enforce_units'] = []

    # Set method options
    method = {'interperiod_storage': True}

    # Initialize available units and grids
    # WARNING: necessary to define all 3 layers Hydrogen / Biomethane / CO2 to enable rSOC or Methanator unit
    # The electricity network is limited to 15 kW, without reinforcement, and the hydrogen network raised from its 0 kW default (from layers.csv) to 100 kW
    grids = initialize_grids({'Electricity': {'Network_capacity_existing': 15, 'Network_capacity_options': []},
                                             'Hydrogen': {"Cost_supply_cst": 0.45, "Cost_demand_cst": 0.2,  # default export price = 0.15 CHF/kWh (5 CHF/kg H2)
                                                          'Network_capacity_existing': 100},
                                             'Biomethane': {},
                                             'CO2': {},
                                             })

    units = initialize_units(scenario, grids, interperiod_data=True)  # enable interperiod storage

    # Set parameters
    parameters = {}

    # Annual hydrogen export can be forced in the parameters
    # parameters['HydrogenAnnualExport'] = 20e3  # kWh
    # scenario['specific'] = ['forced_H2_annual_export']

    # A continuous daily hydrogen export can be forced (value is a variable in the optimization) it can be 0 actually if not attractive
    scenario['specific'] = ['forced_H2_fixed_daily_export']

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='7b')

    # Plot results
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()
    plotting.plot_sankey(reho.results['totex'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()
    plotting.plot_electricity_flows(reho.results['totex'][0], color='ColorPastel', day_of_the_year=40, time_range='2 weeks', label='EN_long').show()
    plotting.plot_storage_profile(reho.results['totex'][0], resolution='weekly').show()
