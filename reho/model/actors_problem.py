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

    def get_max_profit_actor(self, actor="Utility"):
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
            - 'utility_profit_min': sampled values for the Utility actor's minimum profit.
            - 'owner_PIR_min'     : sampled values for the Owner actor's profit-investment ratio.
        Sampling strategies:
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
        l_bound = [util_lb, own_lb]
        u_bound = [util_ub + 1e-5, own_ub + 1e-5]

        sampler = qmc.Sobol(d=2, scramble=True)
        k = math.ceil(math.log2(n_samples or 1))
        points = sampler.random_base2(m=k)[:n_samples]
        df_samples = pd.DataFrame(qmc.scale(points, l_bound, u_bound), columns=['utility_profit_min', 'owner_PIR_min']).round(4)

        self.samples = df_samples.loc[df_samples.index.repeat(len(ins_target))].reset_index(drop=True)
        self.samples['ins_target'] = np.tile(ins_target, n_samples)




    def actor_decomposition_optimization(self):
        """
        Run the single_optimization with DWD for each sampled actor epsilon.

        Parameters
        ----------
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