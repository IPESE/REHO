from reho.model.reho import *
from reho.plotting import plotting

if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    qbuildings_data = reader.read_csv(buildings_filename='../Pathways/QBuildings/Chauderon_3builds.csv')

    # Select clustering options for weather data
    cluster = {'custom_weather': 'data/profiles/Pully-hour.csv', 'Location': 'Pully', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'CAPEX'
    scenario['name'] = 'fixed'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    #df_fix_Units = pd.read_excel('results/3h_totex.xlsx', sheet_name='df_Unit', index_col='Unit')
    #fix_units_list = ['PV', 'ElectricalHeater_DHW', 'ElectricalHeater_SH']  # select the ones being fixed

    # Set method options
    method = {'building-scale': True, 'fix_units': True}  # select the method fixing the unit sizes

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.df_fix_Units = pd.read_excel('results/3h_totex.xlsx', sheet_name='df_Unit', index_col='Unit')
    reho.fix_units_list = ['PV', 'ElectricalHeater_DHW', 'ElectricalHeater_SH']  # select the ones being fixed
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='3h_csv')

    # Plot results
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long',title="Economical performance").show()