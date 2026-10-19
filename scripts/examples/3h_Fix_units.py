from reho.model.reho import *
from reho.plotting import plotting


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
    scenario['exclude_units'] = []
    scenario['enforce_units'] = []

    # Set method options
    method = {'building-scale': True, 'fix_units': True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Scenario 1: min TOTEX
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Scenario 2: min TOTEX with fixed units
    # Give dataframe to fix Units_Mult and Units_Use. The index of the dataframe contains the units being fixed !
    reho.scenario['name'] = 'units_fixed'
    df_fix_units = pd.DataFrame([15, 15, 15, 15], index=["PV_Building" + str(i) for i in range(1, 5)], columns=["Units_Mult"])
    df_fix_units["Units_Use"] = 1
    reho.df_fix_Units = df_fix_units
    reho.single_optimization()

    # Scenario 3: min TOTEX with existing units
    # Run optimization with units already installed (PV), but the optimization can install more capacity
    # The index of the dataframe contains the units being fixed !
    reho.method["fix_units"] = False
    reho.scenario["name"] = "units_ext"
    reho.parameters["Units_Ext"] = pd.DataFrame([15, 15, 15, 15], index=["PV_Building" + str(i) for i in range(1, 5)], columns=["Units_Ext"])
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='3h')
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()
