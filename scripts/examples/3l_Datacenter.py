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
    scenario['name'] = 'gwp'
    scenario['exclude_units'] = ["Battery", "Battery_district", "DataHeat_DHW", "DataHeat_SH"]


    # Set method options
    method = {'district-scale': True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'Data': {},
                                             'Heat': {}
                                             })
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    # Set parameters
    parameters = {'Network_ext': np.array([500, 500, 0]), 'data_EUD_avg': 50}  # existing capacities of networks in alphabetical order

    DW_params = {'max_iter': 2}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method,
                DW_params=DW_params, solver="gurobi")

    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='3l')

    # Plot results
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()
    plotting.plot_sankey(reho.results['gwp'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()

