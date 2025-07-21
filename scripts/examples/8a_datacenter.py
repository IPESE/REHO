from reho.model.reho import *
from reho.plotting import plotting

if __name__ == '__main__':
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, nb_buildings=1)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'GWP'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ["FC", "ETZ", "Battery", "Battery_district", "Battery_IP", "Battery_IP_district",
                                 "H2_storage_IP_district", "rSOC", "MTR", "DataHeat_DHW", "DataHeat_SH"]


    # Set method options
    method = {
        'district-scale': True
    }

    # Initialize available units and grids
    # WARNING: necessary to define all 3 layers Hydrogen / Biomethane / CO2 to enable rSOC or Methanator unit
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'Data': {},
                                             'Heat': {}
                                             })

    grids["Electricity"]["ReinforcementOfNetwork"] = np.array([2000])  # limit the 2000 kW default value (from layers.csv) for export or import electricity
    grids["Heat"]["ReinforcementOfNetwork"] = np.array([0])  # keep the 0 kW default value (from layers.csv) for export or import Heat
    grids["Data"]["ReinforcementOfNetwork"] = np.array([2000])  # keep the 0 kW default value (from layers.csv) for export or import Data

    # enable district units, interperiod storage units for both (True), district only ('district') or building only ('building')
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    # Set parameters
    parameters = {'Network_ext': np.array([500, 500, 0]), 'data_EUD_avg': 50}  # existing capacities of networks in alphabetical order

    DW_params = {'max_iter': 2}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method,
                DW_params=DW_params, solver="gurobi")

    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='8a')

    # Plot results
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()
    plotting.plot_sankey(reho.results['totex'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()

