from model.reho import *
from model.preprocessing.QBuildings import *


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
    reho_model = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters,
                    cluster=cluster, scenario=scenario, method=method)

    tariffs_ranges = {'Electricity': {"Cost_demand_cst": [0.05, 0.20], "Cost_supply_cst": [0.15, 0.30]},
                      'NaturalGas': {"Cost_supply_cst": [0.1, 0.30]}}

    reho_model.generate_configurations(n_sample=1, tariffs_ranges=tariffs_ranges)
    # if already have generated configuration, simply import them
    # reho_model.read_configurations()

    # find actors bounds
    reho_model.scenario["name"] = "Lodger"
    reho_model.generate_pareto_actors(n_sample=1, bounds=None, actor="Lodger")
    reho_model.scenario["name"] = "Owner"
    reho_model.generate_pareto_actors(n_sample=1, bounds=None, actor="Owner")
    reho_model.scenario["name"] = "Utility"
    reho_model.generate_pareto_actors(n_sample=1, bounds=None, actor="Utility")

    # define samples
    bound_o = -np.array([reho_model.results[i][0].df_actors.loc["Owner"][0] for i in reho_model.results])
    bound_d = -np.array([reho_model.results[i][0].df_actors.loc["Utility"][0] for i in reho_model.results])
    bounds = {"Utility": [0, bound_d.max()/2], "Owner": [0, bound_o.max()/10], "Lodger": [2.0, 3.0]}

    # Run MOO actors
    reho_model.scenario["name"] = "MOO_actors"
    reho_model.generate_pareto_actors(n_sample=25, bounds=bounds, actor="Lodger")

    print(reho_model.samples, "\n")
    print(reho_model.results["Lodger"][0].df_actors_tariff.xs("Electricity").mean(), "\n")
    print(reho_model.results["Lodger"][0].df_actors)

    # Save results
    SR.save_results(reho_model, save=["pickle_all"], filename='actors_MOO')
