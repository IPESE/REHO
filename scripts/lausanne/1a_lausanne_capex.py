from reho.model.reho import *

results = {}  # Dictionary to store results for each district
dist = ['Le Vallon', 'Hôpitaux']
#dist = ['Le Vallon', 'Hôpitaux', 'Victor-Ruffy', 'Béthusy', 'Rue Centrale', 'Chauderon', 'Flon', 'Montbenon', 'Gare_Petit-Chêne', 'Georgette', 'Avant-Poste', 'Marterey', 'Cité', 'Riponne_Tunnel', 'Chailly', 'Plaisance', 'Bois de Rovéréaz', 'Craivavers', 'Devin', 'La Sallaz']
# dist = ['Vennes', 'Route de Berne', 'Valmont', 'Grangette', 'Praz-Séchaud', 'Ch. des Roches', 'Grand-Vennes', 'Sauvabelin', 'Pré-Fleuri', 'Borde', 'Rouvraie', 'Bellevaux', 'Rte du Signal', 'Pré-du-Marché', 'Valentin', 'Pontaise', 'Stade', 'Ancien-Stand', 'Bois-Mermet', 'Bois-Gentil']
# dist = ['Bossons', 'Blécherette', 'Beaulieu', 'Bergières', 'Pierrefleur', 'Maupas', 'Av. d-Echallens', 'Montétan', 'Chablière', 'Valency', 'Rue de Morges', 'Rue de Sébeillon', 'Tivoli', 'Prélaz', 'Gare de Sébeillon', 'Av. de Provence', 'Malley', 'Montoie', 'Vallée de la Jeunesse', 'Pyramides']
# dist = ['Prés-de-Vidy', 'Bourget', 'Bourdonnette', 'Marc-Dufour', 'Milan', 'Les Cèdres_EPFL', 'Cour', 'Mont-d-Or', 'Bellerive', 'Grancy', 'Harpe', 'Av. d-Ouchy', 'Ouchy', 'Montchoisi', 'Elysée', 'Florimont', 'Av. Rambert', 'Chissiez', 'Mon-Repos', 'Av. Secrétan', 'Ch. de la Vuachère']
if __name__ == '__main__':
    for name_district in dist:
        # Set building parameters
        reader = QBuildingsReader()
        qbuildings_data = reader.read_csv(buildings_filename='../lausanne/QBuildings/Lausanne_sectors.csv', district=name_district, nb_buildings=2)

        # Select weather data
        cluster = {'Location': 'Pully', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

        # Set scenario
        scenario = dict()
        scenario['Objective'] = 'CAPEX'
        scenario['name'] = 'capex'
        scenario['exclude_units'] = ['OIL_Boiler', 'WOOD_Stove', 'HeatPump', 'ThermalSolar', 'DataHeat',
                                     'NG_Cogeneration', 'NG_boiler', 'WaterTankSH', 'Battery','PV']
        scenario['enforce_units'] = []

        # Set method options
        method = {'building-scale': True}

        # Initialize available units and grids
        grids = infrastructure.initialize_grids({'Electricity': {"Cost_demand_cst": 0.08, "Cost_supply_cst": 0.20},
                                                 'NaturalGas': {"Cost_demand_cst": 0.06, "Cost_supply_cst": 0.20}}
                                                )#,
                                                 #"Heat": {"Cost_demand_cst": 0.001, "Cost_supply_cst": 0.005}})
        units = infrastructure.initialize_units(scenario, grids)



        # Run optimization
        reho_model = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
        reho_model.single_optimization()

        # Save results in the dictionary
        results[name_district] = reho_model

# Save all results outside the loop
for district, result in results.items():
    reho.save_results(result, format=['xlsx', 'pickle'], filename='lausanne_' + district)
