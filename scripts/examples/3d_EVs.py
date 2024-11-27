import datetime
from reho.model.reho import *

if __name__ == '__main__':
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, egid=['1017073/1017074', '1017109', '1017079', '1030377/1030380'])

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']

    # Set method options
    method = {'building-scale': True}

    # Set specific parameters
    parameters = dict()

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })

    units = infrastructure.initialize_units(scenario, grids, method, district_data=True)

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario,
                method=method, parameters=parameters, solver="gurobi")
    reho.single_optimization()

    # Save results
    date = datetime.datetime.now().strftime("%d_%H%M")
    reho.save_results(format=['xlsx', 'pickle'], filename='3f')

    # Formatting of results (quick)
    result_file_path = 'results/3f_totex.xlsx'
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
    df_mobility.to_excel(f"results/3f_mobility{date}.xlsx")

