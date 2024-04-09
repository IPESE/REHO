from reho.model.reho import *
import datetime

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
    scenario['EMOO'] = {}
    scenario['specific'] = []
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    parameters = {'Population': 12}

    # Set method options
    method = {'building-scale': True}
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario,
                method=method, parameters=parameters, solver="gurobi")

    # Set specific parameters
    # reho.parameters['TransformerCapacity'] = np.array([1e6, 1e6, 0, 1e6])  # TODO : robustesse of mobility Network
    reho.parameters['Population'] = 9
    reho.parameters['Mode_Speed'] = {'Bike2_district': 20}
    # reho.parameters['DailyDist'] = 9

    # reho.parameters.update(EV_gen.scenario_profiles_temp(cluster))

    # Other params 
    # Mobility demand profile can be changed in the csv file data/mobility/dailyprofiles.csv + function get_demand_profiles

    # Run optimization
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='Mob')

    # Mobility Formatting of results 
    date = datetime.datetime.now().strftime("%d_%H%M")
    result_file_path = 'results/Mob_totex.xlsx'
    df_Unit_t = pd.read_excel(result_file_path, sheet_name="df_Unit_t",
                              index_col=[0, 1, 2, 3])  # refaire sans passer par le xlsx
    df_Grid_t = pd.read_excel(result_file_path, sheet_name="df_Grid_t",
                              index_col=[0, 1, 2, 3])
    # df_Unit_t.index.name = ['Layer','Unit','Period','Time']
    df_Unit_t = df_Unit_t[df_Unit_t.index.get_level_values("Layer") == "Mobility"]
    df_Grid_t = df_Grid_t[df_Grid_t.index.get_level_values("Layer") == "Mobility"]
    df_dd = df_Grid_t[df_Grid_t.index.get_level_values("Hub") == "Network"]
    # df_dd.index = df_dd.index.droplevel('Hub')
    df_dd.reset_index("Hub", inplace=True)

    df_mobility = df_Unit_t[['Units_demand', 'Units_supply']].unstack(level='Unit')
    df_mobility['Domestic_energy'] = df_dd['Domestic_energy']
    df_mobility.sort_index(inplace = True)
    df_mobility.to_excel(f"results/3f_mobility{date}.xlsx")
    print(f"Results are saved in 3f_mobility{date}")
