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

    # Choose energy system structure options
    scenario['exclude_units'] = ['ThermalSolar', 'NG_Cogeneration', 'Battery']
    scenario['enforce_units'] = []

    # Set method options
    method = {'actors_problem': True, "refurbishment": True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Initiate the actor-based problem formulation
    reho = ActorsProblem(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, DW_params={'max_iter': 3}, solver="gurobiasl")

    # Generate configurations
    tariffs_ranges = {'Electricity': {"Cost_supply_cst": [0.15, 0.45]},
                      'NaturalGas': {"Cost_supply_cst": [0.10, 0.30]}}
    try:
        reho.read_configurations()  # if configurations were already generated, simply import them
    except FileNotFoundError:
        reho.generate_configurations(n_sample=3, tariffs_ranges=tariffs_ranges)

    # Set value / sampling range for actors epsilon
    actors_epsilon = {"renter_expense_max": 100000, "owner_PIR_min": [0, 0.1]}

    bounds = reho.set_actors_epsilon(actors_epsilon)
    reho.sample_actors_epsilon(bounds=bounds, n_samples=3, linear=False)

    #Run actor-based optimization
    reho.scenario["name"] = "MOO_actors"
    reho.actor_decomposition_optimization(scenario)

    # Save results
    reho.save_results(format=["pickle"], filename='6a')