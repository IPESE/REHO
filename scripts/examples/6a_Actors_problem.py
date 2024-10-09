from reho.model.actors_problem import *


if __name__ == '__main__':

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX_bui'
    scenario['EMOO'] = {}
    scenario['specific'] = []

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, nb_buildings=2)

    # Set specific parameters
    parameters = {}

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T'], 'Periods': 10, 'PeriodDuration': 24}

    # Choose energy system structure options
    scenario['exclude_units'] = ['ThermalSolar', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    # Set method options
    method = {'actors_problem': True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Initiate the actor-based problem formulation
    reho = ActorsProblem(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")

    # Generate configurations
    tariffs_ranges = {'Electricity': {"Cost_supply_cst": [0.15, 0.45]},
                      'NaturalGas': {"Cost_supply_cst": [0.10, 0.30]}}
    try:
        reho.read_configurations()  # if configurations were already generated, simply import them
    except FileNotFoundError:
        reho.generate_configurations(n_sample=2, tariffs_ranges=tariffs_ranges)

    # Find actors bounds
    reho.scenario["name"] = "Renters"
    reho.execute_actors_problem(n_sample=1, bounds=None, actor="Renters")
    reho.scenario["name"] = "Owners"
    reho.execute_actors_problem(n_sample=1, bounds=None, actor="Owners")
    reho.scenario["name"] = "Utility"
    reho.execute_actors_problem(n_sample=1, bounds=None, actor="Utility")

    # Define samples
    bound_o = -np.array([reho.results[i][0]["df_Actors"].loc["Owners"][0] for i in reho.results])
    bound_d = -np.array([reho.results[i][0]["df_Actors"].loc["Utility"][0] for i in reho.results])
    bounds = {"Utility": [0, bound_d.max()/2], "Owners": [0, bound_o.max()/10], "Renters": [2.0, 3.0]}

    # Run actor-based optimization
    reho.scenario["name"] = "MOO_actors"
    reho.execute_actors_problem(n_sample=2, bounds=bounds, actor="Renters")

    print(reho.samples, "\n")
    print(reho.results["Renters"][0]["df_Actors_tariff"].xs("Electricity").mean(), "\n")
    print(reho.results["Renters"][0]["df_Actors"])

    # Save results
    reho.save_results(format=["save_all"], filename='actors_MOO')
