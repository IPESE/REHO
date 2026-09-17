"""District-scale optimization problem.

:class:`MasterProblem` implements the Dantzig-Wolfe decomposition: it coordinates
one :class:`~reho.model.sub_problem.SubProblem` per building, selects a convex
combination of the configurations they propose, and returns the dual values that
steer the next round of sub-problems.

See also
--------
reho.model.sub_problem.SubProblem : building-scale problem, generates the columns.
reho.model.reho.REHO : user-facing entry point.
"""

import contextlib
import copy
import multiprocessing as mp
import os
import warnings
from itertools import groupby

import geopandas as gpd
import numpy as np
import pandas as pd

import reho.model.infrastructure as infrastructure
import reho.model.postprocessing.write_results as write_results
import reho.model.preprocessing.actors as actors
import reho.model.preprocessing.buildings_profiles as buildings_profiles
import reho.model.preprocessing.mobility_generator as mobility
from reho.logger import configure_logging, get_logger
from reho.model.ampl_interface import (
    DISTRICT_UNIT_MODELS,
    INTERPERIOD_DISTRICT_UNIT_MODELS,
    create_ampl_session,
    exitcode_from_ampl,
    read_unit_models,
)
from reho.model.options import initialise_DW_params, initialize_default_methods
from reho.model.preprocessing import renovation
from reho.model.preprocessing.local_data import return_local_data
from reho.model.sub_problem import SubProblem
from reho.paths import (
    path_to_ampl_model,
    path_to_clustering,
    path_to_district_units,
    path_to_sia_equivalence,
    path_to_sia_norms,
    path_to_units,
)

__all__ = ["MasterProblem", "fix_unit_sizes"]

logger = get_logger(__name__)

#: Specific heat capacity of water, used to size district-heating flow rates [kJ/(kg.K)].
CP_WATER = 4.18

#: Latent enthalpy of the CO2 heat carrier, used when method['DHN_CO2'] is set [kJ/kg].
DELTA_H_CO2 = 179.5

#: Default temperature difference between DHN supply and return when none is given [K].
DEFAULT_DHN_DELTA_T = 10.0

#: Clustering options applied when the caller does not provide any.
DEFAULT_CLUSTER = {"Location": "Geneva", "Attributes": ["T", "I", "W"], "Periods": 10, "PeriodDuration": 24}

#: SIA norm tables, read once per process by :func:`_load_sia_data`.
_sia_data_cache = {}


def _load_sia_data():
    """Read the SIA norm tables, once per process.

    The tables are static package data, shared by every :class:`MasterProblem`: they must not be
    modified in place.

    Returns
    -------
    dict
        ``df_SIA_380``, the room mix of the SIA 380/1 categories, and ``df_SIA_2024``, the sheets of
        ``sia2024_data.xlsx``.
    """
    if not _sia_data_cache:
        _sia_data_cache["df_SIA_380"] = pd.read_csv(path_to_sia_equivalence, sep=';', index_col=[0], header=[0])
        _sia_data_cache["df_SIA_2024"] = pd.read_excel(path_to_sia_norms, sheet_name=['profiles', 'calculs', 'data'],
                                                       engine='openpyxl', index_col=[0], skiprows=[0, 2, 3, 4], header=[0])
    return _sia_data_cache


def _sp_solver_attributes(Scn_ID, Pareto_ID, ampl):
    """Solver statistics of a solved AMPL session.

    Parameters
    ----------
    Scn_ID : str
        Name of the scenario.
    Pareto_ID : int
        Index of the Pareto point.
    ampl : amplpy.AMPL
        A session on which ``solve()`` has been called.

    Returns
    -------
    pandas.DataFrame
        One row, indexed by ``(Scn_ID, Pareto_ID)``: solving time, number of constraints and
        variables before and after presolve, and value of the objective.
    """
    solving_time = ampl.getValue('_total_solve_time')
    constr = ampl.getValue('_ncons')
    pres_constr = ampl.getValue('_sncons')  # after presolve
    var = ampl.getValue('_nvars')
    pres_var = ampl.getValue('_snvars')  # after presolve
    binaries = ampl.getValue('_snbvars')  # after presolve
    integer = ampl.getValue('_snivars')  # after presolve
    no_ojectives = ampl.getValue('_snobjs')  # after presolve
    val_objectives = ampl.getCurrentObjective().getValues().toList()[0]

    mux = pd.MultiIndex.from_tuples([(Scn_ID, Pareto_ID)], names=['Scn_ID', 'Pareto_ID'])
    df = pd.DataFrame([[solving_time, constr, pres_constr, var, pres_var, binaries, integer, no_ojectives, val_objectives]], index=mux,
                      columns=['solving_time', 'constraints', 'presolve_constraints', 'variables', 'presolve_variables',
                               'presolve_binaries', 'presolve_integer', 'no_objective', 'val_objective'])
    return df


