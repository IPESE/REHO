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

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'  # select an objective function as defined in ampl_model/scenario.mod
    scenario['EMOO'] = {}  # remain empty for now
    scenario['specific'] = []  # remain empty for now
    scenario['name'] = 'totex'  # any name is possible here
    scenario['exclude_units'] = ['Battery']  # specify some units to be excluded
    scenario['enforce_units'] = []  # specify some units to be enforced

    # Set method options (as defined in sub_problem.py > initialize_default_methods)
    # By default a district-scale design is performed with a compact formulation.
    # Watch out the maximum number of buildings is around 10 due to exponential complexity.
    method = {}

    # Available units and grids are part of the scenario and are initialized by REHO:
    #  - scenario['grids'] takes the arguments of configuration.initialize_grids()
    #  - scenario['units'] takes the arguments of configuration.initialize_units()
    # The 'reference' scenario below sets them from the existing technologies of each building.

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, cluster=cluster, scenario='reference', method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='0')

    # Plot results
    # plotting.plot_eud(reho.results).show()
    plotting.plot_combined_profiles(reho.results[reho.scenario['name']][0], units_to_plot=["HeatPump", "PV", "ElectricalHeater", "Battery"]).show()

    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()
    plotting.plot_performance(reho.results, plot='gwp', indexed_on='Scn_ID', label='EN_long', title="Environmental performance").show()
    plotting.plot_sankey(reho.results[reho.scenario['name']][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()
