from reho.model.postprocessing.sensitivity_analysis import *
from reho.plotting import plotting


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, nb_buildings=1)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids,district_data = True)

    # Set method options
    method = {'building-scale': True}

    # Run sensitivity analysis
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    SA = SensitivityAnalysis(reho, SA_type="Monte_Carlo", sampling_parameters=8)

    SA_parameters = {'Elec_retail': [0.2, 0.45],"share_cars" : [0,0.6], 'DailyDist' : [15,30]}
    SA.build_SA( SA_parameters=SA_parameters,unit_parameter = [])
    SA.run_SA()

    # Save results
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Pareto_ID', label='EN_long', title="Economical performance").show()
    reho.save_results(format=['xlsx', 'pickle'], filename='4b')
