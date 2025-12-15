import pandas as pd
from reho.model.pathway_problem import *
from reho.plotting import plotting
import time

if __name__ == '__main__':
    results_folder = 'results_PSCC'
    results_path = str(Path(__file__).parent / 'results' / f'{results_folder}')

    year = 2030
    path_methods = dict()
    #path_methods['optimize_pathway'] = True
    path_methods['enforce_pathway'] = True

    buildings_filename = str(Path(__file__).parent / 'QBuildings' / 'QBuildings_SDEWES_updated_regbl_60B_todelete.csv')
    pathways_filename = str(Path(__file__).parent / 'QBuildings' / 'System_pathway_SDEWES.csv')
    #pathways_filename = str(Path(__file__).parent / 'QBuildings' / 'System_pathway_SDEWES_phase_out.csv')

    # read specific column from csv file
    transf = pd.read_csv(buildings_filename, usecols=['transformer_new'])
    #transf_list = transf['transformer_new'].unique().tolist()
    transf_list = ['group_1']

    process_time_list = []
    transf_list_2 = []
    n_build_list = []
    error_transf = []
    error_list = []
    #transf_list = [ 'group_24']
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
            #scenario['Objective'] = 'TOTEX'
            scenario['Objective'] = ['OPEX', 'CAPEX']  # for multi-objective optimization two objectives are needed
            #scenario['Objective'] = ['CAPEX', 'GWP']  # for multi-objective optimization two objectives are needed
            scenario['nPareto'] = 2  # number of points per objective (total number of optimizations = nPareto * 2 + 2)
            scenario['name'] = f'pathway_{year}'
            scenario['exclude_units'] = ['Battery', 'Battery_district', 'NG_Cogeneration',
                                         'HeatPump_Geothermal_district', 'HeatPump_DHN',
                                         'NG_Cogeneration_district', 'NG_Boiler_district']
            scenario["specific"] = ['unique_heating_system',# Do not allow two different heating systems (Example: not NG boiler and heatpump simultaneously)]
                                    'no_ElectricalHeater_without_HP',
                                    'enforce_PV',  # Enforce PV Units_Use to 0 or 1 on all buildings]
                                    'enforce_PV_mult',
                                    #'max_total_PV_power',
                                    # 'enforce_DHN',
                                    ]
            #scenario['EMOO'] = {'EMOO_PV_upper': 0.007}  # [kW/m2_roof]

            # Set method options
            method = {'building-scale': True}
            DW_params = {'max_iter': 3}

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

            pathway_data = pd.read_csv(pathways_filename)

            for key in qbuildings_data['buildings_data'].keys():
                # get egid of the building
                egid = qbuildings_data['buildings_data'][key]['egid']
                # Find matching row in pathway_data
                match_row = pathway_data[pathway_data['egid'].astype(str) == str(egid)]
                if not match_row.empty:
                    # Get the data from match_row columns except for egid and add it to the qbuildings_data TODO: check if I should add all info now or as needed. seems more efficient to add all now, even if not used
                    for i in match_row.columns:
                        if i != 'egid':
                            qbuildings_data['buildings_data'][key][i] = match_row[i].values[0]
                else:
                    # If no match found, give an error message and end the program
                    raise ValueError(f"No match found for egid {egid} in pathway_data.")

            # Add enforce heating units in the scenario['specific']
            Ext_heat_Units = np.array([qbuildings_data['buildings_data'][key][f'heating_system_{year}'] for key in qbuildings_data['buildings_data']])

            building_keys = list(qbuildings_data['buildings_data'].keys())
            # set parameters
            Ext_Units_file = pd.read_pickle(f'{results_path}/results {year-5}/pathway_{int(year)-5}_{transformer}.pickle')
            Ext_Units = Ext_Units_file[f'pathway_{int(year)-5}'][0]['df_Unit']['Units_Mult']
            parameters = dict()
            parameters['Units_Ext'] = Ext_Units

            for unit in list(np.unique(Ext_heat_Units)):
                if f'enforce_{unit}' not in scenario['specific']:
                    scenario['specific'].append(f'enforce_{unit}')
                # Add the heating system to the parameters
                parameters['{}_install'.format(unit)] = np.array([[1] if qbuildings_data['buildings_data'][key][f'heating_system_{year}'] == unit else [0] for key in qbuildings_data['buildings_data'].keys()])

            # TODO: Add option for other heating systems for DHW
            if f'heating_system_2_2025' in pathway_data.columns:
                parameters['ThermalSolar_install'] = np.array([[1] if qbuildings_data['buildings_data'][key][f'heating_system_2_2025'] == 'ThermalSolar' else [0] for key in qbuildings_data['buildings_data'].keys()])
                scenario['specific'].append(f'enforce_ThermalSolar')

            # Check if PV is in the initial scenario

            if f'electric_system_{year}' in pathway_data.columns:
                parameters['PV_install'] = np.array([[1] if qbuildings_data['buildings_data'][key][f'electric_system_{year}'] == 'PV' else [0] for key in qbuildings_data['buildings_data'].keys()])
            else:
                parameters['PV_install'] = np.array([[0] for key in qbuildings_data['buildings_data'].keys()])

            if parameters['PV_install'].sum() > 0:
                parameters['PV_mult'] = np.array(
                    [[qbuildings_data['buildings_data'][key][f'pv_mult_2025']]
                     if qbuildings_data['buildings_data'][key][f'pv_mult_2025'] > 0
                     else [-1]
                     for key in qbuildings_data['buildings_data']
                     ], dtype=object)
                    #scenario['specific'].append('enforce_PV_mult')

            # Run optimization
            reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters,
                        cluster=cluster, scenario=scenario, method=method, solver="gurobiasl", DW_params=DW_params)
            #reho.single_optimization()  # run optimization
            reho.generate_pareto_curve()

            plotting.plot_performance(reho.results,plot='costs',indexed_on='Pareto_ID',label='EN_long',title="Economical performance").show()
            # Save results
            # check if path exists
            if not os.path.exists(f'{results_path}/Results {year}'):
                os.makedirs(f'{results_path}/Results {year}')
            #reho.save_results(format=['pickle'], filename=f'{results_folder}/Results {year}/pathway_{year}_{transformer}')

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
    #process_time_df.to_csv(f'{results_path}/Results {year}/process_time_{year}.csv', index=False)

    error_transf_df = pd.DataFrame({'Transformers': error_transf, 'Error': error_list})
    #error_transf_df.to_csv(f'{results_path}/Results {year}/error_transf_{year}.csv', index=False)