from reho.model.reho import *
from reho.plotting import plotting


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(transformer=234, nb_buildings=4)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = ['HeatPump_DHN']
    scenario["specific"] = ["enforce_DHN"]

    # Set method options
    # You can specify if the DHN is based on CO2. If not, a water DHN is assumed.
    method = {'building-scale': True, 'DHN_CO2': True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'Heat': {}})

    units = infrastructure.initialize_units(scenario, method, grids, district_data=True)

    # Set specific parameters
    # Specify the temperature of the DHN
    parameters = {'T_DHN_supply_cst': np.repeat(20.0, 4), "T_DHN_return_cst": np.repeat(15.0, 4)}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.get_DHN_costs()  # run one optimization forcing DHN to find costs DHN connection per house
    reho.single_optimization()  # run optimization with DHN costs

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='3e')

    # Plot results
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()
    plotting.plot_sankey(reho.results['totex'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()
