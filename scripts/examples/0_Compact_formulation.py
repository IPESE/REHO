import subprocess

from reho.model.reho import *
from reho.plotting import plotting
from reho.test.test_examples import test_all_examples

if __name__ == '__main__':
        
    # Set building parameters
    reader = QBuildingsReader()  # load QBuildingsReader class
    reader.establish_connection('Suisse')  # connect to QBuildings database
    # qbuildings_data = reader.read_db({'egid': ['2034144/2034143/2749579/2034146/2034145']})  # read data
    qbuildings_data = reader.read_db({'egid': '954117'}, nb_buildings=5) 

    # Select clustering options for weather data
    #  - I refers to Irradiance, T to Temperature, and W to Weekday
    #  - specify the desired number of typical days
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Enforce the existing energy system of each building, to model the reference case
    enforce_units, exclude_units, pv_capacities = reader.get_reference_reho_units(qbuildings_data['buildings_data'])

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'  # select an objective function as defined in ampl_model/scenario.mod
    scenario['EMOO'] = {}  # remain empty for now
    scenario['specific'] = []  # remain empty for now
    scenario['name'] = 'reference'  # any name is possible here
    scenario['exclude_units'] = exclude_units  # specify some units to be excluded
    scenario['enforce_units'] = enforce_units  # specify some units to be enforced

    # Set method options (as defined in sub_problem.py > initialize_default_methods)
    # By default a district-scale design is performed with a compact formulation.
    # Watch out the maximum number of buildings is around 10 due to exponential complexity.
    method = {'fix_units': bool(pv_capacities)}

    # Initialize available units and grids
    # The enforced units are only kept if their layer is enabled: an oil-heated building needs the Oil layer.
    grids = infrastructure.initialize_grids({'Electricity': {}, 'NaturalGas': {}, 'Oil': {}, 'Wood': {}, 'Heat': {}})
    units = infrastructure.initialize_units(scenario, grids)  # units are based on data/infrastructure/building_units.csv

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    if pv_capacities:  # fix the existing PV capacities (kW)
        reho.df_fix_Units = pd.DataFrame({'Units_Mult': pv_capacities, 'Units_Use': 1})
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='0')

    # Plot results
    # plotting.plot_eud(reho.results).show()
    plotting.plot_combined_profiles(reho.results[reho.scenario['name']][0], units_to_plot=["HeatPump", "PV", "ElectricalHeater", "Battery"]).show()

    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()
    plotting.plot_performance(reho.results, plot='gwp', indexed_on='Scn_ID', label='EN_long', title="Environmental performance").show()
    plotting.plot_sankey(reho.results[reho.scenario['name']][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()
