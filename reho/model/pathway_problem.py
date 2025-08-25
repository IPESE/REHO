import random
from collections import OrderedDict
import re
import numpy as np
from reho.model.reho import *

__doc__ = """
File for constructing and solving the optimization for the pathway problem formulation.
"""


class PathwayProblem(REHO):
    """
    Performs a pathway-based optimization.

    Parameters are inherited from the REHO class.

    See also
    --------
    reho.model.reho.REHO

    Notes
    -------
    This class is still under construction.
    """
    # TODO: Add an option to save the transition pathway
    def __init__(self, qbuildings_data, units, grids, pathway_parameters, pathway_data, parameters=None, set_indexed=None, cluster=None, method=None, scenario=None, solver="highs", DW_params=None, path_methods=None, group=None):

        super().__init__(qbuildings_data, units, grids, parameters, set_indexed, cluster, method, scenario, solver, DW_params)

        # Initialize PathwayProblem-specific attributes
        self.pathway_parameters = pathway_parameters
        self.pathway_data = pathway_data
        self.qbuildings_data = qbuildings_data
        self.units = units

        self.y_start = self.pathway_parameters['y_start']
        self.y_end = self.pathway_parameters['y_end']

        self.method = method
        if path_methods is None:
            self.path_methods = {}
        else:
            self.path_methods = path_methods
        self.initialise_methods()

        self.group = group

        if 'y_span' not in self.pathway_parameters.keys():
            self.y_span = np.linspace(self.y_start, self.y_end, self.pathway_parameters['N_steps_pathway'], endpoint=True)
        else:
            self.y_span = self.pathway_parameters['y_span']

    def execute_pathway_building_scale(self):

        # Set up the initial scenario
        self.scenario['specific'] = ['unique_heating_system', # Do not allow two different heating systems (Ex: not NG boiler and heatpump simultaneously)
                                     'no_ElectricalHeater_without_HP', # Do not allow Electrical Heater without Heat Pump
                                     'enforce_PV',            # Enforce PV Units_Use to 0 or 1 on all buildings
                                     #'enforce_Battery'        # Enforce Battery Units_Use to 0 or 1 on all buildings
                                     ]
        # Generate the pathway for units if path_methods generate_pathway is True
        if self.path_methods['generate_pathway'] == True:
            self.generate_pathway_unit_use()
        else:
            # Check if the heating scenario is defined for all years in y_span
            for year in self.y_span:
                if f'heating_system_{int(year)}' not in self.pathway_data.columns:
                    raise ValueError(f"No heating system defined in pathway_data for year {int(year)}.")
            # Add the existing heating system in qbuildings_data based on the egid
            for key in self.qbuildings_data['buildings_data'].keys():
                # get egid of the building
                egid = self.qbuildings_data['buildings_data'][key]['egid']
                # Find matching row in pathway_data
                match_row = self.pathway_data[self.pathway_data['egid'].astype(str) == str(egid)]
                if not match_row.empty:
                    # Get the data from match_row columns except for egid and add it to the qbuildings_data TODO: check if I should add all info now or as needed. seems more efficient to add all now, even if not used
                    for i in match_row.columns:
                        if i != 'egid':
                            self.qbuildings_data['buildings_data'][key][i] = match_row[i].values[0]
                else:
                    # If no match found, give an error message and end the program
                    raise ValueError(f"No match found for egid {egid} in pathway_data.")

        # Add enforce heating units in the scenario['specific']
        if self.path_methods['enforce_pathway'] == True:
            Ext_heat_Units = np.array([self.qbuildings_data['buildings_data'][key][f'heating_system_{self.y_start}'] for key in
                 self.qbuildings_data['buildings_data']] + [self.qbuildings_data['buildings_data'][key][f'heating_system_{self.y_end}'] for key in
                   self.qbuildings_data['buildings_data']])
        elif self.path_methods['optimize_pathway'] == True:
            Ext_heat_Units = np.array([self.qbuildings_data['buildings_data'][key][f'heating_system_{self.y_start}'] for key in
                 self.qbuildings_data['buildings_data']])

        building_keys = list(self.qbuildings_data['buildings_data'].keys())

        for unit in list(np.unique(Ext_heat_Units)):
            if f'enforce_{unit}' not in self.scenario['specific']:
                self.scenario['specific'].append(f'enforce_{unit}')
            # Add the heating system to the parameters
            self.parameters['{}_install'.format(unit)] = np.array([[1] if self.qbuildings_data['buildings_data'][key][f'heating_system_{self.y_start}'] == unit else [0] for key in self.qbuildings_data['buildings_data'].keys()])

        # TODO: Add option for other heating systems for DHW
        if f'heating_system_2_{self.y_start}' in self.pathway_data.columns:
            self.parameters['ThermalSolar_install'] = np.array([[1] if self.qbuildings_data['buildings_data'][key][f'heating_system_2_{self.y_start}'] == 'ThermalSolar' else [0] for key in self.qbuildings_data['buildings_data'].keys()])
            self.scenario['specific'].append(f'enforce_ThermalSolar')

        # Check if PV is in the initial scenario
        if f'electric_system_{self.y_start}' in self.pathway_data.columns:
            self.parameters['PV_install'] = np.array([[1] if self.qbuildings_data['buildings_data'][key][f'electric_system_{self.y_start}'] == 'PV' else [0] for key in self.qbuildings_data['buildings_data'].keys()])
        else:
            self.parameters['PV_install'] = np.array([[0] for key in self.qbuildings_data['buildings_data'].keys()])

        if self.parameters['PV_install'].sum() > 0:
            if f'pv_mult_{self.y_start}' not in self.pathway_data.columns:
                max_PV = self.get_max_pv_capacity() # if a mult is not provided we install the max PV
                # TODO: add the max_pv as enforce PV mult
            else:
                self.parameters['PV_mult'] = np.array([[self.qbuildings_data['buildings_data'][key][f'pv_mult_{self.y_start}']]
                    if self.qbuildings_data['buildings_data'][key][f'pv_mult_{self.y_start}'] > 0
                    else [-1]
                    for key in self.qbuildings_data['buildings_data']
                ], dtype=object)
            self.scenario['specific'].append('enforce_PV_mult')
            # TODO: add enforce PV_mult

        # Run optimization problem for the existing system
        self.single_optimization(Pareto_ID=self.y_start)

        # Generate pathways for the electric system TODO: adapt code to when I have more than one electric system
        # Get the logistic curve parameters for PV
        pv_k_factor = self.get_s_curve_factors('PV','k_factor', 's_curve_k_factor')
        pv_c_factor = self.get_s_curve_factors('PV', 'c_factor', 's_curve_c_factor')

        # Get phase-in timeline (number of buildings using the unit each year)
        # Get the number of houses that can install a PV. TODO: Some EGIDs might have almost no roof (this might also happen with the heating system), because the ratio is very small in this case mult will be 0.1 the Fmin. Check if we are getting these cases
        PV_init_total = 0
        PV_init_list = []
        PV_final_tot = 0
        PV_final_list = []
        for building, building_data in self.qbuildings_data['buildings_data'].items():
            # Get the number of houses that currently installed a PV
            key_name_1 = f'electric_system_{self.y_start}'
            # check if electric_system_{self.y_start} is in qbuildings_data
            if key_name_1 in  building_data and building_data[key_name_1] == 'PV':
                PV_init_total +=1
                PV_init_list = PV_init_list + [1]
            else:
                PV_init_list = PV_init_list + [0]
            key_name_2 = f'electric_system_{self.y_end}'
            # check if electric_system_{self.y_end} is in qbuildings_data
            if key_name_2 in building_data and building_data[key_name_2] == 'PV':
                PV_final_tot += 1
                PV_final_list = PV_final_list + [1]
            else:
                PV_final_list = PV_final_list + [0]

        if f'electric_system_{self.y_end}' in self.pathway_data.columns:
            elec_schedule = self.generate_s_curve(initial_value=PV_init_total, target_value=PV_final_tot, k_factor=pv_k_factor, c_factor=pv_c_factor, force_target=True, starting_value=True)
        else:
            elec_schedule = self.generate_s_curve(initial_value=PV_init_total, target_value=PV_final_tot, k_factor=pv_k_factor, c_factor=pv_c_factor, force_target=False, starting_value=True)
        #elec_schedule = self.generate_partial_s_curve(initial_value=PV_init_total, target_value=PV_final_tot, k=pv_k_factor, obs_year=self.y_start, obs_value=234, final_value=False)
        elec_schedule = [int(round(v)) for v in elec_schedule]

        # TODO: adapt this for if there are mults or not, and if we want to install max or not
        # verify if max_PV has been defined in the local scope
        if 'max_PV' not in locals():
            max_PV = self.get_max_pv_capacity()
        # TODO: change the code for when there are PV installed (mults cannot be max_PV in this case)
        if 'enforce_PV_mult' in self.scenario['specific']:
            PV_mult_raw = self.parameters['PV_mult']  # This is an array of lists, some empty
            instalable_mults_future = []
            for i, pv_list in enumerate(PV_mult_raw):
                if pv_list:  # non-empty list means PV_mult was > 0
                    instalable_mults_future.append(pv_list[0])
                else:
                    instalable_mults_future.append(max_PV[i])
        else:
            instalable_mults_future = max_PV

        # Get the pathway
        pathway_elec_mul, pathway_elec_use = self.select_unit_random(PV_init_list, elec_schedule, method='unit_phase_in', mults=instalable_mults_future)

        if len(self.path_methods['exclude_pathway_units']) > 0:
            self.scenario['exclude_units'].extend(self.path_methods['exclude_pathway_units'])

        # Loop through all time periods
        for t in range(1, len(self.y_span)):
            year = int(self.y_span[t])
            print(f'Running optimisation for year {year}')

            # Update constraints for the current time period
            #self.parameters['PV_install'] = pathway_elec_use[t]
            self.parameters['PV_install'] = np.array(
                [[1] if self.qbuildings_data['buildings_data'][key][f'electric_system_{year}'] == 'PV' else [0]
                 for key in self.qbuildings_data['buildings_data'].keys()])

            # Initialize HeatPump_install with zeros
            building_keys = list(self.qbuildings_data['buildings_data'].keys())

            # Loop through each unit type
            for unit in np.unique(Ext_heat_Units):
                if self.path_methods['enforce_pathway'] == True:
                    if unit == 'NG_Boiler':

                        NG_previous = self.parameters[f'{unit}_install']
                        self.parameters[f'{unit}_install'] = np.array([[1] if self.qbuildings_data['buildings_data'][key][f'heating_system_{year}'] == unit
                                                                        else [0] for key in building_keys])
                        NG_next = self.parameters[f'{unit}_install']
                        new_SolarThermal = ((NG_next - NG_previous) == 1).astype(int)
                        if new_SolarThermal.sum() > 0 and 'ThermalSolar_install' not in self.parameters:
                            self.parameters['ThermalSolar_install'] = new_SolarThermal
                            if 'enforce_ThermalSolar' not in self.scenario['specific']:
                                self.scenario['specific'].append('enforce_ThermalSolar')
                        else: #
                            self.parameters['ThermalSolar_install'] = self.parameters['ThermalSolar_install'] + new_SolarThermal
                    else:
                        self.parameters[f'{unit}_install'] = np.array([[1] if self.qbuildings_data['buildings_data'][key][f'heating_system_{year}'] == unit
                                                                       else [0] for key in building_keys])
                elif self.path_methods['optimize_pathway'] == True:
                    self.parameters[f'{unit}_install'] = np.array([[1] if self.qbuildings_data['buildings_data'][key][f'heating_system_{year}'] == unit
                                                                   else [0] if self.qbuildings_data['buildings_data'][key][f'heating_system_{year}'] == f'{unit}_out' else [0] for key in building_keys])

            # Update the existing conditions
            self.parameters['Units_Ext'] = self.results[self.scenario["name"]][int(self.y_span[t-1])]['df_Unit']['Units_Mult']

            # Optimize the new system
            self.single_optimization(Pareto_ID=year)

    def get_max_pv_capacity(self):
        """
        Calculate the maximum photovoltaic (PV) capacity for each house in the current scenario.

        This function temporarily modifies the scenario configuration to enforce the maximum PV constraint,
        performs an optimization run, and retrieves the maximum number of PV units per house. It ensures that
        any pre-existing PV enforcement flags (`enforce_PV`, `enforce_PV_mult`) are removed before the run
        and restored afterward.

        Steps performed:
        - Temporarily removes `'enforce_PV'` and `'enforce_PV_mult'` flags from the scenario if present.
        - Adds `'enforce_PV_max'` to enforce a scenario with maximum PV installation.
        - Runs a single optimization (`single_optimization`) with the `Pareto_ID='PV_max'`.
        - Extracts unit-level results for PV technologies, excluding district-level systems.
        - Sums the number of PV units installed per house based on the `Units_Mult` column.
        - Restores any previously removed enforcement flags.

        Returns
        -------
        list of float
            A list containing the maximum number of PV units installed per house, based on optimization results.

        Notes
        -----
        - Only PV systems that are not part of a district-level system are considered.
        - The function uses the `House` list from `self.infrastructure` to organize results per building.
        - Existing scenario flags are preserved and restored to ensure scenario integrity.
        """
        print('Calculating maximum PV capacity')
        # check if enforce_PV is in the scenario and remove if yes
        dummy = False
        dummy_2 = False
        if 'enforce_PV' in self.scenario['specific']:
            self.scenario['specific'].remove('enforce_PV')
            dummy = True
        if 'enforce_PV_mult' in self.scenario['specific']:
            self.scenario['specific'].remove('enforce_PV_mult')
            dummy_2 = True
        self.scenario['specific'].append('enforce_PV_max')
        # Get the maximum PV capacity
        self.single_optimization(Pareto_ID='PV_max')
        df_Unit = self.results[self.scenario['name']]['PV_max']['df_Unit']
        df_max_PV = df_Unit.loc[(df_Unit.index.str.contains('PV')) & ~(df_Unit.index.str.contains('district'))]
        REHO_max_PV = [np.sum([row['Units_Mult'] for index, row in df_max_PV.iterrows() if index.split('_')[-1] == h]) for h in self.infrastructure.House]
        self.scenario['specific'].remove('enforce_PV_max')
        # TODO: See if necessary to append the enforce_PV again
        if dummy == True:
            self.scenario['specific'].append('enforce_PV')
        if dummy_2 == True:
            self.scenario['specific'].append('enforce_PV_mult')

        return REHO_max_PV

    def generate_pathway_unit_use(self, save_data=False):
        #TODO: in pathway_problem_SiL there is the imposition of when to phase out the heating system

        # Check if the initial heating scenario is defined with
        if f'heating_system_{self.y_start}' in self.pathway_data.columns:
            # Add existing heating system in qbuildings_data based on the egid
            for key in self.qbuildings_data['buildings_data'].keys():
                # get egid of the building
                egid = self.qbuildings_data['buildings_data'][key]['egid']
                # Find matching row in pathway_data
                match_row = self.pathway_data[self.pathway_data['egid'].astype(str) == str(egid)]
                if not match_row.empty:
                    # Get the data from match_row columns except for egid and add it to the qbuildings_data TODO: check if I should add all info now or as needed. seems more efficient to add all now, even if not used
                    for i in match_row.columns:
                        if i != 'egid':
                            self.qbuildings_data['buildings_data'][key][i] = match_row[i].values[0]
                else:
                    # If no match found, give an error message and end the program
                    raise ValueError(f"No match found for egid {egid} in pathway_data.")
        else:
            # If no heating system is defined, raise an error
            raise ValueError(f"No heating system defined in pathway_data for year {self.y_start}.") # TODO: Instead of error, run REHO and use results as initial scenario

        if f'heating_system_2_{self.y_start}' in self.pathway_data.columns:
            # Add an existing heating system in qbuildings_data based on the egid
            for key in self.qbuildings_data['buildings_data'].keys():
                # get egid of the building
                egid = self.qbuildings_data['buildings_data'][key]['egid']
                # Find matching row in pathway_data
                match_row = self.pathway_data[self.pathway_data['egid'].astype(str) == str(egid)]
                if not match_row.empty:
                    # Get the heating_system_2_{self.y_start} value from match_row columns
                    self.qbuildings_data['buildings_data'][key][f'heating_system_2_{self.y_start}'] = match_row[f'heating_system_2_{self.y_start}'].values[0]

        # Phasing out the heating systems method, when I know the final heating system.
        # Create a DataFrame with the initial and final heating systems for each building
        heating_pathway = pd.DataFrame()
        heating_pathway['id_building'] = [b['id_building'] for b in self.qbuildings_data['buildings_data'].values()]
        heating_pathway[self.y_start] = [b[f'heating_system_{self.y_start}'] for b in self.qbuildings_data['buildings_data'].values()]
        heating_pathway[self.y_end] = [b[f'heating_system_{self.y_end}'] for b in self.qbuildings_data['buildings_data'].values()]

        final_pathways = []
        for unit in heating_pathway[self.y_start].unique():
            # Filter only buildings that start with this heating unit
            unit_pathway = heating_pathway[heating_pathway[self.y_start] == unit].copy()
            N_initial = len(unit_pathway)
            N_final = (unit_pathway[self.y_end] == unit).sum()  # buildings still using this unit in the end

            # Get the logistic curve parameters for the unit
            k_factor = self.get_s_curve_factors(unit, 'k_factor', 's_curve_k_factor')
            c_factor = self.get_s_curve_factors(unit, 'c_factor', 's_curve_c_factor')

            # Get the phase-out timeline (number of buildings using the unit each year)
            phase_out_schedule = self.generate_s_curve(initial_value=N_initial, target_value=N_final, k_factor=k_factor, c_factor=c_factor, force_target=True, starting_value=True)
            phase_out_schedule = [int(round(v)) for v in phase_out_schedule]

            # Start with all buildings using this unit (represented by 1)
            initial_state = [1] * N_initial
            # Final state is the final heating system (represented by 0)
            final_state = [1 if i == unit else 0 for i in unit_pathway[self.y_end].values]

            # Use random logic to decide which buildings stop using the unit at each step
            pathway_use_unit = self.select_unit_random(initial_state, phase_out_schedule, method='unit_phase_out', final_selection=final_state)
            # Create a DataFrame for the unit's pathway
            for i in range(1, len(self.y_span)):
                year = int(self.y_span[i])
                # Create column for this year based on phase-out logic
                col = pd.Series(pathway_use_unit[i].flatten(), name=year)
                # Replace 1s with the unit name (still in use), and 0s with the final heating system
                col = col.replace(1, unit)
                if self.path_methods['enforce_pathway'] == True:
                    col = np.where(col == 0, unit_pathway[self.y_end], col)
                elif self.path_methods['optimize_pathway'] == True:
                    col = np.where(col == 0, f'{unit}_out', col)
                # Add the column to the unit's pathway
                unit_pathway[f'heating_system_{year}'] = col
            # Append the full pathway for this unit to the final list
            final_pathways.append(unit_pathway)
        # Combine all unit-level transitions into a complete DataFrame
        df_heat_pathway = pd.concat(final_pathways, axis=0).reset_index(drop=True)

        # Add the heating system pathway to the qbuildings_data
        for key, building in self.qbuildings_data['buildings_data'].items():
            id_building = building['id_building']
            match_row = df_heat_pathway[df_heat_pathway['id_building'] == id_building]
            if not match_row.empty:
                # Drop columns we don’t want to include
                filtered_data = match_row.drop(columns=['id_building', self.y_start, self.y_end]).iloc[0].to_dict()
                # Add remaining columns to the building data
                building.update(filtered_data)

        # Generate pathways for the electric system TODO: adapt code to when I have more than one electric system
        # Get the logistic curve parameters for PV
        pv_k_factor = self.get_s_curve_factors('PV', 'k_factor', 's_curve_k_factor')
        pv_c_factor = self.get_s_curve_factors('PV', 'c_factor', 's_curve_c_factor')

        # Get phase-in timeline (number of buildings using the unit each year)
        # Get the number of houses that can install a PV. TODO: Some EGIDs might have almost no roof (this might also happen with the heating system), because the ratio is very small in this case mult will be 0.1 the Fmin. Check if we are getting these cases
        PV_init_total, PV_final_tot, PV_init_list = 0, 0, []
        for building, building_data in self.qbuildings_data['buildings_data'].items():
            # Get the number of houses that currently installed a PV
            key_name_1 = f'electric_system_{self.y_start}'
            # check if electric_system_{self.y_start} is in qbuildings_data
            if key_name_1 in building_data and building_data[key_name_1] == 'PV':
                PV_init_total += 1
                PV_init_list = PV_init_list + [1]
            else:
                PV_init_list = PV_init_list + [0]
            key_name_2 = f'electric_system_{self.y_end}'
            # check if electric_system_{self.y_end} is in qbuildings_data
            if key_name_2 in building_data:
                if building_data[key_name_2] == 'PV':
                    PV_final_tot += 1

        # Check if a target value is in the pathway_parameters
        if 'unit_target' in self.pathway_parameters and 'PV' in self.pathway_parameters['unit_target']:
            # Get the target value for PV
            PV_final_tot = self.pathway_parameters['unit_target']['PV']
            # Check if PV_final_tot is larger than the number of buildings
            if PV_final_tot > len(self.qbuildings_data['buildings_data']):
                raise ValueError(f"The target value for PV is larger than the number of buildings.")
            elec_schedule = self.generate_s_curve(initial_value=PV_init_total, target_value=PV_final_tot, k_factor=pv_k_factor, c_factor=pv_c_factor, force_target=False, starting_value=True)
            #elec_schedule = self.generate_partial_s_curve(initial_value=0,target_value=PV_final_tot,k=0.1232,obs_year=2025,obs_value=234,final_value=False)
        elif f'electric_system_{self.y_end}' in self.pathway_data.columns:
            elec_schedule = self.generate_s_curve(initial_value=PV_init_total, target_value=PV_final_tot, k_factor=pv_k_factor, c_factor=pv_c_factor, force_target=True, starting_value=True)
        else:
            # raise ValueError
            raise ValueError(f"A target for the number of PVs is not defined in the pathway_parameters or the final PV system is not defined in the pathway data.")

        #elec_schedule = self.generate_partial_s_curve(initial_value=PV_init_total, target_value=PV_final_tot, k=pv_k_factor, obs_year=self.y_start, obs_value=234, final_value=False)
        elec_schedule = [int(round(v)) for v in elec_schedule]

        # Get the pathway
        pathway_elec_use = self.select_unit_random(PV_init_list, elec_schedule,method='unit_phase_in')

        # Create a DataFrame for the PVs' pathway
        pv_pathway_df = pd.DataFrame()
        for i in range(0, len(self.y_span)):
            year = int(self.y_span[i])
            # Create a column for this year based on phase-out logic
            col = pd.Series(pathway_elec_use[i].flatten(), name=year)
            # Replace 1s with PV, and 0s with None
            col = col.replace(1, 'PV')
            col = np.where(col == 0, None, col)
            # Add the column to the unit's pathway
            pv_pathway_df[f'electric_system_{year}'] = col
        # Add the electric system pathway to the qbuildings_data
        row = 0
        for key, building in self.qbuildings_data['buildings_data'].items():
            match_row = pv_pathway_df.loc[row]
            # Update the building data with the new electric system
            building.update(match_row)
            row += 1

            # Reorder dictionary
            # Extract keys and sort electric and heating system fields
            electric_keys = sorted([k for k in building if k.startswith('electric_system_')],key=lambda x: int(re.search(r'\d+', x).group()))
            heating_keys = sorted([k for k in building if k.startswith('heating_system_')],key=lambda x: int(re.search(r'\d+', x).group()))
            heating_2_keys = sorted([k for k in building if k.startswith('heating_system_2_')],key=lambda x: int(re.search(r'\d+', x).group()))

            # Collect all other keys in their original order, excluding the above
            other_keys = [k for k in building if not (k.startswith('electric_system_') or k.startswith('heating_system_') or k.startswith('heating_system_2_'))]

            # Rebuild the dictionary
            ordered_building = OrderedDict()
            for k in other_keys + electric_keys + heating_keys + heating_2_keys:
                ordered_building[k] = building[k]

            # Overwrite original
            building = dict(ordered_building)

        if save_data == True:
            # Get the list of columns to save
            column_list = ['egid']
            for i in range(len(self.y_span)):
                column_list.append(f'heating_system_{int(self.y_span[i])}')
            # Add the column_list f'heating_system_2_{self.y_sart}' in case it exists in the qbuildings_data
            if f'heating_system_2_{self.y_start}' in self.qbuildings_data['buildings_data'][key].keys():
                column_list.append(f'heating_system_2_{self.y_start}')
            for i in range(len(self.y_span)):
                column_list.append(f'electric_system_{int(self.y_span[i])}')
            # Add the column_list f'pv_mult_{self.y_sart}' in case it exists in the qbuildings_data
            if f'pv_mult_{self.y_start}' in self.qbuildings_data['buildings_data'][key].keys():
                column_list.append(f'pv_mult_{self.y_start}')
            # Create a list of dicts for each building
            data = []
            for building_name, building_info in self.qbuildings_data['buildings_data'].items():
                row = {'building': building_name}
                for column in column_list:
                    row[column] = building_info.get(column, None)
                data.append(row)
            # Convert list of dicts to DataFrame
            df = pd.DataFrame(data)

            # Save the DataFrame to a CSV file
            if self.path_methods['enforce_pathway'] == True:
                df.to_csv('results/System_pathway.csv', index=False)
            elif self.path_methods['optimize_pathway'] == True:
                df.to_csv('results/System_pathway_phase_out.csv', index=False)

    def get_s_curve_factors(self, unit, factor_type, default_col):
        # TODO: redo the docstring, self.default_s_curve_factors was eliminated
        """
        Retrieve the S-curve factor value for a given unit and factor type.

        This function checks whether a specific S-curve factor (e.g., `k_factor` or `c_factor`)
        is explicitly defined in the pathway parameters. If not found, it falls back to the default
        S-curve value stored in the default factor table.

        Steps performed:
        - Check if `factor_type` exists in `self.pathway_parameters` and has a value for the given `unit`.
        - If found, return the parameter from `self.pathway_parameters`.
        - If not found, retrieve the default from `self.default_s_curve_factors` using the specified column.

        Parameters
        ----------
        unit : str
            The name of the energy system unit (e.g., 'PV', 'gas_boiler').
        factor_type : str
            The type of S-curve factor to retrieve ('k_factor' or 'c_factor').
        default_col : str
            The column name in the default S-curve factor DataFrame to use as fallback (e.g., 's_curve_k_factor').

        Returns
        -------
        float
            The S-curve factor value corresponding to the specified unit and factor type.

        Notes
        -----
        - If the unit is not found in `pathway_parameters`, the method defaults to looking it up
          in the `default_s_curve_factors` table.
        - This method assumes the `default_s_curve_factors` DataFrame has a 'Unit' column for lookups.
        """
        if factor_type in self.pathway_parameters and unit in self.pathway_parameters[factor_type]:
            return self.pathway_parameters[factor_type][unit]
        for unit_row in self.units['building_units']:
            if unit_row['name'] == unit:
                return unit_row[default_col]

    def generate_s_curve(self, initial_value=1e-2, target_value=1e-3, k_factor=1, c_factor=2035, force_target=False, starting_value=True):
        """
        Generate a logistic (S-curve) progression for EMOO values across a range of years.

        This function creates a smooth logistic transition from an initial value to a target value
        across a specified year range, typically used for modeling gradual changes (e.g., emissions,
        efficiency improvements, or technology uptake).

        Parameters
        ----------
        initial_value : float, optional
            Starting value of the curve (default is ``1e-2``).

        target_value : float, optional
            Ending value of the curve (default is ``1e-3``).

        k_factor : float, optional
            Steepness factor of the S-curve. Higher values lead to a sharper transition (default is ``1``).

        c_factor : int, optional
            Year of inflection (center point) where the curve changes most rapidly (default is ``2035``).

        force_target : bool, optional
            If ``True``, explicitly sets the final value of the curve to match `target_value`
            (default is ``False``).

        starting_value : bool, optional
            If ``True``, explicitly sets the first value of the curve to match `initial_value`
            (default is ``True``).

        Returns
        -------
        np.array
            A NumPy array of EMOO values corresponding to the input year span, forming a logistic curve.

        Notes
        -----
        - If `initial_value` equals `target_value`, the function returns a constant array.
        - The curve is scaled to exactly match start and/or end values if `starting_value` or `force_target` are enabled.
        - Internally, the function uses the logistic function:
          ``f(x) = target + (initial - target) / (1 + exp(-k * (c - year)))``
        """
        if initial_value == target_value:
            EMOO_list = [initial_value for key in self.y_span]
        else:
            EMOO_list = target_value + (initial_value - target_value) / (1 + np.exp(-k_factor * (c_factor - self.y_span)))
            # Determine what the start and stop should scale to
            if starting_value is True:
                start_val = initial_value
            else:
                start_val = EMOO_list[0]
            if force_target is True:
                stop_val = target_value
            else:
                stop_val = EMOO_list[-1]
            # Normalize and stretch the curve between desired start/stop
            EMOO_list = (EMOO_list-EMOO_list[0])*(stop_val-start_val)/(EMOO_list[-1]-EMOO_list[0]) + start_val
        return EMOO_list

    def generate_partial_s_curve(self,initial_value=0,target_value=1,k=0.1,obs_year=2025,obs_value=4.9,final_value=False):
        # Check if flat curve
        if initial_value == target_value:
            EMOO_list = [initial_value for key in self.y_span]
        elif obs_value == target_value:
            EMOO_list = [target_value for key in self.y_span]
        else:
            if initial_value == obs_value:  # Correct initial_value in order not to get extreme values for c and EMOO_list
                if target_value >= initial_value:
                    initial_value = initial_value - target_value / 1000
                else:
                    initial_value = initial_value + target_value / 1000

            # Compute c
            c = np.log((initial_value - target_value) / (obs_value - target_value) - 1) / (-k) + obs_year

            # Compute EMOO_list
            EMOO_list = target_value + (initial_value - target_value) / (1 + np.exp(-k * (c - self.y_span)))

            # Stretch the curve
            diff_start = obs_value
            diff_stop = EMOO_list[-1]
            if final_value is True:
                diff_stop = target_value
            EMOO_list = (EMOO_list - EMOO_list[0]) * (diff_stop - diff_start) / (EMOO_list[-1] - EMOO_list[0]) + diff_start  # Stretching the curve
        return EMOO_list



    def select_unit_random(self, initial_selection, steps, method, final_selection=None, mults=None): # TODO: maybe we just need one function that gets the mul or not depending on the method selected
        """
        Randomly select buildings to phase in or phase out a unit over a series of time steps.

        This function simulates the stepwise deployment or removal of units (e.g., technologies or systems)
        across a set of buildings. The selection process is randomized but reproducible (seeded with 42).
        It tracks both unit status and optionally associated capacities over time.

        Parameters
        ----------
        initial_selection : list of int
            A boolean-like list where `1` indicates the building initially has the unit, and `0` indicates absence.

        steps : list of int
            A list specifying the number of units that should exist at each time step.

        method : str
            The operation mode, either:
            - ``'unit_phase_in'``: units are added over time,
            - ``'unit_phase_out'``: units are removed over time.

        final_selection : list of int, optional
            Used only with ``'unit_phase_out'``. Indicates the desired final unit configuration. Buildings marked
            with `1` will retain the unit and will not be selected for phase-out.

        mults : list of float, optional
            A list of multipliers representing capacity or weight per building. If provided, the function also returns
            the evolving capacities over time.

        Returns
        -------
        dict or tuple of dict
            If `mults` is ``None``:
                dict
                    A dictionary mapping each step index to a NumPy array of unit statuses for all buildings.

            If `mults` is provided:
                tuple of (dict, dict)
                    - A dictionary mapping step index to the capacity (multiplied unit status) per building.
                    - A dictionary mapping step index to the boolean unit status per building.

        Raises
        ------
        ValueError
            If `method` is not one of ``'unit_phase_in'`` or ``'unit_phase_out'``.
        """
        if method not in {"unit_phase_in", "unit_phase_out"}:
            raise ValueError("Invalid method. Must be 'unit_phase_in' or 'unit_phase_out'.")

        random.seed(42)
        unit_status_per_step = {} # Boolean status of buildings per step
        total_status_per_step = {}
        capacities_per_step = {} if mults is not None else None

        current_status = initial_selection.copy()
        final_dummy = final_selection.copy() if final_selection is not None else None

        j = 0
        total_status_per_step[j] = unit_status_per_step[j] = np.array([[i] for i in current_status])
        # Initialize capacity if applicable
        if mults is not None:
            capacities_per_step[j] = np.array([[i] for i in np.array(mults) * np.array(current_status)])

        # Determine initial list of selectable building positions
        if method == "unit_phase_in":
            selectable_positions = [i for i in np.array(range(len(initial_selection))) if np.array(current_status)[i] == 0] # if a building already has a unit, it cannot be selected
        else:  # unit_phase_out
            if final_selection is None:
                selectable_positions = [i for i in np.array(range(len(initial_selection))) if np.array(current_status)[i] == 1]
            else:
                selectable_positions = [i for i in np.array(range(len(final_selection))) if np.array(final_dummy)[i] == 0] # if a building will keep a unit, it cannot be selected

        previous_step_value = steps[0]
        # Iterate over remaining steps
        for step_value in steps[1:]:
            j += 1
            buildings_to_change = abs(step_value - previous_step_value)
            if buildings_to_change > 0:
                position_selection = random.sample(selectable_positions, k=buildings_to_change) # Return a list that contains any k number of the items from a list
            else:
                position_selection = []
            # Update the current status of the buildings
            if method == "unit_phase_in":
                current_status = np.array(current_status) + np.array([1 if i in position_selection else 0 for i in range(len(initial_selection))])
                selectable_positions = [i for i in np.array(range(len(initial_selection))) if np.array(current_status)[i] == 0]
                unit_status_per_step[j] = np.array([[ii] for ii in [1 if i in position_selection else 0 for i in range(len(initial_selection))]])
            else: # unit_phase_out
                current_status = np.array(current_status) - np.array([1 if i in position_selection else 0 for i in range(len(initial_selection))])
                if final_selection is None:
                    selectable_positions = [i for i in np.array(range(len(initial_selection))) if np.array(current_status)[i] == 1]
                else:
                    final_dummy = np.array(final_dummy) + np.array([1 if i in position_selection else 0 for i in range(len(initial_selection))])
                    selectable_positions = [i for i in np.array(range(len(final_selection))) if np.array(final_dummy)[i] == 0]
                unit_status_per_step[j] = np.array([[ii] for ii in [0 if i in position_selection else 1 for i in range(len(initial_selection))]])

            total_status_per_step[j] = np.array([[i] for i in current_status])
            if mults is not None:
                capacities_per_step[j] = np.array([[i] for i in np.array(mults) * np.array(current_status)])

            previous_step_value = step_value
        if mults is None:
            return total_status_per_step
        else:
            return capacities_per_step, total_status_per_step

    def initialise_methods(self):
        if 'enforce_pathway' not in self.path_methods and self.path_methods['optimize_pathway'] == True:
            self.path_methods['enforce_pathway'] = False
        if 'optimize_pathway' not in self.path_methods and self.path_methods['enforce_pathway'] == True:
            self.path_methods['optimize_pathway'] = False
        if 'enforce_pathway' not in self.path_methods and self.path_methods['optimize_pathway'] == False:
            self.path_methods['enforce_pathway'] = True
        if 'optimize_pathway' not in self.path_methods and self.path_methods['enforce_pathway'] == False:
            self.path_methods['optimize_pathway'] = True
        # raise valueError if 'enforce_pathway' and 'optimize_pathway' are both False
        if self.path_methods['enforce_pathway'] is False and self.path_methods['optimize_pathway'] is False:
            raise ValueError("The path_method 'enforce_pathway' and 'optimize_pathway' cannot be both False.")
        # raise valueError if 'enforce_pathway' and 'optimize_pathway' are both True
        if self.path_methods['enforce_pathway'] is True and self.path_methods['optimize_pathway'] is True:
            raise ValueError("The path_method 'enforce_pathway' and 'optimize_pathway' cannot be both True.")
        # raise valueError if both 'enforce_pathway' and 'optimize_pathway' are not in self.path_methods
        if 'enforce_pathway' not in self.path_methods and 'optimize_pathway' not in self.path_methods:
            raise ValueError("The path_method 'enforce_pathway' or 'optimize_pathway' must be defined in path_methods.")


        if 'generate_pathway' not in self.path_methods:
            self.path_methods['generate_pathway'] = True
        if 'install_PV_max' not in self.path_methods:
            self.path_methods['install_PV_max'] = False
        if 'install_PV_mult' not in self.path_methods:
            self.path_methods['install_PV_mult'] = False
        if 'exclude_pathway_units' not in self.path_methods:
            self.path_methods['exclude_pathway_units'] = []