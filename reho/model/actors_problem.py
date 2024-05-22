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
    
    def execute_actors_problem(self, n_sample=10, bounds=None, actor="Owners"):
        self.method["actors_problem"] = True
        self.method["include_all_solutions"] = True
        self.method['building-scale'] = True
        self.scenario["Objective"] = "TOTEX_bui"
        self.set_indexed["ActorObjective"] = np.array([actor])
        if bounds is not None:
            sampler = qmc.LatinHypercube(d=2)
            sample = sampler.random(n=n_sample)
            l_bound = [bounds[key][0] for key in bounds]
            u_bound = [bounds[key][1] for key in bounds]
            samples = pd.DataFrame(qmc.scale(sample, l_bound, u_bound), columns=['utility_portfolio', 'owner_portfolio'])
            self.samples = samples.round(4)
        else:
            self.samples = pd.DataFrame([[None, None]] * n_sample, columns=['utility_portfolio', 'owner_portfolio'])
    
        Scn_ID = self.scenario['name']
        self.pool = mp.Pool(mp.cpu_count())
        results = {ids: self.pool.apply_async(self.run_actors_optimization, args=(self.samples, ids)) for ids in self.samples.index}
        while len(results[list(self.samples.index)[-1]].get()) != 2:
            time.sleep(1)
        for ids in self.samples.index:
            df_Results, df_Results_MP = results[ids].get()
            self.add_df_Results(None, Scn_ID, ids, self.scenario)
            self.get_KPIs(Scn_ID, ids)
            self.results_MP[Scn_ID][ids] = df_Results_MP
    
        self.samples["objective"] = None
        for i in self.results_MP[self.scenario["name"]]:
            if self.results_MP[self.scenario["name"]][i] is not None:
                self.samples.loc[i, "objective"] = self.results_MP[self.scenario["name"]][i][0]["df_District"]["Objective"]["Network"]
    
        self.pool.close()
    
        gc.collect()  # free memory
    
    def run_actors_optimization(self, samples, ids):
        if any([samples[col][0] for col in samples]):  # if samples contain values
            param = samples.iloc[ids]
            self.parameters = {'utility_portfolio_min': param['utility_portfolio'], 'owner_portfolio_min': param['owner_portfolio']}
        scenario, SP_scenario, SP_scenario_init = self.select_SP_obj_decomposition(self.scenario)
        try:
            scn = self.scenario["name"]
            self.MP_iteration(scenario, Scn_ID=scn, binary=True, Pareto_ID=0)
            self.add_df_Results(None, scn, 0, self.scenario)
            return self.results[scn][0], self.results_MP[scn][0]
        except:
            return None, None
    
    def read_configurations(self, path=None):
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
            init_beta = [10, 5, 2, 1, 0.5, 0.2, 0.1]
    
            for beta in init_beta:  # execute SP for MP initialization
                if self.method['parallel_computation']:
                    results = {h: self.pool.apply_async(self.SP_initiation_execution, args=(SP_scenario_init, Scn_ID, s, h, None, beta)) for h in
                               self.infrastructure.houses}
                    while len(results[list(self.buildings_data.keys())[-1]].get()) != 2:
                        time.sleep(1)
                    for h in self.infrastructure.houses:
                        (df_Results, attr) = results[h].get()
                        self.add_df_Results_SP(Scn_ID, s, self.iter, h, df_Results, attr)
                self.feasible_solutions += 1  # after each 'round' of SP execution the number of feasible solutions increases
        self.pool.close()
    
        if not os.path.exists(path_to_configurations):
            os.makedirs(path_to_configurations)
    
        filename = 'tr_' + str(self.buildings_data["Building1"]["transformer"]) + '_' + str(len(self.buildings_data)) + '.pickle'
        writer = open(os.path.join(path_to_configurations, filename), 'wb')
        pickle.dump([self.results_SP, self.feasible_solutions, self.number_SP_solutions], writer)