def fix_unit_sizes(ampl, df_fix_Units, units, targets=None):
    """Fix the size and the use of units to the values of ``df_fix_Units``.

    Used by ``method['fix_units']`` to evaluate the operation of a design decided elsewhere, for
    instance the optimum of a previous scenario.

    Parameters
    ----------
    ampl : amplpy.AMPL
        A built, not yet solved session.
    df_fix_Units : pandas.DataFrame
        Columns ``Units_Mult`` and ``Units_Use``, indexed by unit, e.g. ``PV_Building1`` or ``rSOC_district``.
    units : iterable of str
        Units of the problem held by ``ampl``.
    targets : iterable of str, optional
        Units to fix, e.g. those of the technologies of ``fix_units_list``: the ones that ``df_fix_Units``
        does not size are fixed to zero, i.e. not installed. By default, the units of the problem that
        ``df_fix_Units`` sizes.

    Notes
    -----
    PV capacities are relaxed by 1e-9 because the AMPL model bounds the panel area by the available
    roof area; fixing the two to the exact same value makes the problem infeasible on rounding alone.
    """
    units = set(units)
    targets = df_fix_Units.index if targets is None else targets
    for unit in [unit for unit in targets if unit in units]:
        if unit in df_fix_Units.index:
            size = df_fix_Units.Units_Mult.loc[unit] * (1 - 1e-9 if unit.startswith("PV_") else 1)
            use = float(df_fix_Units.Units_Use.loc[unit])
        else:
            size, use = 0, 0
        ampl.getVariable('Units_Mult').get(unit).fix(size)
        ampl.getVariable('Units_Use').get(unit).fix(use)


