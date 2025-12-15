import numpy as np
import pandas as pd
from pathlib import Path

from reho.model.pathway_problem import *
from reho.plotting import plotting
import time

if __name__ == '__main__':
    buildings_filename = str(Path(__file__).parent / 'QBuildings' / 'QBuildings_SDEWES_updated_regbl_60B.csv')
    #pathways_filename = str(Path(__file__).parent / 'QBuildings' / 'System_pathway_SDEWES.csv')
    pathways_filename = str(Path(__file__).parent / 'QBuildings' / 'System_pathway_SDEWES_phase_out.csv')

    # read specific column from csv file
    transf = pd.read_csv(buildings_filename, usecols=['transformer_new'])
    transf_list = transf['transformer_new'].unique().tolist()

    process_time_list = []
    transf_list_2 = []
    n_build_list = []
    error_transf = []
    error_list = []
    transf_list = [ 'group_1']
    for transformer in transf_list:
        tic = time.perf_counter()
        try:
            # Set building parameters
            reader = QBuildingsReader()
            qbuildings_data = reader.read_csv(buildings_filename=buildings_filename,transformer_new=transformer)
            #qbuildings_data = reader.read_csv(buildings_filename=buildings_filename, egid = [883347, 882759, 886145, 886827, 884388, 886398, 2118598, 280002000, 886772])

            nb_buildings = len(qbuildings_data['buildings_data'])

            # Select clustering options for weather data
            cluster = {'custom_weather': 'data/profiles/Pully-hour.csv', 'Location': 'Pully', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

            # Set scenario
            scenario = dict()
            scenario['Objective'] = 'TOTEX'
            scenario['name'] = 'pathway'
            scenario['exclude_units'] = ['Battery', 'Battery_district', 'NG_Cogeneration',
                                         'HeatPump_Geothermal_district', 'HeatPump_DHN',
                                         'NG_Cogeneration_district', 'NG_Boiler_district']

            # Set method options
            method = {'building-scale': True, 'parallel_computation': True}

            path_to_custom_layers = str(Path(__file__).parent.parent / 'data' / 'layers_UrbanTwin_wood.csv')
            available_grids = {'Electricity': {}, 'NaturalGas': {}, 'Heat': {}, 'Oil': {}, 'Wood': {}}

            # Initialize available units and grids
            grids = infrastructure.initialize_grids(available_grids, file=path_to_custom_layers)

            grids['Electricity']['ReinforcementOfNetwork'] = np.array([1E6])
            grids['NaturalGas']['ReinforcementOfNetwork'] = np.array([1E6])
            grids['Oil']['ReinforcementOfNetwork'] = np.array([1E6])
            grids['Heat']['ReinforcementOfNetwork'] = np.array([1E8])
            grids['Electricity']['Network_ext'] = 1E6
            grids['NaturalGas']['Network_ext'] = 1E6
            grids['Oil']['Network_ext'] = 1E6
            grids['Heat']['Network_ext'] = 1E8

            path_to_custom_units = str(Path(__file__).parent.parent / 'data' / 'building_units_UrbanTwin.csv')
            units = infrastructure.initialize_units(scenario, grids, building_data=path_to_custom_units)

            # Set pathway methods
            path_methods = dict()
            path_methods['generate_pathway'] = False
            path_methods['optimize_pathway'] = True
            #path_methods['exclude_pathway_units'] = ['WOOD_Stove']

            pathway_parameters = dict()
            pathway_parameters['y_start'] = 2025 # start year for the pathway analysis
            pathway_parameters['y_end'] = 2050 # end year for the pathway analysis
            pathway_parameters['N_steps_pathway'] = 6 # number of points in the analysis

            # Pathway data
            #pathway_data = pd.read_csv('../Pathways/QBuildings/Pathway_SDEWES_no_EH_ST_change_PV_300000871_886466.csv')
            pathway_data = pd.read_csv(pathways_filename)

            reho_path = PathwayProblem(qbuildings_data=qbuildings_data,units=units,grids=grids,pathway_parameters=pathway_parameters,
                                       pathway_data=pathway_data,cluster=cluster,scenario=scenario,method=method,solver="gurobiasl",
                                       path_methods=path_methods,group=transformer)
            reho_path.execute_pathway_building_scale()

            #plotting.plot_performance(reho_path.results,plot='costs',indexed_on='Pareto_ID',label='EN_long',title="Economical performance").show()
            # Save results
            reho_path.save_results(format=['xlsx'], filename=f'pathway_out_{transformer}')

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
    process_time_df.to_csv(str(Path(__file__).parent /'results'/'process_time.csv'), index=False)

    error_transf_df = pd.DataFrame({'Transformers': error_transf, 'Error': error_list})
    error_transf_df.to_csv(str(Path(__file__).parent /'results'/'error_transf.csv'), index=False)