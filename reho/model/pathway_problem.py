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
    def __init__(self, qbuildings_data, units, grids, parameters=None, set_indexed=None, cluster=None, method=None, scenario=None, solver="highs", DW_params=None):

        super().__init__(qbuildings_data, units, grids, parameters, set_indexed, cluster, method, scenario, solver, DW_params)

    def execute_pathway_building_scale(self,pathway_data,existing_system):

        #TO DO: The initial scenario should be built here

        # Get the scenario name
        Scn_ID = self.scenario["name"]  # Do we need this scenario identification?

        # Insert initial system as first result
        self.results = {}
        self.results[Scn_ID] = {}
        self.results[Scn_ID][0] = existing_system

        # Remove all specific constraints
        #self.scenario['specific'] = []

        # If the set of time period is not given
        if 'y_span' not in pathway_data.keys():
            y_span = list(np.linspace(pathway_data['y_start'], pathway_data['y_end'], pathway_data['y_steps']))
            #y_span = list(np.linspace(2025, 2050, len(pathway_data['EMOO'][list(pathway_data['EMOO'].keys())[0]])))
        else:
                y_span = pathway_data['y_span']

        # Loop through all time periods
        for i in range(1,len(y_span)):
            print(y_span[i])
            # Update the constraints
            if 'EMOO' in pathway_data.keys():
                if 'PV' in pathway_data['EMOO'].keys():
                    self.parameters['PV_install'] = pathway_data['EMOO']['PV']['Units_Use'][i]

            # Update the existing conditions
            self.parameters['Units_Ext'] = self.results[Scn_ID][i-1]['df_Unit']['Units_Mult']* 0.99

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