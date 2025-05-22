import numpy as np
import pandas as pd

from reho.model.pathway_problem import *
from reho.plotting import plotting
import time

if __name__ == '__main__':
    # read specific column from csv file
    transf = pd.read_csv('../Pathways/QBuildings/QBuildings_SDEWES_updated_2_60B.csv', usecols=['transformer_new'])
    transf_list = transf['transformer_new'].unique().tolist()

    process_time_list = []
    transf_list_2 = []
    n_build_list = []
    error_transf = []
    error_list = []
    #transf_list = ['group_1']
    for transformer in transf_list:
        tic = time.perf_counter()
        try:
            # Set building parameters
            reader = QBuildingsReader()
            qbuildings_data = reader.read_csv(buildings_filename='../Pathways/QBuildings/QBuildings_SDEWES_updated_2_60B.csv',transformer_new=transformer)
            nb_buildings = len(qbuildings_data['buildings_data'])

            # Select clustering options for weather data
            cluster = {'custom_weather': 'data/profiles/Pully-hour.csv', 'Location': 'Pully', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

            # Set scenario
            scenario = dict()
            scenario['Objective'] = 'TOTEX'
            scenario['name'] = 'pathway'
            scenario['exclude_units'] = ['ThermalSolar', 'Battery', 'Battery_district', 'NG_Cogeneration',
                                         'HeatPump_Geothermal_district', 'HeatPump_DHN',
                                         'NG_Cogeneration_district', 'NG_Boiler_district']
            # 'ElectricalHeater'

            # Set method options
            method = {'building-scale': True, 'parallel_computation': True}

            # Initialize available units and grids
            grids = infrastructure.initialize_grids({'Electricity': {"Cost_supply_cst": 0.2810, "Cost_demand_cst": 0.1535}, # (23-04-2025) https://www.lausanne.ch/vie-pratique/energies-et-eau/services-industriels/particuliers/je-choisis-mon-offre/electricite.html?tab=tarifs
                                                     'NaturalGas': {"Cost_supply_cst": 0.1511, "Cost_demand_cst": 0.0}, # (23-04-2025) https://www.lausanne.ch/vie-pratique/energies-et-eau/services-industriels/particuliers/je-choisis-mon-offre/gaz-naturel.html?tab=tarifs
                                                     'Heat': {"Cost_supply_cst": 0.1609, "Cost_demand_cst": 0.000}, # (23-04-2025) https://www.lausanne.ch/vie-pratique/energies-et-eau/services-industriels/professionnels/les-offres/chaleur.html?tab=tarifs
                                                     'Oil': {"Cost_supply_cst": 0.0941, "Cost_demand_cst": 0.000}, #  (23-04-2025) energy content of oil is 137,381 Btu per gallon or 10.63619997 kWh/l (https://www.eia.gov/energyexplained/units-and-calculators/)
                                                     })                                                            # oil migros Lausanne 100.11	CHF/100 l (https://www.migrol.ch/fr/energie-chaleur/acheter-%C3%A9nergie/mazout/commander-mazout/?m=100&zip=1000&city=Lausanne#/)

            grids['Electricity']['ReinforcementOfNetwork'] = np.array([1E6])
            grids['NaturalGas']['ReinforcementOfNetwork'] = np.array([1E6])
            grids['Oil']['ReinforcementOfNetwork'] = np.array([1E6])
            grids['Heat']['ReinforcementOfNetwork'] = np.array([1E8])
            grids['Electricity']['Network_ext'] = 1E6
            grids['NaturalGas']['Network_ext'] = 1E6
            grids['Oil']['Network_ext'] = 1E6
            grids['Heat']['Network_ext'] = 1E8

            units = infrastructure.initialize_units(scenario, grids)

            pathway_parameters = dict()
            pathway_parameters['y_start'] = 2025 # start year for the pathway analysis
            pathway_parameters['y_end'] = 2050 # end year for the pathway analysis
            pathway_parameters['N_steps_pathway'] = 6 # number of points in the analysis

            # Pathway data
            #pathway_data = pd.read_csv('../Pathways/QBuildings/Pathway_SDEWES_test_no_EH_change_PV_300000871_886466.csv')
            pathway_data = pd.read_csv('../Pathways/QBuildings/System_pathway_SDEWES_partial_curve.csv')

            reho_path = PathwayProblem(qbuildings_data=qbuildings_data, units=units, grids=grids, pathway_parameters= pathway_parameters, pathway_data=pathway_data, cluster=cluster, scenario=scenario, method=method, solver="gurobi", group=transformer)
            reho_path.execute_pathway_building_scale(pathway_unit_use=True)
            #plotting.plot_performance(reho_path.results, plot='costs', indexed_on='Pareto_ID', label='EN_long',title="Economical performance").show()
            # Save results
            reho_path.save_results(format=['pickle'], filename=f'pathway_{transformer}')
        except Exception as e:
            error_transf.append(transformer)
            error_list.append(e)
            print(f"Error with transformer {transformer}: {e}")
        toc = time.perf_counter()
        process_time_list.append((toc - tic) / 60)  # time in minutes
        transf_list_2.append(transformer)
        n_build_list.append(nb_buildings)

    # save the process time in a csv file
    process_time_df = pd.DataFrame({'Transformer': transf_list, 'N Buildings': n_build_list, 'Process time': process_time_list})
    process_time_df.to_csv('../Pathways/results/process_time.csv', index=False)

    error_transf_df = pd.DataFrame({'Transformers': error_transf, 'Error': error_list})
    error_transf_df.to_csv('../Pathways/results/error_transf.csv', index=False)