from model.preprocessing.data_generation import *
import model.infrastructure as infrastructure
from model.compact_optimization import *
import model.postprocessing.write_results as WR
from itertools import groupby
import warnings
import time
import gc
import model.preprocessing.electricity_profile_parser as el_parser
import pickle
from os.path import exists
import multiprocessing as mp

class district_decomposition:

    def __init__(self, qbuildings_data, units, grids, parameters=None, set_indexed=None,
                 cluster=None, method=None, DW_params=None):
        """
        Description
        -----------
        - Initialize the district_decomposition class. The REHO class inherits this class, so the inputs are similar.
        - Store district attributes, scenario, method, attributes for the decomposition and initiate attribute
            that will store results.

        Inputs
        ------
        qbuildings_data : dictionary,  Buildings characteristics such as surface area, class, egid, ...
        units : units characteristics
        grids : grids characteristics
        exclude_units : List of the unit not considered
        parameters : dictionary,  Parameters set in the script (usually energy tariffs)
        set_indexed :dictionary,  The indexes used in the model
        cluster : dictionary,  Define location district, number of periods and number of timesteps
        method : dictionary, The different method to run the optimization (decomposed, PV orientations, parallel computation,...)
        DW_params : dictionary, hyperparameters of the decomposition and other useful information

        """
        # methods
        self.method = initialize_default_methods(method)

        # District attributes / used also in REHO
        if method['use_facades'] or method['use_pv_orientation']:
            self.qbuildings_data = qbuildings_data
        self.buildings_data = qbuildings_data['buildings_data']
        self.ERA = sum([self.buildings_data[house]['ERA'] for house in self.buildings_data.keys()])
        self.infrastructure = infrastructure.infrastructure(qbuildings_data, units, grids)

        if cluster is None:
            self.cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}
        else:
            self.cluster = cluster
        self.File_ID = WD.get_cluster_file_ID(self.cluster)

        if parameters is None:
            self.parameters = {}
        else:
            self.parameters = parameters

        # Heat gains from electricity and people, domestic hot water demand, domestic electricity demand
        self.parameters['HeatGains'], self.parameters['DHW_flowrate'], domestic_elec = DGF.profiles_from_sia2024(self.buildings_data, self.File_ID, self.cluster, self.method['include_stochasticity'], self.method['sd_stochasticity'])
        if self.method["read_electricity_profiles"] is not None:
            self.parameters['Domestic_electricity'] = el_parser.read_typical_profiles(self.method["read_electricity_profiles"], self.File_ID)
        else:
            self.parameters['Domestic_electricity'] = domestic_elec

        if set_indexed is None:
            self.set_indexed = {}
        else:
            self.set_indexed = set_indexed

        # attributes for the decomposition algorithm
        if DW_params is None:
            self.DW_params = {}  # init of values in initiate_decomposition method
        else:
            self.DW_params = DW_params
        self.DW_params = self.initialise_DW_params(self.DW_params, self.cluster, self.buildings_data)

        self.lists_MP = {"list_parameters_MP": ['utility_portfolio_min', 'owner_portfolio_min', 'EMOO_totex_lodger', 'TransformerCapacity',
                                                'EV_y', 'EV_plugged_out', 'n_vehicles', 'EV_capacity', 'EV_displacement_init',
                                                "area_district", "velocity", "density", "delta_enthalpy", "cinv1_dhn", "cinv2_dhn"],
                         "list_constraints_MP": []
                         }

        self.df_fix_Units = pd.DataFrame()
        self.fix_units_list = []


    def initialize_optimization_tracking_attributes(self):
        # internal IT parameter
        self.pool = None
        self.iter = 0  # keeps track of iterations, takes value of last iteration circle
        self.feasible_solutions = 0  # keeps track how many sets of SP solutions are proposed to the MP eg '2' means two per building
        list_obj = list(self.infrastructure.lca_kpis) + ["TOTEX", "CAPEX", "OPEX", "GWP"]
        self.flags = {obj: 0 for obj in list_obj} # keep track if the initialization has already been done

        # output attributes
        self.stopping_criteria = pd.DataFrame()

        # result attributes
        self.number_SP_solutions = pd.DataFrame()  # records number of solutions per iteration circle
        self.number_MP_solutions = pd.DataFrame()  # records number of solutions per iteration circle

        self.results_SP = WR.encapsulation()
        self.results_MP = WR.encapsulation()

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
        Description
        -----------
        the SPs in decomposition have another objective than in the compact formulation because their
        objective function is formulated as a reduced cost
        Also adding global linking constraints, like Epsilon, changes the scenario to choose.
        3: min OPEX,epsilon_CAPEX -> 12
        8: min CAPEx, epsilon_OPEX -> 13
        10: min OPEX,epsilon_CAPEX -> 14
        11: min CAPEx, epsilon_OPEX -> 15
        for CAPEX (1), OPEX (2), TOTEX (4) and CO2 emissions (9) the same objective is taken

        Inputs
        ------
        scenario: dictionary, objective function

        Outputs
        -------
        SP_scenario: dictionary, scenario for the SP (iterations)
        SP_scenario_init: dictionary, scenario for the SP (initiation)

        """
        SP_scenario = scenario.copy()
        SP_scenario['EMOO'] = scenario['EMOO'].copy()
        SP_scenario['specific'] = scenario['specific'].copy()

        SP_scenario_init = scenario.copy()
        SP_scenario_init['EMOO'] = scenario['EMOO'].copy()
        SP_scenario_init['specific'] = scenario['specific'].copy()

        # use GM or GU only for initialization. Then pi dictates when to restrict power exchanges
        SP_scenario_init['EMOO']['EMOO_grid'] = SP_scenario_init['EMOO']['EMOO_grid'] * 0.999
        SP_scenario['EMOO']['EMOO_grid'] = 0.0

        if "TransformerCapacity" in self.parameters:
            nb_buildings = round(self.parameters["Domestic_electricity"].shape[0] / self.DW_params['timesteps'])
            profile_building_x = self.parameters["Domestic_electricity"].reshape(nb_buildings, self.DW_params['timesteps'])
            max_DEL = profile_building_x.max(axis=1).sum()
            SP_scenario_init['EMOO']['EMOO_GU_demand'] = self.parameters["TransformerCapacity"][0] * 0.999/max_DEL
            SP_scenario_init['EMOO']['EMOO_GU_supply'] = self.parameters["TransformerCapacity"][0] * 0.999/max_DEL

        for scenario_cst in SP_scenario['specific']:
            if scenario_cst in self.lists_MP['list_constraints_MP']:
                SP_scenario['specific'].remove(scenario_cst)
                SP_scenario_init['specific'].remove(scenario_cst)

        return scenario, SP_scenario, SP_scenario_init

    def initiate_decomposition(self, scenario, Scn_ID=0, Pareto_ID=1, epsilon_init=None):
        """
        Description
        -----------
        The SPs are initialized for the given objective.
        In case the optimization includes an epsilon constraint, there are two ways to initialize.
        Either the epsilon constraint is applied on the SPs, or the initialization is done with beta.
        The former has the risk to be infeasible for certain SPs, therefore the latter is preferred.
        Three beta values are given to mark the extreme points and an average point.
        Set up the parallel optimization if needed

        Inputs
        ------
        scenario : dictionary, Which objective function to optimize and the value of epsilon constraints to apply
        Scn_ID : int, ID of the optimization scenario
        Pareto_ID : int,  Id of the pareto point. For single objective optimization it is 1 by default
        epsilon_init : array, Epsilon constraints to apply for the initialization
        """
        # check if TOTEX, OPEX or multi-objective optimization -> init with beta
        if self.method['building-scale']:
            init_beta = [None]  # keep same objective function
        elif not self.method['include_all_solutions'] or self.flags[scenario['Objective']] == 0 or scenario['EMOO']['EMOO_grid'] != 0:
            self.flags[scenario['Objective']] = 1  # never been optimized with this objective previously
            init_beta = [1000.0, 10, 1, 0.1, 0.001]
        else:
            init_beta = []  # skip the initialization

        for beta in init_beta: # execute SP for MP initialization
            if self.method['parallel_computation']:

                # to run multiprocesses, a copy of the model is performed with pickles -> make sure there are no ampl libraries
                results = {h: self.pool.apply_async(self.SP_initiation_execution, args=(scenario, Scn_ID, Pareto_ID, h, epsilon_init, beta)) for h in self.infrastructure.houses}

                # sometimes, python goes to fast and extract the results before calculating them. This step makes python wait finishing the calculations
                while len(results[list(self.buildings_data.keys())[-1]].get()) != 2:
                    time.sleep(1)

                # the memory to write and share results is not parallel -> results have to be stored outside calculation
                for h in self.infrastructure.houses:
                    (df_Results, attr) = results[h].get()
                    self.add_Result_SP(Scn_ID, Pareto_ID, self.iter, h, df_Results, attr)

            else:
                for id, h in enumerate(self.infrastructure.houses):
                    df_Results, attr = self.SP_initiation_execution(scenario, Scn_ID=Scn_ID, Pareto_ID=Pareto_ID, h=h, epsilon_init=epsilon_init, beta=beta)
                    self.add_Result_SP(Scn_ID, Pareto_ID, self.iter, h, df_Results, attr)

            self.feasible_solutions += 1  # after each 'round' of SP execution the number of feasible solutions increase
        return

    def SP_initiation_execution(self, scenario, Scn_ID=0, Pareto_ID=1, h=None, epsilon_init=None, beta=None):
        """
        Description
        -----------
        Adapt the model depending on the method, execute the optimization and get the results

        Inputs
        ------
        scenario : dictionary, Which objective function to optimize and the value of epsilon constraints to apply
        Scn_ID : int, scenario ID
        Pareto_ID : int, Id of the pareto point. For single objective optimization it is 1 by default
        h : string,House id
        epsilon_init : float, Epsilon constraint to apply for the initialization
        beta : float, Beta initial value used for initialization

        Outputs
        -------
        df_Results : results of the optimization (unit installed, power exchanged, costs, GWP emissions, ...)
        attr : results of the optimization process (CPU time, objective value, nb variables or constraints, ...)
        """

        print('INITIATE HOUSE: ', h)

        # find district structure and parameter for one single building
        buildings_data_SP, parameters_SP, infrastructure_SP = self.__split_parameter_sets_per_building(h)

        # epsilon constraints on districts may lead to infeasibilities on building level -> apply them in MP only
        if epsilon_init is not None and self.method['building-scale']:
            emoo = scenario["EMOO"].copy()
            emoo.pop("EMOO_grid")
            if len(emoo) == 1:
                if 'EMOO_lca' in emoo:
                    scenario["EMOO"]["EMOO_lca"][list(emoo["EMOO_lca"].keys())[0]] = epsilon_init.loc[h]
                else:
                    scenario["EMOO"][list(emoo.keys())[0]] = epsilon_init.loc[h]
            else:
                raise warnings.warn("Multiple epsilon constraints")
        elif not self.method['building-scale']:
            scenario, beta_list = self.get_beta_values(scenario, beta)
            parameters_SP['beta_duals'] = beta_list

        if self.method['use_facades'] or self.method['use_pv_orientation']:
            REHO = compact_optimization(infrastructure_SP, buildings_data_SP, parameters_SP, self.set_indexed, self.cluster, scenario, self.method, self.qbuildings_data)
        else:
            REHO = compact_optimization(infrastructure_SP, buildings_data_SP, parameters_SP, self.set_indexed, self.cluster, scenario, self.method)
        ampl = REHO.build_model_without_solving()

        if self.method['fix_units']:
            for unit in self.fix_units_list:
                if unit == 'PV':
                    ampl.getVariable('Units_Mult').get('PV_' + h).fix(self.df_fix_Units.Units_Mult.loc['PV_' + h] * 0.999)
                    ampl.getVariable('Units_Use').get('PV_' + h).fix(float(self.df_fix_Units.Units_Use.loc['PV_' + h]))
                else:
                    ampl.getVariable('Units_Mult').get(unit + '_' + h).fix( self.df_fix_Units.Units_Mult.loc[unit + '_' + h])
                    ampl.getVariable('Units_Use').get(unit + '_' + h).fix( float(self.df_fix_Units.Units_Use.loc[unit + '_' + h]))

        ampl.solve()
        exitcode = exitcode_from_ampl(ampl)

        df_Results = WR.dataframes_results(ampl, scenario, self.method, self.buildings_data)
        attr = self.get_solver_attributes(Scn_ID, Pareto_ID, ampl)

        del ampl
        gc.collect()  # free memory
        if exitcode != 0:
            # It might be that the solution is optimal with unscaled infeasibilities. So we check if we really found a solution (via its cost value)
            if exitcode != 'solved?' or df_Results.df_Performance['Costs_op'][0] + df_Results.df_Performance['Costs_inv'][0] == 0:
                raise Exception('Sub problem did not converge')

        return df_Results, attr

    def MP_iteration(self, scenario, binary, Scn_ID=0, Pareto_ID=1, read_DHN=False):
        """
        Description
        -----------
        Run the optimisation of the Master Problem (MP):
        - Create the ampl_MP master problem
        - Set the sets and the parameters in ampl
        - Actualise the grid exchanges and the costs of each sub problem (house) without the grid costs
        - Run the optimisation
        - Extract the results (lambda, dual variables pi and mu, objective value of the MP (TOTEX, grid exchanges, ...)
        - Delete the ampl_MP model

        Inputs
        ------
        scenario: dictionary
        binary: bool, if the decision variable 'lambda' is binary or continuous
        Scn_ID: scenario ID
        Pareto_ID: int, pareto ID

        Raises
        ------
        ValueError: If the sets are not arrays or if the parameters are not arrays or floats or dataframes.
        If the MP optimization did not converge
        """

        ### Create the ampl Master Problem (MP)
        ampl_MP = AMPL(Environment(os.environ["AMPL_PATH"]))

        # AMPL (GNU) OPTIONS
        ampl_MP.setOption('show_stats', 2)
        ampl_MP.setOption('solution_round', 11)
        ampl_MP.setOption('rel_boundtol', 1e-12)
        ampl_MP.setOption('presolve_eps', 1e-4)  # -ignore difference between upper and lower bound by this tolerance
        ampl_MP.setOption('presolve_inteps', 1e-6)  # -tolerance added/substracted to each upper/lower bound
        ampl_MP.setOption('presolve_fixeps', 1e-9)
        ampl_MP.setOption('show_stats', 1)
        ampl_MP.setOption('solver', 'gurobi')
        #ampl_MP.eval("option cplex_options 'bestbound mipgap=5e-7 integrality=1e-09 timing=1 timelimit=120';")
        ampl_MP.eval('option show_boundtol 0;')
        ampl_MP.eval('option abs_boundtol 1e-10;')

        # Load Master Problem (MP) Formulation
        ampl_MP.cd(path_to_ampl_model)
        ampl_MP.read('master_problem.mod')
        if self.method["actors_cost"]:
            ampl_MP.read('master_problem_actors.mod')

        if len(self.infrastructure.UnitsOfDistrict) > 0:
            ampl_MP.cd(path_to_district_units)
            if "EV_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read('evehicle.mod')
                self.lists_MP["list_constraints_MP"] = self.lists_MP["list_constraints_MP"] + ['unidirectional_service', 'unidirectional_service2']
            if "NG_Boiler_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read('ng_boiler_district.mod')
            if "HeatPump_Geothermal_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read('heatpump_district.mod')
            if "NG_Cogeneration_district" in self.infrastructure.UnitsOfDistrict:
                ampl_MP.read('ng_cogeneration_district.mod')

        ampl_MP.cd(path_to_units_storage)
        ampl_MP.read('battery.mod')

        if read_DHN:
            ampl_MP.cd(path_to_units)
            ampl_MP.read('DHN.mod')

        ampl_MP.cd(path_to_clustering_results)
        ampl_MP.readData('frequency_' + self.File_ID + '.dat')
        ampl_MP.cd(path_to_ampl_model)

        # -------------------------------------------------------------------------------------------------------------
        # Set Parameters, only bool to choose if including all solutions found also from other Pareto_IDs
        # ------------------------------------------------------------------------------------------------------------
        # collect data
        df_Performance = self.return_combined_SP_results(self.results_SP, 'df_Performance')
        df_Performance = df_Performance.drop(index='Network', level='Hub').groupby(level=['Scn_ID', 'Pareto_ID', 'FeasibleSolution', 'Hub']).head(1).droplevel('Hub')  # select current Scn_ID and Pareto_ID
        df_Grid_t = np.round(self.return_combined_SP_results(self.results_SP, 'df_Grid_t'), 6)

        # prepare df to have the same index than the AMPL model
        if not self.method['include_all_solutions']:
            df_Performance = df_Performance.xs((Scn_ID, Pareto_ID), level=('Scn_ID', 'Pareto_ID'))
            df_Grid_t = df_Grid_t.xs((Scn_ID, Pareto_ID, 'Network'), level=('Scn_ID', 'Pareto_ID', 'Hub'))
        else:
            df_Performance = df_Performance.droplevel(['Scn_ID', 'Pareto_ID'])
            df_Grid_t = df_Grid_t.droplevel(['Scn_ID', 'Pareto_ID']).xs('Network', level='Hub')

        df_Performance = df_Performance.droplevel(level='Iter')
        df_Grid_t = df_Grid_t.droplevel(level='Iter').reorder_levels(['Layer', 'FeasibleSolution', 'house', 'Period', 'Time'])

        # assign data
        MP_parameters = {}
        MP_parameters['Costs_inv_rep_SPs'] = df_Performance.Costs_inv + df_Performance.Costs_rep
        MP_parameters['Costs_ft_SPs'] = pd.DataFrame(np.round(df_Performance.Costs_ft, 6)).set_axis(['Costs_ft_SPs'], axis=1)
        MP_parameters['GWP_house_constr_SPs'] = pd.DataFrame(df_Performance.GWP_constr).set_axis(['GWP_house_constr_SPs'], axis=1)

        df_lca_Units = self.return_combined_SP_results(self.results_SP, 'df_lca_Units')
        df_lca_Units = df_lca_Units.groupby(level=['Scn_ID', 'Pareto_ID', 'FeasibleSolution', 'house']).sum()
        MP_parameters['lca_house_units_SPs'] = df_lca_Units.droplevel(["Scn_ID", "Pareto_ID"]).stack().swaplevel(1, 2)
        if not self.method['include_all_solutions']:
            MP_parameters['lca_house_units_SPs'] = MP_parameters['lca_house_units_SPs'].xs(self.feasible_solutions - 1, level="FeasibleSolution", drop_level=False)

        MP_parameters['Grids_Parameters'] = self.infrastructure.Grids_Parameters
        MP_parameters['Grids_Parameters_lca'] = self.infrastructure.Grids_Parameters_lca
        MP_parameters['Units_flowrate'] = self.infrastructure.Units_flowrate.query('Unit.str.contains("district")')
        MP_parameters['Units_Parameters'] = self.infrastructure.Units_Parameters.query('index.str.contains("district")')
        MP_parameters['Units_Parameters_lca'] = self.infrastructure.Units_Parameters_lca.query('index.get_level_values("Units").str.contains("district")')

        if self.method['use_dynamic_emission_profiles']:
            ids = self.number_SP_solutions.iloc[-1]
            df = df_Grid_t[['GWP_supply']].xs("Electricity", level="Layer", drop_level=False)
            MP_parameters['GWP_supply'] = df.xs((ids["FeasibleSolution"], ids["House"]), level=("FeasibleSolution", "house"))


        for key in self.lists_MP['list_parameters_MP']:
            if key in self.parameters.keys():
                MP_parameters[key] = self.parameters[key]

        MP_parameters['df_grid'] = df_Grid_t[['Grid_demand', 'Grid_supply']]
        MP_parameters['ERA'] = np.asarray([self.buildings_data[house]['ERA'] for house in self.buildings_data.keys()])
        MP_parameters['Area_tot'] = self.ERA

        if 'EV_plugged_out' not in MP_parameters:
            if len(self.infrastructure.UnitsOfDistrict) != 0:
                if 'EV_district' in self.infrastructure.UnitsOfDistrict:
                    MP_parameters['EV_plugged_out'], MP_parameters['EV_plugging_in'] = EV_gen.generate_EV_plugged_out_profiles_district(self.cluster)

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

        # -------------------------------------------------------------------------------------------------------------
        # Set Sets
        # ------------------------------------------------------------------------------------------------------------
        MP_set_indexed = {}
        for sets in ['House', 'Layers', 'LayerTypes', 'LayersOfType', 'Lca_kpi']:
            MP_set_indexed[sets] = self.infrastructure.Set[sets]
        MP_set_indexed['LayersOfType']['ResourceBalance'].sort()

        MP_set_indexed['UnitsOfLayer'] = dict()
        for layer in self.infrastructure.Set['UnitsOfLayer']:
            lst =  self.infrastructure.Set['UnitsOfLayer'][layer]
            MP_set_indexed['UnitsOfLayer'][layer] = np.array(list(filter(lambda k: 'district' in k, lst)))

        MP_set_indexed['FeasibleSolutions'] = df_Performance.index.unique('FeasibleSolution').to_numpy()  # index to array as set

        if self.method['actors_cost']:
            #MP_parameters['Costs_tot_actors_min'] = df_Performance[["Costs_op", "Costs_inv", "Costs_rep"]].sum(axis=1).groupby("house").min()
            MP_set_indexed['ActorObjective'] = self.set_indexed["ActorObjective"]

            df_Unit_t = self.return_combined_SP_results(self.results_SP, 'df_Unit_t').xs("Electricity", level="Layer")
            df_PV_t = pd.DataFrame()
            for bui in self.infrastructure.houses:
                dummy = df_Unit_t.xs("PV_" + bui, level="Unit")
                df_PV_t = pd.concat([df_PV_t, dummy])
            MP_parameters["PV_prod"] = df_PV_t["Units_supply"].droplevel(["Scn_ID", "Pareto_ID", "Iter"])

        if "Heat" in self.infrastructure.grids.keys():
            if 'T_DHN_supply_cst' and 'T_DHN_return_cst' in self.parameters:
                T_DHN_mean = (self.parameters["T_DHN_supply_cst"] + self.parameters["T_DHN_return_cst"]) / 2
                if "HeatPump_Geothermal_district" in self.infrastructure.UnitsOfDistrict:
                    MP_set_indexed["HP_Tsupply"] = np.array([T_DHN_mean.mean()])
                    MP_set_indexed["HP_Tsink"] = np.array([T_DHN_mean.mean()])
        if read_DHN:
            MP_set_indexed["House_ID"] = np.array(range(0, len(self.infrastructure.houses)))+1

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
                MP_set_indexed['UnitsOfType'][u['UnitOfType']] = np.append( MP_set_indexed['UnitsOfType'][u['UnitOfType']], [name])

        # ---------------------------------------------------------------------------------------------------------------
        # give values to ampl
        # ---------------------------------------------------------------------------------------------------------------

        for s in MP_set_indexed:
            for i, instance in ampl_MP.getSet(str(s)):
                if isinstance(MP_set_indexed[s], np.ndarray):
                    instance.setValues(MP_set_indexed[s])
                elif isinstance(MP_set_indexed[s], dict):
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

        if not binary: ampl_MP.getConstraint('convexity_binary').drop()

        # Solve ampl_MP
        ampl_MP.solve()

        df_Results_MP = WR.dataframes_results_MP(ampl_MP, binary, self.method, self.infrastructure, read_DHN=read_DHN)
        print(ampl_MP.getCurrentObjective().getValues().toPandas())

        df = self.get_solver_attributes(Scn_ID, Pareto_ID, ampl_MP)
        self.add_Result_MP(Scn_ID, Pareto_ID, self.iter, df_Results_MP, df)
        exitcode = exitcode_from_ampl(ampl_MP)

        del ampl_MP
        gc.collect()
        if exitcode != 0: raise Exception('Master problem did not converge')

    def SP_iteration(self, scenario, Scn_ID=0, Pareto_ID=1):
        """
        Description
        -----------
        Set up the parallel optimization if needed

        Inputs
        ------
        scenario: dictionary
        Scn_ID: scenario ID
        Pareto_ID: int, pareto ID
        """

        if self.method['parallel_computation']:
            # to run multiprocesses, a copy of the model is performed with pickles -> make sure ampl libraries are removed
            results = {h: self.pool.apply_async(self.SP_execution, args=(scenario, Scn_ID, Pareto_ID, h)) for h in self.infrastructure.houses}

            while len(results[list(self.buildings_data.keys())[-1]].get()) != 2:
                time.sleep(1)
            # for now the memory which needs to be writable & shared is not parallel -> results have to be stored outside calculation
            for h in self.infrastructure.houses:
                (df_Results, attr) = results[h].get()
                self.add_Result_SP(Scn_ID, Pareto_ID, self.iter, h, df_Results, attr)
        else:
            for h in self.infrastructure.houses:
                df_Results, attr = self.SP_execution(scenario, Scn_ID, Pareto_ID, h)
                self.add_Result_SP(Scn_ID, Pareto_ID, self.iter, h, df_Results, attr)

        self.feasible_solutions += 1  # after each 'round' of SP execution-> increase

    def SP_execution(self, scenario, Scn_ID, Pareto_ID, House):
        """
        Description
        -----------
        Insert dual variables in ampl model, apply scenario, adapt model depending on the methods and get results

        Inputs
        ------
        scenario: dictionary
        Scn_ID: scenario ID
        Pareto_ID: int, pareto ID
        House: string, house ID

        Outputs
        -------
        df_Results : results of the optimization (unit installed, power exchanged, costs, GWP emissions, ...)
        attr : results of the optimization process (CPU time, objective value, nb variables or constraints, ...)

        Raises
        ------
        If the SP optimization did not converge
        """
        print('iterate HOUSE: ', House, 'iteration: ', self.iter)

        # Give dual variables to Subproblem
        pi = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter - 1, House, 'pi').reorder_levels(['Layer', 'Period', 'Time'])
        pi_GWP = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter - 1, House, 'pi_GWP').reorder_levels(['Layer', 'Period', 'Time'])
        pi_lca = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter - 1, House, 'pi_lca')
        pi_h = pd.concat([pi], keys=[House], names=['House']).reorder_levels(['House', 'Layer', 'Period', 'Time'])

        parameters_SP = {}
        parameters_SP['Cost_supply_network'] = pi
        parameters_SP['Cost_demand_network'] = pi * 0.999
        parameters_SP['Cost_supply'] = pi_h
        parameters_SP['Cost_demand'] = pi_h * 0.999
        parameters_SP['GWP_supply'] = pi_GWP
        # set emissions of feed in to 0 -> changed in  postcompute
        parameters_SP['GWP_demand'] = pi_GWP.mul(0)
        parameters_SP['lca_kpi_demand'] = pi_lca
        parameters_SP['lca_kpi_demand'] = pi_lca.mul(0)

        # find district structure, objective, beta and parameter for one single building
        buildings_data_SP, parameters_SP, infrastructure_SP = self.__split_parameter_sets_per_building(House, parameters_SP)
        beta = - self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter - 1, House, 'beta')
        scenario, beta_list = self.get_beta_values(scenario, beta)
        parameters_SP['beta_duals'] = beta_list

        # Execute optimization
        if self.method['use_facades'] or self.method['use_pv_orientation']:
            REHO = compact_optimization(infrastructure_SP, buildings_data_SP, parameters_SP, self.set_indexed, self.cluster, scenario, self.method, self.qbuildings_data)
        else:
            REHO = compact_optimization(infrastructure_SP, buildings_data_SP, parameters_SP, self.set_indexed, self.cluster, scenario, self.method)

        ampl = REHO.build_model_without_solving()

        if self.method['fix_units']:
            for unit in self.fix_units_list:
                if unit == 'PV':
                    ampl.getVariable('Units_Mult').get('PV_' + House).fix(self.df_fix_Units.Units_Mult.loc['PV_' + House] * 0.999)
                    ampl.getVariable('Units_Use').get('PV_' + House).fix(float(self.df_fix_Units.Units_Use.loc['PV_' + House]))
                else:
                    ampl.getVariable('Units_Mult').get(unit + '_' + House).fix( self.df_fix_Units.Units_Mult.loc[unit + '_' + House])
                    ampl.getVariable('Units_Use').get(unit + '_' + House).fix( float(self.df_fix_Units.Units_Use.loc[unit + '_' + House]))

        ampl.solve()
        exitcode = exitcode_from_ampl(ampl)

        df_Results = WR.dataframes_results(ampl, scenario, self.method, self.buildings_data)
        attr = self.get_solver_attributes(Scn_ID, Pareto_ID, ampl)

        del ampl
        gc.collect()  # free memory

        if exitcode != 0:
            # It might be that the solution is optimal with unscaled infeasibilities. So we check if we really found a solution (via its cost value)
            if exitcode != 'solved?' or df_Results.df_Performance['Costs_op'][0] + df_Results.df_Performance['Costs_inv'][0] == 0:
                raise Exception('Sub problem did not converge')

        return df_Results, attr

    def check_Termination_criteria(self, scenario, Scn_ID=0, Pareto_ID=1):
        """
        Description
        -----------
        Verify a number of termination criteria:
            - optimal solution found based on reduced costs -> last solutions proposed by the SPs did not improve the MP
            - no improvements

        Inputs
        ------
        scenario: dictionary, scenario of the optimization
        Scn_ID: scenario ID
        Pareto_ID: int, pareto ID

        Outputs
        -------
        df.any(axis=None): bool, if one of the stopping criteria is reached

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
        Cop = pd.DataFrame(dtype='float')
        Cinv = pd.DataFrame(dtype='float')

        for h in last_SP_results:
            df_Grid_t = pd.concat([last_SP_results[h].df_Grid_t], keys=[(self.iter, self.feasible_solutions - 1, h)], names=['Iter', 'FeasibleSolution', 'house'])
            df_Grid_t = df_Grid_t.xs('Network', level='Hub')
            pi = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter, h, 'pi')
            pi_GWP = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter, h, 'pi_GWP')
            pi_lca = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter, h, 'pi_lca')

            # Operation impact
            Cop_h = self.get_annual_grid_opex(df_Grid_t, cost_demand=pi, cost_supply=pi)
            Cop_h_GWP = self.get_annual_grid_opex(df_Grid_t, cost_demand=pi_GWP, cost_supply=pi_GWP)
            Cop_h_lca = [self.get_annual_grid_opex(df_Grid_t, cost_demand=pi_lca.xs(kpi), cost_supply=pi_lca.xs(kpi)) for kpi in self.infrastructure.lca_kpis]
            Cop_h_lca = pd.concat(Cop_h_lca, axis=1)
            Cop_h = pd.concat([Cop_h, Cop_h_GWP, Cop_h_lca], axis=1)
            Cop_h.columns = ["TOTEX", "GWP"] + list(self.infrastructure.lca_kpis)
            Cop = pd.concat([Cop, Cop_h])

            # Investment impact
            df = last_SP_results[h].df_Performance.iloc[0]
            Cinv_h = pd.Series(df.Costs_rep + df.Costs_inv, index=["TOTEX"])
            Cinv_h_GWP = pd.Series(df.GWP_constr, index=["GWP"])
            Cinv_h_lca = last_SP_results[h].df_lca_Units.sum()
            Cinv_h = pd.DataFrame(pd.concat([Cinv_h, Cinv_h_GWP, Cinv_h_lca])).transpose()
            Cinv_h.index = Cop_h.index
            Cinv = pd.concat([Cinv, Cinv_h])

        # calculate objective function for each Pareto_ID with latest dual values
        reduced_cost = pd.DataFrame()
        for h in last_SP_results:
            mu = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter, h, 'mu')
            Cop_house = Cop.xs((self.iter, self.feasible_solutions - 1, h))
            Cinv_house = Cinv.xs((self.iter, self.feasible_solutions - 1, h))
            obj_fct = pd.Series( [Cinv_house["TOTEX"], Cop_house["TOTEX"]], index=["CAPEX", "OPEX"])
            obj_fct = pd.concat([obj_fct, Cop_house + Cinv_house])

            beta = - self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter, h, "beta")
            if beta.sum() == 0 and len(scenario["EMOO"].keys()) > 1:
                warnings.warn('beta value = 0')
            beta_penalty = sum(beta * obj_fct)

            Costs_ft = last_SP_results[h].df_Performance.iloc[0].Costs_ft
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
        if 'timesteps' not in DW_params: DW_params['timesteps'] = cluster['Periods'] * cluster['PeriodDuration'] + 2
        if 'max_iter' not in DW_params: DW_params['max_iter'] = 15
        if 'n_houses' not in DW_params: DW_params['n_houses'] = len(buildings_datas.keys())
        if 'iter_no_improv' not in DW_params: DW_params['iter_no_improv'] = 5
        if 'threshold_subP_value' not in DW_params: DW_params['threshold_subP_value'] = 0
        if 'threshold_no_improv' not in DW_params: DW_params['threshold_no_improv'] = 0.00005
        if 'grid_cost_exchange' not in DW_params: DW_params['grid_cost_exchange'] = 0.0
        if 'weight_lagrange_cst' not in DW_params: DW_params['weight_lagrange_cst'] = 2.0
        if self.method['building-scale']: DW_params['max_iter'] = 1
        return DW_params

    def get_final_MP_results(self, Pareto_ID=1, Scn_ID=0):
        """
        Build the final design and operating results based on the optimal set of lambdas.

        Attributes
        ----------
        result_object_of_REHO,  List of dataframes
        """

        # select the result chosen by the MP
        last_results = self.results_MP[Scn_ID][Pareto_ID][self.iter]
        lambdas = last_results.df_DW['lambda']
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
            df_U_District = pd.concat([last_results.df_Unit], keys=[(self.iter, 'District')], names=['FeasibleSolution', 'house'])
            df_Unit = pd.concat([df_Unit, df_U_District])
        df_Unit = df_Unit.set_index(df_Unit.index.rename('Hub', level='house'))
        return df_Unit

    def get_annual_grid_opex(self, df_Grid_t, cost_supply=pd.Series(dtype='float'), cost_demand=pd.Series(dtype='float')):
        """
        Inputs
        ------
        df_Grid_t: pandas dataframe, from result object REHO
        Cost_supply_cst: optional, cost profile of supply
        Cost_demand_cst: optional, cost profile of demand

        Outputs
        -------
        annual_grid_costs: possibility to set tariffs/dual value pi. default: use costs from model
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
        df_Time = self.results_SP[ids['Scn_ID']][ids['Pareto_ID']][ids['Iter']][ids['FeasibleSolution']][ids['House']].df_Time
        dp = df_Time.dp
        dp.iloc[-1] = 0  # exclude typical periods
        dp.iloc[-2] = 0

        # Transform profiles to annual values
        df_costs = df_costs.groupby(level=['Iter', 'FeasibleSolution', 'house', 'Period'],  sort=False).sum()  # 'daily' sum
        df_costs = df_costs.mul(df_Time.dp, level='Period', axis=0)  # mul frequency of typical days
        annual_grid_costs = df_costs.groupby(level=['Iter', 'FeasibleSolution', 'house'], sort=False).sum()  # 'annual' sum
        return annual_grid_costs

    def select_MP_objective(self, ampl, scenario):
        list_constraints = ['EMOO_CAPEX_constraint', 'EMOO_OPEX_constraint', 'EMOO_GWP_constraint', 'EMOO_TOTEX_constraint',
                            'EMOO_lca_constraint', 'disallow_exchanges_1', 'disallow_exchanges_2'] + self.lists_MP["list_constraints_MP"]
        for cst in list_constraints:
            ampl.getConstraint(cst).drop()

        if 'EMOO' in scenario:
            emoo = scenario['EMOO'].copy()
            for epsilon_constraint in emoo:
                ampl.getConstraint(epsilon_constraint + '_constraint').restore()
                epsilon_parameter = ampl.getParameter(epsilon_constraint)
                if epsilon_constraint in ["EMOO_lca"]:
                    epsilon_parameter.setValues(scenario['EMOO'][epsilon_constraint])
                else:
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

        if isinstance(beta, (float, int, type(None))):
            index = list(self.flags.keys()) # list of objective function
            beta_list = pd.Series(np.zeros(len(index)), index=index) + 1e-6 # default penalty on other objectives
        elif isinstance(beta, pd.Series):
            beta_list = beta
            beta_list = beta_list.replace(0, 1e-6)
        else:
            raise warnings.warn("Wrong type beta")

        # select objective using beta values
        if scenario['Objective'] in ['TOTEX', 'TOTEX_bui']:
            beta_list[['CAPEX', 'OPEX']] = 1
        else:
            beta_list[scenario['Objective']] = 1
        scenario['Objective'] = 'SP_obj_fct'

        # add beta values on emoo constraint
        if isinstance(beta, (float, int)) and not self.method['building-scale']:
            emoo = scenario["EMOO"].copy()
            for cst in ["EMOO_grid", "EMOO_GU_supply", "EMOO_GU_demand"]:
                emoo.pop(cst, None)
            if 'EMOO_lca' in scenario["EMOO"].keys():
                key = list(emoo['EMOO_lca'].keys())[0].replace("EMOO_", "")
                beta_list[key] = beta
            elif len(emoo) == 1:
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


    def remove_emoo_constraints(self, scenario):
        # remove emoo constraints
        EMOOs = list(scenario['EMOO'].keys())
        keys_to_remove = ['EMOO_CAPEX', 'EMOO_OPEX', 'EMOO_GWP', 'EMOO_TOTEX', 'EMOO_lca']
        if 'EMOO' in scenario:
            for key in list(set(EMOOs).intersection(keys_to_remove)):
                scenario['EMOO'].pop(key, None)
        return scenario


    def get_dual_values_SPs(self, Scn_ID, Pareto_ID, iter, House, dual_variable):
        """
        Description
        -----------
        Select the right dual variables for the given Scn_ID, Pareto_ID, iter and house IDs

        Inputs
        ------
        Scn_ID: scenario ID
        Pareto_ID: int, pareto ID
        iter: int, iter ID
        House: string, house ID
        dual_variable: string, dual variable to get

        Outputs
        -------
        dual_value : array, dual variables
        """
        attribute = None
        if dual_variable in ['pi', 'pi_GWP', 'pi_lca']:
            attribute = 'df_Dual_t'
        elif dual_variable in ['beta_cap', 'beta_op', 'beta_tot', 'beta_gwp']:
            attribute = 'df_District'
        elif dual_variable in ['beta']:
            attribute = 'df_beta'
        elif dual_variable in ['mu']:
            attribute = 'df_Dual'

        df = getattr(self.results_MP[Scn_ID][Pareto_ID][iter], attribute)
        if dual_variable == 'mu':
            dual_value = df[dual_variable][House]  # dual variable from previous iteration
        elif dual_variable == 'pi_lca':
            dual_value = df[self.infrastructure.Set["Lca_kpi"]].stack()
            dual_value.index = dual_value.index.reorder_levels((3, 0, 1, 2))
        else:
            dual_value = df[dual_variable]  # dual variable from previous iteration
        return dual_value  # dual value for one BES only


    def get_solver_attributes(self, Scn_ID, Pareto_ID, ampl):
        """
        Description
        -----------

        Inputs
        ------
        Scn_ID: scenario ID
        Pareto_ID: int, ID of the pareto point, default is 1
        ampl: ampl model with results concerning one SP

        Outputs
        -------
        df: Dataframe with information on the optimization (CPU time, nb constraints, ...)
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

    def reset_Results(self):
        # result attributes
        self.results_SP = WR.encapsulation()
        self.results_MP = WR.encapsulation()
        self.solver_attributes_SP = pd.DataFrame()
        self.solver_attributes_MP = pd.DataFrame()

    def add_Result_SP(self, Scn_ID, Pareto_ID, iter, house, result, attr):

        self.results_SP[Scn_ID][Pareto_ID][iter][self.feasible_solutions][house] = result

        attr = pd.concat([attr], keys=[(house, iter, self.feasible_solutions)], names=['House', 'Iter', 'FeasibleSolution'])
        self.solver_attributes_SP = pd.concat([self.solver_attributes_SP, attr])

        df = pd.DataFrame([[Scn_ID, Pareto_ID, iter, house, self.feasible_solutions]],  columns=['Scn_ID', 'Pareto_ID', 'Iter', 'House', 'FeasibleSolution'])
        self.number_SP_solutions = pd.concat([self.number_SP_solutions, df], ignore_index=True)

        number_iter_global = int((len(self.number_SP_solutions) - 1) / len(self.buildings_data))
        if 'MP_solution' not in self.number_SP_solutions.columns: self.number_SP_solutions['MP_solution'] = 0
        self.number_SP_solutions.iloc[-1, self.number_SP_solutions.columns.get_loc('MP_solution')] = number_iter_global


    def add_Result_MP(self, Scn_ID, Pareto_ID, iter, result, attr):

        self.results_MP[Scn_ID][Pareto_ID][iter] = result
        attr = pd.concat([attr], keys=[iter], names=['Iter'])
        self.solver_attributes_MP = pd.concat([self.solver_attributes_MP, attr])
        col = self.number_SP_solutions.columns.difference(["House"])
        self.number_MP_solutions = self.number_SP_solutions[col].groupby('MP_solution').mean()

    def __split_parameter_sets_per_building(self, h, parameters_SP = dict({})):
        """
        Description
        -----------
        Some inputs are for the district and some other for the houses. This function fuses the two
        and gives the parameters per house. This is important to run an optimization on a single building
        Inputs
        ------
        h : string,  House ID
        parameters_SP: dictionary, Parameters of the house

        Outputs
        -------
        buildings_data_SP: dictionary, egid, surface area, class of the building, ...
        parameters_SP: dictionary, Parameters from the script for a single house (f.e. tariffs)
        infrastructure_SP: dictionary, The district structure for a single house
        """
        ID = np.where(h == self.infrastructure.House)[0][0]

        single_building_data = {"buildings_data": {h: self.buildings_data[h]}}
        buildings_data_SP = {h: self.buildings_data[h]}
        building_units = {"building_units": self.infrastructure.units}

        for key in self.parameters:
            if key not in self.lists_MP["list_parameters_MP"]:
                if isinstance(self.parameters[key], (int, float)):
                    parameters_SP[key] = self.parameters[key]
                elif self.parameters[key].shape[0] >= self.DW_params['timesteps']:  # if demands profiles (heat gains / DHW / electricity) are set for more than 1 building
                    nb_buildings = round(self.parameters[key].shape[0]/self.DW_params['timesteps'])
                    profile_building_x = self.parameters[key].reshape(nb_buildings, self.DW_params['timesteps'])
                    parameters_SP[key] = profile_building_x[ID]
                else:
                    parameters_SP[key] = self.parameters[key][ID]

        infrastructure_SP = infrastructure.infrastructure(single_building_data, building_units, self.infrastructure.grids)  # initialize District

        # TODO: better integration Units_Parameters specific to each house
        unit_param = self.infrastructure.Units_Parameters.loc[[string.endswith(h) for string in self.infrastructure.Units_Parameters.index]]
        infrastructure_SP.Units_Parameters[["Units_Fmax", "Cost_inv2"]] = unit_param[["Units_Fmax", "Cost_inv2"]]

        return buildings_data_SP, parameters_SP, infrastructure_SP

    def return_combined_SP_results(self, dict_results, result_dataframe):

        t = {(i, j, k, l, m): getattr(dict_results[i][j][k][l][m], result_dataframe)
             for i in dict_results.keys()
             for j in dict_results[i].keys()
             for k in dict_results[i][j].keys()
             for l in dict_results[i][j][k].keys()
             for m in dict_results[i][j][k][l].keys()
             }

        df_district_results = pd.concat(t.values(), keys=t.keys(), names=['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'], axis=0)
        df_district_results = df_district_results.sort_index()
        # TODO maybe drop building level as it is in the result_dataframe

        return df_district_results
