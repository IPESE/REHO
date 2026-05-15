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
    scenario['exclude_units'] = ["FC", "ETZ", "Battery_IP"]
    scenario['enforce_units'] = ["rSOC", "MTR", "CO2_storage_IP", "CH4_storage_IP"]

    # Set method options
    method = {'interperiod_storage': True}

    # Initialize available units and grids
    # WARNING: necessary to define all 3 layers Hydrogen / Biomethane / CO2 to enable rSOC or Methanator unit
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'Hydrogen': {},
                                             'Biomethane': {},
                                             'CO2': {},
                                             })

    grids["Electricity"]["ReinforcementOfNetwork"] = np.array([5])  # limit the 2000 kW default value (from layers.csv) for export or import electricity
    grids["Hydrogen"]["ReinforcementOfNetwork"] = np.array([0])  # keep the 0 kW default value (from layers.csv) for export or import hydrogen

    units = infrastructure.initialize_units(scenario, grids, interperiod_data=True)  # enable interperiod storage

    # Set parameters
    parameters = {}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='7a')

    # Plot results
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()
    plotting.plot_sankey(reho.results['totex'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()
    plotting.plot_electricity_flows(reho.results['totex'][0], color='ColorPastel', day_of_the_year=40, time_range='2 weeks', label='EN_long').show()
    plotting.plot_storage_profile(reho.results['totex'][0], resolution='hourly').show()
