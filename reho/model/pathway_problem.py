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

        #self.scenario['specific'].remove('enforce_PV_max')
        # TO DO: See if necessary to append the enforce_PV again
        #if dummy == True:
        #    self.scenario['specific'].append('enforce_PV')

        return REHO_max_PV

    def execute_pathway_building_scale(self, pathway_data_2, pathway_unit_use=None):

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
            Ext_heat_Units = np.array([self.qbuildings_data['buildings_data'][key][f'heating_system_{self.y_start}'] for key in self.qbuildings_data['buildings_data']])
            for unit in list(np.unique(Ext_heat_Units)):
                if f'enforce_{unit}' not in self.scenario['specific']:
                    self.scenario['specific'].append(f'enforce_{unit}')
                # Add the heating system to the parameters
                self.parameters['{}_install'.format(unit)] = np.array(
                    [[1] if self.qbuildings_data['buildings_data'][key][
                                f'heating_system_{self.y_start}'] == unit else [0]
                     for key in self.qbuildings_data['buildings_data'].keys()])
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
            y_span = list(np.linspace(self.y_start, self.y_end, self.pathway_parameters['N_steps_pathway'], endpoint=True))
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
            phase_out_schedule = self.get_logistic_2(E_start=N_initial,E_stop=N_final,k_factor=k_factor, c_factor=c_factor,y_span=y_span,final_value=True,starting_value=True)
            phase_out_schedule = [int(round(v)) for v in phase_out_schedule]

            # Start with all buildings using this unit (represented by 1)
            initial_state = [1] * N_initial
            # Use random logic to decide which buildings stop using the unit at each step
            pathway_use_unit = self.select_unit_random(initial_state,phase_out_schedule, method='unit_phase_out')
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
            key_name_2 = f'electric_system_{self.y_end}'
            # check if electric_system_{self.y_end} is in qbuildings_data
            if key_name_2 in building_data and building_data[key_name_2] == 'PV':
                PV_final_tot += 1
                PV_final_list = PV_final_list + [1]

        if f'electric_system_{self.y_end}' in self.pathway_data.columns:
            elec_schedule = self.get_logistic_2(E_start=PV_init_total, E_stop=PV_final_tot, k_factor=pv_k_factor, c_factor=pv_c_factor, y_span=y_span, final_value=True,starting_value=True)
        else:
            elec_schedule = self.get_logistic_2(E_start=PV_init_total, E_stop=PV_final_tot, k_factor=pv_k_factor, c_factor=pv_c_factor, y_span=y_span, final_value=False,starting_value=True)
        elec_schedule = [int(round(v)) for v in elec_schedule]

        # TO DO: adapt this for if there are mults or not, and if we want to install max or not
        # verify if max_PV has been defined
        if 'max_PV' in locals():
            # max_PV is defined in the local scope
            x = 1
        else:
            # max_PV is not defined
            max_PV = self.get_max_pv_capacity()
        # TO DO: change the code for when there are PV installed (mults cannot be max_PV in this case)
        mults = max_PV
        # Get the pathway
        pathway_elec_mul, pathway_elec_use = self.select_unit_random(PV_init_list, elec_schedule, method='unit_phase_in', mults=mults)

        # Loop through all time periods
        for i in range(1,len(y_span)):
            print(y_span[i])
            # Update the constraints
            if 'EMOO' in pathway_data_2.keys():
                if 'PV' in pathway_data_2['EMOO'].keys():
                    self.parameters['PV_install'] = pathway_data_2['EMOO']['PV']['Units_Use'][i]

            # Update the existing conditions
            self.parameters['Units_Ext'] = self.results[self.scenario["name"]][i-1]['df_Unit']['Units_Mult'] #TO DO: substitute i-1 by y_span[i-1]

            # Optimize the new system
            self.single_optimization(Pareto_ID=i) #TO DO: substitute i by y_span[i]

    def get_logistic(self,E_start=1e-2,E_stop=1e-3,y_start=2024,y_stop=2050,k_factor=1,c_factor=2035,n_steps=2, final_value=False,starting_value=True):
        """
        Function to generate a logistic curve (S-curve) for the EMOO values
        Parameters:
        - E_start: Initial value of the EMOO
        - E_stop: Final value of the EMOO
        - y_start: Initial year
        - y_stop: Final year
        - k: steepness of the curve
        - c: inflection point of the curve
        - n: number of points
        - final_value: If True, the final value is E_stop
        - starting_value: If True, the starting value is E_start
        Returns:
        - EMOO_list: List of EMOO values
        - y_span: List of years
        """
        y_span=np.linspace(start=y_start,stop=y_stop,num=n_steps,endpoint=True)
        if E_start==E_stop:
            EMOO_list = [E_start for key in y_span]
        else:
            EMOO_list = E_stop+(E_start-E_stop)/(1+np.exp(-k_factor*(c_factor-y_span)))
            if starting_value is True:
                diff_start = E_start
            else:
                diff_start = EMOO_list[0]
            if final_value is True:
                diff_stop=E_stop
            else:
                diff_stop = EMOO_list[-1]
            EMOO_list = (EMOO_list-EMOO_list[0])*(diff_stop-diff_start)/(EMOO_list[-1]-EMOO_list[0]) + diff_start # Stretching the curve
        return EMOO_list, y_span

    def get_logistic_2(self,E_start=1e-2,E_stop=1e-3,k_factor=1,c_factor=2035, y_span=[2025, 2050], final_value=False,starting_value=True):
        """
        Function to generate a logistic curve (S-curve) for the EMOO values
        Parameters:
        - E_start: Initial value of the EMOO
        - E_stop: Final value of the EMOO
        - y_start: Initial year
        - y_stop: Final year
        - k: steepness of the curve
        - c: inflection point of the curve
        - y_span:
        - final_value: If True, the final value is E_stop
        - starting_value: If True, the starting value is E_start
        Returns:
        - EMOO_list: List of EMOO values
        - y_span: List of years
        """
        if E_start==E_stop:
            EMOO_list = [E_start for key in y_span]
        else:
            EMOO_list = E_stop+(E_start-E_stop)/(1+np.exp(-k_factor*(c_factor-y_span)))
            if starting_value is True:
                diff_start = E_start
            else:
                diff_start = EMOO_list[0]
            if final_value is True:
                diff_stop=E_stop
            else:
                diff_stop = EMOO_list[-1]
            EMOO_list = (EMOO_list-EMOO_list[0])*(diff_stop-diff_start)/(EMOO_list[-1]-EMOO_list[0]) + diff_start # Stretching the curve
        return EMOO_list

    def select_unit_random(self, initial_selection, steps, method, mults=None): # TO DO: maybe we just nees one function that gets the mul or not depending on the method selected
        """
        Function to select random buildings to phase_out or phase_in a unit. It receives an array with the number of buildings with a unit in each step.
        - EMOO_bool_tot: each key is a step of the pathway. For each key there is a boolean list of which building has PV installed (example: EMOO_data[0]=[1,0,0,0,0], EMOO_data[2]=[1,0,0,0,1])
        - EMOO_bool: each key is a step of the pathway. For each key there is a boolean list of which building installed PV for the current step(example: EMOO_data[0]=[1,0,0,0,0], EMOO_data[2]=[0,0,0,0,1])
        - EMOO_data: each key is a step of the pathway. For each key, there is the list of PV installed capacity for each building (example: EMOO_data[0]=[5,0,0,0,0], EMOO_data[2]=[5,0,0,0,10])
        """
        if method not in {"unit_phase_in", "unit_phase_out"}:
            raise ValueError("Invalid method. Must be 'unit_phase_in' or 'unit_phase_out'.")

        EMOO_bool = {}
        EMOO_bool_tot = {}
        random.seed(42)

        j = 0
        bool_selection = initial_selection
        EMOO_bool[j] = np.array([[i] for i in bool_selection])
        EMOO_bool_tot[j] = EMOO_bool[j]
        if mults is not None:
            EMOO_data = {}
            EMOO_data[j] = np.array([[i] for i in np.array(mults) * np.array(bool_selection)])
        previous_step = steps[0]
        if method == "unit_phase_in":
            position_list = [i for i in np.array(range(len(initial_selection))) if np.array(bool_selection)[i] == 0] # if a building already has a unit, it cannot be selected
        else:
            position_list = [i for i in np.array(range(len(initial_selection))) if np.array(bool_selection)[i] == 1]
        for step in steps[1:]:
            j += 1
            nb_bui_to_select = abs(step - previous_step)
            if nb_bui_to_select != 0:
                position_selection = random.sample(position_list, k=nb_bui_to_select) # Return a list that contains any k number of the items from a list
            else:
                position_selection = []
            if method == "unit_phase_in":
                bool_selection = np.array(bool_selection) + np.array([1 if i in position_selection else 0 for i in range(len(initial_selection))])
                position_list = [i for i in np.array(range(len(initial_selection))) if np.array(bool_selection)[i] == 0]
                EMOO_bool[j] = np.array([[ii] for ii in [1 if i in position_selection else 0 for i in range(len(initial_selection))]])
            else:
                bool_selection = np.array(bool_selection) - np.array([1 if i in position_selection else 0 for i in range(len(initial_selection))])
                position_list = [i for i in np.array(range(len(initial_selection))) if np.array(bool_selection)[i] == 1]
                EMOO_bool[j] = np.array([[ii] for ii in [0 if i in position_selection else 1 for i in range(len(initial_selection))]])

            EMOO_bool_tot[j] = np.array([[i] for i in bool_selection])
            if mults is not None:
                EMOO_data[j] = np.array([[i] for i in np.array(mults) * np.array(bool_selection)])
            previous_step = step
        if mults is None:
            return EMOO_bool_tot
        else:
            return EMOO_data, EMOO_bool_tot



    def select_values_random(self, initial_selection, steps, values=None):
        """
        This function is used to select random buildings for the pathway.
        For instance, if you have 5 buildings, and you want to gradually install PV in the buildings.
        For each pathway step, you need to specify the number of buildings in which you want PV to be installed: steps=[1,1,2,3,4,4,5,5]
        Here is the list of PV capacity that you want to install: values=[5,5,5,10,10]
        Consider that the first building already has its 5kW installed: initial_selection=[1,0,0,0,0]
        Then, this function will return you 3 dictionaries:
        - EMOO_data: each key is a step of the pathway. For each key, there is the list of PV installed capacity for each building (example: EMOO_data[0]=[5,0,0,0,0], EMOO_data[2]=[5,0,0,0,10])
        - EMOO_bool_tot: each key is a step of the pathway. For each key there is a boolean list of which building has PV installed (example: EMOO_data[0]=[1,0,0,0,0], EMOO_data[2]=[1,0,0,0,1])
        - EMOO_bool: each key is a step of the pathway. For each key there is a boolean list of which building installed PV for the current step(example: EMOO_data[0]=[1,0,0,0,0], EMOO_data[2]=[0,0,0,0,1])
        """
        EMOO_data = {}
        EMOO_bool = {}
        EMOO_bool_tot = {}
        random.seed(42)

        j = 0
        bool_selection = initial_selection
        EMOO_bool[j] = np.array([[i] for i in bool_selection])
        EMOO_bool_tot[j] = EMOO_bool[j]
        EMOO_data[j] = np.array([[i] for i in np.array(values) * np.array(bool_selection)])
        previous_step = steps[0]
        position_list = [i for i in np.array(range(len(values))) if np.array(bool_selection)[i] == 0]
        for step in steps[1:]:
            j += 1
            nb_bui_to_select = step - previous_step
            if nb_bui_to_select != 0:
                position_selection = random.sample(position_list, k=nb_bui_to_select) #Return a list that contains any k of the items from a list
            else:
                position_selection = []
            bool_selection = np.array(bool_selection) + np.array([1 if i in position_selection else 0 for i in range(len(values))])
            position_list = [i for i in np.array(range(len(values))) if np.array(bool_selection)[i] == 0]
            EMOO_bool[j] = np.array([[ii] for ii in [1 if i in position_selection else 0 for i in range(len(values))]])
            EMOO_bool_tot[j] = np.array([[i] for i in bool_selection])
            EMOO_data[j] = np.array([[i] for i in np.array(values) * np.array(bool_selection)])
            previous_step = step

        return EMOO_data, EMOO_bool, EMOO_bool_tot