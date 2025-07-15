import copy
import gc
import time
import multiprocessing as mp
from itertools import groupby

import coloredlogs
import pandas as pd

import reho.model.infrastructure as infrastructure
from reho.model.preprocessing.local_data import *
import reho.model.preprocessing.mobility_generator as mobility
import reho.model.postprocessing.write_results as write_results

from reho.model.sub_problem import *

__doc__ = """
File for handling data and optimization for an AMPL master problem.
"""


class MasterProblem:
    """
    Applies the decomposition method.

    Stores district attributes, scenario, method, attributes for the decomposition, and initiate an attribute
    that will store results.

    Parameters
    ----------
    qbuildings_data : dict
        Contains 3 layers: A dictionary of the buildings characteristics such as surface area, class, egid, a DataFrame for Roofs characteristics and a DataFrame for Facades characteristics.
    units : dict
        Units characteristics.
    grids : dict
        Grids characteristics.
    parameters : dict, optional
        Parameters set in the script (usually energy tariffs).
    set_indexed : dict, optional
        The indexes used in the model.
    cluster : dict, optional
        Define location, number of periods, and number of timesteps.
        To use your own weather file, you can add a key ``custom_weather`` with the corresponding path.
    method : dict, optional
        The different methods to run the optimization (refer to :ref:`tbl-methods`).
    solver : str, optional
        Chosen solver for AMPL (gurobi, cplex, highs, cbc, etc.).
    DW_params : dict, optional
        Hyperparameters of the decomposition and other useful information.

    Notes
    -----
    - The REHO class inherits this class, so the inputs are similar.
    - ``qbuildings_data`` contains by default only the buildings' data. The roofs and facades are added solely with the use of methods: *use_pv_orientation* and *use_facades*.
    """

    def __init__(self, qbuildings_data, units, grids, parameters=None, set_indexed=None,
                 cluster=None, method=None, solver=None, DW_params=None):

        # ampl solver
        self.solver = solver

        # methods
        self.method = initialize_default_methods(method)
        self.logger = logging.getLogger(__name__)
        if method['print_logs']:
            coloredlogs.install(level=logging.INFO, logger=self.logger, isatty=True,
                                fmt="%(message)s", stream=sys.stdout)

        # infrastructure
        self.qbuildings_data = qbuildings_data
        self.buildings_data = qbuildings_data['buildings_data']
        self.ERA = sum([self.buildings_data[house]['ERA'] for house in self.buildings_data.keys()])

        self.infrastructure = infrastructure.Infrastructure(qbuildings_data, units, grids)
        self.infrastructure_SP = dict()
        self.build_infrastructure_SP()

        if cluster is None:
            self.cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}
        else:
            self.cluster = copy.deepcopy(cluster)

        # load SIA norms
        sia_data = dict()
        sia_data["df_SIA_380"] = pd.read_csv(path_to_sia_equivalence, sep=';', index_col=[0], header=[0])
        sia_data["df_SIA_2024"] = pd.read_excel(path_to_sia_norms, sheet_name=['profiles', 'calculs', 'data'],
                                                engine='openpyxl', index_col=[0], skiprows=[0, 2, 3, 4], header=[0])

        # retrieve location data
        self.local_data = return_local_data(cluster, qbuildings_data)

        if parameters is None:
            self.parameters = {}
        else:
            self.parameters = copy.deepcopy(parameters)

        # build end use demands profile
        self.parameters['HeatGains'], self.parameters['DHW_flowrate'], self.parameters['Domestic_electricity'] = \
            buildings_profiles.eud_profiles(self.buildings_data, self.cluster, sia_data["df_SIA_380"], sia_data["df_SIA_2024"], self.local_data["df_Timestamp"],
                                            self.method['include_stochasticity'], self.method['sd_stochasticity'], self.method['use_custom_profiles'])

        # build solar gains profile
        self.parameters['SolarGains'] = buildings_profiles.solar_gains_profile(self.qbuildings_data, sia_data, self.local_data)

        if set_indexed is None:
            self.set_indexed = {}
        else:
            self.set_indexed = copy.deepcopy(set_indexed)

        # prepare mobility data
        self.modal_split = None

        # attributes for the decomposition algorithm
        if DW_params is None:
            self.DW_params = {}  # init of values in initiate_decomposition method
        else:
            self.DW_params = copy.deepcopy(DW_params)
        self.DW_params = self.initialise_DW_params(self.DW_params, self.cluster, self.buildings_data)
        self.cpu_use = mp.cpu_count()

        # TODO change the nomenclature of these parameters to semi-automate the separation between MP and SP: (ex: all MP parameters end with _MP)
        self.lists_MP = {"list_parameters_MP": ['Uh', 'Uh_ins', 'ins_target', 'renter_subsidies_bound', 'renter_expense_max','utility_profit_min', 'owner_PIR_max', 'owner_PIR_min', 'EMOO_totex_renter',
                                                'Network_ext', "ff_EV",
                                                'monthly_grid_connection_cost',
                                                "area_district", "velocity", "density", "delta_enthalpy", "cinv1_dhn", "cinv2_dhn", "Population",
                                                "transport_Units", "DailyDist", "Mode_Speed", "Cost_demand_ext", "EV_supply_ext", "share_activity", "Cost_supply_ext",
                                                'EV_y', 'EV_plugged_out', 'n_vehicles', 'EV_capacity',
                                                "max_share", "min_share", "max_share_modes", "min_share_modes", "n_ICEperhab",
                                                "Cost_network_inv1", "Cost_network_inv2", "GWP_network_1", "GWP_network_2", "Units_Ext_district",
                                                "Network_lifetime"],
                         "list_constraints_MP": [],
                         "list_set_indexed_MP": ["Districts", "Distances"]
                         }

        if "EV_district" in self.infrastructure.UnitsOfDistrict:
            self.lists_MP["list_constraints_MP"] += ['unidirectional_service', 'unidirectional_service2', "EV_chargingprofile1", "EV_chargingprofile2",
                                                     'ExternalEV_Costs_positive']

        if self.method['actors_problem']:
            self.lists_MP["list_constraints_MP"] += ['Owner_Link_Subsidy_to_Insulation', 'Owner_profit_max_PIR', 'Owner_noSub', 'Renter_noSub']

        self.df_fix_Units = pd.DataFrame()

    def initialize_optimization_tracking_attributes(self):
        # internal IT parameter
        self.pool = None
        self.iter = 0  # keeps track of iterations, takes value of last iteration circle
        self.feasible_solutions = 0  # keeps track how many sets of SP solutions are proposed to the MP eg '2' means two per building
        list_obj = ["TOTEX", "CAPEX", "OPEX", "GWP"]
        self.flags = {obj: 0 for obj in list_obj}  # keep track if the initialization has already been done

        # output attributes
        self.stopping_criteria = pd.DataFrame()

        # result attributes
        self.number_SP_solutions = pd.DataFrame()  # records number of solutions per iteration circle
        self.number_MP_solutions = pd.DataFrame()  # records number of solutions per iteration circle

        self.results_SP = dict()
        self.results_MP = dict()

        self.solver_attributes_SP = pd.DataFrame()
        self.solver_attributes_MP = pd.DataFrame()
        self.reduced_costs = pd.DataFrame()

    def __getstate__(self):
        self_dict = self.__dict__.copy()
        if hasattr(self, 'pool'):
            del self_dict['pool']
        return self_dict

    def __setstate__(self, state):
        self.__dict__.update(state)

    def select_SP_obj_decomposition(self, scenario):
        """
        The SPs in decomposition have another objective than in the compact formulation because their objective function is formulated as a reduced cost.
        Also adding global linking constraints, like Epsilon, changes the scenario to choose.

        Parameters
        ------
        scenario : dictionary
            objective function

        Returns
        -------
        SP_scenario : dictionary
            scenario for the SP (iterations)
        SP_scenario_init : dictionary
            scenario for the SP (initiation)

        """
        SP_scenario = scenario.copy()
        SP_scenario['EMOO'] = {}
        SP_scenario['specific'] = scenario['specific'].copy()

        SP_scenario_init = scenario.copy()
        SP_scenario_init['EMOO'] = scenario['EMOO'].copy()
        SP_scenario_init['specific'] = scenario['specific'].copy()

        # use GM or GU only for initialization. Then pi dictates when to restrict power exchanges
        SP_scenario_init['EMOO']['EMOO_grid'] = SP_scenario_init['EMOO']['EMOO_grid'] * 0.999

        if "Network_ext" in self.parameters:
            if isinstance(self.parameters["Network_ext"], pd.DataFrame):
                capacity = self.parameters["Network_ext"].xs("Electricity")[0]
            else:
                capacity = self.parameters["Network_ext"][0]
        else:
            capacity = self.infrastructure.Grids_Parameters["Network_ext"].xs("Electricity")
        nb_buildings = round(self.parameters["Domestic_electricity"].shape[0] / self.DW_params['timesteps'])
        profile_building_x = self.parameters["Domestic_electricity"].reshape(nb_buildings, self.DW_params['timesteps'])
        max_DEL = profile_building_x.max(axis=1).sum()
        SP_scenario_init['EMOO']['EMOO_GU_demand'] = capacity * 0.999 / max_DEL
        SP_scenario_init['EMOO']['EMOO_GU_supply'] = capacity * 0.999 / max_DEL

        for scenario_cst in scenario['specific']:
            if scenario_cst in self.lists_MP['list_constraints_MP']:
                SP_scenario['specific'].remove(scenario_cst)
                SP_scenario_init['specific'].remove(scenario_cst)

        return scenario, SP_scenario, SP_scenario_init

    def initiate_decomposition(self, scenario, Scn_ID=0, Pareto_ID=1, epsilon_init=None):
        """
        The SPs are initialized for the given objective.
        In case the optimization includes an epsilon constraint, there are two ways to initialize.
        Either the epsilon constraint is applied on the SPs, or the initialization is done with beta.
        The former has the risk to be infeasible for certain SPs, therefore the latter is preferred.
        Three beta values are given to mark the extreme points and an average point.
        Sets up the parallel optimization if needed

        Parameters
        ----------
        scenario : dictionary
            Which objective function to optimize and the value of epsilon constraints to apply
        Scn_ID : int
            ID of the optimization scenario
        Pareto_ID : int
            Id of the pareto point. For single objective optimization it is 1 by default
        epsilon_init : array
            Epsilon constraints to apply for the initialization
        """
        # check if TOTEX, OPEX or multi-objective optimization -> init with beta
        if self.method["skip_initiation"]:
            init_beta = []
        elif self.method['building-scale'] or self.method['actors_problem']:
            init_beta = [None]  # keep same objective function
        elif not self.method['include_all_solutions'] or self.flags[scenario['Objective']] == 0 or scenario['EMOO']['EMOO_grid'] != 0:
            self.flags[scenario['Objective']] = 1  # never been optimized with this objective previously
            init_beta = [1000.0, 1, 0.001]
        else:
            init_beta = []  # skip the initialization

        for beta in init_beta:  # execute SP for MP initialization
            self.launch_SP_multiprocessing(scenario, Scn_ID, Pareto_ID, epsilon_init, beta, initiation=True)

            if self.method['refurbishment'] is not None:
                for option in self.method['refurbishment']:
                    self.launch_SP_multiprocessing(scenario, Scn_ID, Pareto_ID, None, None, initiation=True, refurbishment_options=option)

        return

    def launch_SP_multiprocessing(self, scenario, Scn_ID, Pareto_ID, epsilon_init, beta, initiation=True, refurbishment_options=None):

        if self.method['parallel_computation']:
            # to run multiprocesses, a copy of the model is performed with pickles -> make sure there are no ampl libraries
            if initiation:
                results = {h: self.pool.apply_async(self.SP_initiation_execution, args=(scenario, Scn_ID, Pareto_ID, h, epsilon_init, beta, refurbishment_options)) for h in self.infrastructure.houses}
            else:
                results = {h: self.pool.apply_async(self.SP_execution, args=(scenario, Scn_ID, Pareto_ID, h, refurbishment_options)) for h in self.infrastructure.houses}

            # sometimes, python goes to fast and extract the results before calculating them. This step makes python wait finishing the calculations
            while len(results[list(self.buildings_data.keys())[-1]].get()) != 2:
                time.sleep(1)

            # the memory to write and share results is not parallel -> results have to be stored outside calculation
            for h in self.infrastructure.houses:
                (df_Results, attr) = results[h].get()
                self.add_df_Results_SP(Scn_ID, Pareto_ID, self.iter, h, df_Results, attr)
        else:
            for h in self.infrastructure.houses:
                if initiation:
                    df_Results, attr = self.SP_initiation_execution(scenario, Scn_ID, Pareto_ID, h, epsilon_init, beta, refurbishment_options)
                else:
                    df_Results, attr = self.SP_execution(scenario, Scn_ID, Pareto_ID, h, refurbishment_options)

                self.add_df_Results_SP(Scn_ID, Pareto_ID, self.iter, h, df_Results, attr)

        self.feasible_solutions += 1  # after each 'round' of SP execution the number of feasible solutions increase
        return

    def SP_initiation_execution(self, scenario, Scn_ID=0, Pareto_ID=1, h=None, epsilon_init=None, beta=None, refurbishment_options=None):
        """
        Adapts the model depending on the method, execute the optimization and get the results

        Parameters
        ----------
        scenario : dictionary
            Which objective function to optimize and the value of epsilon constraints to apply
        Scn_ID : int
            scenario ID
        Pareto_ID : int
            Id of the pareto point. For single objective optimization it is 0 by default.
        h : string
            House id
        epsilon_init : float
            Epsilon constraint to apply for the initialization
        beta : float
            Beta initial value used for initialization

        Returns
        -------
        df_Results :
            results of the optimization (unit installed, power exchanged, costs, GWP emissions, ...)
        attr :
            results of the optimization process (CPU time, objective value, nb variables or constraints, ...)
        """
        if self.method["print_logs"]:
            print('INITIATE HOUSE: ' + h)

        # find district structure and parameter for one single building
        buildings_data_SP, parameters_SP, set_indexed_SP = self.split_parameter_sets_per_building(h)

        if refurbishment_options is not None:
            buildings_data_SP[h]['U_h'], parameters_SP['Costs_ins'], parameters_SP['GWP_ins'] = refurbishment.refurbishment_cost_co2(buildings_data_SP[h], self.local_data, refurbishment_options)

        # epsilon constraints on districts may lead to infeasibilities on building level -> apply them in MP only
        if epsilon_init is not None and self.method['building-scale']:
            emoo = scenario["EMOO"].copy()
            for key in ["EMOO_grid", "EMOO_GU_demand", "EMOO_GU_supply"]:
                emoo.pop(key)
            if len(emoo) == 1:
                scenario["EMOO"][list(emoo.keys())[0]] = epsilon_init.loc[h]
            else:
                raise warnings.warn("Multiple epsilon constraints")
        elif not self.method['building-scale']:
            scenario, beta_list = self.get_beta_values(scenario, beta)
            parameters_SP['beta_duals'] = beta_list

        if self.method['use_facades'] or self.method['use_pv_orientation']:
            REHO = SubProblem(self.infrastructure_SP[h], buildings_data_SP, self.local_data, parameters_SP, set_indexed_SP, self.cluster, scenario, self.method,
                              self.solver, self.qbuildings_data)
        else:
            REHO = SubProblem(self.infrastructure_SP[h], buildings_data_SP, self.local_data, parameters_SP, set_indexed_SP, self.cluster, scenario, self.method,
                              self.solver)

        ampl = REHO.build_model_without_solving()

        if self.method['fix_units']:
            for unit in self.df_fix_Units.index[self.df_fix_Units.index.str.contains(h)]:
                if unit == 'PV_' + h:
                    ampl.getVariable('Units_Mult').get(unit).fix(self.df_fix_Units.Units_Mult.loc[unit] * (1 - 1e-9))
                    ampl.getVariable('Units_Use').get(unit).fix(float(self.df_fix_Units.Units_Use.loc[unit]))
                else:
                    ampl.getVariable('Units_Mult').get(unit).fix(self.df_fix_Units.Units_Mult.loc[unit])
                    ampl.getVariable('Units_Use').get(unit).fix(float(self.df_fix_Units.Units_Use.loc[unit]))

        ampl.solve()
        exitcode = exitcode_from_ampl(ampl)

        df_Results = write_results.get_df_Results_from_SP(ampl, scenario, self.method, buildings_data_SP)
        attr = self.get_solver_attributes(Scn_ID, Pareto_ID, ampl)

        del ampl
        gc.collect()  # free memory
        if exitcode != 0:
            # It might be that the solution is optimal with unscaled infeasibilities. So we check if we really found a solution (via its cost value)
            if exitcode != 'solved?' or df_Results["df_Performance"]['Costs_op'][0] + df_Results["df_Performance"]['Costs_inv'][0] == 0:
                raise Exception('Sub problem did not converge with building', h)

        return df_Results, attr

    def MP_iteration(self, scenario, binary, Scn_ID=0, Pareto_ID=1, read_DHN=False):
        """

        Runs the optimization of the Master Problem (MP):

        - Creates the ampl_MP master problem
        - Sets the sets and the parameters in ampl
        - Actualises the grid exchanges and the costs of each sub problem (house) without the grid costs
        - Runs the optimization
        - Extracts the results (lambda, dual variables pi and mu, objective value of the MP (TOTEX, grid exchanges, ...)
        - Deletes the ampl_MP model

        Parameters
        -----------
        scenario : dictionary
        binary : boolean
            if the decision variable 'lambda' is binary or continuous
        Scn_ID : int
        Pareto_ID: int
        read_DHN : bool

        Raises
        ------
        ValueError: If the sets are not arrays or if the parameters are not arrays or floats or dataframes. Or if the MP optimization did not converge
        """

        if "AMPL_PATH" in os.environ:
            try:
                ampl_MP = AMPL(Environment(os.environ["AMPL_PATH"]))
            except:
                raise Exception(f"Failed to use the local AMPL license as specified by AMPL_PATH: {os.environ['AMPL_PATH']}.")
        else:
            try:
                from amplpy import modules
                modules.load()
                ampl_MP = AMPL()
            except:
                raise Exception(
                    "No AMPL license was found. Please refer to the documentation to set the AMPL license: https://reho.readthedocs.io/en/main/sections/5_Getting_started.html#ampl-license")

        # AMPL (GNU) OPTIONS
        ampl_MP.setOption('solution_round', 11)
        ampl_MP.setOption('rel_boundtol', 1e-12)
        ampl_MP.setOption('presolve_eps', 1e-4)  # -ignore difference between upper and lower bound by this tolerance
        ampl_MP.setOption('presolve_inteps', 1e-6)  # -tolerance added/substracted to each upper/lower bound
        ampl_MP.setOption('presolve_fixeps', 1e-9)
        if not self.method['print_logs']:
            ampl_MP.setOption('show_stats', 0)
            ampl_MP.setOption('solver_msg', 0)

        # -SOLVER OPTIONS
        ampl_MP.setOption('solver', self.solver)
        if self.solver == "gurobi":
            ampl_MP.eval("option gurobi_options 'NodeFileStart=0.5' 'IntFeasTol=1e-6';")

        ampl_MP.eval('option show_boundtol 0;')
        ampl_MP.eval('option abs_boundtol 1e-10;')

        # Load Master Problem (MP) Formulation
        ampl_MP.cd(path_to_ampl_model)
        ampl_MP.read('master_problem.mod')

        if self.method["actors_problem"]:
            ampl_MP.read('actors_problem.mod')

        # Load battery units (district-scale, but same model as building-scale)
        ampl_MP.cd(path_to_units)
        if "Battery_district" in self.infrastructure.UnitsOfDistrict:
            ampl_MP.read('battery.mod')

        # Load district units
        ampl_MP.cd(path_to_district_units)
        if len(self.infrastructure.UnitsOfDistrict) > 0:
            ampl_MP.cd(path_to_district_units)
            if "Mobility" in self.infrastructure.UnitsOfLayer:
                ampl_MP.read('mobility.mod')
            if "EV_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read('evehicle.mod')
            if "Bike_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read('bike.mod')
            if "ElectricBike_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read('electricbike.mod')
            if "ICE_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read('icevehicle.mod')
            if "NG_Boiler_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read('ng_boiler_district.mod')
            if "HeatPump_Geothermal_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read('heatpump_district.mod')
            if "NG_Cogeneration_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read('ng_cogeneration_district.mod')
            if "rSOC_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read('rsoc_district.mod')
            if "MTR_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read('methanator_district.mod')
        if read_DHN:
            ampl_MP.read('dhn.mod')

        # Load interperiod storage units
        ampl_MP.cd(path_to_units_interperiod)
        if self.method["interperiod_storage"]:
            if "Battery_IP_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read("battery_IP.mod")
            if "CH4_storage_IP_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read("CH4storage_IP.mod")
            if "H2_storage_IP_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read("H2storage_IP.mod")
            if "CO2_storage_IP_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read("CO2storage_IP.mod")

        clustering_directory = os.path.join(path_to_clustering, self.local_data['File_ID'])
        ampl_MP.cd(clustering_directory)

        ampl_MP.readData('frequency.csv')
        ampl_MP.readData('index.csv')
        ampl_MP.cd(path_to_ampl_model)

        # -------------------------------------------------------------------------------------------------------------
        # Set Parameters, only bool to choose if including all solutions found also from other Pareto_IDs
        # ------------------------------------------------------------------------------------------------------------
        # collect data
        df_Performance = self.return_combined_SP_results(self.results_SP, 'df_Performance')
        df_Performance = df_Performance.drop(index='Network', level='Hub').groupby(level=['Scn_ID', 'Pareto_ID', 'FeasibleSolution', 'Hub']).head(1).droplevel(
            'Hub')  # select current Scn_ID and Pareto_ID
        df_Grid_t = np.round(self.return_combined_SP_results(self.results_SP, 'df_Grid_t'), 6)
        df_Buildings = self.return_combined_SP_results(self.results_SP, 'df_Buildings')
        df_Buildings = df_Buildings[df_Buildings.index.get_level_values('house') == df_Buildings.index.get_level_values('Hub')].droplevel('Hub')

        # apply slicing or level-dropping uniformly to all three DataFrames
        dfs = [df_Performance, df_Grid_t, df_Buildings]
        if not self.method['include_all_solutions']:
            dfs = [df.xs((Scn_ID, Pareto_ID), level=('Scn_ID', 'Pareto_ID')) for df in dfs]
        else:
            dfs = [df.droplevel(['Scn_ID', 'Pareto_ID']) for df in dfs]
        df_Performance, df_Grid_t, df_Buildings = dfs

        df_Performance = df_Performance.droplevel(level='Iter')
        df_Grid_t = df_Grid_t.droplevel(level=['Iter', 'Hub']).reorder_levels(['Layer', 'FeasibleSolution', 'house', 'Period', 'Time'])
        df_Buildings = df_Buildings.droplevel(level='Iter')

        # assign data
        MP_parameters = {}
        MP_parameters['Costs_inv_rep_SPs'] = df_Performance.Costs_inv + df_Performance.Costs_rep
        MP_parameters['Costs_ft_SPs'] = pd.DataFrame(np.round(df_Performance.Costs_ft, 6)).set_axis(['Costs_ft_SPs'], axis=1)
        MP_parameters['GWP_house_constr_SPs'] = pd.DataFrame(df_Performance.GWP_constr).set_axis(['GWP_house_constr_SPs'], axis=1)

        MP_parameters['Grids_Parameters'] = self.infrastructure.Grids_Parameters
        MP_parameters['Units_flowrate'] = self.infrastructure.Units_flowrate.query('Unit.str.contains("district")')
        MP_parameters['Units_Parameters'] = self.infrastructure.Units_Parameters.query('index.str.contains("district")')

        if self.method['use_dynamic_emission_profiles']:
            MP_parameters['GWP_supply'] = self.local_data["df_Emissions_GWP100a"]['GWP_supply']
            MP_parameters['GWP_demand'] = MP_parameters["GWP_supply"] * (1 - 1e-9)

        MP_parameters['df_grid'] = df_Grid_t[['Grid_demand', 'Grid_supply']]
        MP_parameters['ERA'] = np.asarray([self.buildings_data[house]['ERA'] for house in self.buildings_data.keys()])
        MP_parameters['Area_tot'] = self.ERA

        if "Mobility" in self.infrastructure.UnitsOfLayer:
            mobility_parameters = mobility.generate_mobility_parameters(self.cluster, self.parameters, self.infrastructure, self.modal_split)
            for param in mobility_parameters:
                MP_parameters[param] = mobility_parameters[param]

        if read_DHN:
            if 'T_DHN_supply_cst' and 'T_DHN_return_cst' in self.parameters:
                if not self.method["DHN_CO2"]:
                    dT = np.array(self.parameters["T_DHN_supply_cst"] - self.parameters["T_DHN_return_cst"])
                    MP_parameters['delta_enthalpy'] = dT.mean() * 4.18
                    MP_parameters['density'] = 1000

            if "area_district" not in MP_parameters:
                min_x, min_y, max_x, max_y = gpd.GeoDataFrame.from_dict(self.buildings_data, orient="index").total_bounds
                MP_parameters["area_district"] = (max_x - min_x) * (max_y - min_y)
        else:
            if "area_district" in MP_parameters:
                del MP_parameters["area_district"]

        for key in self.lists_MP['list_parameters_MP'] + ["Cost_supply_network", "Cost_demand_network"]:
            if key in self.parameters.keys():
                if key == "Units_Ext_district":
                    MP_parameters["Units_Ext"] = self.parameters[key]
                else:
                    MP_parameters[key] = self.parameters[key]

        # -------------------------------------------------------------------------------------------------------------
        # Set Sets
        # ------------------------------------------------------------------------------------------------------------
        MP_set_indexed = {}
        additional = []
        if 'ReinforcementOfNetwork' in self.infrastructure.Set.keys():
            additional = additional + ["ReinforcementOfNetwork"]

        for sets in ['House', 'Layers', 'LayerTypes', 'LayersOfType', 'HousesOfLayer'] + additional:
            MP_set_indexed[sets] = self.infrastructure.Set[sets]
        MP_set_indexed['LayersOfType']['ResourceBalance'].sort()

        MP_set_indexed['UnitsOfLayer'] = dict()
        for layer in self.infrastructure.Set['UnitsOfLayer']:
            lst = self.infrastructure.Set['UnitsOfLayer'][layer]
            MP_set_indexed['UnitsOfLayer'][layer] = np.array(list(filter(lambda k: 'district' in k, lst)))

        MP_set_indexed['FeasibleSolutions'] = df_Performance.index.unique('FeasibleSolution').to_numpy()  # index to array as set

        if self.method['actors_problem']:
            if "ActorObjective" in self.set_indexed:
                MP_set_indexed['ActorObjective'] = self.set_indexed["ActorObjective"]

            df_Unit_t = self.return_combined_SP_results(self.results_SP, 'df_Unit_t').xs("Electricity", level="Layer")
            df_PV_t = pd.DataFrame()
            for bui in self.infrastructure.houses:
                df_PV_t = pd.concat([df_PV_t, df_Unit_t.xs("PV_" + bui, level="Unit")])
            MP_parameters["PV_prod"] = df_PV_t["Units_supply"].droplevel(["Scn_ID", "Pareto_ID", "Iter"])
            MP_parameters["Uh"] = pd.DataFrame.from_dict({house:self.buildings_data[house]['U_h'] for house in self.buildings_data.keys()}, orient="Index").rename(columns={0: "Uh"})
            MP_parameters["Uh_ins"] = df_Buildings[["U_h"]].rename(columns={"U_h": "Uh_ins"})

        if "Heat" in self.infrastructure.grids.keys():
            if 'T_DHN_supply_cst' and 'T_DHN_return_cst' in self.parameters:
                T_DHN_mean = (self.parameters["T_DHN_supply_cst"] + self.parameters["T_DHN_return_cst"]) / 2
                if "HeatPump_Geothermal_district" in self.infrastructure.UnitsOfDistrict:
                    MP_set_indexed["HP_Tsupply"] = np.array([T_DHN_mean.mean()])
                    MP_set_indexed["HP_Tsink"] = np.array([T_DHN_mean.mean()])
        if read_DHN:
            MP_set_indexed["House_ID"] = np.array(range(0, len(self.infrastructure.houses))) + 1

        if "Mobility" in self.infrastructure.UnitsOfLayer:
            MP_set_indexed['transport_Units'] = np.append(np.setdiff1d(self.infrastructure.UnitsOfLayer["Mobility"], ["EV_charger_district"]),
                                                          ['PT_train', 'PT_bus'])
            MP_set_indexed['transport_Units_MD'], MP_set_indexed['transport_Units_cars'] = mobility.generate_transport_units_sets(self.infrastructure.UnitsOfType)
            MP_set_indexed['Distances'] = np.array(MP_parameters['DailyDist'].index)

        if self.method['external_district']:
            MP_set_indexed['Districts'] = np.array(self.set_indexed["Districts"])

        # ---------------------------------------------------------------------------------------------------------------
        # CENTRAL UNITS
        # ---------------------------------------------------------------------------------------------------------------
        if len(self.infrastructure.district_units) > 0:
            MP_set_indexed['Units'] = np.array([])
            MP_set_indexed['UnitTypes'] = np.array([])
            MP_set_indexed['UnitsOfType'] = {}
            for u in self.infrastructure.district_units:
                name = u['name']
                MP_set_indexed['Units'] = np.append(MP_set_indexed['Units'], [name])
                if not u['UnitOfType'] in MP_set_indexed['UnitTypes']:
                    MP_set_indexed['UnitTypes'] = np.append(MP_set_indexed['UnitTypes'], u['UnitOfType'])
                    MP_set_indexed['UnitsOfType'][u['UnitOfType']] = np.array([])
                MP_set_indexed['UnitsOfType'][u['UnitOfType']] = np.append(MP_set_indexed['UnitsOfType'][u['UnitOfType']], [name])

        # ---------------------------------------------------------------------------------------------------------------
        # give values to ampl
        # ---------------------------------------------------------------------------------------------------------------

        for s in MP_set_indexed:
            if isinstance(MP_set_indexed[s], np.ndarray):
                ampl_MP.getSet(str(s)).setValues(MP_set_indexed[s])
            elif isinstance(MP_set_indexed[s], dict):
                for i, instance in ampl_MP.getSet(str(s)):
                    instance.setValues(MP_set_indexed[s][i])
            elif isinstance(MP_set_indexed[s], pd.DataFrame):
                ampl_MP.setData(MP_set_indexed[s])
            else:
                raise ValueError('Type Error setting AMPLPY Set', s)

        # select district units in exclude and enforce units
        exclude_units = [s for s in scenario['exclude_units'] if any(xs in s for xs in ['district'])]
        enforce_units = [s for s in scenario['enforce_units'] if any(xs in s for xs in ['district'])]
        for i, value in ampl_MP.getVariable('Units_Use').instances():
            for u in exclude_units:
                if u in i:
                    ampl_MP.getVariable('Units_Use').get(str(i)).fix(0)
            for u in enforce_units:
                if u in i:
                    ampl_MP.getVariable('Units_Use').get(str(i)).fix(1)

        for i in MP_parameters:
            if isinstance(MP_parameters[i], np.ndarray):
                Para = ampl_MP.getParameter(i)
                Para.setValues(MP_parameters[i])

            elif isinstance(MP_parameters[i], float):
                Para = ampl_MP.getParameter(i)
                Para.setValues([MP_parameters[i]])

            elif isinstance(MP_parameters[i], int):
                Para = ampl_MP.getParameter(i)
                Para.setValues([MP_parameters[i]])

            elif isinstance(MP_parameters[i], pd.DataFrame):
                if not MP_parameters[i].empty:
                    ampl_MP.setData(MP_parameters[i])

            elif isinstance(MP_parameters[i], pd.Series):
                MP_parameters[i].name = i
                df = pd.DataFrame(MP_parameters[i])
                ampl_MP.setData(df)

            elif isinstance(MP_parameters[i], list):
                Para = ampl_MP.getParameter(i)
                Para.setValues(np.array(MP_parameters[i]))
            else:
                raise ValueError('Type Error setting AMPLPY Parameter', i)

        # -------------------------------------------------------------------------------------------------------------
        # Set scenario and Pareto_IDs
        # ------------------------------------------------------------------------------------------------------------
        if self.method['building-scale']:
            scenario = self.remove_emoo_constraints(scenario)

        ampl_MP = self.select_MP_objective(ampl_MP, scenario)

        if not binary:
            ampl_MP.getConstraint('convexity_binary').drop()

        # Solve ampl_MP
        ampl_MP.solve()

        df_Results_MP = write_results.get_df_Results_from_MP(ampl_MP, binary, self.method, self.infrastructure, read_DHN=read_DHN, scenario=scenario)
        self.logger.info(str(ampl_MP.getCurrentObjective().getValues().toPandas()))

        df = self.get_solver_attributes(Scn_ID, Pareto_ID, ampl_MP)
        self.add_df_Results_MP(Scn_ID, Pareto_ID, self.iter, df_Results_MP, df)
        exitcode = exitcode_from_ampl(ampl_MP)

        del ampl_MP
        gc.collect()
        if exitcode != 0:
            raise Exception('Master problem did not converge')

    def SP_iteration(self, scenario, Scn_ID=0, Pareto_ID=1):
        """
        Sets up the parallel optimization if needed.

        Parameters
        ----------
        scenario : dictionary

        Scn_ID : int
            scenario ID
        Pareto_ID: int
            pareto ID
        """
        self.launch_SP_multiprocessing(scenario, Scn_ID, Pareto_ID, None, None, initiation=False)
        if self.method['refurbishment'] is not None:
            for option in self.method['refurbishment']:
                self.launch_SP_multiprocessing(scenario, Scn_ID, Pareto_ID, None, None, initiation=False, refurbishment_options=option)


    def SP_execution(self, scenario, Scn_ID, Pareto_ID, h, refurbishment_options=None):
        """
        Inserts dual variables in ampl model, apply scenario, adapt model depending on the methods and get results.

        Parameters
        ----------
        scenario: dictionary

        Scn_ID : int
            scenario ID
        Pareto_ID : int
            pareto ID
        h : string
            house ID

        Returns
        -------
        df_Results :
            results of the optimization (unit installed, power exchanged, costs, GWP emissions, ...)
        attr :
            results of the optimization process (CPU time, objective value, nb variables or constraints, ...)

        Raises
        ------
        ValueError: If the SP optimization did not converge
        """
        self.logger.info('iterate HOUSE: ' + h + 'iteration: ' + str(self.iter))

        # Give dual variables to Subproblem
        pi = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter - 1, h, 'pi').reorder_levels(['Layer', 'Period', 'Time'])
        pi_GWP = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter - 1, h, 'pi_GWP').reorder_levels(['Layer', 'Period', 'Time'])
        pi_h = pd.concat([pi], keys=[h], names=['Building']).reorder_levels(['Building', 'Layer', 'Period', 'Time'])

        parameters_SP = {'Cost_supply_network': pi,
                         'Cost_demand_network': pi * (1 - 1e-9),
                         'Cost_supply': pi_h,
                         'Cost_demand': pi_h * (1 - 1e-9),
                         'GWP_supply': pi_GWP,
                         'GWP_demand': pi_GWP.mul(0),  # set emissions of feed in to 0 -> changed in  postcompute
                         }

        if self.method['actors_problem']:
            parameters_SP.update(actors.get_actor_parameters(self.scenario, self.set_indexed, self.results_MP, Scn_ID, Pareto_ID, self.iter, h))
        # find district structure, objective, beta and parameter for one single building
        buildings_data_SP, parameters_SP, set_indexed_SP = self.split_parameter_sets_per_building(h, parameters_SP)
        beta = - self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter - 1, h, 'beta')
        scenario, beta_list = self.get_beta_values(scenario, beta)
        parameters_SP['beta_duals'] = beta_list

        if refurbishment_options is not None:
            buildings_data_SP[h]['U_h'], parameters_SP['Costs_ins'], parameters_SP['GWP_ins'] = refurbishment.refurbishment_cost_co2(buildings_data_SP[h], self.local_data, refurbishment_options)

        # Execute optimization
        if self.method['use_facades'] or self.method['use_pv_orientation']:
            REHO = SubProblem(self.infrastructure_SP[h], buildings_data_SP, self.local_data, parameters_SP, set_indexed_SP, self.cluster,
                              scenario, self.method, self.solver, self.qbuildings_data)
        else:
            REHO = SubProblem(self.infrastructure_SP[h], buildings_data_SP, self.local_data, parameters_SP, set_indexed_SP, self.cluster,
                              scenario, self.method, self.solver)

        ampl = REHO.build_model_without_solving()

        if self.method['fix_units']:
            for unit in self.df_fix_Units.index[self.df_fix_Units.index.str.contains(h)]:
                if unit == 'PV_' + h:
                    ampl.getVariable('Units_Mult').get(unit).fix(self.df_fix_Units.Units_Mult.loc[unit] * (1 - 1e-9))
                    ampl.getVariable('Units_Use').get(unit).fix(float(self.df_fix_Units.Units_Use.loc[unit]))
                else:
                    ampl.getVariable('Units_Mult').get(unit).fix(self.df_fix_Units.Units_Mult.loc[unit])
                    ampl.getVariable('Units_Use').get(unit).fix(float(self.df_fix_Units.Units_Use.loc[unit]))

        ampl.solve()
        exitcode = exitcode_from_ampl(ampl)

        df_Results = write_results.get_df_Results_from_SP(ampl, scenario, self.method, buildings_data_SP)
        attr = self.get_solver_attributes(Scn_ID, Pareto_ID, ampl)

        del ampl
        gc.collect()  # free memory

        if exitcode != 0:
            # It might be that the solution is optimal with unscaled infeasibilities. So we check if we really found a solution (via its cost value)
            if exitcode != 'solved?' or df_Results["df_Performance"]['Costs_op'][0] + df_Results["df_Performance"]['Costs_inv'][0] == 0:
                raise Exception('Sub problem did not converge with building', h)

        return df_Results, attr

    def check_Termination_criteria(self, scenario, Scn_ID=0, Pareto_ID=1):
        """
        Verifies a number of termination criteria:

        - Optimal solution found based on reduced costs -> last solutions proposed by the SPs did not improve the MP
        - No improvements


        Returns
        -------
        df.any(axis=None) : boolean
            If one of the stopping criteria is reached

        """
        # --------------------------------------------------------------
        # termination criteria based on no improvements
        # --------------------------------------------------------------
        solving_attributes = self.solver_attributes_MP.xs((Scn_ID, Pareto_ID), level=('Scn_ID', 'Pareto_ID'))
        delta = solving_attributes.val_objective.pct_change()  # .abs()
        no_improvments_list = -delta < self.DW_params['threshold_no_improv']

        if no_improvments_list.values[-1]:
            number_repetition_same_bool = [sum(1 for items in group) for _, group in groupby(no_improvments_list)]
            no_improvments = number_repetition_same_bool[-1]  # find the number of consecutive lack of improvements
        else:
            no_improvments = 0

        if no_improvments == self.DW_params['iter_no_improv']:
            iter_criteria = True
        else:
            iter_criteria = False

        # --------------------------------------------------------------
        # optimal solution found based on reduced costs
        # --------------------------------------------------------------
        last_SP_results = self.results_SP[Scn_ID][Pareto_ID][self.iter][self.feasible_solutions - 1]
        last_MP_results = self.results_MP[Scn_ID][Pareto_ID][self.iter]

        Cop = pd.DataFrame(dtype='float')
        Cinv = pd.DataFrame(dtype='float')
        rc_actors = pd.Series(dtype='float')

        for h in last_SP_results:
            df_Grid_t = pd.concat([last_SP_results[h]["df_Grid_t"]], keys=[(self.iter, self.feasible_solutions - 1, h)],
                                  names=['Iter', 'FeasibleSolution', 'house'])
            df_Grid_t = df_Grid_t.xs(h, level='Hub')
            pi = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter, h, 'pi')
            pi_GWP = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter, h, 'pi_GWP')

            # Operation impact
            Cop_h = self.get_annual_grid_opex(df_Grid_t, cost_demand=pi, cost_supply=pi)
            Cop_h_GWP = self.get_annual_grid_opex(df_Grid_t, cost_demand=pi_GWP, cost_supply=pi_GWP)
            Cop_h = pd.concat([Cop_h, Cop_h_GWP], axis=1)
            Cop_h.columns = ["TOTEX", "GWP"]
            Cop = pd.concat([Cop, Cop_h])

            # Investment impact
            df = last_SP_results[h]["df_Performance"].iloc[0]
            Cinv_h = pd.Series(df.Costs_rep + df.Costs_inv, index=["TOTEX"])
            Cinv_h_GWP = pd.Series(df.GWP_constr, index=["GWP"])
            Cinv_h = pd.DataFrame(pd.concat([Cinv_h, Cinv_h_GWP])).transpose()
            Cinv_h.index = Cop_h.index
            Cinv = pd.concat([Cinv, Cinv_h])
            if self.method['actors_problem']:
                nu = {}
                nu["Renters"] = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter, h, 'nu_Renters').dropna()
                nu["Utility"] = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter, h, 'nu_Utility').dropna().iat[0]
                nu["Owners"] = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter, h, 'nu_Owners').dropna()
                if scenario['Objective'] == "TOTEX_actor":
                    nu[self.set_indexed["ActorObjective"][0]] = 1.0
                rc_actors[h] = nu["Renters"][h] * actors.get_actor_expenses('Renters', h, last_MP_results=last_MP_results, last_SP_results=last_SP_results)\
                               +nu["Utility"] * actors.get_actor_expenses('Utility', h, last_MP_results=last_MP_results, last_SP_results=last_SP_results)\
                               +nu["Owners"][h] * actors.get_actor_expenses('Owner', h, last_MP_results=last_MP_results, last_SP_results=last_SP_results)

        # calculate objective function for each Pareto_ID with latest dual values
        reduced_cost = pd.DataFrame()
        for h in last_SP_results:
            mu = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter, h, 'mu')
            Cop_house = Cop.xs((self.iter, self.feasible_solutions - 1, h))
            Cinv_house = Cinv.xs((self.iter, self.feasible_solutions - 1, h))
            obj_fct = pd.Series([Cinv_house["TOTEX"], Cop_house["TOTEX"]], index=["CAPEX", "OPEX"])
            impacts = Cop_house + Cinv_house
            obj_fct = pd.concat([obj_fct, impacts.replace(np.nan, 0)])

            beta = - self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter, h, "beta")
            if beta.sum() == 0 and len(scenario["EMOO"].keys()) > 1:
                warnings.warn('beta value = 0')
            beta_penalty = sum(beta * obj_fct)

            Costs_ft = last_SP_results[h]["df_Performance"].iloc[0].Costs_ft
            if self.method['actors_problem']:
                if scenario['Objective'] == "TOTEX_actor":
                    reduced_cost_h = Costs_ft + beta_penalty - mu - rc_actors[h]
                else:
                    reduced_cost_h = obj_fct[scenario['Objective']] + Costs_ft + beta_penalty - mu - rc_actors[h]
            else:
                reduced_cost_h = obj_fct[scenario['Objective']] + Costs_ft + beta_penalty - mu
            reduced_cost.at[h, 'Reduced_cost'] = reduced_cost_h

        if (reduced_cost.Reduced_cost >= self.DW_params['threshold_subP_value']).all():
            optimal_criteria = True
        else:
            optimal_criteria = False

        # --------------------------------------------------------------
        # construct dataframe
        # --------------------------------------------------------------
        mux = pd.MultiIndex.from_tuples([(Scn_ID, Pareto_ID, self.iter)], names=['Scn_ID', 'Pareto_ID', 'Iter'])
        df = pd.DataFrame([[iter_criteria, optimal_criteria]], columns=['max_iter_no_improv_reached', 'all_optimal'], index=mux)

        df_value = pd.DataFrame([[no_improvments, reduced_cost.sum()]], columns=['iterations_no_improvement', 'total_reduced_cost'], index=mux)
        df_criteria = pd.concat([df, df_value], axis=1)
        self.stopping_criteria = pd.concat([self.stopping_criteria, df_criteria])

        # save reduced costs
        reduced_cost = pd.concat([reduced_cost], keys=[(Scn_ID, Pareto_ID, self.iter)], names=['Scn_ID', 'Pareto_ID', 'Iter'])
        self.reduced_costs = pd.concat([self.reduced_costs, reduced_cost])

        return df.any(axis=None)

    ####################################################################################################################
    #
    # THE FOLLOWING ATTRIBUTES ARE DOING DATA PROCESSING
    #
    ####################################################################################################################

    def initialise_DW_params(self, DW_params, cluster, buildings_datas):
        if 'timesteps' not in DW_params:
            DW_params['timesteps'] = cluster['Periods'] * cluster['PeriodDuration'] + 2
        if 'max_iter' not in DW_params:
            DW_params['max_iter'] = 15
        if 'n_houses' not in DW_params:
            DW_params['n_houses'] = len(buildings_datas.keys())
        if 'iter_no_improv' not in DW_params:
            DW_params['iter_no_improv'] = 5
        if 'threshold_subP_value' not in DW_params:
            DW_params['threshold_subP_value'] = 0
        if 'threshold_no_improv' not in DW_params:
            DW_params['threshold_no_improv'] = 0.00005
        if 'grid_cost_exchange' not in DW_params:
            DW_params['grid_cost_exchange'] = 0.0
        if 'weight_lagrange_cst' not in DW_params:
            DW_params['weight_lagrange_cst'] = 2.0
        if self.method['building-scale']:
            DW_params['max_iter'] = 1

        return DW_params

    def get_final_MP_results(self, Pareto_ID=1, Scn_ID=0):
        """
        Builds the final design and operating results based on the optimal set of lambdas.
        """

        # select the result chosen by the MP
        last_results = self.results_MP[Scn_ID][Pareto_ID][self.iter]
        lambdas = last_results["df_DW"]['lambda']
        MP_selection = lambdas[lambdas >= 0.999].index

        # get selected Units
        df_Unit_all = self.return_combined_SP_results(self.results_SP, 'df_Unit')
        df_Unit_all = df_Unit_all.reset_index(level='Unit')

        # drop useless indices
        df_Unit_all = df_Unit_all.droplevel(['Scn_ID', 'Pareto_ID', 'Iter'])
        df_Unit = df_Unit_all[df_Unit_all.index.isin(MP_selection.values)]

        # set index for further usage
        df_Unit = df_Unit.set_index('Unit', append=True)

        # append central district units
        if len(self.infrastructure.district_units) > 0:
            df_U_District = pd.concat([last_results["df_Unit"]], keys=[(self.iter, 'District')], names=['FeasibleSolution', 'house'])
            df_Unit = pd.concat([df_Unit, df_U_District])
        df_Unit = df_Unit.set_index(df_Unit.index.rename('Hub', level='house'))
        return df_Unit

    def get_annual_grid_opex(self, df_Grid_t, cost_supply=pd.Series(dtype='float'), cost_demand=pd.Series(dtype='float')):
        """
        Parameters
        ----------
        df_Grid_t : pd.DataFrame
            from result object REHO
        cost_supply : series
            cost profile of supply
        cost_demand : series
            cost profile of demand

        Returns
        -------
        annual_grid_costs :
            possibility to set tariffs/dual value pi. default: use costs from model
        """
        if cost_supply.empty:
            tariff_supply = df_Grid_t.Cost_supply
        else:
            tariff_supply = cost_supply.values

        if cost_demand.empty:
            tariff_demand = df_Grid_t.Cost_demand
        else:
            tariff_demand = cost_demand.values

        df_costs = tariff_supply * df_Grid_t.Grid_supply - tariff_demand * df_Grid_t.Grid_demand

        # Annual sum
        ids = self.number_SP_solutions.iloc[0]
        df_Time = self.results_SP[ids['Scn_ID']][ids['Pareto_ID']][ids['Iter']][ids['FeasibleSolution']][ids['House']]["df_Time"]
        dp = df_Time.dp
        dp.iloc[-1] = 0  # exclude typical periods
        dp.iloc[-2] = 0

        # Transform profiles to annual values
        df_costs = df_costs.groupby(level=['Iter', 'FeasibleSolution', 'house', 'Period'], sort=False).sum()  # 'daily' sum
        df_costs = df_costs.mul(df_Time.dp, level='Period', axis=0)  # mul frequency of typical days
        annual_grid_costs = df_costs.groupby(level=['Iter', 'FeasibleSolution', 'house'], sort=False).sum()  # 'annual' sum
        return annual_grid_costs

    def select_MP_objective(self, ampl, scenario):
        list_constraints = ['EMOO_CAPEX_constraint', 'EMOO_OPEX_constraint', 'EMOO_GWP_constraint', 'EMOO_TOTEX_constraint', 'disallow_exchanges_1', 'disallow_exchanges_2', 'EMOO_elec_export_constraint'] + self.lists_MP["list_constraints_MP"]

        for cst in list_constraints:
            try:
                ampl.getConstraint(cst).drop()
            except:
                pass

        if 'EMOO' in scenario:
            emoo = scenario['EMOO'].copy()
            for epsilon_constraint in emoo:
                ampl.getConstraint(epsilon_constraint + '_constraint').restore()
                epsilon_parameter = ampl.getParameter(epsilon_constraint)
                epsilon_parameter.setValues([scenario['EMOO'][epsilon_constraint]])

        if 'specific' in scenario:
            for specific_constraint in scenario['specific']:
                if specific_constraint in list_constraints:
                    ampl.getConstraint(specific_constraint).restore()

        for i, o in ampl.getObjectives():
            o.drop()
        ampl.getObjective(scenario['Objective']).restore()
        return ampl

    def get_beta_values(self, scenario, beta=None):
        scenario = scenario.copy()
        if isinstance(beta, (float, int, type(None))):
            index = list(self.flags.keys())  # list of objective function
            beta_list = pd.Series(np.zeros(len(index)), index=index) + 1e-6  # default penalty on other objectives
        elif isinstance(beta, pd.Series):
            beta_list = beta
            beta_list = beta_list.replace(0, 1e-6)
        else:
            raise warnings.warn("Wrong type beta")

        # select objective using beta values
        if scenario['Objective'] in ['TOTEX', 'TOTEX_actor']:
            beta_list[['CAPEX', 'OPEX']] = 1
        else:
            beta_list[scenario['Objective']] = 1
        scenario['Objective'] = 'SP_obj_fct'

        # add beta values on emoo constraint
        if isinstance(beta, (float, int)) and not self.method['building-scale']:
            emoo = scenario["EMOO"].copy()
            for cst in [k for k in scenario["EMOO"].keys() if k not in ['EMOO_TOTEX', 'EMOO_CAPEX', 'EMOO_OPEX', 'EMOO_GWP']]:
                emoo.pop(cst, None)
            if len(emoo) == 1:
                key = list(emoo.keys())[0].replace("EMOO_", "")
                beta_list[key] = beta
            elif len(emoo) == 0:
                if scenario["Objective"] == "OPEX":
                    beta_list["CAPEX"] = beta
                else:
                    beta_list["OPEX"] = beta
            elif len(emoo) > 1:
                raise warnings.warn("Multiple epsilon constraints")

        scenario = self.remove_emoo_constraints(scenario)
        return scenario, beta_list

    @staticmethod
    def remove_emoo_constraints(scenario):

        EMOOs = list(scenario['EMOO'].keys())
        keys_to_remove = ['EMOO_CAPEX', 'EMOO_OPEX', 'EMOO_GWP', 'EMOO_TOTEX', "EMOO_elec_export", "EMOO_EV"]
        if 'EMOO' in scenario:
            for key in list(set(EMOOs).intersection(keys_to_remove)):
                scenario['EMOO'].pop(key, None)
        return scenario

    def get_dual_values_SPs(self, Scn_ID, Pareto_ID, iter, House, dual_variable):
        """
        Selects the right dual variables for the given Scn_ID, Pareto_ID, iter and house IDs.

        Parameters
        ----------
        Scn_ID : int
            scenario ID
        Pareto_ID: int
            pareto ID
        iter : int
            iter ID
        House : string
            house ID
        dual_variable : string
            dual variable to get

        Returns
        -------
        dual_value : array
            dual variables
        """
        attribute = None
        if dual_variable in ['pi', 'pi_GWP']:
            attribute = 'df_Dual_t'
        elif dual_variable in ['beta_cap', 'beta_op', 'beta_tot', 'beta_gwp']:
            attribute = 'df_District'
        elif dual_variable in ['beta']:
            attribute = 'df_beta'
        elif dual_variable in ['mu']:
            attribute = 'df_Dual'
        elif dual_variable in ['nu_Renters', 'nu_Owners','nu_Utility']:
            attribute = 'df_Actors_dual'

        df = self.results_MP[Scn_ID][Pareto_ID][iter][attribute]
        if dual_variable == 'mu':
            dual_value = df[dual_variable][House]  # dual variable from previous iteration
        else:
            dual_value = df[dual_variable]  # dual variable from previous iteration
        return dual_value  # dual value for one BES only

    def get_solver_attributes(self, Scn_ID, Pareto_ID, ampl):
        """

        Parameters
        ----------
        Scn_ID: int
            scenario ID
        Pareto_ID: int
            ID of the pareto point, default is 1
        ampl: ampl model
            results concerning one SP

        Returns
        -------
        df : pd.DataFrame
            Information on the optimization (CPU time, nb constraints, ...)
        """
        time = ampl.getValue('_total_solve_time')
        constr = ampl.getValue('_ncons')
        pres_constr = ampl.getValue('_sncons')  # after presolve
        var = ampl.getValue('_nvars')
        pres_var = ampl.getValue('_snvars')  # after presolve
        binaries = ampl.getValue('_snbvars')  # after presolve
        integer = ampl.getValue('_snivars')  # after presolve
        no_ojectives = ampl.getValue('_snobjs')  # after presolve
        val_objectives = ampl.getCurrentObjective().getValues().toList()[0]

        mux = pd.MultiIndex.from_tuples([(Scn_ID, Pareto_ID)], names=['Scn_ID', 'Pareto_ID'])
        df = pd.DataFrame([[time, constr, pres_constr, var, pres_var, binaries, integer, no_ojectives, val_objectives]], index=mux,
                          columns=['solving_time', 'constraints', 'presolve_constraints', 'variables', 'presolve_variables',
                                   'presolve_binaries', 'presolve_integer', 'no_objective', 'val_objective'])

        if not self.method['district-scale']:  # for decompose method, stored in solver_attributes_MP or _SP
            self.solver_attributes = pd.concat([self.solver_attributes, df])

        return df

    def sort_decomp_result(self, Scn_ID, idxvalues):

        new_order_SPresults = {}
        new_order_MPresults = {}
        for id, sc in enumerate(idxvalues):
            new_order_SPresults[id + 1] = self.results_SP[Scn_ID][sc]
            new_order_MPresults[id + 1] = self.results_MP[Scn_ID][sc]

        self.results_SP[Scn_ID] = new_order_SPresults
        self.results_MP[Scn_ID] = new_order_MPresults
        self.number_SP_solutions = self.number_SP_solutions.sort_values(['Pareto_ID', 'FeasibleSolution'])
        self.number_MP_solutions = self.number_MP_solutions.sort_values(['Pareto_ID', 'FeasibleSolution'])
        self.solver_attributes_SP = self.solver_attributes_SP.sort_values(['Pareto_ID', 'FeasibleSolution'])
        self.solver_attributes_MP = self.solver_attributes_MP.sort_values(['Pareto_ID', 'Iter'])
        if not self.method['building-scale']:
            self.reduced_costs = self.reduced_costs.sort_values(['Pareto_ID', 'Iter'])

    def add_df_Results_SP(self, Scn_ID, Pareto_ID, iter, house, df_Results, attr):
        if Scn_ID not in self.results_SP:
            self.results_SP[Scn_ID] = {}
        if Pareto_ID not in self.results_SP[Scn_ID]:
            self.results_SP[Scn_ID][Pareto_ID] = {}
        if iter not in self.results_SP[Scn_ID][Pareto_ID]:
            self.results_SP[Scn_ID][Pareto_ID][iter] = {}
        if self.feasible_solutions not in self.results_SP[Scn_ID][Pareto_ID][iter]:
            self.results_SP[Scn_ID][Pareto_ID][iter][self.feasible_solutions] = {}
        if house not in self.results_SP[Scn_ID][Pareto_ID][iter][self.feasible_solutions]:
            self.results_SP[Scn_ID][Pareto_ID][iter][self.feasible_solutions][house] = {}

        self.results_SP[Scn_ID][Pareto_ID][iter][self.feasible_solutions][house] = df_Results
        attr = pd.concat([attr], keys=[(house, iter, self.feasible_solutions)], names=['House', 'Iter', 'FeasibleSolution'])
        self.solver_attributes_SP = pd.concat([self.solver_attributes_SP, attr])

        df = pd.DataFrame([[Scn_ID, Pareto_ID, iter, house, self.feasible_solutions]], columns=['Scn_ID', 'Pareto_ID', 'Iter', 'House', 'FeasibleSolution'])
        self.number_SP_solutions = pd.concat([self.number_SP_solutions, df], ignore_index=True)

        number_iter_global = int((len(self.number_SP_solutions) - 1) / len(self.buildings_data))
        if 'MP_solution' not in self.number_SP_solutions.columns:
            self.number_SP_solutions['MP_solution'] = 0
        self.number_SP_solutions.iloc[-1, self.number_SP_solutions.columns.get_loc('MP_solution')] = number_iter_global

    def add_df_Results_MP(self, Scn_ID, Pareto_ID, iter, df_Results, attr):

        if Scn_ID not in self.results_MP:
            self.results_MP[Scn_ID] = {}
        if Pareto_ID not in self.results_MP[Scn_ID]:
            self.results_MP[Scn_ID][Pareto_ID] = {}
        if iter not in self.results_MP[Scn_ID][Pareto_ID]:
            self.results_MP[Scn_ID][Pareto_ID][iter] = {}

        self.results_MP[Scn_ID][Pareto_ID][iter] = df_Results
        attr = pd.concat([attr], keys=[iter], names=['Iter'])
        self.solver_attributes_MP = pd.concat([self.solver_attributes_MP, attr])
        col = self.number_SP_solutions.columns.difference(["House"])
        self.number_MP_solutions = self.number_SP_solutions[col].groupby('MP_solution').mean(numeric_only=True)

    def split_parameter_sets_per_building(self, h, parameters_SP=dict({}), set_indexed_SP=dict({})):
        """
        Some inputs are for the district and some other for the houses. This function fuses the two
        and gives the parameters per house. This is important to run an optimization on a single building

        Parameters
        ----------
        h : string
            House ID
        parameters_SP : dict
            Parameters of the house
        set_indexed_SP : dict
            Set indexed of the house

        Returns
        -------
        buildings_data_SP : dict
            egid, surface area, class of the building, ...
        parameters_SP : dict
            Parameters from the script for a single house (f.e. tariffs)
        set_indexed_SP: dict
            The set_indexed variable without the values concerning only the master problem (district scale)
        """
        ID = np.where(h == self.infrastructure.House)[0][0]
        buildings_data_SP = {h: self.buildings_data[h].copy()}

        for key in self.parameters:
            if key not in self.lists_MP["list_parameters_MP"]:
                if isinstance(self.parameters[key], (int, float)):
                    parameters_SP[key] = self.parameters[key]
                elif isinstance(self.parameters[key], pd.DataFrame):
                    if "Hub" in self.parameters[key].index.names:
                        parameters_SP[key] = self.parameters[key].xs(h, level="Hub", drop_level=False)
                    else:
                        parameters_SP[key] = self.parameters[key]
                else:
                    if len(self.parameters[key]) == len(self.buildings_data):
                        try:
                            parameters_SP[key] = self.parameters[key][ID]  # one parameter per building
                        except:
                            parameters_SP[key] = self.parameters[key].iloc[[ID]]  # one parameter per building
                    else:
                        try:
                            timesteps = int(len(self.parameters[key]) / len(self.buildings_data))
                            profile_building_x = self.parameters[key].reshape(len(self.buildings_data), timesteps)  # for time series
                            parameters_SP[key] = profile_building_x[ID]
                        except:
                            parameters_SP[key] = self.parameters[key]  # one parameter for all buildings

        for key in self.set_indexed:
            if key not in self.lists_MP["list_set_indexed_MP"]:
                set_indexed_SP[key] = self.set_indexed[key]

        return buildings_data_SP, parameters_SP, set_indexed_SP

    def build_infrastructure_SP(self):
        for h in self.buildings_data:
            single_building_data = {"buildings_data": {h: self.buildings_data[h]}}
            building_units = {"building_units": self.infrastructure.units}
            infrastructure_SP = infrastructure.Infrastructure(single_building_data, building_units, self.infrastructure.grids)

            # TODO: better integration Units_Parameters specific to each house
            unit_param = self.infrastructure.Units_Parameters.loc[[string.endswith(h) for string in self.infrastructure.Units_Parameters.index]]
            infrastructure_SP.Units_Parameters[["Units_Fmax", "Cost_inv2"]] = unit_param[["Units_Fmax", "Cost_inv2"]]
            self.infrastructure_SP[h] = infrastructure_SP
        return

    @staticmethod
    def return_combined_SP_results(df_Results, df_name):

        t = {(i, j, k, l, m): df_Results[i][j][k][l][m][df_name]
             for i in df_Results.keys()
             for j in df_Results[i].keys()
             for k in df_Results[i][j].keys()
             for l in df_Results[i][j][k].keys()
             for m in df_Results[i][j][k][l].keys()
             }

        df_district_results = pd.concat(t.values(), keys=t.keys(), names=['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'], axis=0)
        df_district_results = df_district_results.sort_index()
        return df_district_results
