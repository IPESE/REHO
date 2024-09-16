from reho.model.reho import *

if __name__ == '__main__':
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

    df_mobility = df_Unit_t[['Units_demand','Units_supply']].unstack(level = 'Unit')
    df_mobility['Domestic_energy'] = df_dd['Domestic_energy']
    df_mobility.to_excel("results/3f_mobility.xlsx")