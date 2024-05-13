from reho.model.postprocessing.sensitivity_analysis import *
from reho.plotting import plotting

if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(transformer=3658, nb_buildings=2)

    # Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Set method options
    method = {'building-scale': True}

    # Run sensitivity analysis
    reho_model = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    SA = sensitivity_analysis(reho_model, SA_type="Monte_Carlo", sampling_parameters=8)

    SA_parameter = {'Elec_retail': [0.2, 0.45], 'Elec_feedin': [0.0, 0.15], 'NG_retail': [0.2, 0.4], "PVA_efficiency_ref": [0.10, 0.35]}
    SA.build_SA(unit_parameter=['Cost_inv1', 'Cost_inv2'], SA_parameter=SA_parameter)
    SA.run_SA()

    # Save results
    plotting.plot_performance(reho_model.results, plot='costs', indexed_on='Pareto_ID', label='EN_long').show()
    reho_model.save_results(format=['xlsx', 'pickle'], filename='3j')
