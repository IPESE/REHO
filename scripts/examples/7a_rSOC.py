from reho.model.reho import *
from reho.plotting import plotting

if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=5, egid=['2034144/2034143/2749579/2034146/2034145'])

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['NG_Cogeneration', "FC", "ETZ","Battery_IP","H2_storage_IP"]
    scenario['enforce_units'] = []

    # Set method options
    method = {'interperiod_storage': True, "building-scale": False}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {"Cost_supply_cst": 0.30, "Cost_demand_cst": 0.16},
                                             'NaturalGas': {"Cost_supply_cst": 0.15, "Cost_demand_cst": 0.12},
                                             'Hydrogen': {"Cost_supply_cst": 0.45,"Cost_demand_cst": 0.15}, # 5 €/kg H2 (between 3 and 7): 120 MJ/kg --> 5/(120/3.6) = 0.15 €/kWh
                                             'Biomethane': {},
                                             'CO2': {"Cost_supply_cst": 0.01,"Cost_demand_cst": 0},
                                             })

    units = infrastructure.initialize_units(scenario, grids, interperiod_data=True)

    #parameters = {"Network_ext": np.array([10, 10, 0, 0, 0])}
    grids["Electricity"]["ReinforcementOfNetwork"] = np.array(
        [0,15])  # available capacities of networks [Electricity]
    grids["NaturalGas"]["ReinforcementOfNetwork"] = np.array(
        [0])  # available capacities of networks [Electricity]
    grids["Hydrogen"]["ReinforcementOfNetwork"] = np.array(
        [0])  # available capacities of networks [Electricity]
    grids["Biomethane"]["ReinforcementOfNetwork"] = np.array(
        [0])  # available capacities of networks [Electricity]
    grids["CO2"]["ReinforcementOfNetwork"] = np.array(
        [0])  # available capacities of networks [Electricity]
    #grids["Electricity"]["Network_supply_connection"] = 0

    #parameters = {'HydrogenNetExport': 10000,'NetExportTol': 1, "Network_ext": np.array([1000, 0, 1000, 0, 0])}
    parameters = { "Network_ext": np.array([15, 0, 0, 0, 0])}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='7a')

    # Plot results
    # plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()
    # plotting.plot_performance(reho.results, plot='gwp', indexed_on='Scn_ID', label='EN_long', title="Environmental performance").show()
    plotting.plot_sankey(reho.results['totex'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()

    plotting.plot_electricity_flows(reho.results['totex'][0], color='ColorPastel',
                                    day_of_the_year=40, time_range='2weeks', label='EN_long').show()

    # plotting.plot_electricity_flows(reho.results['totex'][0], color='ColorPastel', day_of_the_year=340, time_range='2 weeks', label='EN_long').show()

    plotting.plot_storage_profile(reho.results['totex'][0], resolution='hourly').show()