def _solve_SP_task(task):
    """Build, solve and extract the sub-problem of one building.

    This function runs in a worker process when the sub-problems are solved in parallel. ``task``
    holds the data of a single building, as assembled by :meth:`MasterProblem.prepare_SP_task`, so
    that the whole master problem is not sent to the worker with each sub-problem.

    Parameters
    ----------
    task : dict
        Payload built by :meth:`MasterProblem.prepare_SP_task`.

    Returns
    -------
    df_Results : dict of pandas.DataFrame
        Results of the sub-problem, see :func:`~reho.model.postprocessing.write_results.get_df_Results_from_SP`.
    attr : pandas.DataFrame
        Solver statistics, see :func:`_sp_solver_attributes`.

    Raises
    ------
    RuntimeError
        If the sub-problem did not converge.
    """
    h = task['h']
    sp = SubProblem(task['infrastructure_SP'], task['buildings_data_SP'], task['local_data'],
                    task['parameters_SP'], task['set_indexed_SP'], task['cluster'],
                    task['scenario'], task['method'], task['solver'], task.get('qbuildings_data'))
    ampl = sp.build_model_without_solving()

    if task['method']['fix_units']:
        targets = [f"{technology}_{h}" for technology in task['fix_units_list']] if task['fix_units_list'] else None
        fix_unit_sizes(ampl, task['df_fix_Units'], task['infrastructure_SP'].Units, targets)

    ampl.solve()
    exitcode = exitcode_from_ampl(ampl)

    df_Results = write_results.get_df_Results_from_SP(ampl, task['scenario'], task['method'], task['buildings_data_SP'])
    attr = _sp_solver_attributes(task['Scn_ID'], task['Pareto_ID'], ampl)

    del ampl
    if exitcode != 0:
        # It might be that the solution is optimal with unscaled infeasibilities. So we check if we really found a solution (via its cost value)
        performance = df_Results["df_Performance"]
        if exitcode != 'solved?' or performance['Costs_op'].iloc[0] + performance['Costs_inv'].iloc[0] == 0:
            raise RuntimeError(f"The sub-problem of {h} did not converge (solve_result: {exitcode!r}).")

    return df_Results, attr


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
        self.logger = get_logger(__name__)
        configure_logging(enabled=self.method['print_logs'])

        # infrastructure
        self.qbuildings_data = qbuildings_data
        self.buildings_data = qbuildings_data['buildings_data']
        self.ERA = sum([self.buildings_data[house]['ERA'] for house in self.buildings_data.keys()])

        self.infrastructure = infrastructure.Infrastructure(qbuildings_data, units, grids)
        self.infrastructure_SP = dict()
        self.build_infrastructure_SP()

        self.cluster = copy.deepcopy(DEFAULT_CLUSTER if cluster is None else cluster)

        # load SIA norms (cached at module level: static files, re-used across REHO instances)
        sia_data = _load_sia_data()

        # retrieve location data
        self.local_data = return_local_data(self.cluster, qbuildings_data)

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
        self.DW_params = initialise_DW_params(self.DW_params, self.cluster, self.buildings_data,
                                              building_scale=self.method['building-scale'])
        self.cpu_use = mp.cpu_count()
        self.pool = None  # open only while sub-problems are being solved, see worker_pool

        # TODO change the nomenclature of these parameters to semi-automate the separation between MP and SP: (ex: all MP parameters end with _MP)
        self.lists_MP = {"list_parameters_MP": ['Uh', 'Uh_ins', 'ins_target', 'ins_target_max', 'renter_subsidies_bound',
                                                'Costs_House_upfront_m2_MP', 'renter_expense_max','utility_profit_min', 'owner_PIR_max', 'owner_PIR_min', 'EMOO_totex_renter',
                                                'Network_ext', "ff_EV", "ff_ICE", 'monthly_grid_connection_cost', "Costs_House_upfront_m2_MP",
                                                "area_district", "velocity", "density", "delta_enthalpy", "cinv1_dhn", "cinv2_dhn", "Population",
                                                "transport_Units", "DailyDist", "Mode_Speed", "Cost_demand_ext", "EV_supply_ext", "share_activity", "Cost_supply_ext",
                                                'EV_y', 'EV_plugged_out', 'n_vehicles', 'EV_capacity', "beta_GWP_MP",
                                                "max_share", "min_share", "max_share_modes", "min_share_modes", "n_ICEperhab",
                                                "Cost_network_inv1", "Cost_network_inv2", "GWP_network_1", "GWP_network_2", "Units_Ext_district",
                                                "Network_lifetime", "HydrogenAnnualExport_district","data_EUD_avg", "SOEC_conv_eff","SOFC_elec_eff_CH4"],
                         "list_constraints_MP": [],
                         "list_set_indexed_MP": ["Districts", "Distances"]
                         }

        if "EV_district" in self.infrastructure.UnitsOfDistrict:
            self.lists_MP["list_constraints_MP"] += ['unidirectional_service', 'unidirectional_service2', "EV_chargingprofile1", "EV_chargingprofile2",
                                                     'ExternalEV_Costs_positive']

        if "rSOC_district" in self.infrastructure.UnitsOfDistrict:
            self.lists_MP["list_constraints_MP"] += ['forced_H2_annual_export_district']

        if self.method['actors_problem']:
            self.lists_MP["list_constraints_MP"] += ['Owner_Link_Subsidy_to_renovation', 'Owner_profit_max_PIR', 'Owner_noSub', 'Renter_noSub', 'Rent_fix_increase','Rent_fix_absolute']

        self.df_fix_Units = pd.DataFrame()
        self.fix_units_list = []

    def initialize_optimization_tracking_attributes(self):
        """
        Reset the attributes that track the decomposition, before a new optimization.

        - ``iter``: current iteration of the master problem.
        - ``feasible_solutions``: number of rounds of sub-problems solved, i.e. of configurations
          proposed by each building.
        - ``flags``: whether the sub-problems were already initiated for each objective
          (TOTEX, CAPEX, OPEX, GWP).
        - ``results_SP`` and ``results_MP``: results of every sub-problem and master problem solved.
        - ``number_SP_solutions`` and ``number_MP_solutions``: records of the solutions of each round.
        - ``solver_attributes_SP`` and ``solver_attributes_MP``: solver statistics of each solve.
        - ``stopping_criteria`` and ``reduced_costs``: convergence indicators of each iteration.

        The pool of worker processes is left untouched: it belongs to the ``with`` block that opened it,
        see :meth:`worker_pool`.
        """
        # internal IT parameter
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
        self.pool = None  # a pool of processes is not pickled

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
        scenario : dictionary
            scenario for the MP
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
        # This cap limits each building's grid exchange during initiation, relative to its peak domestic
        # electricity. Below 1 the domestic demand alone saturates it, leaving nothing for heating: the
        # sub-problems then turn out infeasible at the coldest hour rather than at the network balance.
        if capacity < max_DEL:
            self.logger.warning(
                f"Electricity Network_ext ({float(capacity):.0f} kW) is below the district peak domestic demand "
                f"({float(max_DEL):.0f} kW) over {nb_buildings} buildings, so the decomposition initiation caps "
                f"grid use at {float(capacity) * 0.999 / max_DEL:.2f} of that peak. Sub-problems are likely to be "
                f"infeasible; raise Network_ext to size the network for the district."
            )

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
        elif self.method['building-scale']:
            init_beta = [None]  # keep same objective function
        elif not self.method['include_all_solutions'] or self.flags[scenario['Objective']] == 0 or scenario['EMOO']['EMOO_grid'] != 0:
            init_beta = [1000.0, 1, 0.001]
        else:
            init_beta = []  # skip the initialization

        if self.method['include_all_solutions']:
            self.flags[scenario['Objective']] = 1  # never been optimized with this objective previously

        for beta in init_beta:  # execute SP for MP initialization
            self.launch_SP_multiprocessing(scenario, Scn_ID, Pareto_ID, epsilon_init, beta, initiation=True)
            if self.method['renovation'] is not None:
                for option in self.method['renovation']:
                    self.launch_SP_multiprocessing(scenario, Scn_ID, Pareto_ID, None, None, initiation=True, renovation_options=option)

        return

    @contextlib.contextmanager
    def worker_pool(self):
        """
        Keep a pool of worker processes open, for the sub-problems solved within a ``with`` block.

        The block that opens the pool closes it, and waits for its workers to exit; the blocks nested
        in it reuse the same pool. Each decomposition runs in such a block, and so do the successive
        decompositions of a Pareto curve, of the actors samples and of a sensitivity analysis: their
        sub-problems share one pool. On an exception, the workers are terminated rather than awaited.

        No pool is opened with the compact formulation, or when ``method['parallel_computation']``
        is disabled: the sub-problems are then solved in the main process.

        Starting the workers takes a few seconds, as each of them imports REHO. A script that runs
        several decompositions in a row can share one pool between them, by wrapping them in a block:

        >>> with reho.worker_pool():
        ...     for objective in ["TOTEX", "OPEX"]:
        ...         reho.scenario["Objective"] = objective
        ...         reho.single_optimization()

        Yields
        ------
        multiprocessing.pool.Pool or None
            The pool of ``cpu_use`` worker processes, or None when the sub-problems are solved in the
            main process.

        Notes
        -----
        A pool left open until the interpreter exits is destroyed after the modules it relies on, which
        prints an ``Exception ignored in: <function Pool.__del__>`` traceback: the pool is therefore
        never kept beyond the block.
        """
        decomposition = self.method['district-scale'] or self.method['building-scale']
        if self.pool is not None or not (decomposition and self.method['parallel_computation']):
            yield self.pool
            return

        pool = self.pool = mp.Pool(self.cpu_use)
        try:
            yield pool
        except BaseException:
            pool.terminate()
            raise
        else:
            pool.close()
        finally:
            pool.join()
            self.pool = None

    def launch_SP_multiprocessing(self, scenario, Scn_ID, Pareto_ID, epsilon_init, beta, initiation=True, renovation_options=None):
        """
        Solve the sub-problem of every building once, and store the configurations they propose.

        The sub-problems are prepared in the main process by :meth:`prepare_SP_task`, then solved by
        :func:`_solve_SP_task`: in parallel in the pool of :meth:`worker_pool` with
        ``method['parallel_computation']``, otherwise one after the other. The results are stored by
        :meth:`add_df_Results_SP`, and ``feasible_solutions`` is incremented.

        Parameters
        ----------
        scenario : dict
            Scenario of the optimization.
        Scn_ID : str
            Name of the scenario.
        Pareto_ID : int
            Index of the Pareto point.
        epsilon_init : pd.Series or None
            Epsilon constraint of each building, for the initiation at the building scale.
        beta : float or None
            Weight of the secondary objective, for the initiation, see :meth:`get_beta_values`.
        initiation : bool, optional
            Solve the sub-problems of the initiation (:meth:`SP_initiation_execution`) rather than those
            of an iteration (:meth:`SP_execution`). Default is True.
        renovation_options : str, optional
            Elements of the envelope to renovate, e.g. ``'window/facade'``.
        """

        tasks = {h: self.prepare_SP_task(scenario, Scn_ID, Pareto_ID, h, epsilon_init=epsilon_init, beta=beta,
                                         initiation=initiation, renovation_options=renovation_options)
                 for h in self.infrastructure.houses}

        with self.worker_pool() as pool:
            if pool is None:
                collected = {h: _solve_SP_task(task) for h, task in tasks.items()}
            else:
                pending = {h: pool.apply_async(_solve_SP_task, args=(task,)) for h, task in tasks.items()}
                # the results are stored in the main process, once every sub-problem is solved
                collected = {h: result.get() for h, result in pending.items()}

        for h, (df_Results, attr) in collected.items():
            self.add_df_Results_SP(Scn_ID, Pareto_ID, self.iter, h, df_Results, attr)

        self.feasible_solutions += 1  # after each 'round' of SP execution the number of feasible solutions increase
        return

    def prepare_SP_task(self, scenario, Scn_ID, Pareto_ID, h, epsilon_init=None, beta=None, initiation=True, renovation_options=None):
        """
        Assemble the data of the sub-problem of one building, to be solved by :func:`_solve_SP_task`.

        Everything that needs the master problem (splitting the district parameters, reading the dual
        values, setting the beta values) happens here, in the main process. The returned dictionary is
        what is sent to a worker process: it holds only the data of this building.

        Parameters
        ----------
        scenario : dict
            Scenario of the optimization; it is copied, not modified.
        Scn_ID : str
            Name of the scenario.
        Pareto_ID : int
            Index of the Pareto point.
        h : str
            Building, e.g. ``'Building1'``.
        epsilon_init : pandas.Series, optional
            Epsilon constraint of each building, for the initiation at the building scale.
        beta : float, optional
            Weight of the secondary objective for the initiation, see :meth:`get_beta_values`.
        initiation : bool, optional
            Prepare a sub-problem of the initiation rather than of an iteration, which uses the dual
            values of the last master problem. Default is True.
        renovation_options : str, optional
            Elements of the envelope to renovate, e.g. ``'window/facade'``.

        Returns
        -------
        dict
            The building ``h``, ``Scn_ID``, ``Pareto_ID``, and the arguments of
            :class:`~reho.model.sub_problem.SubProblem`: ``infrastructure_SP``, ``buildings_data_SP``,
            ``parameters_SP``, ``set_indexed_SP``, ``local_data``, ``cluster``, ``scenario``, ``method``,
            ``solver``, ``df_fix_Units``, ``fix_units_list`` and, with ``use_facades`` or ``use_pv_orientation``,
            ``qbuildings_data``.

        Raises
        ------
        ValueError
            If more than one epsilon constraint is given for the initiation at the building scale.
        """
        scenario = copy.deepcopy(scenario)

        if initiation:
            self.logger.info('INITIATE HOUSE: %s', h)

            # find district structure and parameter for one single building
            buildings_data_SP, parameters_SP, set_indexed_SP = self.split_parameter_sets_per_building(h)

            # epsilon constraints on districts may lead to infeasibilities on building level -> apply them in MP only
            if epsilon_init is not None and self.method['building-scale']:
                emoo = scenario["EMOO"].copy()
                for key in ["EMOO_grid", "EMOO_GU_demand", "EMOO_GU_supply"]:
                    emoo.pop(key)
                if len(emoo) == 1:
                    scenario["EMOO"][list(emoo.keys())[0]] = epsilon_init.loc[h]
                else:
                    raise ValueError(
                        f"Expected a single epsilon constraint to initialise the decomposition of building {h}, "
                        f"got {sorted(emoo)}. Constrain one objective at a time."
                    )
            elif not self.method['building-scale']:
                scenario, beta_list = self.get_beta_values(scenario, beta)
                parameters_SP['beta_duals'] = beta_list
        else:
            self.logger.info('ITERATE HOUSE: %s, iteration: %s', h, self.iter)

            # Give dual variables to Subproblem
            pi = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter - 1, h, 'pi').reorder_levels(['Layer', 'Period', 'Time'])
            pi_GWP = self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter - 1, h, 'pi_GWP').reorder_levels(['Layer', 'Period', 'Time'])
            pi_h = pd.concat([pi], keys=[h], names=['Building']).reorder_levels(['Building', 'Layer', 'Period', 'Time'])

            parameters_SP = dict()
            if self.method['actors_problem']:
                parameters_SP.update(
                    actors.get_actor_parameters(self.scenario, self.set_indexed, self.results_MP, Scn_ID, Pareto_ID,
                                                self.iter, h))
            # find district structure, objective, beta and parameter for one single building
            buildings_data_SP, parameters_SP, set_indexed_SP = self.split_parameter_sets_per_building(h, parameters_SP)

            parameters_SP['Cost_supply_network'] = pi
            parameters_SP['Cost_demand_network'] = pi * (1 - 1e-9)
            parameters_SP['Cost_supply'] = pi_h
            parameters_SP['Cost_demand'] = pi_h * (1 - 1e-9)
            parameters_SP['GWP_supply'] = pi_GWP
            parameters_SP['GWP_demand'] = pi_GWP.mul(0)

            beta_series = - self.get_dual_values_SPs(Scn_ID, Pareto_ID, self.iter - 1, h, 'beta')
            scenario, beta_list = self.get_beta_values(scenario, beta_series)
            if "beta_duals" in parameters_SP:
                for key in parameters_SP["beta_duals"].index.get_level_values("Obj_fct").unique():
                    beta_list.loc[key] = parameters_SP["beta_duals"].xs(key).xs(h)[0]
            parameters_SP['beta_duals'] = beta_list

        if renovation_options is not None:
            buildings_data_SP[h]['U_h'], parameters_SP['Costs_ins'], parameters_SP['GWP_ins'] = renovation.renovation_cost_co2(buildings_data_SP[h], self.local_data, renovation_options)
            buildings_data_SP[h]["renovation"] = renovation_options

        # ship only the location data the sub-problem consumes (Irr_yearly is only needed with use_pv_orientation)
        local_data_SP = dict(self.local_data)
        if not (self.method['use_pv_orientation'] or self.method['use_facades']):
            local_data_SP.pop('Irr_yearly', None)
        local_data_SP.pop('sun_azimuth', None)
        local_data_SP.pop('df_renovation', None)
        local_data_SP.pop('df_renovation_targets', None)

        task = {'h': h, 'Scn_ID': Scn_ID, 'Pareto_ID': Pareto_ID,
                'infrastructure_SP': self.infrastructure_SP[h],
                'buildings_data_SP': buildings_data_SP,
                'parameters_SP': parameters_SP,
                'set_indexed_SP': set_indexed_SP,
                'local_data': local_data_SP,
                'cluster': self.cluster,
                'scenario': scenario,
                'method': self.method,
                'solver': self.solver,
                'df_fix_Units': self.df_fix_Units if self.method['fix_units'] else None,
                'fix_units_list': list(self.fix_units_list)}
        if self.method['use_facades'] or self.method['use_pv_orientation']:
            task['qbuildings_data'] = self.qbuildings_data
        return task

    def SP_initiation_execution(self, scenario, Scn_ID=0, Pareto_ID=1, h=None, epsilon_init=None, beta=None, renovation_options=None):
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
        task = self.prepare_SP_task(scenario, Scn_ID, Pareto_ID, h, epsilon_init=epsilon_init, beta=beta,
                                    initiation=True, renovation_options=renovation_options)
        return _solve_SP_task(task)

    def _build_MP_model(self, read_DHN=False):
        """Open an AMPL session and read the master-problem model and its district units.

        Parameters
        ----------
        read_DHN : bool, optional
            Also read ``dhn.mod``, which sizes the district-heating pipes.

        Returns
        -------
        amplpy.AMPL
            A session holding the master problem, its technologies and the
            typical-period frequencies of the current cluster.

        See also
        --------
        reho.model.ampl_interface.DISTRICT_UNIT_MODELS : registry of district technology model files.
        """
        ampl_MP = create_ampl_session(
            self.solver,
            print_logs=self.method['print_logs'],
            options={'rel_boundtol': 1e-12},
            evals=('option show_boundtol 0;', 'option abs_boundtol 1e-10;'),
        )
        ampl_MP.read('master_problem.mod')

        district_units = self.infrastructure.UnitsOfDistrict

        # The district battery reuses the building-scale model file.
        if "Battery_district" in district_units:
            ampl_MP.cd(path_to_units)
            ampl_MP.read('battery.mod')

        ampl_MP.cd(path_to_district_units)
        if "Mobility" in self.infrastructure.UnitsOfLayer:
            ampl_MP.read('mobility.mod')
        read_unit_models(ampl_MP, DISTRICT_UNIT_MODELS, district_units)

        if read_DHN:
            ampl_MP.cd(path_to_district_units)
            ampl_MP.read('dhn.mod')

        if self.method["actors_problem"]:
            ampl_MP.cd(path_to_ampl_model)
            ampl_MP.read('actors_problem.mod')
            if "EV_district" in district_units:
                ampl_MP.read('actors_mobility.mod')  # needs the parameters of the mobility sector

        if self.method["interperiod_storage"]:
            read_unit_models(ampl_MP, INTERPERIOD_DISTRICT_UNIT_MODELS, district_units)

        ampl_MP.cd(os.path.join(path_to_clustering, self.local_data['File_ID']))
        ampl_MP.readData('frequency.csv')
        ampl_MP.readData('index.csv')
        ampl_MP.cd(path_to_ampl_model)
        return ampl_MP

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

        ampl_MP = self._build_MP_model(read_DHN)

        # -------------------------------------------------------------------------------------------------------------
        # Set Parameters, only bool to choose if including all solutions found also from other Pareto_IDs
        # ------------------------------------------------------------------------------------------------------------
        # collect data
        df_Performance = self.return_combined_SP_results(self.results_SP, 'df_Performance')
        df_Performance = df_Performance.drop(index='Network', level='Hub').groupby(level=['Scn_ID', 'Pareto_ID', 'FeasibleSolution', 'Hub']).head(1).droplevel('Hub')  # select current Scn_ID and Pareto_ID
        df_Grid_t = np.round(self.return_combined_SP_results(self.results_SP, 'df_Grid_t'), 6)
        df_Buildings = self.return_combined_SP_results(self.results_SP, 'df_Buildings')
        df_Buildings = df_Buildings[df_Buildings.index.get_level_values('house') == df_Buildings.index.get_level_values('Hub')].droplevel('Hub')
        df_Unit_t = self.return_combined_SP_results(self.results_SP, 'df_Unit_t').xs("Electricity", level="Layer")

        # apply slicing or level-dropping uniformly to all three DataFrames
        dfs = [df_Performance, df_Grid_t, df_Buildings, df_Unit_t]
        if self.method['include_all_solutions']:
            dfs = [df.droplevel(['Scn_ID', 'Pareto_ID']) for df in dfs]
        else:
            dfs = [df.xs((Scn_ID, Pareto_ID), level=('Scn_ID', 'Pareto_ID')) for df in dfs]
        df_Performance, df_Grid_t, df_Buildings, df_Unit_t = dfs

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

        MP_parameters['df_grid'] = df_Grid_t[['Grid_demand', 'Grid_supply']]
        MP_parameters['ERA'] = np.asarray([self.buildings_data[house]['ERA'] for house in self.buildings_data.keys()])
        MP_parameters['Area_tot'] = self.ERA

        if "Mobility" in self.infrastructure.UnitsOfLayer:
            mobility_parameters = mobility.generate_mobility_parameters(self.cluster, self.parameters, self.infrastructure, self.modal_split)
            for param in mobility_parameters:
                MP_parameters[param] = mobility_parameters[param]

        if read_DHN:
            has_dhn_temperatures = 'T_DHN_supply_cst' in self.parameters and 'T_DHN_return_cst' in self.parameters
            if has_dhn_temperatures and not self.method["DHN_CO2"]:
                dT = np.array(self.parameters["T_DHN_supply_cst"] - self.parameters["T_DHN_return_cst"])
                MP_parameters['delta_enthalpy'] = dT.mean() * CP_WATER
                MP_parameters['density'] = 1000  # water [kg/m3]

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

            df_PV_t = pd.DataFrame()
            for bui in self.infrastructure.houses:
                df_PV_t = pd.concat([df_PV_t, df_Unit_t.xs("PV_" + bui, level="Unit")])
            MP_parameters["PV_prod"] = df_PV_t["Units_supply"].droplevel(["Iter"])

        if self.method['renovation'] is not None or "U_h" in self.parameters:
            MP_parameters["Uh"] = pd.DataFrame.from_dict({house: self.buildings_data[house]['U_h'] for house in self.buildings_data.keys()}, orient="Index").rename(columns={0: "Uh"})
            MP_parameters["Uh_ins"] = df_Buildings[["U_h"]].rename(columns={"U_h": "Uh_ins"})
            if "U_h" in self.parameters:
                for row in self.parameters["U_h"].index:
                    mask = MP_parameters["Uh_ins"].index.get_level_values(1) == row
                    MP_parameters["Uh_ins"].loc[mask, "Uh_ins"] = self.parameters["U_h"].loc[row][0]

        if ("Heat" in self.infrastructure.grids
                and "HeatPump_Geothermal_district" in self.infrastructure.UnitsOfDistrict
                and 'T_DHN_supply_cst' in self.parameters and 'T_DHN_return_cst' in self.parameters):
            T_DHN_mean = (self.parameters["T_DHN_supply_cst"] + self.parameters["T_DHN_return_cst"]) / 2
            MP_set_indexed["HP_Tsupply"] = np.array([T_DHN_mean.mean()])
            MP_set_indexed["HP_Tsink"] = np.array([T_DHN_mean.mean()])
        if read_DHN:
            MP_set_indexed["House_ID"] = np.array([int(s.replace("Building", "")) for s in list(self.infrastructure.houses.keys())])

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
                name = u['Unit']
                MP_set_indexed['Units'] = np.append(MP_set_indexed['Units'], [name])
                if not u['UnitOfType'] in MP_set_indexed['UnitTypes']:
                    MP_set_indexed['UnitTypes'] = np.append(MP_set_indexed['UnitTypes'], u['UnitOfType'])
                    MP_set_indexed['UnitsOfType'][u['UnitOfType']] = np.array([])
                MP_set_indexed['UnitsOfType'][u['UnitOfType']] = np.append(MP_set_indexed['UnitsOfType'][u['UnitOfType']], [name])

        if "i_rate" in self.parameters.keys():
            MP_parameters["i_rate"] = self.parameters["i_rate"][0]

        # ---------------------------------------------------------------------------------------------------------------
        # give values to ampl
        # ---------------------------------------------------------------------------------------------------------------

        for s in MP_set_indexed:
            if isinstance(MP_set_indexed[s], np.ndarray):
                ampl_MP.getSet(str(s)).setValues(MP_set_indexed[s])
            elif isinstance(MP_set_indexed[s], dict):
                for i, instance in ampl_MP.getSet(str(s)):
                    instance.setValues(MP_set_indexed[s][i[0]])
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
                    ampl_MP.getVariable('Units_Use').get(str(i[0])).fix(0)
            for u in enforce_units:
                if u in i:
                    ampl_MP.getVariable('Units_Use').get(str(i[0])).fix(1)

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

            elif isinstance(MP_parameters[i], dict):
                Para = ampl_MP.getParameter(i)
                Para.setValues(MP_parameters[i])

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

        if self.method['fix_units']:
            fix_unit_sizes(ampl_MP, self.df_fix_Units, self.infrastructure.UnitsOfDistrict, self.fix_units_list or None)

        # Solve ampl_MP
        ampl_MP.solve()

        df_Results_MP = write_results.get_df_Results_from_MP(ampl_MP, binary, self.method, self.infrastructure, read_DHN=read_DHN, scenario=scenario)
        self.logger.info(str(ampl_MP.getCurrentObjective().getValues().toPandas()))

        df = self.get_solver_attributes(Scn_ID, Pareto_ID, ampl_MP)
        self.add_df_Results_MP(Scn_ID, Pareto_ID, self.iter, df_Results_MP, df)
        exitcode = exitcode_from_ampl(ampl_MP)

        del ampl_MP
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
        if self.method['renovation'] is not None:
            for option in self.method['renovation']:
                self.launch_SP_multiprocessing(scenario, Scn_ID, Pareto_ID, None, None, initiation=False, renovation_options=option)


    def SP_execution(self, scenario, Scn_ID, Pareto_ID, h, renovation_options=None):
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
        task = self.prepare_SP_task(scenario, Scn_ID, Pareto_ID, h, initiation=False, renovation_options=renovation_options)
        return _solve_SP_task(task)

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
        """
        Set the objective function and the constraints of the master problem.

        The epsilon constraints and the optional constraints of the master problem are dropped, then
        restored as the scenario requires: the epsilon constraints of ``scenario['EMOO']`` with their
        values, and the constraints of ``scenario['specific']`` that belong to the master problem. The
        objective ``scenario['Objective']`` is the only one kept.

        Parameters
        ----------
        ampl : amplpy.AMPL
            Session holding the master problem.
        scenario : dict
            Scenario of the optimization.

        Returns
        -------
        amplpy.AMPL
            The same session.
        """
        list_constraints = ['EMOO_CAPEX_constraint', 'EMOO_OPEX_constraint', 'EMOO_GWP_constraint', 'EMOO_TOTEX_constraint', 'disallow_exchanges_1', 'disallow_exchanges_2', 'EMOO_elec_export_constraint'] + self.lists_MP["list_constraints_MP"]

        for cst in list_constraints:
            try:
                ampl.getConstraint(cst).drop()
            except Exception:
                # Constraints belonging to technologies absent from this problem are
                # simply not declared in the model: there is nothing to drop.
                self.logger.debug("Constraint %r is not part of the master problem, not dropped.", cst)

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
        """
        Weights of the objectives in the objective function of the sub-problems.

        In the decomposition, a sub-problem minimizes ``SP_obj_fct``, a weighted sum of its OPEX, CAPEX
        and GWP. The objective of the scenario gets a weight of 1 (OPEX and CAPEX both, for TOTEX), the
        others a negligible weight of 1e-6. A number ``beta`` is the weight of a secondary objective,
        which diversifies the configurations proposed during the initiation: the objective constrained
        by the epsilon constraint of the scenario if there is one; otherwise CAPEX when minimizing OPEX,
        and OPEX for the other objectives. Finally, the epsilon constraints on the objectives are removed
        from the scenario returned (see :meth:`remove_emoo_constraints`); the scenario given is left
        unchanged.

        Parameters
        ----------
        scenario : dict
            Scenario of the optimization.
        beta : float or int or pd.Series or None, optional
            Weight of the secondary objective (ignored at the building scale), or directly the weight of
            each objective as a Series indexed by objective, where zeros are replaced by 1e-6.

        Returns
        -------
        scenario : dict
            Scenario of the sub-problem, with the objective ``SP_obj_fct``.
        beta_list : pd.Series
            Weight of each objective, sent to AMPL as ``beta_duals``.

        Raises
        ------
        TypeError
            If ``beta`` is of another type.
        ValueError
            If the scenario has epsilon constraints on more than one objective.
        """
        scenario = scenario.copy()
        # The epsilon constraints are removed below: without a copy of their dictionary, the next
        # buildings solved in the same process would no longer see them.
        scenario['EMOO'] = dict(scenario.get('EMOO', {}))
        objective = scenario['Objective']
        if isinstance(beta, (float, int, type(None))):
            index = list(self.flags.keys())  # list of objective function
            beta_list = pd.Series(np.zeros(len(index)), index=index) + 1e-6  # default penalty on other objectives
        elif isinstance(beta, pd.Series):
            beta_list = beta
            beta_list = beta_list.replace(0, 1e-6)
        else:
            raise TypeError(f"beta must be a float, an int, a pandas Series or None, got {type(beta).__name__}.")

        # select objective using beta values
        if objective in ['TOTEX', 'TOTEX_actor']:
            beta_list[['CAPEX', 'OPEX']] = 1
        else:
            beta_list[objective] = 1
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
                if objective == "OPEX":
                    beta_list["CAPEX"] = beta
                else:
                    beta_list["OPEX"] = beta
            elif len(emoo) > 1:
                raise ValueError(
                    f"Expected at most one objective-level epsilon constraint, got {sorted(emoo)}. "
                    "Constrain one objective at a time."
                )

        scenario = self.remove_emoo_constraints(scenario)
        return scenario, beta_list

    @staticmethod
    def remove_emoo_constraints(scenario):
        """
        Remove the epsilon constraints on the objectives from a scenario.

        These are ``EMOO_CAPEX``, ``EMOO_OPEX``, ``EMOO_GWP``, ``EMOO_TOTEX``, ``EMOO_elec_export`` and
        ``EMOO_EV``; the other epsilon constraints, such as ``EMOO_grid``, are kept.

        Parameters
        ----------
        scenario : dict
            Scenario, modified in place.

        Returns
        -------
        dict
            The same scenario.
        """

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
        df = _sp_solver_attributes(Scn_ID, Pareto_ID, ampl)

        if not self.method['district-scale']:  # for decompose method, stored in solver_attributes_MP or _SP
            self.solver_attributes = pd.concat([self.solver_attributes, df])

        return df

    def sort_decomp_result(self, Scn_ID, idxvalues):
        """
        Renumber the Pareto points of the decomposition results, in a given order.

        Used by :meth:`~reho.model.reho.REHO.generate_pareto_curve` to order the points of a Pareto
        front: point ``idxvalues[i]`` becomes point ``i + 1`` in ``results_SP`` and ``results_MP``. The
        records ``number_SP_solutions``, ``number_MP_solutions``, ``solver_attributes_SP``,
        ``solver_attributes_MP`` and ``reduced_costs`` are sorted by ``Pareto_ID``, whose values are left
        unchanged.

        Parameters
        ----------
        Scn_ID : str
            Name of the scenario.
        idxvalues : array-like
            Current IDs of the Pareto points, in the new order.
        """

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
        """
        Store the results of a sub-problem, and record the solution.

        The results are stored in ``results_SP[Scn_ID][Pareto_ID][iter][feasible_solutions][house]``,
        the solver statistics are appended to ``solver_attributes_SP``, and the solution to
        ``number_SP_solutions``.

        Parameters
        ----------
        Scn_ID : str
            Name of the scenario.
        Pareto_ID : int
            Index of the Pareto point.
        iter : int
            Iteration of the master problem.
        house : str
            Building of the sub-problem.
        df_Results : dict
            Result DataFrames of the sub-problem, see
            :func:`~reho.model.postprocessing.write_results.get_df_Results_from_SP`.
        attr : pd.DataFrame
            Solver statistics, see :meth:`get_solver_attributes`.
        """
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
        """
        Store the results of the master problem, and update the record of the solutions.

        The results are stored in ``results_MP[Scn_ID][Pareto_ID][iter]``, the solver statistics are
        appended to ``solver_attributes_MP``, and ``number_MP_solutions`` is recomputed from
        ``number_SP_solutions``.

        Parameters
        ----------
        Scn_ID : str
            Name of the scenario.
        Pareto_ID : int
            Index of the Pareto point.
        iter : int
            Iteration of the master problem.
        df_Results : dict
            Result DataFrames of the master problem, see
            :func:`~reho.model.postprocessing.write_results.get_df_Results_from_MP`.
        attr : pd.DataFrame
            Solver statistics, see :meth:`get_solver_attributes`.
        """

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

    def split_parameter_sets_per_building(self, h, parameters_SP=None, set_indexed_SP=None):
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
        if parameters_SP == None:
            parameters_SP = dict()
        if set_indexed_SP == None:
            set_indexed_SP = dict()
        ID = np.where(h == self.infrastructure.House)[0][0]
        buildings_data_SP = {h: self.buildings_data[h].copy()}

        for key in self.parameters:
            if key not in self.lists_MP["list_parameters_MP"]:
                if isinstance(self.parameters[key], (int, float)):
                    parameters_SP[key] = self.parameters[key]
                elif isinstance(self.parameters[key], pd.DataFrame):
                    if "Hub" in self.parameters[key].index.names:
                        if h in self.parameters[key].index.get_level_values("Hub"):
                            if isinstance(self.parameters[key].index, pd.MultiIndex):
                                parameters_SP[key] = self.parameters[key].xs(h, level="Hub", drop_level=False)
                            else:
                                parameters_SP[key] = self.parameters[key].loc[h].values[0]
                    else:
                        parameters_SP[key] = self.parameters[key]
                else:
                    if len(self.parameters[key]) == len(self.buildings_data):
                        # One value per building: positional for arrays and lists, label-based for pandas.
                        try:
                            parameters_SP[key] = self.parameters[key][ID]
                        except (KeyError, IndexError, TypeError):
                            parameters_SP[key] = self.parameters[key].iloc[[ID]]
                    else:
                        # One time series per building, stored as a single flat array.
                        try:
                            timesteps = int(len(self.parameters[key]) / len(self.buildings_data))
                            profile_building_x = self.parameters[key].reshape(len(self.buildings_data), timesteps)
                            parameters_SP[key] = profile_building_x[ID]
                        except (AttributeError, ValueError):
                            # Not reshapeable: a single value shared by every building.
                            parameters_SP[key] = self.parameters[key]

        for key in self.set_indexed:
            if key not in self.lists_MP["list_set_indexed_MP"]:
                set_indexed_SP[key] = self.set_indexed[key]

        return buildings_data_SP, parameters_SP, set_indexed_SP

    def build_infrastructure_SP(self):
        """
        Build the infrastructure of the sub-problem of each building.

        Each building gets its own :class:`~reho.model.infrastructure.Infrastructure`, restricted to
        the building units, stored in ``infrastructure_SP[building]``. The maximum size (``Units_Fmax``)
        and specific investment cost (``Cost_inv2``) of its units are copied from the infrastructure of
        the district, which holds the values specific to each building.
        """
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
        """
        Concatenate one result DataFrame over every sub-problem solved.

        Parameters
        ----------
        df_Results : dict
            Results of the sub-problems, nested as
            ``df_Results[Scn_ID][Pareto_ID][Iter][FeasibleSolution][house]``, i.e. ``results_SP``.
        df_name : str
            Name of the DataFrame to gather, e.g. ``'df_Unit'``.

        Returns
        -------
        pd.DataFrame
            The DataFrames stacked, with the index levels ``Scn_ID``, ``Pareto_ID``, ``Iter``,
            ``FeasibleSolution`` and ``house`` prepended, sorted by index.
        """

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
