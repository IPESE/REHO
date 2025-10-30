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

    """

    def __init__(self, qbuildings_data, units, grids, parameters=None, set_indexed=None, cluster=None, method=None, scenario=None, solver="highs", DW_params=None):

        super().__init__(qbuildings_data, units, grids, parameters, set_indexed, cluster, method, scenario, solver, DW_params)

    def get_max_profit_actor(self, actor="Utility"):
        """
        Get the maximum profit for a given actor by running a single optimization with the actor's objective.
        Parameters
        ----------
        actor str
            The actor for which to calculate the maximum profit. Options are "Utility" or "Owners"
        Returns
        -------
        float
            The maximum profit value for the specified actor.

        """
        scenario = self.scenario.copy()
        set_indexed = self.set_indexed.copy()

        self.scenario['name'] = actor
        self.scenario["Objective"] = "TOTEX_actor"
        self.set_indexed["ActorObjective"] = np.array([actor])
        self.single_optimization(Pareto_ID=0)
        obj = -self.results[actor][0]['df_Actors'].loc[actor][0]

        self.scenario = scenario
        self.set_indexed = set_indexed
        return obj


    def sample_actors_epsilon(self, bounds=None, n_samples=1, ins_target = [0]):
        """
        Generate N samples of actor epsilon parameters and store them in `self.samples`.
        Produces a pandas DataFrame with columns:
            - 'utility_profit_min': sampled values for the Utility (ECM) actor's minimum profit (absolute value, usually set to 0).
            - 'owner_PIR_min'     : sampled values for the Owner (Landlord) actor's profit-investment ratio (percentage).
        Sampling strategies:
            - Sobol sequence: low-discrepancy quasi-random samples (default).

        Parameters
        ----------
        bounds : dict
            Dictionary specifying the lower and upper bounds for landlord's and ECM's (utility's) epsilon constraints:
                - 'Owners' : [lower_bound, upper_bound] for owner_PIR_min.
                - 'Utility': [lower_bound, upper_bound] for utility_profit_min.
        n_samples : int, optional
            Number of samples to generate (default=1) for each ins_target value.
        ins_target : list, optional
            List of insulation renovation targets (percentage of total building envelope area) to consider.

        Examples
        --------
        >>> reho.sample_actors_epsilon(bounds={"Owners": [0.0, 1.0], "Utility": [0, 1000]}, n_samples=2, ins_target=[0,0.2])

        Notes
        -----
        The total number of optimization runs will be `n_samples * len(ins_target)`.

        """
        util_lb, util_ub = bounds['Utility']
        own_lb, own_ub = bounds['Owners']

        # Sobol sampling in normalized [0, 1]^2 space
        sampler = qmc.Sobol(d=2, scramble=True)
        k = math.ceil(math.log2(n_samples or 1))
        points = sampler.random_base2(m=k)[:n_samples]

        # Linear transformation: scale from [0, 1] to original bounds
        # utility_profit: [0, 1] -> [util_lb, util_ub]
        # owner_PIR: [0, 1] -> [own_lb, own_ub]
        utility_samples = util_lb + points[:, 0] * (util_ub - util_lb)
        owner_samples = own_lb + points[:, 1] * (own_ub - own_lb)

        df_samples = pd.DataFrame({
            'utility_profit_min': utility_samples,
            'owner_PIR_min': owner_samples
        }).round(4)

        self.samples = df_samples.loc[df_samples.index.repeat(len(ins_target))].reset_index(drop=True)
        self.samples['ins_target'] = np.tile(ins_target, n_samples)

    def actor_decomposition_optimization(self):
        """
        Run the single_optimization with DWD for each sampled actor epsilon.
        """
        for ids in self.samples.index:
            self.iter = 0
            sample_param = self.samples.iloc[ids]
            for param in sample_param.index:
                self.parameters[param] = sample_param[param]
            self.single_optimization(Pareto_ID=ids)
            self.results[self.scenario['name']][ids]['Samples']['Sampling_result'] = sample_param
            self.add_dual_Results(Scn_ID=self.scenario['name'], Pareto_ID=ids)

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