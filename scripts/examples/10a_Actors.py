from reho.model.reho import *
from reho.model.preprocessing.QBuildings import *


if __name__ == '__main__':

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX_bui'
    scenario['EMOO'] = {}
    scenario['specific'] = []
    scenario['name'] = 0

    # Set building parameters
    reader = QBuildingsReader(load_roofs=True)
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(10559, nb_buildings=2)

    # Set specific parameters
    parameters = {}

    # Select clustering file
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T'], 'Periods': 10, 'PeriodDuration': 24}

    # Choose energy system structure options
    scenario['exclude_units'] = ['ThermalSolar']
    scenario['enforce_units'] = []

    # to obtain a district scale design with many buildings, a decomposition of the problem is needed
    method = {'use_pv_orientation': True, 'actors_cost': True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {"Cost_demand_cst": 0.10, "Cost_supply_cst": 0.26},
                                        'NaturalGas': {"Cost_demand_cst": 0.06, "Cost_supply_cst": 0.20}})
    units = infrastructure.initialize_units(scenario, grids)

    # Generate configuration
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters,
                    cluster=cluster, scenario=scenario, method=method, solver="gurobi")

    tariffs_ranges = {'Electricity': {"Cost_demand_cst": [0.05, 0.20], "Cost_supply_cst": [0.15, 0.30]},
                      'NaturalGas': {"Cost_supply_cst": [0.1, 0.30]}}

    reho.generate_configurations(n_sample=1, tariffs_ranges=tariffs_ranges)
    # if already have generated configuration, simply import them
    # reho.read_configurations()

    # find actors bounds
    reho.scenario["name"] = "Renters"
    reho.generate_pareto_actors(n_sample=1, bounds=None, actor="Renters")
    reho.scenario["name"] = "Owners"
    reho.generate_pareto_actors(n_sample=1, bounds=None, actor="Owners")
    reho.scenario["name"] = "Utility"
    reho.generate_pareto_actors(n_sample=1, bounds=None, actor="Utility")

    # define samples
    bound_o = -np.array([reho.results[i][0]["df_Actors"].loc["Owners"][0] for i in reho.results])
    bound_d = -np.array([reho.results[i][0]["df_Actors"].loc["Utility"][0] for i in reho.results])
    bounds = {"Utility": [0, bound_d.max()/2], "Owners": [0, bound_o.max()/10], "Renters": [2.0, 3.0]}

    # Run MOO actors
    reho.scenario["name"] = "MOO_actors"
    reho.generate_pareto_actors(n_sample=25, bounds=bounds, actor="Renters")

    print(reho.samples, "\n")
    print(reho.results["Renters"][0]["df_Actors_tariff"].xs("Electricity").mean(), "\n")
    print(reho.results["Renters"][0]["df_Actors"])

    # Save results
    SR.save_results(reho, save=["save_all"], filename='actors_MOO')
