import random

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



    def execute_pathway_building_scale(self, pathway_data_2, existing_system):
        """
        #TO DO: The initial scenario should be built here
        # Set up initial scenario
        self.scenario['specific'] = ['unique_heating_system', # Do not allow two different heating systems (Ex: not NG boiler and heatpump simultaneously)
                                     'enforce_PV',            # Enforce PV Units_Use to 0 or 1 on all buildings
                                     #'enforce_Battery'        # Enforce Battery Units_Use to 0 or 1 on all buildings
                                     ]

        # Check if the initial heating scenario is defined with
        if f'heating_system_{self.pathway_parameters['y_start']}' in self.pathway_data.columns:
            # Add enforce heating units in the scenario['specific']
            Ext_heat_Units = list(self.pathway_data[f'heating_system_{self.pathway_parameters['y_start']}'].unique())
            for unit in Ext_heat_Units:
                if f'enforce_{unit}' not in self.scenario['specific']:
                    self.scenario['specific'].append(f'enforce_{unit}')

            # Add existing heating system in qbuildings_data based on the egid
            for key in self.qbuildings_data['buildings_data'].keys():
                # get egid of the building
                egid = self.qbuildings_data['buildings_data'][key]['egid']
                # Find matching row in pathway_data
                match_row = self.pathway_data[self.pathway_data['egid'] == egid]
                if not match_row.empty:
                    # Get the data from match_row columns except for egid and add it to the qbuildings_data TO DO: check if I should add al info now or as needed. seems mo efficient to add all now, even if not used
                    for i in match_row.columns:
                        if i != 'egid':
                            self.qbuildings_data['buildings_data'][key][i] = match_row[i].values[0]
                else:
                    # If no match found, give error message and end the program
                    raise ValueError(f"No match found for egid {egid} in pathway_data.")

            # Add the heating system to the parameters
            for heating_system in Ext_heat_Units:
                self.parameters['{}_install'.format(heating_system)] = np.array(
                    [1 if self.qbuildings_data['buildings_data'][key][f'heating_system_{self.pathway_parameters['y_start']}'] == heating_system else 0
                     for key in self.qbuildings_data['buildings_data'].keys()])

        # TO DO: Add an if mult_heating_systemy_y_stat is in the data

        else:
            # If no heating system is defined, raise an error
            raise ValueError(f"No heating system defined in pathway_data for year {self.pathway_parameters['y_start']}.") # TO DO: Instead of error, run REHO and use results as initial scenario

        # Check if PV is in the initial scenario
        if f'electric_system_{self.pathway_parameters['y_start']}' in self.pathway_data.columns:
            self.parameters['PV_install'] = np.array(
                [1 if self.qbuildings_data['buildings_data'][key][f'electric_system_{self.pathway_parameters['y_start']}'] == 'PV' else 0
                 for key in self.qbuildings_data['buildings_data'].keys()])
        else:
            self.parameters['PV_install'] = np.array([[0] for key in self.qbuildings_data['buildings_data'].keys()])

        if self.parameters['PV_install'].sum() > 0:
            if f'mult_electric_system_{self.pathway_parameters['y_start']}' not in self.pathway_data.columns:
            max_PV = self.get_max_pv_capacity()

        existing_system = self.single_optimization(Pareto_ID=0)
        """







        # Get the scenario name
        Scn_ID = self.scenario["name"]  # Do we need this scenario identification?

        # Insert initial system as first result
        self.results = {}
        self.results[Scn_ID] = {}
        self.results[Scn_ID][0] = existing_system

        # Remove all specific constraints
        #self.scenario['specific'] = []

        # If the set of time period is not given
        if 'y_span' not in pathway_data_2.keys():
            y_span = list(np.linspace(pathway_data_2['y_start'], pathway_data_2['y_end'], pathway_data_2['y_steps']))
        else:
            y_span = pathway_data_2['y_span']

        # Loop through all time periods
        for i in range(1,len(y_span)):
            print(y_span[i])
            # Update the constraints
            if 'EMOO' in pathway_data_2.keys():
                if 'PV' in pathway_data_2['EMOO'].keys():
                    self.parameters['PV_install'] = pathway_data_2['EMOO']['PV']['Units_Use'][i]

            # Update the existing conditions
            self.parameters['Units_Ext'] = self.results[Scn_ID][i-1]['df_Unit']['Units_Mult']

            # Optimize the new system
            self.single_optimization(Pareto_ID=i)

    def get_logistic(self,E_start=1e-2,E_stop=1e-3,y_start=2024,y_stop=2050,k=1,c=2035,n=2, final_value=False,starting_value=True):
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
        y_span=np.linspace(start=y_start,stop=y_stop,num=n,endpoint=True)
        if E_start==E_stop:
            EMOO_list=[E_start for key in y_span]
        else:
            EMOO_list=E_stop+(E_start-E_stop)/(1+np.exp(-k*(c-y_span)))
            if starting_value is True:
                diff_start=E_start
            else:
                diff_start=EMOO_list[0]
            if final_value is True:
                diff_stop=E_stop
            else:
                diff_stop=EMOO_list[-1]
            EMOO_list=(EMOO_list-EMOO_list[0])*(diff_stop-diff_start)/(EMOO_list[-1]-EMOO_list[0])+diff_start# Stretching the curve
        return EMOO_list, y_span

    def select_values_random(self, values, initial_selection, steps):
        """
        This function is used to select random buildings for the pathway.
        For instance, if you have 5 buildings and you want to gradually install PV in the buildings.
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
                position_selection = random.sample(position_list, nb_bui_to_select)
            else:
                position_selection = []
            bool_selection = np.array(bool_selection) + np.array(
                [1 if i in position_selection else 0 for i in range(len(values))])
            position_list = [i for i in np.array(range(len(values))) if np.array(bool_selection)[i] == 0]
            EMOO_bool[j] = np.array([[ii] for ii in [1 if i in position_selection else 0 for i in range(len(values))]])
            EMOO_bool_tot[j] = np.array([[1 if i != 0 else 0] for i in np.array(values) * np.array(bool_selection)])
            EMOO_data[j] = np.array([[i] for i in np.array(values) * np.array(bool_selection)])
            previous_step = step
        return EMOO_data, EMOO_bool, EMOO_bool_tot