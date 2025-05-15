from scipy.stats import qmc
from reho.model.reho import *

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

    def execute_actors_initiation(self, Scn_ID="Owners"):
        self.method["actors_problem"] = True
        self.method["include_all_solutions"] = True
        self.method['district-scale'] = True
        self.scenario["Objective"] = "TOTEX_bui"
        self.set_indexed["ActorObjective"] = np.array([Scn_ID])
        self.samples = pd.DataFrame([[None, None, None]], columns=['utility_profit', 'owner_profit', 'PIR'])
        ids = 0

        results = self.run_actors_initiation(ids=ids)
        df_Results, df_Results_MP, solver_attributes = results
        solver_attributes = solver_attributes.droplevel('Iter').iloc[[-1]].copy()
        self.add_df_Results_MP(Scn_ID, ids, self.iter, df_Results_MP, solver_attributes)    # store results MP (pool.apply_async don't store it)
        self.add_df_Results(None, Scn_ID, ids, self.scenario)   # process results based on results MP
        self.get_KPIs(Scn_ID, ids)

        self.samples["objective"] = None

        if self.results_MP[self.scenario["name"]][ids] is not None:
            self.samples.loc[ids, "objective"] = self.results_MP[self.scenario["name"]][ids][0]["df_District"]["Objective"]["Network"]
        gc.collect()  # free memory

    def run_actors_initiation(self, ids):
        scenario, SP_scenario, SP_scenario_init = self.select_SP_obj_decomposition(self.scenario)
        if 'Renter_noSub' not in scenario.get('specific', []):
            scenario['specific'] = scenario.get('specific', []) + ['Renter_noSub']
        try:
            scn = self.scenario["name"]
            self.MP_iteration(scenario, Scn_ID=scn, binary=True, Pareto_ID=ids)
            self.add_df_Results(None, scn, ids, self.scenario)
            return self.results[scn][ids], self.results_MP[scn][ids][self.iter], self.solver_attributes_MP
        except:
            return None, None

    def set_actors_epsilon(self, actors_epsilon=None, n_samples=1, mode='default'):
        if actors_epsilon is None:
            actors_epsilon = {}
        # allowed keys and their mapping to scenario actors
        _key_map = {
            'utility_profit_lb': 'Utility',
            'owner_profit_lb': 'Owners',
            'owner_profit_ub': 'PIR',
            'renter_risk_factor': None
        }
        # quick unknown‐key check
        extra = set(actors_epsilon) - set(_key_map)
        if extra:
            warnings.warn(f"Unknown ε‐keys: {sorted(extra)}")
            sys.exit(1)

        delta = 1e-6
        bounds = {}  #hold [lower, upper] for 'Utility','Owners','PIR'

        # Utility & Owners profit‐lb share:
        for eps_key in ('utility_profit_lb', 'owner_profit_lb'):
            actor = _key_map[eps_key]
            lb, ub = actors_epsilon.get(eps_key, [0, delta])
            if ub > 0:
                print(f"Calculate boundary for {actor} …")
                self.scenario['name'] = actor
                self.execute_actors_initiation(Scn_ID=actor)
            else:
                print(f"Calculate boundary for {actor}: DEFAULT 0")
                if actor == 'Utility' and ub <= 0:
                    self.parameters["renter_expense_max"] = [1e7] * len(self.buildings_data)
            bounds[actor] = [lb, ub if ub > 0 else delta]

        # Copy PIR upper‐bound
        bounds['PIR'] = actors_epsilon.get('owner_profit_ub', [0, delta])

        # Renter risk no bound sampling needed
        if 'renter_expense_ub' in actors_epsilon:
            self.parameters['risk_factor'] = actors_epsilon['renter_expense_ub']

        # CH-mode override on number of samples
        if mode == 'CH':
            step = 0.02
            low, high = bounds['Owners']
            n_samples = math.ceil((high - low) / step) + 1

        # Build Sobol sampler & draw
        dims = ['Utility', 'Owners', 'PIR']
        sampler = qmc.Sobol(d=len(dims), scramble=True)
        k = math.ceil(math.log2(n_samples))
        pts = sampler.random_base2(m=k)[:n_samples]

        # Scale into real bounds and label
        l_bound = [bounds[a][0] for a in dims]
        u_bound = [bounds[a][1] for a in dims]
        cols = ['utility_profit', 'owner_profit', 'PIR']
        df = pd.DataFrame(qmc.scale(pts, l_bound, u_bound), columns=cols)

        self.samples = df.round(4)

    def actor_decomposition_optimization(self, scenario, actor='Renters'):
        self.scenario["Objective"] = scenario["Objective"]
        self.scenario["specific"] = scenario["specific"]
        self.method['building-scale'] = False
        self.method['district-scale'] = True
        self.set_indexed["ActorObjective"] = np.array([actor])

        for ids in self.samples.index:
            self.iter = 0
            param = self.samples.iloc[ids]
            self.parameters['PIR'] = param['PIR']
            self.parameters["renter_expense_max"] = actors.generate_renter_expense_max(self.buildings_data,
                                                                                       self.parameters)
            if param['utility_profit'] <= 0.001:
                self.parameters['utility_profit_min'] = param['utility_profit'] * 0
            else:
                self.parameters['utility_profit_min'] = param['utility_profit'] * - \
                self.results['Utility'][0]["df_Actors"].loc['Utility'][0]

            if param['owner_profit'] <= 0.001:
                self.parameters['owner_profit_min'] = [0] * len(self.buildings_data)
            else:
                self.parameters['owner_profit_min'] = param['owner_profit'] * np.array(
                    [self.results_MP["Owners"][0][0]['df_Actors_expense']['owner_profit'][building]
                     * self.parameters["renter_expense_max"][idx]
                     / self.results_MP["Owners"][0][0]['df_Actors_expense']['renter_expense'][building]
                     for idx, building in enumerate(list(self.buildings_data.keys()))])
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