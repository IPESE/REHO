from reho.model.actors_problem import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader(load_roofs=True, load_facades=True)
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, nb_buildings=40, correct_Uh=True)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['EMOO'] = {}
    scenario['specific'] = ['no_ElectricalHeater_without_HP', 'Owner_Link_Subsidy_to_renovation','Renter_noSub', 'Rent_fix_absolute']
    # Rent_fix2 calculates based on absolute values of the building costs
    # if Rent_fix_increase  is active, the rent increase is considered. and parameter 'Costs_House_upfront_m2_MP' has to be set in parameters to 0

    scenario["name"] = "actors"

    # Choose energy system structure options
    scenario['exclude_units'] = ['ThermalSolar', 'NG_Cogeneration', 'Battery']
    scenario['enforce_units'] = []

    # Set method options
    method = {'actors_problem': True, "renovation": ["window/facade/roof/footprint"], 'use_pv_orientation': True,
              "include_all_solutions": True, "save_streams": False,
              "save_timeseries": False, 'print_logs': True, "save_data_input": True, 'parallel_computation': False}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Define maximum rent affordable
    reho = ActorsProblem(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, DW_params={'max_iter': 4}, solver="gurobiasl")
    reho.parameters['renter_expense_max'] = actors.generate_renter_expense_max(method='absolute', qbuildings_data=qbuildings_data, income=70000)

    # Set value / sampling range for actors epsilon
    bounds = {"Owners": [0.0, 0], "Utility": [0.0, 0.0]}
    reho.sample_actors_epsilon(bounds=bounds, n_samples=1, ins_target=[0])

    #Run actor-based optimization
    reho.actor_decomposition_optimization()

    # Save results
    reho.save_results(format=["pickle"], filename='8a')