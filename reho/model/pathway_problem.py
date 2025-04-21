import random

import pandas as pd

from reho.model.reho import *

__doc__ = """
File for constructing and solving the optimization for the pathway problem formulation.
"""


class PathwayProblem(REHO):
    """
    Performs an pathway-based optimization.

    Parameters are inherited from the REHO class.

    See also
    --------
    reho.model.reho.REHO

    Notes
    -------
    This class is still under construction.
    """
    def __init__(self, qbuildings_data, units, grids, pathway_parameters, pathway_data, parameters=None, set_indexed=None, cluster=None, method=None, scenario=None, solver="highs", DW_params=None, path_methods=None):

        super().__init__(qbuildings_data, units, grids, parameters, set_indexed, cluster, method, scenario, solver, DW_params)

        # Initialize PathwayProblem-specific attributes
        self.pathway_parameters = pathway_parameters
        self.pathway_data = pathway_data
        self.qbuildings_data = qbuildings_data

        self.y_start = self.pathway_parameters['y_start']
        self.y_end = self.pathway_parameters['y_end']

        self.default_s_curve_factors = pd.read_csv(os.path.join(path_to_infrastructure, 'building_units.csv'), sep=';', usecols=['Unit', 's_curve_k_factor', 's_curve_c_factor'])

    def get_max_pv_capacity(self):
        print('Calculating maximum PV capacity')
        # check if enforce_PV is in the scenario and remove if yes
        dummy = False
        if 'enforce_PV' in self.scenario['specific']:
            self.scenario['specific'].remove('enforce_PV')
            dummy = True
        self.scenario['specific'].append('enforce_PV_max')
        # Get the maximum PV capacity
        self.single_optimization(Pareto_ID='PV_max')
        REHO_max_PV = self.results[self.scenario['name']]['PV_max']['df_Unit']

        self.scenario['specific'].remove('enforce_PV_max')
        # TO DO: See if necessary to append the enforce_PV again
        if dummy == True:
            self.scenario['specific'].append('enforce_PV')

        return REHO_max_PV

    def execute_pathway_building_scale(self, pathway_unit_use=None):

        #TO DO: The initial scenario should be built here
        # Set up initial scenario
        self.scenario['specific'] = ['unique_heating_system', # Do not allow two different heating systems (Ex: not NG boiler and heatpump simultaneously)
                                     'enforce_PV',            # Enforce PV Units_Use to 0 or 1 on all buildings
                                     #'enforce_Battery'        # Enforce Battery Units_Use to 0 or 1 on all buildings
                                     ]

        # Check if the initial heating scenario is defined with
        if f'heating_system_{self.y_start}' in self.pathway_data.columns:
            # Add existing heating system in qbuildings_data based on the egid
            for key in self.qbuildings_data['buildings_data'].keys():
                # get egid of the building
                egid = self.qbuildings_data['buildings_data'][key]['egid']
                # Find matching row in pathway_data
                match_row = self.pathway_data[self.pathway_data['egid'] == egid]
                if not match_row.empty:
                    # Get the data from match_row columns except for egid and add it to the qbuildings_data TO DO: check if I should add all info now or as needed. seems more efficient to add all now, even if not used
                    for i in match_row.columns:
                        if i != 'egid':
                            self.qbuildings_data['buildings_data'][key][i] = match_row[i].values[0]
                else:
                    # If no match found, give error message and end the program
                    raise ValueError(f"No match found for egid {egid} in pathway_data.")

            # Add enforce heating units in the scenario['specific']
            Ext_heat_Units = np.array([self.qbuildings_data['buildings_data'][key][f'heating_system_{self.y_start}'] for key in self.qbuildings_data['buildings_data']]
                            + [self.qbuildings_data['buildings_data'][key][f'heating_system_{self.y_end}'] for key in self.qbuildings_data['buildings_data']])

            building_keys = list(self.qbuildings_data['buildings_data'].keys())
            self.parameters['HeatPump_install'] = np.array([[0] for key in self.qbuildings_data['buildings_data'].keys()])

            for unit in list(np.unique(Ext_heat_Units)):
                # check if the unit has HeatPump in a part of the name
                if 'HeatPump' in unit:
                    # check if the unit is not already in the scenario
                    if 'enforce_HeatPump' not in self.scenario['specific']:
                        self.scenario['specific'].append(f'enforce_HeatPump')
                    # check if the unit is not already in the parameters
                    for b_idx, key in enumerate(building_keys):
                        heating_system = self.qbuildings_data['buildings_data'][key][f'heating_system_{self.y_start}']
                        if heating_system == unit:
                            self.parameters['HeatPump_install'][b_idx][0] += 1
                else:
                    if f'enforce_{unit}' not in self.scenario['specific']:
                        self.scenario['specific'].append(f'enforce_{unit}')
                    # Add the heating system to the parameters
                    self.parameters['{}_install'.format(unit)] = np.array([[1] if self.qbuildings_data['buildings_data'][key][f'heating_system_{self.y_start}'] == unit else [0] for key in self.qbuildings_data['buildings_data'].keys()])
            # TO DO: Add an if mult_heating_systemy_y_start is in the data

        else:
            # If no heating system is defined, raise an error
            raise ValueError(f"No heating system defined in pathway_data for year {self.y_start}.") # TO DO: Instead of error, run REHO and use results as initial scenario

        # Check if PV is in the initial scenario
        if f'electric_system_{self.y_start}' in self.pathway_data.columns:
            self.parameters['PV_install'] = np.array(
                [[1] if self.qbuildings_data['buildings_data'][key][f'electric_system_{self.y_start}'] == 'PV' else [0]
                 for key in self.qbuildings_data['buildings_data'].keys()])
        else:
            self.parameters['PV_install'] = np.array([[0] for key in self.qbuildings_data['buildings_data'].keys()])

        if self.parameters['PV_install'].sum() > 0:
            if f'mult_electric_system_{self.y_start}' not in self.pathway_data.columns:
                max_PV = self.get_max_pv_capacity() # if a mult is not provided we install the max PV
            # TO DO: add enforce PV_mult

        #existing_system = self.single_optimization(Pareto_ID=0) # TO DO: substitute Pareto_ID=0 by self.y_start, test if i need existing_system = self.single_optimization(Pareto_ID=0)
        self.single_optimization(Pareto_ID=0) # TO DO: substitute Pareto_ID=0 by self.y_start

        # Remove all specific constraints
        #self.scenario['specific'] = []

        # If the set of time period is not given
        if 'y_span' not in self.pathway_parameters.keys():
            y_span = np.linspace(self.y_start, self.y_end, self.pathway_parameters['N_steps_pathway'], endpoint=True)
        else:
            y_span = self.pathway_parameters['y_span']

        # Phasing out the heating systems method, when I know the final heating system. TO DO: Do the same when I don't know the final heating system, and or the method of increase coverage
        # Create a DataFrame with initial and final heating system for each building
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
            if 'k_factor' in self.pathway_parameters and unit in self.pathway_parameters['k_factor']:
                k_factor = self.pathway_parameters['k_factor'][unit]
            else:
                k_factor = self.default_s_curve_factors.loc[self.default_s_curve_factors['Unit'] == unit, 's_curve_k_factor'].values[0]
            if 'c_factor' in self.pathway_parameters.keys() and unit in self.pathway_parameters['c_factor'].keys():
                c_factor = self.pathway_parameters['c_factor'][unit]
            else:
                c_factor = self.default_s_curve_factors.loc[self.default_s_curve_factors['Unit'] == unit, 's_curve_c_factor'].values[0]

            # Get phase-out timeline (number of buildings using the unit each year)
            phase_out_schedule = self.generate_s_curve(initial_value=N_initial, target_value=N_final, k_factor=k_factor, c_factor=c_factor, y_span=y_span, force_target=True, starting_value=True)
            phase_out_schedule = [int(round(v)) for v in phase_out_schedule]

            # Start with all buildings using this unit (represented by 1)
            initial_state = [1] * N_initial
            # Final state is the final heating system (represented by 0)
            #position_list = [i for i in np.array(range(len(initial_selection))) if np.array(bool_selection)[i] == 1]
            final_state = [1 if i == unit else 0 for i in unit_pathway[self.y_end].values]

            # Use random logic to decide which buildings stop using the unit at each step
            pathway_use_unit = self.select_unit_random(initial_state,phase_out_schedule, method='unit_phase_out', final_selection=final_state)
            #TO DO: test if select_unit_random works well when we have more NG, where some of them don't phase out
            for i in range(1,len(y_span)):
                year = y_span[i]
                # Create column for this year based on phase-out logic
                col = pd.Series(pathway_use_unit[i].flatten(), name=year)
                # Replace 1s with the unit name (still in use), and 0s with the final heating system
                col = col.replace(1, unit)
                col = np.where(col == 0, unit_pathway[self.y_end], col)
                # Add the column to the unit's pathway
                unit_pathway[f'heating_system_{int(year)}'] = col
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

        # List of years you're interested in
        years = ['heating_system_2025','heating_system_2030', 'heating_system_2035', 'heating_system_2040', 'heating_system_2045', 'heating_system_2050']

        # Create a list of dicts for each building
        data = []
        for building_name, building_info in self.qbuildings_data['buildings_data'].items():
            row = {'building': building_name}
            for year in years:
                row[year] = building_info.get(year, None)  # safely get the value or None if missing
            data.append(row)

        # Convert list of dicts to DataFrame
        df = pd.DataFrame(data)

        # Optionally, set the building name as index
        df.set_index('building', inplace=True)


        # Generate pathway for the electric system TO DO: adapt code to when I have more than one electric system
        # Get the logistic curve parameters for PV
        if 'k_factor' in self.pathway_parameters and 'PV' in self.pathway_parameters['k_factor']:
            pv_k_factor = self.pathway_parameters['k_factor']['PV']
        else:
            pv_k_factor = self.default_s_curve_factors.loc[self.default_s_curve_factors['Unit'] == 'PV', 's_curve_k_factor'].values[0]
        if 'c_factor' in self.pathway_parameters.keys() and 'PV' in self.pathway_parameters['c_factor'].keys():
            pv_c_factor = self.pathway_parameters['c_factor']['PV']
        else:
            pv_c_factor = self.default_s_curve_factors.loc[self.default_s_curve_factors['Unit'] == 'PV', 's_curve_c_factor'].values[0]

        # Get phase-in timeline (number of buildings using the unit each year)
        # Get the number of house that can install a PV. TO DO: Some EGIDs might have almost no roof (this might also happen with the heating system), because the ratio is very small in this case mult will be 0.1 the Fmin. Check if we are getting these cases
        PV_init_total = 0
        PV_init_list = []
        PV_final_tot = 0
        PV_final_list = []
        for building, building_data in self.qbuildings_data['buildings_data'].items():
            # Get the number of house that currently installed a PV
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
            elec_schedule = self.generate_s_curve(initial_value=PV_init_total, target_value=PV_final_tot, k_factor=pv_k_factor, c_factor=pv_c_factor, y_span=y_span, force_target=True, starting_value=True)
        else:
            elec_schedule = self.generate_s_curve(initial_value=PV_init_total, target_value=PV_final_tot, k_factor=pv_k_factor, c_factor=pv_c_factor, y_span=y_span, force_target=False, starting_value=True)
        elec_schedule = [int(round(v)) for v in elec_schedule]

        # TO DO: adapt this for if there are mults or not, and if we want to install max or not
        # verify if max_PV has been defined
        if 'max_PV' in locals():
            # max_PV is defined in the local scope
            x = 1 # TO DO: correct this line
        else:
            # max_PV is not defined
            max_PV = self.get_max_pv_capacity()
        # TO DO: change the code for when there are PV installed (mults cannot be max_PV in this case)
        # TO DO: simplify this, maybe put these two codes in get_max_pv_capacity
        df_instalable_mults = max_PV.loc[(max_PV.index.str.contains('PV')) & ~(max_PV.index.str.contains('district'))]
        instalable_mults_future = [np.sum([row['Units_Mult'] for index, row in df_instalable_mults.iterrows() if index.split('_')[-1] == h]) for h in self.infrastructure.House]

        # Get the pathway
        pathway_elec_mul, pathway_elec_use = self.select_unit_random(PV_init_list, elec_schedule, method='unit_phase_in', mults=instalable_mults_future)

        # Loop through all time periods
        for t in range(1, len(y_span)):
            year = int(y_span[t])
            print(year)

            # Update constraints for the current time period
            self.parameters['PV_install'] = pathway_elec_use[t]

            # Initialize HeatPump_install with zeros
            building_keys = list(self.qbuildings_data['buildings_data'].keys())
            self.parameters['HeatPump_install'] = np.array([[0] for key in self.qbuildings_data['buildings_data'].keys()])

            # Loop through each unit type
            for unit in np.unique(Ext_heat_Units):
                if 'HeatPump' in unit:
                    for b_idx, key in enumerate(building_keys):
                        heating_system = self.qbuildings_data['buildings_data'][key][f'heating_system_{year}']
                        if heating_system == unit:
                            self.parameters['HeatPump_install'][b_idx][0] += 1  # Increment if it matches
                else:
                    # For other units, create individual install arrays
                    self.parameters[f'{unit}_install'] = np.array([[1] if self.qbuildings_data['buildings_data'][key][f'heating_system_{year}'] == unit else [0] for key in building_keys])

            # Update the existing conditions
            self.parameters['Units_Ext'] = self.results[self.scenario["name"]][t-1]['df_Unit']['Units_Mult'] #TO DO: substitute t-1 by y_span[t-1]

            # Optimize the new system
            self.single_optimization(Pareto_ID=t) #TO DO: substitute i by y_span[i]

    def generate_s_curve(self, initial_value=1e-2, target_value=1e-3, k_factor=1, c_factor=2035, y_span=[2025, 2050], force_target=False, starting_value=True):
        """
        Generates a logistic (S-curve) trend for EMOO values over a given year span.

        Parameters:
        - initial_value (float): Starting EMOO value (low end of the S-curve).
        - target_value (float): Ending EMOO value (high end of the S-curve).
        - k_factor (float): Controls the steepness of the curve.
        - c_factor (int): Year of the inflection point (center of the curve).
        - y_span (list or np.array): Range of years for the curve.
        - force_target (bool): If True, ensures the last value of the curve is exactly target_value.
        - starting_value (bool): If True, ensures the first value of the curve is exactly initial_value.

        Returns:
        - EMOO_list (np.array): Logistic curve values.
        """
        if initial_value == target_value:
            EMOO_list = [initial_value for key in y_span]
        else:
            EMOO_list = target_value + (initial_value - target_value) / (1 + np.exp(-k_factor * (c_factor - y_span)))
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

    def select_unit_random(self, initial_selection, steps, method, final_selection=None, mults=None): # TO DO: maybe we just nees one function that gets the mul or not depending on the method selected
        """
        Randomly selects buildings to phase in or phase out a unit over time steps.

        Parameters:
        - initial_selection (list): Boolean list where 1 means the building has a unit initially.
        - steps (list): List of time steps indicating how many units should exist at each step.
        - method (str): Either 'unit_phase_in' or 'unit_phase_out'.
        - final_selection (list, optional): Boolean list of final unit configuration.
        - mults (list, optional): Multiplier list (e.g. installed capacities) for buildings.

        Returns:
        - If mults is None: Dict of building unit statuses at each step.
        - If mults is provided: Tuple of (capacities dict, unit statuses dict).
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
