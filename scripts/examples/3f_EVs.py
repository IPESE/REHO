from reho.model.reho import *

if __name__ == '__main__':
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(transformer=3658, nb_buildings=2)

    # Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    # Set method options
    method = {'building-scale': True}

    # Set specific parameters
    parameters = {'TransformerCapacity': np.array([1e6, 0, 1e6]),  # TODO : robustesse of mobility Network
                  'n_vehicles': 6}

    # Run optimization
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario,
                method=method, parameters=parameters, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='3f')

    # # Formatting of results (quick)
    # result_file_path = 'results/3f_totex.xlsx'
    # df_Unit_t = pd.read_excel(result_file_path, sheet_name="df_Unit_t",
    #                           index_col=[0, 1, 2, 3])  # refaire sans passer par le xlsx
    # df_Unit_t.index.name = ['Layer','Unit', 'Period', 'Time']
    # df_Unit_t = df_Unit_t[df_Unit_t.index.get_level_values("Layer") == "Mobility"]
    # df_mobility = df_Unit_t['Units_demand','Units_supply'].unstack(level = 'Unit')

