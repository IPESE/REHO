from reho.model.reho import *
import time

tic = time.perf_counter()

scale_list = ['building-scale', 'district-scale']
scenarios_list = ['totex']
nb_buildings_list = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
nb_excl_list = [5, 6, 7, 8]
nb_excl_list.reverse()
excluded_list = ['Battery', 'OIL_Boiler', 'NG_Cogeneration', 'NG_boiler', 'ThermalSolar', 'WaterTankSH', 'HeatPump', 'PV']

results = {}  # Dictionary to store results

if __name__ == '__main__':
    for scale in scale_list:
        method = {scale: True}
        for scenarios in scenarios_list:
            for nb_buildings in nb_buildings_list:
                for nb_excl in nb_excl_list:
                    # Set scenario
                    scenario = dict()
                    if scenarios == 'totex':
                        scenario['Objective'] = 'TOTEX'
                        scenario['EMOO'] = {}
                        scenario['specific'] = []
                        scenario['name'] = scenarios
                    for nb_buildings in nb_buildings_list:
                        # Set building parameters
                        reader = QBuildingsReader()
                        qbuildings_data = reader.read_csv(buildings_filename='../lausanne/QBuildings/Lausanne_sectors.csv', nb_buildings=nb_buildings)

                        # Set specific parameters
                        parameters = {}

                        # Select clustering file
                        cluster = {'Location': 'Pully', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24, 'weather_file': '../lausanne/weather/Pully-hour.dat'}

                        # Choose energy system structure options
                        scenario['exclude_units'] = excluded_list[:nb_excl]
                        scenario['enforce_units'] = []

                        # Initialize available units and grids
                        grids = infrastructure.initialize_grids({'Electricity': {"Cost_demand_cst": 0.08, "Cost_supply_cst": 0.20},
                                                                 'NaturalGas': {"Cost_demand_cst": 0.06, "Cost_supply_cst": 0.20}})
                        units = infrastructure.initialize_units(scenario, grids)

                        # Run optimization
                        reho_model = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters,
                                          cluster=cluster, scenario=scenario, method=method)

                        if 'totex' in scenarios:
                            reho_model.single_optimization()
                        elif 'pareto' in scenarios:
                            reho_model.generate_pareto_curve()

                        # Store results
                        results[(scale, scenarios, nb_buildings, nb_excl)] = reho_model

# Save results outside the loop
for key, result in results.items():
    scale, scenario, nb_buildings, nb_excl = key
    reho.save_results(result, format=['xlsx', 'pickle'], filename=f'{scale}_{scenario}_{nb_buildings}_{nb_excl}')

toc = time.perf_counter()
print(f"Took {(toc-tic)/60:.4f} minutes")
