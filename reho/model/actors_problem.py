from scipy.stats import qmc
from reho.model.reho import *
import sys
import warnings

__doc__ = """
File for constructing and solving the optimization for the actor-based problem formulation.
"""


class ActorsProblem(REHO):
    """
    Performs an actor-based optimization.

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

    def read_configurations(self, path=None):
        """

        Parameters
        ----------
        path

        Returns
        -------

        """
        if path is None:
            filename = 'tr_' + str(self.buildings_data["Building1"]["transformer"]) + '_' + str(len(self.buildings_data)) + '.pickle'
            path = os.path.join(path_to_configurations, filename)
        with open(path, 'rb') as reader:
            [self.results_SP, self.feasible_solutions, self.number_SP_solutions] = pickle.load(reader)

    def generate_configurations(self, n_sample=5, tariffs_ranges=None, delta_feed_in=0.15):
        if tariffs_ranges is None:
            tariffs_ranges = {'Electricity': {"Cost_supply_cst": [0.15, 0.45]},
                              'NaturalGas': {"Cost_supply_cst": [0.10, 0.30]}}
        l_bounds = []
        u_bounds = []
        names = []
        for layers in tariffs_ranges:
            for param in tariffs_ranges[layers]:
                l_bounds = l_bounds + [tariffs_ranges[layers][param][0]]
                u_bounds = u_bounds + [tariffs_ranges[layers][param][1]]
                names = names + [layers + '_' + param]

        sampler = qmc.LatinHypercube(d=len(l_bounds))
        sample = sampler.random(n=n_sample)
        samples = pd.DataFrame(qmc.scale(sample, l_bounds, u_bounds), columns=names)
        samples = samples.round(3)
        samples['Electricity_Cost_demand_cst'] = samples['Electricity_Cost_supply_cst'] - delta_feed_in

        tariffs_ranges['Electricity']['Cost_demand_cst'] = [tariffs_ranges['Electricity']['Cost_supply_cst'][0] - delta_feed_in,
                                                            tariffs_ranges['Electricity']['Cost_supply_cst'][1] - delta_feed_in]

        self.pool = mp.Pool(mp.cpu_count())
        for s in samples.index:
            for layer in tariffs_ranges:
                for param in tariffs_ranges[layer]:
                    self.infrastructure.grids[layer][param] = samples.loc[s, layer + "_" + param]

            scenario, SP_scenario, SP_scenario_init = self.select_SP_obj_decomposition(self.scenario)
            Scn_ID = self.scenario['name']
            init_beta = [2, 1, 0.5]

            for beta in init_beta:  # execute SP for MP initialization
                if self.method['parallel_computation']:
                    results = {h: self.pool.apply_async(self.SP_initiation_execution, args=(SP_scenario_init, Scn_ID, s, h, None, beta)) for h in
                               self.infrastructure.houses}
                    while len(results[list(self.buildings_data.keys())[-1]].get()) != 2:
                        time.sleep(1)
                    for h in self.infrastructure.houses:
                        df_Results, attr = results[h].get()
                        self.add_df_Results_SP(Scn_ID, s, self.iter, h, df_Results, attr)

                    if self.method['refurbishment']:
                        self.feasible_solutions += 1
                        self.refurbishment = True
                        results = {h: self.pool.apply_async(self.SP_initiation_execution, args=(SP_scenario_init, Scn_ID, s, h, None, beta)) for h in
                                   self.infrastructure.houses}
                        for h in self.infrastructure.houses:
                            df_Results, attr = results[h].get()
                            self.add_df_Results_SP(Scn_ID, s, self.iter, h, df_Results, attr)

                else:
                    for id, h in enumerate(self.infrastructure.houses):
                        df_Results, attr = self.SP_initiation_execution(SP_scenario_init, Scn_ID=Scn_ID, Pareto_ID=s,
                                                                        h=h, epsilon_init=None, beta=beta)
                        self.add_df_Results_SP(Scn_ID, s, self.iter, h, df_Results, attr)

                    if self.method['refurbishment']:
                        self.feasible_solutions += 1
                        self.refurbishment = True
                        df_Results, attr = self.SP_initiation_execution(SP_scenario_init, Scn_ID=Scn_ID, Pareto_ID=s,
                                                                        h=h, epsilon_init=None, beta=beta)
                        self.add_df_Results_SP(Scn_ID, s, self.iter, h, df_Results, attr)

                self.refurbishment = False
                self.feasible_solutions += 1
        self.pool.close()

        if not os.path.exists(path_to_configurations):
            os.makedirs(path_to_configurations)

        filename = 'tr_' + str(self.buildings_data["Building1"]["transformer"]) + '_' + str(len(self.buildings_data)) + '.pickle'
        writer = open(os.path.join(path_to_configurations, filename), 'wb')
        pickle.dump([self.results_SP, self.feasible_solutions, self.number_SP_solutions], writer)

    def set_actors_epsilon(self, actors_epsilon=None):
        """
        Define and validate epsilon bounds for each actor in the decomposition.

        Valid keys in the `actors_epsilon` dict:
          - utility_profit_min : [float, float]
              Lower and upper bounds for the Utility actor's minimum profit.
          - owner_PIR_min      : [float, float]
              Lower and upper bounds for the Owner actor's profit-investment ratio (PIR).
          - renter_expense_max : float
              Maximum allowable expense for the Renter actor.

        If a bound is omitted or invalid, default values are applied:
          - Utility: computed automatically by an initialization run.
          - Owners : defaults to [0.0, 0.1].
          - Renters : defaults to 1e7.

        Parameters
        ----------
        actors_epsilon : dict, optional
            User-specified epsilon bounds. If None, defaults are used for all actors.

        Returns
        -------
        bounds : dict
            Maps 'Utility' and 'Owners' to their [lower, upper] bound lists.
        """

        # Define epsilon keys
        valid_keys = {'utility_profit_min', 'owner_PIR_min', 'renter_expense_max'}
        actors_epsilon = actors_epsilon or {}

        extra = set(actors_epsilon) - valid_keys
        if extra:
            self.logger.warning(f"Unknown ε-keys provided: {sorted(extra)}")
            sys.exit(1)

        bounds = {}

        def assign_bounds(key, actor, default_bounds):
            if key in actors_epsilon:
                lb, ub = actors_epsilon[key]
                if lb is None or ub is None or ub < lb:
                    self.logger.warning(f"Invalid bounds for {key}: [{lb}, {ub}]")
                    sys.exit(1)
                self.logger.info(f"Using user-defined bounds for {actor}: [{lb}, {ub}]")
                return [lb, ub]
            return default_bounds

        # Utility bounds: user or calculated
        util_default = None  # placeholder: will calculate if not provided
        util_bounds = assign_bounds('utility_profit_min', 'Utility', util_default)
        if util_bounds is None:
            self.logger.info("Calculating default bounds for Utility")
            self.execute_actors_initiation(Scn_ID='Utility')
            obj = -self.results['Utility'][0]['df_Actors'].loc['Utility'][0]
            util_bounds = [0.0, round(obj, 3)]
            self.logger.info(f"Default Utility bounds set to {util_bounds}")
        bounds['Utility'] = util_bounds

        # Owners PIR bounds: user or fallback
        owners_default = [0.0, 0.1]
        owners_bounds = assign_bounds('owner_PIR_min', 'Owners', owners_default)
        if 'owner_PIR_min' not in actors_epsilon:
            self.logger.info(f"Using default PIR bounds for Owners: {owners_default}")
        bounds['Owners'] = owners_bounds

        # Renter expense cap: user or default
        if 'renter_expense_max' in actors_epsilon:
            self.parameters['renter_expense_max'] = actors.generate_renter_expense_max_new(self.buildings_data,
                                                                        actors_epsilon['renter_expense_max'], limit=True)
        else:
            self.logger.info(f"Using default renter_expense_max")

        return bounds

    def execute_actors_initiation(self, Scn_ID="Utility"):
        """
        Initialize and solve the actor-specific master problem for a single actor

        - Configure the scenario
        - Run one iteration of the master problem
        - Compute the actor's unbounded optimal solution

        Parameters
        ----------
        Scn_ID : str, optional
            Actor identifier to initialize (default "Utility").
        """
        ids = 0
        self.scenario['name'] = Scn_ID
        self.scenario["Objective"] = "TOTEX_bui"
        self.set_indexed["ActorObjective"] = np.array([Scn_ID])

        scenario, SP_scenario, SP_scenario_init = self.select_SP_obj_decomposition(self.scenario)
        if 'Renter_noSub' not in scenario.get('specific', []):
            scenario['specific'] = scenario.get('specific', []) + ['Renter_noSub']
        self.parameters['renter_expense_max'] = actors.generate_renter_expense_max_new(self.buildings_data, limit=False)

        self.MP_iteration(scenario, Scn_ID=Scn_ID, binary=True, Pareto_ID=ids)
        self.add_df_Results_MP(Scn_ID, ids, self.iter, self.results_MP[Scn_ID][ids][self.iter], self.solver_attributes_MP.droplevel('Iter').iloc[[-1]])
        self.add_df_Results(None, Scn_ID, ids, self.scenario)   # process results based on results MP
        self.get_KPIs(Scn_ID, ids)
        gc.collect()  # free memory

    def sample_actors_epsilon(self, bounds=None, n_samples=1, linear=False):
        """
        Generate N samples of actor epsilon parameters and store them in `self.samples`.
        Produces a pandas DataFrame with columns:
            - 'utility_profit_min': sampled values for the Utility actor's minimum profit.
            - 'owner_PIR_min'     : sampled values for the Owner actor's profit-investment ratio.
        Sampling strategies:
            - linear grid: evenly spaced values between provided [lower, upper] bounds.
            - Sobol sequence: low-discrepancy quasi-random samples (default).

        Parameters
        ----------
        bounds : dictionary

        n_samples : int, optional
            Number of samples to generate (default=1).
        linear : boolean, optional
            If True,  use linear grid sampling; if False, apply Sobol sampling  (default=False).
        """
        util_lb, util_ub = bounds['Utility']
        own_lb, own_ub = bounds['Owners']
        cols = ['utility_profit_min', 'owner_PIR_min']

        if linear:
            if n_samples < 2:
                df = pd.DataFrame([{cols[0]: util_lb, cols[1]: own_lb}])
            else:
                util_vals = [
                    util_lb + i * (util_ub - util_lb) / (n_samples - 1)
                    for i in range(n_samples)
                ]
                own_vals = [
                    own_lb + i * (own_ub - own_lb) / (n_samples - 1)
                    for i in range(n_samples)
                ]
                df = pd.DataFrame({cols[0]: util_vals, cols[1]: own_vals})
        else:
            delta = 1e-5
            l_bound = [util_lb, own_lb]
            u_bound = [util_ub + delta, own_ub + delta]
            sampler = qmc.Sobol(d=2, scramble=True)
            k = math.ceil(math.log2(n_samples or 1))
            points = sampler.random_base2(m=k)[:n_samples]
            df = pd.DataFrame(qmc.scale(points, l_bound, u_bound), columns=cols)
        # Round and assign
        self.samples = df.round(4)

    def actor_decomposition_optimization(self, scenario, actor='Renters'):
        """
        Run the single_optimization with DWD for each sampled actor epsilon.

        Parameters
        ----------
        scenario : dictionary
        actor : str
            Identifier of the actor being optimized (default 'Renters').
        """
        self.scenario["Objective"] = scenario["Objective"]
        self.scenario["specific"] = scenario["specific"]
        self.set_indexed["ActorObjective"] = np.array([actor])

        for ids in self.samples.index:
            self.iter = 0
            param = self.samples.iloc[ids]

            self.parameters['utility_profit_min'] = param['utility_profit_min']
            self.parameters['owner_PIR_min'] = param['owner_PIR_min']

            try:
                self.single_optimization(Pareto_ID=ids)
                self.results[self.scenario['name']][ids]['Samples']['Sampling_result'] = param
                self.add_dual_Results(Scn_ID=self.scenario['name'], Pareto_ID=ids)
                self.logger.info(f"Sample {ids}: Optimization completed.")

            except Exception as e:
                self.results[self.scenario['name']][ids] = None
                self.logger.error(f"Sample {ids}: Optimization failed with error: {e}", exc_info=True)

    def add_dual_Results(self, Scn_ID, Pareto_ID):
        self.results[Scn_ID][Pareto_ID]['df_Dual'] = {}
        results = self.results[Scn_ID][Pareto_ID]['df_Dual']
        results.update({
            'df_Actors_dual': {},
            'df_Dual_t': {},
            'df_Dual': {},
        })
        for i in range(self.iter):
            mp_results = self.results_MP[Scn_ID][Pareto_ID][i]
            for key, df in mp_results.items():
                if key == 'df_Dual' or key == 'df_Actors_dual' or key == 'df_Dual_t':
                    results[key][f'Iter.{i}'] = df
        self.results[Scn_ID][Pareto_ID]['df_Dual'] = results

    def get_profit_ratio(self):
        Costs_inv = self.results['Owners'][0]['df_Performance']['Costs_inv']
        Costs_House_upfront = self.results['Owners'][0]['df_Performance']['Costs_House_upfront']
        owner_profit = self.results['Owners'][0]['df_Performance']['owner_profit']
        opr = (owner_profit / (Costs_inv + Costs_House_upfront)).mean()
        return opr