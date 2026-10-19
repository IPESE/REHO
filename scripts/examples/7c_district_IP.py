from reho.model.reho import *
from reho.plotting import plotting

if __name__ == '__main__':
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, nb_buildings=4)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ["FC", "ETZ", "Battery", "Battery_district", "Battery_IP", "Battery_IP_district",
                                 "H2_storage_IP_district", "rSOC", "MTR", "DHN_hex"]

    # scenario['enforce_units'] = ['HeatPump_DHN']
    # scenario["specific"] = ["enforce_DHN"]

    # Set method options
    method = {
        'interperiod_storage': True,
        'district-scale': True
    }

    # Initialize available units and grids
    # WARNING: necessary to define all 3 layers Hydrogen / Biomethane / CO2 to enable rSOC or Methanator unit
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'Hydrogen': {},
                                             'Biomethane': {},
                                             'CO2': {},
                                             'Heat': {}
                                             })

    grids["Biomethane"]["ReinforcementOfNetwork"] = np.array([0])  # keep the 0 kW default value (from layers.csv) for export or import hydrogen
    grids["CO2"]["ReinforcementOfNetwork"] = np.array([0])  # keep the 0 kW default value (from layers.csv) for export or import hydrogen
    grids["Electricity"]["ReinforcementOfNetwork"] = np.array([15])  # limit the 2000 kW default value (from layers.csv) for export or import electricity
    grids["Heat"]["ReinforcementOfNetwork"] = np.array([10])  # keep the 0 kW default value (from layers.csv) for export or import hydrogen
    grids["Hydrogen"]["ReinforcementOfNetwork"] = np.array([0])  # keep the 0 kW default value (from layers.csv) for export or import hydrogen

    # enable district units, interperiod storage units for both (True), district only ('district') or building only ('building')
    units = infrastructure.initialize_units(scenario, grids, district_data=True, interperiod_data='district')

    # Set parameters
    parameters = {'Network_ext': np.array([0, 0, 15, 10, 0])}  # existing capacities of networks [Electricity, Heat]

    DW_params = {'max_iter': 2}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method,
                DW_params=DW_params, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='7c')

    # Plot results
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()
    plotting.plot_sankey(reho.results['totex'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()
    plotting.plot_electricity_flows(reho.results['totex'][0], color='ColorPastel', day_of_the_year=40, time_range='2 weeks', label='EN_long').show()
    plotting.plot_storage_profile(reho.results['totex'][0], resolution='hourly').show()
