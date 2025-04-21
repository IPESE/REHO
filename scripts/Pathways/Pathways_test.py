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
    scenario['Objective'] = 'OPEX'
    scenario['name'] = 'path_opex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    # Set method options
    method = {'building-scale': True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # set parameters
    Ext_Units = pd.read_excel('results/Units_Ext.xlsx', sheet_name='df_Unit', index_col='Unit')
    #parameters = {'Units_Ext': pd.DataFrame(), "Units_Ext_district": pd.DataFrame()}
    parameters = {'Units_Ext': Ext_Units}

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Plot results
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long',title="Economical performance").show()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='1a_opex')
