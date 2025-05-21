from reho.model.actors_problem import *


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
    scenario['EMOO'] = {}
    scenario['specific'] = ['Renter_noSub', 'Owner_Link_Subsidy_to_Insulation']
    scenario["name"] = "actors"

    # Choose energy system structure options
    scenario['exclude_units'] = ['ThermalSolar', 'NG_Cogeneration', 'Battery']
    scenario['enforce_units'] = []

    # Set method options
    method = {'actors_problem': True, "refurbishment": True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Define maximum rent affordable (optional)
    reho = ActorsProblem(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, DW_params={'max_iter': 3}, solver="gurobiasl")
    reho.parameters['renter_expense_max'] = actors.generate_renter_expense_max_new(qbuildings_data, income=70000)

    # Set value / sampling range for actors epsilon
    max_profit_utility = reho.get_max_profit_actor("Utility")
    bounds = {"Owners": [0.0, 0.1], "Utility": [0.0, max_profit_utility]}
    reho.sample_actors_epsilon(bounds=bounds, n_samples=3)

    #Run actor-based optimization
    reho.actor_decomposition_optimization()

    # Save results
    reho.save_results(format=["pickle"], filename='6a')