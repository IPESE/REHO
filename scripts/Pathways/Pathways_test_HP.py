import pandas as pd

from reho.model.reho import *
from reho.plotting import plotting
import time


if __name__ == '__main__':
    # read specific column from csv file
    transf = pd.read_csv('../Pathways/QBuildings/QBuildings_SDEWES_updated_no_EH_2.csv', usecols=['transformer_new'])
    transf_list = transf['transformer_new'].unique().tolist()

    process_time_list = []
    transf_list_2 = []
    n_build_list = []
    error_transf = []
    for transformer in transf_list:
        tic = time.perf_counter()
        try:
            # Set building parameters
            reader = QBuildingsReader()
            qbuildings_data = reader.read_csv(buildings_filename='../Pathways/QBuildings/QBuildings_SDEWES_updated_no_EH_2.csv', transformer_new=transformer)
            nb_buildings = len(qbuildings_data['buildings_data'])

            # Select clustering options for weather data
            cluster = {'custom_weather': 'data/profiles/Pully-hour.csv', 'Location': 'Pully', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

            # Set scenario
            scenario = dict()
            scenario['Objective'] = 'TOTEX'
            scenario['name'] = 'path_totex'
            scenario['specific'] = ['unique_heating_system', # Do not allow two different heating systems (Exple: not NG boiler and heatpump simultaneously)]
                                    'enforce_PV',  # Enforce PV Units_Use to 0 or 1 on all buildings
                                    ]
            scenario['exclude_units'] = ['ThermalSolar', 'Battery', 'Battery_district', 'NG_Cogeneration',
                                         'HeatPump_Geothermal_district', 'HeatPump_DHN', 'HeatPump_Geothermal',
                                         'NG_Cogeneration_district', 'NG_Boiler_district']
            scenario['enforce_units'] = []

            # Set method options
            method = {'building-scale': True, 'parallel_computation': True}

            # Initialize available units and grids
            grids = infrastructure.initialize_grids({'Electricity': {},
                                                     'NaturalGas': {},
                                                     'Oil': {},
                                                     'Heat': {}
                                                     })

            grids['Electricity']['ReinforcementOfNetwork'] = np.array([1E6])
            grids['NaturalGas']['ReinforcementOfNetwork'] = np.array([1E6])
            grids['Oil']['ReinforcementOfNetwork'] = np.array([1E6])
            grids['Heat']['ReinforcementOfNetwork'] = np.array([1E6])
            grids['Electricity']['Network_ext'] = 1E6
            grids['NaturalGas']['Network_ext'] = 1E6
            grids['Oil']['Network_ext'] = 1E6
            grids['Heat']['Network_ext'] = 1E6

            units = infrastructure.initialize_units(scenario, grids)

            # Pathway data
            pathway_data = pd.read_csv('../Pathways/QBuildings/Pathway_SDEWES_test.csv')

            for key in qbuildings_data['buildings_data'].keys():
                # get egid of the building
                egid = qbuildings_data['buildings_data'][key]['egid']
                # Find matching row in pathway_data
                match_row = pathway_data[pathway_data['egid'] == egid]
                if not match_row.empty:
                    # Get the data from match_row columns except for egid and add it to the
                    qbuildings_data['buildings_data'][key]['heating_system_2050'] = match_row['heating_system_2050'].values[0]

            Ext_heat_Units = np.array([qbuildings_data['buildings_data'][key][f'heating_system_2050'] for key in qbuildings_data['buildings_data']])
            parameters = dict()
            for unit in list(np.unique(Ext_heat_Units)):
                # check if the unit has HeatPump in a part of the name
                if 'HeatPump' in unit:
                    # check if the unit is not already in the scenario
                    if 'enforce_HeatPump' not in scenario['specific']:
                        scenario['specific'].append(f'enforce_HeatPump')
                    # check if the unit is not already in the parameters
                    if f'HeatPump_install' not in parameters.keys():
                        parameters['HeatPump_install'] = np.array([[1] if qbuildings_data['buildings_data'][key][f'heating_system_2050'] == unit else [0] for key in qbuildings_data['buildings_data'].keys()])
                else:
                    if f'enforce_{unit}' not in scenario['specific']:
                        scenario['specific'].append(f'enforce_{unit}')
                    # Add the heating system to the parameters
                    parameters['{}_install'.format(unit)] = np.array([[1] if qbuildings_data['buildings_data'][key][f'heating_system_2050'] == unit else [0] for key in qbuildings_data['buildings_data'].keys()])

            parameters['PV_install'] = np.array([[1] for key in qbuildings_data['buildings_data'].keys()])

            # Run optimization
            reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
            #reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
            reho.single_optimization()

            # Plot results
            #plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long',title="Economical performance").show()

            # convert dictionary parameters in a dataframe
            df_parameters = pd.DataFrame({k: v.ravel() for k, v in parameters.items()})

            # Add parameters_df as a new DataFrame under the results dictionary
            reho.results['path_totex'][0]['df_Parameters'] = df_parameters
            # Save results
            reho.save_results(format=['xlsx'], filename=f'No_geo_HP_2050_{transformer}')
        except Exception as e:
            error_transf.append(transformer)
            print(f"Error with transformer {transformer}: {e}")
        toc = time.perf_counter()
        process_time_list.append((toc - tic) / 60)  # time in minutes
        transf_list_2.append(transformer)
        n_build_list.append(nb_buildings)

    # save the process time in a csv file
    process_time_df = pd.DataFrame({'Transformer': transf_list, 'N Buildings': n_build_list, 'Process time': process_time_list})
    process_time_df.to_csv('../Pathways/results/process_time_2050.csv', index=False)

    error_transf_df = pd.DataFrame(error_transf, columns=['Transformers'])
    error_transf_df.to_csv('../Pathways/results/error_transf_2050.csv', index=False)