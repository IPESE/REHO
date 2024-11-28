from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(transformer=234, nb_buildings=6)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    grids["Electricity"]["ReinforcementTrOfLayer"] = np.array([30, 100]) # available capacities of transformer
    parameters = {'Transformer_Ext': np.array([30, 1e6]), # available capacities of grids (Electricity, NaturalGas)
                  "CostTransformer_inv1": np.array([1, 0]), # fixed cost of grids reinforcement (Electricity, NaturalGas)
                  "CostTransformer_inv2": np.array([1, 0])} # variable cost of grids reinforcement (Electricity, NaturalGas)

    # Set method options
    method = {'district-scale': True}
    DW_params = {'max_iter': 4}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, parameters=parameters, method=method, DW_params=DW_params, solver="gurobiasl")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='2a')
