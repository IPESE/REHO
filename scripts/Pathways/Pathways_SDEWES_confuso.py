import numpy as np
import pandas as pd

from reho.model.pathway_problem import *
from reho.plotting import plotting

if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    qbuildings_data = reader.read_csv(buildings_filename='../Pathways/QBuildings/QBuildings_SDEWES_updated.csv',nb_buildings=10)

    # Select clustering options for weather data
    cluster = {'custom_weather': 'data/profiles/Pully-hour.csv', 'Location': 'Pully', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # --------------------------------------------------------------------------------------------------------------------#
    # 1. Define initial state of the system, in 2024.
    #---------------------------------------------------------------------------------------------------------------------#

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'system_2024'
    scenario['specific'] = ['enforce_OIL_Boiler',    # Enforce Oil boiler Units_Use to 0 or 1 on buildings heated by Oil boiler
                            'enforce_NG_Boiler',     # Enforce Oil boiler Units_Use to 0 or 1 on buildings heated by NG boiler
                            'enforce_DHN_hex',       # Enforce DHN Units_Use to 0 or 1 on all buildings
                            'unique_heating_system', # Do not allow two different heating systems (Exple: not NG boiler and heatpump simultaneously)]
                            'enforce_PV',            # Enforce PV Units_Use to 0 or 1 on all buildings
                            ]
    scenario['exclude_units'] = ['ThermalSolar', 'Battery', 'Battery_district', 'NG_Cogeneration',
                                 'HeatPump_Geothermal_district', 'HeatPump_Geothermal', 'HeatPump_DHN',
                                 'NG_Cogeneration_district', 'NG_Boiler_district']

    # Set method options
    method = {'building-scale': True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'Oil': {},
                                             'Heat': {}
                                             })
    units = infrastructure.initialize_units(scenario, grids)

    # Fix units installed in 2024
    parameters = {}
    '''
    For when the heating system names are improved
    heat_system = ['OIL_Boiler', 'NG_Boiler']
    for heat in heat_system:
        parameters['{}_install'.format(heat)] = np.array([1 if qbuildings_data['buildings_data'][key]['heating_system_2024'] == heat else 0 for key in qbuildings_data['buildings_data'].keys()])
    '''
    parameters['OIL_Boiler_install'] = np.array([[1] if qbuildings_data['buildings_data'][key]['heating_system_2024'] == 'Oil' else [0] for key in qbuildings_data['buildings_data'].keys()])
    parameters['NG_Boiler_install'] = np.array([[1] if qbuildings_data['buildings_data'][key]['heating_system_2024'] == 'Gas' else [0] for key in qbuildings_data['buildings_data'].keys()])
    parameters['DHN_hex_install'] = np.array([[1] if qbuildings_data['buildings_data'][key]['heating_system_2024'] == 'DHN' else [0] for key in qbuildings_data['buildings_data'].keys()])
    # PV install equal to zero for all buildings
    parameters['PV_install'] = np.array([[0] for key in qbuildings_data['buildings_data'].keys()])

    pathway_parameters = dict()
    pathway_parameters['y_start'] = 2024 # start year for the pathway analysis
    pathway_parameters['y_end'] = 2050 # end year for the pathway analysis
    pathway_parameters['N_iter_pathway'] = 6 # number of points in the analysis
    pathway_parameters['k_factor'] = {}
    pathway_parameters['k_factor']['PV'] = 0.1
    pathway_parameters['c_factor'] = {}
    pathway_parameters['c_factor']['PV'] = 2037

    # select only the first 10 lines
    pathway_data = pd.read_csv('../Pathways/QBuildings/Pathway_SDEWES_test.csv')[:11]

    # Run optimization
    reho_initial = PathwayProblem(qbuildings_data=qbuildings_data, units=units, grids=grids, pathway_parameters=pathway_parameters, pathway_data=pathway_data, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")

    #reho_initial.single_optimization()
    #reho_initial_syst = reho_initial.results[scenario['name']][0]

    # Read Excel file into a dict of DataFrames, each key is a sheet name
    reho_initial_syst = pd.read_excel(
        os.path.join(os.getcwd(), "results/initial_system_2024.xlsx"),
        sheet_name=None
    )
    # Plot results
    #plotting.plot_performance(reho_initial.results, plot='costs', indexed_on='Scn_ID', label='EN_long',title="Economical performance").show()
    """
    # Save results
    # Save the results in excel
    with pd.ExcelWriter(os.path.join(os.getcwd(), "results/initial_system_2024.xlsx")) as writer:
        for sheet, value in reho_initial_syst.items():
            df = pd.DataFrame(value)
            df.to_excel(writer, sheet_name=sheet)

    # --------------------------------------------------------------------------------------------------------------------#
    # 2. Determine maximum PV than can be installed.
    #---------------------------------------------------------------------------------------------------------------------#
    reho_initial.scenario['specific'].remove('enforce_PV')
    reho_initial.scenario['specific'].append('enforce_PV_max')
    reho_initial.single_optimization(Pareto_ID=1)
    reho_max_PV = reho_initial.results['system_2024'][1]

    # Save the results in excel
    with pd.ExcelWriter(os.path.join(os.getcwd(), "results/max_PV.xlsx")) as writer:
        for sheet, value in reho_max_PV.items():
            df = pd.DataFrame(value)
            df.to_excel(writer, sheet_name=sheet)
    """

    reho_max_PV = reho_initial.get_max_pv_capacity()
    #reho_max_PV = max_PV.results[scenario['name']][0]

    # --------------------------------------------------------------------------------------------------------------------#
    # 3. Define pathway (S-curver) for the installation of PV
    #---------------------------------------------------------------------------------------------------------------------#
    # Define the S-curve parameters
    N_iter_pathway = 6
    y_start = 2025
    y_stop = 2050
    k=0.1
    #k_int=int(np.round(k*1000))
    c=2037

    # Get the number of house that currently installed a PV
    PV_init_int = int(np.round(reho_initial_syst['df_Unit'].loc[reho_initial_syst['df_Unit'].index.astype(str).str.contains('PV')]['Units_Use'].sum()))
    # Get the number of house that can install a PV (for enforcement of PV_max)
    PV_tot_int = reho_max_PV.loc[reho_max_PV.index.str.contains('PV')]['Units_Use'].sum()


    EMOO_list_PV, y_span = reho_initial.get_logistic(E_start=PV_init_int, E_stop=PV_tot_int, y_start=y_start,y_stop=y_stop, k=k, c=c, n=N_iter_pathway, final_value=False,starting_value=True)
    EMOO_list_PV = [int(np.round(i)) for i in EMOO_list_PV]  # Transform the steps to integers

    # Create the list of Units_Use and Units_Mult constraint for each step.
    # Note: The possible PV cpacities are given by the enforce_PV_max scenario above. However, the already installed capacities do not correspond necessary to these maximum values. It is therefore necessary to modify the list.
    df_PV_installable = reho_max_PV.loc[(reho_max_PV.index.str.contains('PV')) & ~(reho_max_PV.index.str.contains('district'))]  # What the max scenario gave; TO DO: make that the dataframe only gives the name of the unit and the Units_Mult
    installable_PV = [np.sum([row['Units_Mult'] for index, row in df_PV_installable.iterrows() if index.split('_')[-1] == h]) for h in reho_initial.infrastructure.House]  # In the form of a list ordered correctly

    df_PV_installed = reho_initial_syst['df_Unit'].loc[(reho_initial_syst['df_Unit'].index.astype(str).str.contains('PV')) & ~(reho_initial_syst['df_Unit'].index.astype(str).str.contains('district'))]  # What is already installed
    installed_PV = [np.sum([row['Units_Mult'] for index, row in df_PV_installed.iterrows() if index.split('_')[-1] == h]) for h in reho_initial.infrastructure.House]  # In the form of a list ordered correctly

    installable_PV_future = [installable_PV[num] if installed_PV[num] == 0 else installed_PV[num] for num in range(len(installable_PV))]  # Correction of the list of available capacities
    initial_selection_PV = [1 if key != 0 else 0 for key in installed_PV]  # Creation of the initial installed capacities boolean

    # Create the dict to send to the pathway function
    pathway_data_2 = {}
    pathway_data_2['y_start'] = 2025 # year to start the simulation
    pathway_data_2['y_end'] = 2050 # year to end the simulation
    #pathway_data_2['y_steps'] = 2  # number of points in the pathway scenario
    pathway_data_2['y_span'] = y_span # years to be considered in the pathway scenario
    pathway_data_2['kPV'] = 0.1
    pathway_data_2['c'] = 2037
    pathway_data_2['EMOO'] = {}
    pathway_data_2['EMOO']['PV'] = {}
    pathway_data_2['EMOO']['PV']['Units_Mult'] = {}
    pathway_data_2['EMOO']['PV']['Units_Use'] = {}

    pathway_data_2['EMOO']['PV']['Units_Mult'], temp, pathway_data_2['EMOO']['PV']['Units_Use'] = reho_initial.select_values_random(values=installable_PV_future,initial_selection=initial_selection_PV,steps=EMOO_list_PV)  # Random attribution

    # define new scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'system_2024'
    scenario['specific'] = ['enforce_OIL_Boiler',    # Enforce Oil boiler Units_Use to 0 or 1 on buildings heated by Oil boiler
                            'enforce_NG_Boiler',     # Enforce Oil boiler Units_Use to 0 or 1 on buildings heated by NG boiler
                            'enforce_DHN_hex',       # Enforce DHN Units_Use to 0 or 1 on all buildings
                            'unique_heating_system', # Do not allow two different heating systems (Exple: not NG boiler and heatpump simultaneously)]
                            'enforce_PV',            # Enforce PV Units_Use to 0 on all buildings
                            ]
    scenario['exclude_units'] = ['ThermalSolar', 'Battery', 'Battery_district', 'NG_Cogeneration',
                                 'HeatPump_Geothermal_district', 'HeatPump_Geothermal', 'HeatPump_DHN',
                                 'NG_Cogeneration_district', 'NG_Boiler_district', 'ElectricalHeater']


    reho_path = PathwayProblem(qbuildings_data=qbuildings_data, units=units, grids=grids, pathway_parameters= pathway_parameters, pathway_data=pathway_data, parameters=parameters,cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho_path.execute_pathway_building_scale(pathway_data_2=pathway_data_2)
    plotting.plot_performance(reho_path.results, plot='costs', indexed_on='Pareto_ID', label='EN_long',title="Economical performance").show()
    # Save results
    reho_path.save_results(format=['pickle','xlsx'], filename='pathway_test')