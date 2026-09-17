"""User-facing entry point of REHO.

:class:`REHO` assembles the pieces: it builds the optimization problem from the
buildings, units, grids and scenario given by the user, runs it (single
optimization or Pareto front, compact formulation or Dantzig-Wolfe
decomposition), computes the key performance indicators and saves the results.

Examples
--------
>>> from reho import REHO, QBuildingsReader, initialize_grids, initialize_units
>>> reader = QBuildingsReader()
>>> qbuildings_data = reader.read_csv("data/buildings.csv", nb_buildings=2)
>>> grids = initialize_grids()
>>> units = initialize_units({"exclude_units": []}, grids)
>>> reho = REHO(qbuildings_data, units, grids, scenario={"Objective": "TOTEX"},
...             method={"building-scale": True})
>>> reho.single_optimization()
>>> reho.save_results(format=["xlsx", "pickle"], filename="my_run")

See also
--------
reho.model.master_problem.MasterProblem : decomposition machinery this class inherits from.
reho.model.options : the ``method``, ``scenario`` and ``DW_params`` dictionaries.
"""

import gc
import multiprocessing as mp
import os
import pickle
import warnings
from pathlib import Path  # noqa: F401  (re-exported for scripts doing `from reho.model.reho import *`)

import numpy as np
import pandas as pd

import reho.model.infrastructure as infrastructure
import reho.model.postprocessing.write_results as write_results
from reho.model.master_problem import CP_WATER, DELTA_H_CO2, DEFAULT_DHN_DELTA_T, MasterProblem
from reho.model.options import initialize_default_scenario
from reho.model.postprocessing.KPIs import calculate_KPIs
from reho.model.preprocessing.QBuildings import QBuildingsReader
from reho.model.sub_problem import SubProblem, exitcode_from_ampl, initialize_default_methods
from reho.paths import load_ampl_environment

#: Public surface of ``from reho.model.reho import *``. Prefer explicit imports
#: (``from reho import REHO, QBuildingsReader``); this list exists so that the run
#: scripts written against earlier REHO versions keep working unchanged.
__all__ = [
    "REHO",
    "QBuildingsReader",
    "SubProblem",
    "MasterProblem",
    "infrastructure",
    "initialize_default_methods",
    "initialize_default_scenario",
    "exitcode_from_ampl",
    "Path",
    "np",
    "pd",
]

# Make AMPL_PATH available to every problem built from this module, as importing
# reho.paths used to do implicitly.
load_ampl_environment()

#: Largest sheet an xlsx file holds; larger result tables are left out of the xlsx export.
XLSX_MAX_ROWS = 1_048_576
XLSX_MAX_COLUMNS = 16_384


class REHO(MasterProblem):
    """
    Performs the single or multi-objective optimization.

    Parameters
    ----------
    scenario : dict, optional
        Objective function, epsilon constraints and units to enforce or exclude.
        Missing keys are completed with :data:`reho.model.options.DEFAULT_SCENARIO`.
        Add ``nPareto`` to request a Pareto front, see :meth:`generate_pareto_curve`.
    solver : str, optional
        Solver used by AMPL. Default is ``'highs'``, which ships with REHO.

    Other Parameters
    ----------------
    qbuildings_data, units, grids, parameters, set_indexed, cluster, method, DW_params
        Inherited from :class:`~reho.model.master_problem.MasterProblem`.

    Attributes
    ----------
    results : dict
        ``results[scenario_name][pareto_id]`` -> dict of result DataFrames.
        Filled by :meth:`single_optimization` and :meth:`generate_pareto_curve`.

    See also
    --------
    reho.model.master_problem.MasterProblem
    reho.model.options.initialize_default_scenario
    """

    def __init__(self, qbuildings_data, units, grids, parameters=None, set_indexed=None, cluster=None, method=None, scenario=None, solver="highs",
                 DW_params=None):

        super().__init__(qbuildings_data, units, grids, parameters, set_indexed, cluster, method, solver, DW_params)
        self.initialize_optimization_tracking_attributes()

        self.scenario = initialize_default_scenario(scenario)
        if 'nPareto' in self.scenario:
            self.nPareto = self.scenario['nPareto']  # intermediate points
            self.total_Pareto = self.nPareto * 2 + 2  # both objectives, plus the two boundaries
        else:
            self.nPareto = 1  # no curve, single execution
            self.total_Pareto = 1

        self.results = dict()

        self.solver_attributes = pd.DataFrame()
        self.epsilon_constraints = {}

    def build_sub_problem(self, scenario=None, infrastructure=None, buildings_data=None, parameters=None, set_indexed=None):
        """Instantiate a :class:`~reho.model.sub_problem.SubProblem` with this run's context.

        Centralises the choice of passing ``qbuildings_data`` along: the roof and
        facade geometries are only needed — and only available — when the PV
        orientation or facade methods are enabled.

        Parameters
        ----------
        scenario, infrastructure, buildings_data, parameters, set_indexed : optional
            Override the corresponding attribute of ``self``, which is what the
            decomposition does when it solves one building at a time.

        Returns
        -------
        reho.model.sub_problem.SubProblem
        """
        needs_geometry = self.method['use_facades'] or self.method['use_pv_orientation']
        return SubProblem(
            self.infrastructure if infrastructure is None else infrastructure,
            self.buildings_data if buildings_data is None else buildings_data,
            self.local_data,
            self.parameters if parameters is None else parameters,
            self.set_indexed if set_indexed is None else set_indexed,
            self.cluster,
            self.scenario if scenario is None else scenario,
            self.method,
            self.solver,
            self.qbuildings_data if needs_geometry else None,
        )

    def fix_unit_sizes(self, ampl, house=None):
        """Fix the installed capacities to the values of ``self.df_fix_Units``.

        Used by ``method['fix_units']`` to evaluate the operation of a design that
        was decided elsewhere, for instance the optimum of a previous scenario.

        Parameters
        ----------
        ampl : amplpy.AMPL
            A built, not yet solved session.
        house : str, optional
            Restrict the fixing to the units of that building. Default is all units.

        Notes
        -----
        PV capacities are relaxed by 1e-9 because the AMPL model bounds the panel
        area by the available roof area; fixing the two to the exact same value
        makes the problem infeasible on rounding alone.
        """
        units = self.df_fix_Units.index
        if house is not None:
            units = units[units.str.contains(str(house))]

        for unit in units:
            is_pv = ('PV' in unit) if house is None else (unit == 'PV_' + str(house))
            multiplier = self.df_fix_Units.Units_Mult.loc[unit]
            ampl.getVariable('Units_Mult').get(unit).fix(multiplier * (1 - 1e-9) if is_pv else multiplier)
            ampl.getVariable('Units_Use').get(unit).fix(float(self.df_fix_Units.Units_Use.loc[unit]))

    def single_optimization(self, Pareto_ID=0):
        """Run one optimization and store its results under ``self.results``.

        The formulation follows ``method``: Dantzig-Wolfe decomposition when
        ``building-scale`` or ``district-scale`` is set, compact formulation
        otherwise.

        Parameters
        ----------
        Pareto_ID : int, optional
            Index under which to store the results. Default is 0.

        Raises
        ------
        RuntimeError
            If the problem is infeasible.
        """
        Scn_ID = self.scenario['name']
        if self.method['fix_units'] and self.df_fix_Units.empty:
            warnings.warn("fix_units=True but df_fix_Units is empty - no units will be fixed. "
                          "Assign df_fix_Units before calling single_optimization.")

        if self.method['district-scale'] or self.method['building-scale']:  # decomposition formulation
            ampl, exitcode = self.execute_dantzig_wolfe_decomposition(self.scenario, Scn_ID, Pareto_ID=Pareto_ID)
        else:  # compact formulation
            ampl = self.build_sub_problem().build_model_without_solving()
            if self.method['fix_units']:
                self.fix_unit_sizes(ampl)
            ampl.solve()
            exitcode = exitcode_from_ampl(ampl)

        self.add_df_Results(ampl, Scn_ID, Pareto_ID, self.scenario)
        self.get_KPIs(Scn_ID, Pareto_ID=Pareto_ID)

        gc.collect()  # free memory
        del ampl
        if exitcode == 'infeasible':
            raise RuntimeError(
                f"Scenario {Scn_ID!r} (Pareto point {Pareto_ID}) is infeasible. "
                "Check that the available units can supply every end-use demand, and that the "
                "network capacities (Network_ext) and epsilon constraints leave a feasible region."
            )

    def execute_dantzig_wolfe_decomposition(self, scenario, Scn_ID, Pareto_ID=0, epsilon_init=None, read_DHN=False):
        """Solve a scenario with the Dantzig-Wolfe decomposition.

        1. Initiation: the sub-problem of each building is solved
           (:meth:`~reho.model.master_problem.MasterProblem.initiate_decomposition`), and a first
           master problem combines the configurations they propose.
        2. Iterations: the sub-problems are solved with the dual values of the master problem
           (:meth:`~reho.model.master_problem.MasterProblem.SP_iteration`), then the master
           problem again (:meth:`~reho.model.master_problem.MasterProblem.MP_iteration`), until
           :meth:`~reho.model.master_problem.MasterProblem.check_Termination_criteria` is met,
           from the fourth iteration on, or the iteration counter reaches
           ``DW_params['max_iter'] - 1``.
        3. Finalization: a last master problem, with binary variables, selects exactly one
           configuration per building.

        The sub-problems are solved in a pool of ``cpu_use`` processes.

        Parameters
        ----------
        scenario : dict
            Scenario of the optimization.
        Scn_ID : str
            Name of the scenario, under which the results are stored.
        Pareto_ID : int, optional
            Index of the Pareto point. Default is 0.
        epsilon_init : pandas.Series, optional
            Epsilon constraint of each building, for the initiation at the building scale.
        read_DHN : bool, optional
            Include the district heating network in the master problem. Default is False.

        Returns
        -------
        tuple
            ``(None, None)``, in place of the AMPL session and exit code of the compact formulation:
            the results are stored in ``results_SP`` and ``results_MP``.
        """

        # Initiation
        self.pool = mp.Pool(self.cpu_use)
        self.iter = 0  # new scenario has to start at iter = 0
        scenario, SP_scenario, SP_scenario_init = self.select_SP_obj_decomposition(scenario)

        self.logger.info('INITIATION, Iter:' + str(self.iter) + ' Pareto_ID: ' + str(Pareto_ID))
        self.initiate_decomposition(SP_scenario_init, Scn_ID=Scn_ID, Pareto_ID=Pareto_ID, epsilon_init=epsilon_init)
        self.logger.info('MASTER INITIATION, Iter:' + str(self.iter))
        self.MP_iteration(scenario, Scn_ID=Scn_ID, binary=False, Pareto_ID=Pareto_ID, read_DHN=read_DHN)

        # Iteration
        while self.iter < self.DW_params['max_iter'] - 1:  # last iteration is used to run the binary MP.
            self.iter += 1
            self.logger.info('SUB PROBLEM ITERATION, Iter:' + str(self.iter) + ' Pareto_ID: ' + str(Pareto_ID))
            self.SP_iteration(SP_scenario, Scn_ID=Scn_ID, Pareto_ID=Pareto_ID)
            self.logger.info('MASTER ITERATION, Iter:' + str(self.iter) + ' Pareto_ID: ' + str(Pareto_ID))
            self.MP_iteration(scenario, Scn_ID=Scn_ID, binary=False, Pareto_ID=Pareto_ID, read_DHN=read_DHN)

            if self.check_Termination_criteria(SP_scenario, Scn_ID=Scn_ID, Pareto_ID=Pareto_ID) and (self.iter > 3):
                break

        # Finalization
        self.logger.info(self.stopping_criteria)
        self.iter += 1
        self.logger.info('LAST MASTER ITERATION, Iter:' + str(self.iter) + ' Pareto_ID: ' + str(Pareto_ID))
        self.MP_iteration(scenario, Scn_ID=Scn_ID, binary=True, Pareto_ID=Pareto_ID, read_DHN=read_DHN)
        self.pool.close()
        self.pool.join()
        return None, None

    def generate_pareto_curve(self):
        """Compute the Pareto front between the two objectives of the scenario.

        ``scenario['Objective']`` is a pair of objectives among ``'TOTEX'``, ``'CAPEX'``, ``'OPEX'`` and
        ``'GWP'``, and ``scenario['nPareto']`` the number of intermediate points on each side of the front.

        1. The two ends of the front minimize each objective alone.
        2. ``nPareto`` points minimize the second objective, with an epsilon constraint on the first
           one, evenly spread between its values at the two ends.
        3. Unless ``method['switch_off_second_objective']`` is set, ``nPareto`` more points minimize the
           first objective, with an epsilon constraint on the second one.
        4. The points are renumbered from 1, by decreasing OPEX of the district.

        Every point keeps the constraint ``EMOO_grid``, the specific constraints and the units enforced
        or excluded by the scenario. The results and their KPIs are stored in
        ``results[scenario['name']]``, and the values of the epsilon constraints in
        ``epsilon_constraints``.
        """

        Scn_ID = self.scenario['name']

        def get_objectives_values(ampl, objectives, Pareto_ID):

            obj_values = {}
            surfaces = pd.DataFrame.from_dict({bui: self.buildings_data[bui]["ERA"] for bui in self.buildings_data}, orient="index")
            surfaces.columns = ["ERA"]

            def annualized_investment():
                if self.method['building-scale'] or self.method['district-scale']:
                    df_inv = self.results[Scn_ID][Pareto_ID]["df_Performance"]
                    district = (df_inv.Costs_inv.iloc[-1] + df_inv.Costs_rep.iloc[-1]) / self.ERA
                    buildings = df_inv.Costs_inv.iloc[:-1].div(surfaces.ERA) + df_inv.Costs_rep.iloc[:-1].div(surfaces.ERA)
                else:
                    tau = ampl.getParameter('tau').getValues().toList()  # annuality factor
                    df_h = write_results.get_ampl_data(ampl, 'Costs_House_inv', multi_index=False)
                    df1_h = write_results.get_ampl_data(ampl, 'Costs_House_rep', multi_index=False)
                    df = write_results.get_ampl_data(ampl, 'Costs_inv', multi_index=False)
                    df1 = write_results.get_ampl_data(ampl, 'Costs_rep', multi_index=False)
                    # annualized investment costs with replacements
                    district = (df.sum()[0] + df1.sum()[0]) * tau[0] / surfaces.sum()[0]  # for compact formulation
                    buildings = (df_h.Costs_House_inv.div(surfaces.ERA) + df1_h.Costs_House_rep.div(surfaces.ERA)) * tau[0]  # for decomposition formulation
                return district, buildings

            def opex_per_house():
                if self.method['building-scale'] or self.method['district-scale']:
                    df_op = self.results[Scn_ID][Pareto_ID]["df_Performance"]
                    district = df_op.Costs_op.iloc[-1] / self.ERA
                    building = df_op.Costs_op.iloc[:-1].div(surfaces.ERA)
                else:
                    df_h = write_results.get_ampl_data(ampl, 'Costs_House_op', multi_index=False)
                    df = write_results.get_ampl_data(ampl, 'Costs_op', multi_index=False)
                    district = df.sum()[0] / surfaces.sum()[0]  # normalized OPEX CHF/m2, for compact formulation
                    building = df_h.Costs_House_op.div(surfaces.ERA)
                return district, building

            def totex_per_house():
                capex_district, capex_building = annualized_investment()
                opex_district, opex_building = opex_per_house()
                totex_district = capex_district + opex_district
                totex_house = capex_building + opex_building
                return totex_district, totex_house

            def gwp_per_house():
                df_perf = self.results[Scn_ID][Pareto_ID]["df_Performance"]
                df_GWP = (df_perf["GWP_op"] + df_perf["GWP_constr"])
                GWP_district = df_GWP["Network"] / surfaces.sum()[0]
                GWP_house = df_GWP.drop("Network").div(surfaces.ERA)
                return GWP_district, GWP_house

            for i, obj in enumerate(objectives):
                if "CAPEX" == obj:
                    obj_values["district_obj" + str(i + 1)], obj_values["building_obj" + str(i + 1)] = annualized_investment()
                elif "OPEX" == obj:
                    obj_values["district_obj" + str(i + 1)], obj_values["building_obj" + str(i + 1)] = opex_per_house()
                elif "TOTEX" == obj:
                    obj_values["district_obj" + str(i + 1)], obj_values["building_obj" + str(i + 1)] = totex_per_house()
                elif "GWP" == obj:
                    obj_values["district_obj" + str(i + 1)], obj_values["building_obj" + str(i + 1)] = gwp_per_house()

            return obj_values

        def add_constraints_from_self_scenario():
            scenario = {'EMOO': {'EMOO_grid': self.scenario['EMOO']['EMOO_grid']},
                        'specific': self.scenario['specific'],
                        'exclude_units': self.scenario['exclude_units'],
                        'enforce_units': self.scenario['enforce_units'],
                        }
            return scenario

        def find_obj1_lower_bound():
            scenario = add_constraints_from_self_scenario()
            objective1 = self.scenario["Objective"][0]
            scenario['Objective'] = objective1

            if self.method['district-scale']:
                ampl, exitcode = self.execute_dantzig_wolfe_decomposition(scenario, Scn_ID, Pareto_ID=1)
            else:
                reho = self.build_sub_problem(scenario)
                ampl, exitcode = reho.solve_model()

            scenario = {'Objective': objective1}
            self.add_df_Results(ampl, Scn_ID, 1, scenario)
            self.get_KPIs(Scn_ID, Pareto_ID=1)

            obj_values = get_objectives_values(ampl, self.scenario["Objective"], Pareto_ID=1)

            gc.collect()  # free memory
            self.logger.info('The lower bound of the ' + str(objective1) + 'value is: ' + str(obj_values["district_obj1"]))
            return obj_values

        def find_obj2_lower_bound():
            scenario = add_constraints_from_self_scenario()
            objective2 = self.scenario["Objective"][1]
            scenario['Objective'] = objective2

            if not self.method["switch_off_second_objective"]:
                Pareto_ID = self.total_Pareto
            else:
                Pareto_ID = self.nPareto + 2

            if self.method['district-scale']:
                ampl, exitcode = self.execute_dantzig_wolfe_decomposition(scenario, Scn_ID, Pareto_ID=Pareto_ID)
            else:
                reho = self.build_sub_problem(scenario)
                ampl, exitcode = reho.solve_model()

            scenario = {'Objective': objective2}
            self.add_df_Results(ampl, Scn_ID, Pareto_ID, scenario)
            self.get_KPIs(Scn_ID, Pareto_ID=Pareto_ID)

            obj_values = get_objectives_values(ampl, self.scenario["Objective"], Pareto_ID=Pareto_ID)

            gc.collect()  # free memory
            self.logger.info('The upper bound of the ' + str(self.scenario["Objective"][0]) + 'value is: ' + str(obj_values["district_obj1"]))
            return obj_values

        def return_epsilon_init(C_max, C_min, pareto_max, pareto, objective):
            if self.method['building-scale']:
                if objective == self.scenario["Objective"][0]:
                    epsilon_init = (C_max - C_min) / (pareto_max + 1) * (pareto - 1) + C_min
                elif objective == self.scenario["Objective"][1]:
                    epsilon_init = (C_max - C_min) / (pareto_max + 1) * (pareto + 1) + C_min
                else:
                    epsilon_init = None
            else:
                epsilon_init = None
            return epsilon_init

        def sort_pareto_points():

            df = pd.DataFrame()
            for i in self.results[Scn_ID].keys():
                df2 = pd.DataFrame([self.results[Scn_ID][i]["df_Performance"]['Costs_op'].xs("Network")], index=[i])
                df = pd.concat([df, df2])
            df = df.sort_values([0], ascending=False).reset_index()

            new_order_results = {}

            rename_dict = {}
            for n, idx in enumerate(df['index'].values):
                new_order_results[n + 1] = self.results[Scn_ID][idx]
                rename_dict[idx] = n + 1

            self.results[Scn_ID] = new_order_results

            if self.method['district-scale']:
                self.sort_decomp_result(Scn_ID, df['index'].values)

        # Bounds Pareto curve
        obj1_lower_bound = find_obj1_lower_bound()
        obj1_upper_bound = find_obj2_lower_bound()

        obj1_max = obj1_upper_bound["district_obj1"]
        obj1_min = obj1_lower_bound["district_obj1"]
        obj1_house_max = obj1_upper_bound["building_obj1"]
        obj1_house_min = obj1_lower_bound["building_obj1"]

        # Intermediate Pareto points: OPEX optimization with CAPEX constraint
        scenario = add_constraints_from_self_scenario()
        scenario['Objective'] = self.scenario["Objective"][1]
        self.epsilon_constraints['EMOO_obj1'] = np.array([])

        for nParetoIT in range(2, self.nPareto + 2):
            # Computation of the intermediate RES values
            obj1_eps_lim = (obj1_max - obj1_min) / (self.nPareto + 1) * (nParetoIT - 1) + obj1_min
            epsilon_init = return_epsilon_init(obj1_house_max, obj1_house_min, self.nPareto, nParetoIT, self.scenario["Objective"][0])

            if self.scenario["Objective"][0] in ["OPEX", "CAPEX", "TOTEX", "GWP"]:
                scenario['EMOO']['EMOO_' + self.scenario["Objective"][0]] = obj1_eps_lim

            self.epsilon_constraints['EMOO_obj1'] = np.append(self.epsilon_constraints['EMOO_obj1'], obj1_eps_lim)
            self.logger.info('---------------> ' + str(self.scenario["Objective"][0]) + ' LIMIT: ' + str(obj1_eps_lim))

            # Results computation
            if self.method['district-scale']:
                ampl, exitcode = self.execute_dantzig_wolfe_decomposition(scenario, Scn_ID, Pareto_ID=nParetoIT, epsilon_init=epsilon_init)
            else:
                reho = self.build_sub_problem(scenario)
                ampl, exitcode = reho.solve_model()

            self.add_df_Results(ampl, Scn_ID, nParetoIT, scenario)
            self.get_KPIs(Scn_ID, Pareto_ID=nParetoIT)

            del ampl
            gc.collect()  # free memory

        if not self.method['switch_off_second_objective']:

            # Intermediate Pareto points: CAPEX optimization with OPEX constraint
            scenario = add_constraints_from_self_scenario()
            scenario['Objective'] = self.scenario["Objective"][0]
            self.epsilon_constraints['EMOO_obj2'] = np.array([])

            obj2_min = obj1_upper_bound["district_obj2"]
            obj2_max = obj1_lower_bound["district_obj2"]
            obj2_house_min = obj1_upper_bound["building_obj2"]
            obj2_house_max = obj1_lower_bound["building_obj2"]

            for point, nParetoIT in enumerate(range(self.nPareto + 2, self.total_Pareto)):
                # Computation of the intermediate RES values
                obj2_eps_lim = (obj2_max - obj2_min) / (self.nPareto + 1) * (point + 1) + obj2_min
                epsilon_init = return_epsilon_init(obj2_house_max, obj2_house_min, self.nPareto, point, self.scenario["Objective"][1])

                scenario['EMOO']['EMOO_' + self.scenario["Objective"][1]] = obj2_eps_lim

                self.epsilon_constraints['EMOO_obj2'] = np.append(self.epsilon_constraints['EMOO_obj2'], obj2_eps_lim)
                self.logger.info('---------------> ' + str(self.scenario["Objective"][1]) + ' LIMIT: ' + str(obj2_eps_lim))
                # results computation
                if self.method['district-scale']:
                    ampl, exitcode = self.execute_dantzig_wolfe_decomposition(scenario, Scn_ID, Pareto_ID=nParetoIT, epsilon_init=epsilon_init)
                else:
                    reho = self.build_sub_problem(scenario)
                    ampl, exitcode = reho.solve_model()

                self.add_df_Results(ampl, Scn_ID, nParetoIT, scenario)
                self.get_KPIs(Scn_ID, Pareto_ID=nParetoIT)

                del ampl
                gc.collect()  # free memory

        sort_pareto_points()

        self.logger.info(str(obj1_min) + " " + str(obj1_max))

    def get_DHN_costs(self):
        """Size the district-heating pipes and turn their cost into a per-building parameter.

        Runs one building-scale decomposition with the DHN enforced, reads the
        resulting network flow rates and investment, then rewrites
        ``infrastructure.Units_Parameters`` so that the following optimization
        charges each building for its own connection. ``DHN_pipes`` is removed
        from the district units, since it is now accounted for building by building.
        """
        self.pool = mp.Pool(self.cpu_use)
        self.iter = 0  # new scenario has to start at iter = 0
        method = self.method['building-scale']
        self.method['building-scale'] = True
        scenario = self.scenario.copy()
        scenario["specific"] = scenario["specific"] + ["enforce_DHN"]
        scenario_MP, SP_scenario, SP_scenario_init = self.select_SP_obj_decomposition(scenario)

        self.initiate_decomposition(SP_scenario_init, Scn_ID=0, Pareto_ID=0)
        self.MP_iteration(scenario_MP, Scn_ID=0, binary=False, Pareto_ID=0, read_DHN=True)

        if self.method["DHN_CO2"]:
            delta_enthalpy = DELTA_H_CO2  # latent heat of the CO2 carrier
        elif "T_DHN_supply_cst" in self.parameters and "T_DHN_return_cst" in self.parameters:
            dT = np.array(self.parameters["T_DHN_supply_cst"] - self.parameters["T_DHN_return_cst"])
            delta_enthalpy = dT.mean() * CP_WATER
        else:
            delta_enthalpy = DEFAULT_DHN_DELTA_T * CP_WATER

        f = self.feasible_solutions - 1
        heat_flow = self.results_MP[0][0][0]["df_District"]["flowrate_max"] * delta_enthalpy
        dhn_inv = self.results_MP[0][0][0]["df_District"].loc["Network", "DHN_inv"]
        tau = self.results_SP[0][0][0][f]["Building1"]["df_Performance"]["ANN_factor"].iloc[0]
        dhn_invh = dhn_inv / (tau * sum(heat_flow[0:-1]))
        self.infrastructure.Units_Parameters[["Units_Fmax", "Cost_inv2"]] = self.infrastructure.Units_Parameters[["Units_Fmax", "Cost_inv2"]].astype(float)
        for bui in self.infrastructure.houses.keys():
            self.infrastructure.Units_Parameters.loc["DHN_pipes_" + bui, ["Units_Fmax", "Cost_inv2"]] = [heat_flow[bui] * 1.001, dhn_invh]

        self.pool.close()
        self.method['building-scale'] = method
        self.initialize_optimization_tracking_attributes()

        # remove DHN_pipes from district_units since they are considered at building scale later
        district_units = [i for i in self.infrastructure.district_units if i["UnitOfType"] != "DHN_pipes"]
        units = {"building_units": self.infrastructure.units, "district_units": district_units}
        buildings = {"buildings_data": self.buildings_data}
        self.infrastructure = infrastructure.Infrastructure(buildings, units, self.infrastructure.grids)

    def add_df_Results(self, ampl, Scn_ID, Pareto_ID, scenario):
        """Extract the results of an optimization, and store them in ``results[Scn_ID][Pareto_ID]``.

        With the decomposition, the results are assembled from the master problem and the selected
        sub-problems (:meth:`get_df_Results_from_MP_and_SPs`); with the compact formulation, they are
        read from the AMPL session. The metadata of the run are added as ``df_Metadata``.

        Parameters
        ----------
        ampl : amplpy.AMPL or None
            Solved session of the compact formulation; unused with the decomposition.
        Scn_ID : str
            Name of the scenario.
        Pareto_ID : int
            Index of the Pareto point.
        scenario : dict
            Scenario of the optimization.
        """
        if self.method['building-scale'] or self.method['district-scale']:
            df_Results = self.get_df_Results_from_MP_and_SPs(Scn_ID, Pareto_ID)
        else:
            df_Results = write_results.get_df_Results_from_SP(ampl, scenario, self.method, self.buildings_data)
            # self.get_solver_attributes(Scn_ID, Pareto_ID, ampl)

        if Scn_ID not in self.results:
            self.results[Scn_ID] = {}
        if Pareto_ID not in self.results[Scn_ID]:
            self.results[Scn_ID][Pareto_ID] = {}

        self.results[Scn_ID][Pareto_ID] = df_Results
        self.results[Scn_ID][Pareto_ID]["df_Metadata"] = write_results.set_df_metadata(
            self.scenario, self.method, self.cluster, self.parameters,
            data_source=self.qbuildings_data.get('data_source'),
            data_date=self.qbuildings_data.get('data_date'))

    def get_df_Results_from_MP_and_SPs(self, Scn_ID, Pareto_ID):
        """Assemble the results of the decomposition, from the last master problem and the selected sub-problems.

        The configurations selected by the last master problem (``lambda`` = 1) give the results of
        each building. The master problem gives those of the district: its costs and emissions in
        ``df_Performance``, its exchanges with the external grids (hub ``Network`` of ``df_Grid``,
        ``df_Grid_t`` and ``df_Annuals``), and the operation of the district units.

        Parameters
        ----------
        Scn_ID : str
            Name of the scenario.
        Pareto_ID : int
            Index of the Pareto point.

        Returns
        -------
        dict
            Result DataFrames, described in :doc:`/sections/data/output`.
        """

        df_Results = dict()

        # get the indexes of the SPs selected by the last MP
        last_results = self.results_MP[Scn_ID][Pareto_ID][self.iter]
        lambdas = last_results["df_DW"]['lambda']
        MP_selection = lambdas[lambdas >= 0.999].index

        # df_Time
        ids = self.number_SP_solutions.iloc[0]
        df_Time = self.results_SP[ids['Scn_ID']][ids['Pareto_ID']][ids['Iter']][ids['FeasibleSolution']][
            ids['House']]["df_Time"]

        # df_Performance
        df_Performance = self.get_final_SPs_results(MP_selection, 'df_Performance')
        df_Performance = df_Performance.groupby('Hub').sum()

        for column in ["Costs_op", "Costs_inv", "Costs_cft", "GWP_op", "GWP_constr"]:
            df_Performance.loc[:, column] = last_results["df_District"][column]
        df_Performance.loc['Network', 'ANN_factor'] = df_Performance['ANN_factor'].iloc[0]

        if self.method["actors_problem"]:
            features = ['C_op_renters_to_utility', 'C_op_renters_to_owners', 'C_op_utility_to_owners', 'owner_inv',
                        'owner_profit', 'C_rent_fix', 'renter_expense', 'renter_subsidies', 'owner_subsidies', 'Costs_House_yearly']
            df_actor = self.results_MP[Scn_ID][Pareto_ID][self.iter]["df_District"][features]
            df_Performance = pd.concat([df_Performance, df_actor], axis=1)
            df_Results["df_Actors_tariff"] = self.results_MP[Scn_ID][Pareto_ID][self.iter]["df_Actors_tariff"]
            df_Results["df_Actors"] = self.results_MP[Scn_ID][Pareto_ID][self.iter]["df_Actors"]
            df_Results["Samples"] = self.results_MP[Scn_ID][Pareto_ID][self.iter]["Samples"]

        if "is_ins" in self.results_MP[Scn_ID][Pareto_ID][self.iter]["df_District"]:
            df_renovation = self.results_MP[Scn_ID][Pareto_ID][self.iter]["df_District"][['is_ins']]
            df_Performance = pd.concat([df_Performance, df_renovation], axis=1)

        # df_Grid
        df = self.get_final_SPs_results(MP_selection, 'df_Grid')
        df = df.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
        df_Grid = pd.concat([df, last_results["df_Grid"]])

        # df_Grid_t
        df = self.get_final_SPs_results(MP_selection, 'df_Grid_t')
        df = df.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
        df = df.sort_index(level='Hub')

        h_op = df_Time.dp
        h_op.iloc[-2:] = 1
        df_network = last_results["df_District_t"].copy()
        df_network[["Network_supply", "Network_demand"]] = df_network[["Network_supply", "Network_demand"]].divide(h_op, axis=0, level='Period')

        df_network["Uncontrollable_load"] = df.groupby(["Layer", "Period", "Time"]).sum()["Uncontrollable_load"]

        df_network = pd.concat([df_network], keys=['Network'], names=['Hub']).reorder_levels(['Layer', 'Hub', 'Period', 'Time'])
        df_network = df_network.rename(columns={"Cost_demand_network": "Cost_demand",
                                                "Cost_supply_network": "Cost_supply",
                                                "Network_demand": "Grid_demand",
                                                "Network_supply": "Grid_supply"})

        columns = ["Cost_demand", "Cost_supply", "GWP_demand", "GWP_supply"]
        for h in self.buildings_data.keys():
            for column in columns:
                values_to_assign = df_network[column].values
                target_slice = df.loc[pd.IndexSlice[:, h, :, :], column]

                if len(values_to_assign) != len(target_slice):
                    raise ValueError("Mismatch between target slice length and values length")

        df_Grid_t = pd.concat([df, df_network])

        # df_Unit
        df_Unit = self.get_final_MP_results(Pareto_ID=Pareto_ID, Scn_ID=Scn_ID)
        df_Unit = df_Unit.droplevel(['FeasibleSolution', 'Hub'])
        df_Unit = df_Unit.sort_index(level='Unit')

        # df_Annuals
        df = self.get_final_SPs_results(MP_selection, 'df_Annuals')
        df = df.sort_index(level='house')
        df = df.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
        df = df.sort_index(level='Layer')
        df = df.drop('Network', level='Hub')

        df_network = pd.DataFrame(self.infrastructure.grids.keys(), columns=["Layer"])  # build a df template
        df_network["Hub"] = "Network"
        df_network = df_network.set_index(["Layer", "Hub"])
        df_network[df.columns] = float("nan")

        for key in self.infrastructure.grids.keys():
            data = df_Grid_t.xs((key, "Network"), level=("Layer", "Hub"))[["Grid_demand", "Grid_supply"]]
            data = data.mul(df_Time.dp, level='Period', axis=0)
            df_network.loc[key, ['Demand_MWh', 'Supply_MWh']] = data.sum().values / 1000

        for i, unit in enumerate(self.infrastructure.UnitsOfDistrict):
            for key in self.infrastructure.district_units[i]["UnitOfLayer"]:
                # get annual values df_Unit_t using dp
                data = last_results["df_Unit_t"].xs((key, unit), level=('Layer', 'Unit')).mul(df_Time.dp[:-2], axis=0).sum() / 1000

                # Initialize values in df_network for the specified (key, unit) tuple
                df_network.loc[(key, unit), :] = float('nan')

                # Assign results to specific columns after verifying columns exist in `data`
                if 'Units_demand' in data and 'Units_supply' in data:
                    df_network.loc[(key, unit), ['Demand_MWh', 'Supply_MWh']] = data[
                        ['Units_demand', 'Units_supply']].values
                else:
                    raise ValueError("Expected columns 'Units_demand' and 'Units_supply' not found in `data`.")
        df_Annuals = pd.concat([df, df_network]).sort_index()

        # df_Buildings
        if self.method['renovation'] is not None:
            df_Buildings = self.get_final_SPs_results(MP_selection, 'df_Buildings')
            df_Buildings = df_Buildings[df_Buildings.index.get_level_values('house') == df_Buildings.index.get_level_values('Hub')]
            df_Buildings = df_Buildings.droplevel(['Hub', 'Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution'])
        else:
            df_Buildings = pd.DataFrame.from_dict(self.buildings_data, orient='index')

        df_Buildings.index.names = ['Hub']
        for item in ['x', 'y', 'z', 'geometry']:
            if item in df_Buildings.columns:
                df_Buildings.drop([item], axis=1)

        if self.method['use_pv_orientation'] or self.method['use_facades']:
            # PV_Surface
            df_PV_Surface = self.get_final_SPs_results(MP_selection, 'df_PV_Surface')
            df_PV_Surface = df_PV_Surface.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
            df_PV_Surface.sort_index(level='Hub')

            # df_PV_orientation
            df_PV_orientation = self.get_final_SPs_results(MP_selection, 'df_PV_orientation')
            df_PV_orientation = df_PV_orientation.droplevel(
                ['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
            df_PV_orientation.sort_index(level='Hub')
            df_Results["df_PV_Surface"] = df_PV_Surface
            df_Results["df_PV_orientation"] = df_PV_orientation

        # set results
        df_Results["df_Performance"] = df_Performance
        df_Results["df_Annuals"] = df_Annuals
        df_Results["df_Unit"] = df_Unit
        df_Results["df_Grid"] = df_Grid
        df_Results["df_Grid_t"] = df_Grid_t
        df_Results["df_Time"] = df_Time
        df_Results["df_Buildings"] = df_Buildings

        # Add interperiod storage to results dictionary
        if self.method["interperiod_storage"]:
            # Inter-period storage may exist only at the building scale, only at the
            # district scale, or at neither: an absent frame is not an error.
            try:
                df_interperiod = self.get_final_SPs_results(MP_selection, 'df_Interperiod')
                df_interperiod = df_interperiod.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
            except KeyError:
                df_interperiod = pd.DataFrame()

            df_interperiod_district = last_results.get("df_Interperiod", pd.DataFrame())

            df_interperiod_all = pd.concat([df_interperiod, df_interperiod_district], axis=0)
            df_interperiod_all = df_interperiod_all.sort_index(level=0)

            df_Results["df_Interperiod"] = df_interperiod_all

        if self.method["save_data_input"]:

            # df_Weather
            ids = self.number_SP_solutions.iloc[0]
            df_Weather = self.results_SP[ids["Scn_ID"]][ids["Pareto_ID"]][ids["Iter"]][ids["FeasibleSolution"]][ids["House"]]["df_Weather"]
            df_Results["df_Weather"] = df_Weather

            # df_Index
            ids = self.number_SP_solutions.iloc[0]
            df_Index = self.results_SP[ids["Scn_ID"]][ids["Pareto_ID"]][ids["Iter"]][ids["FeasibleSolution"]][ids["House"]]["df_Index"]
            df_Results["df_Index"] = df_Index

        # df_Buildings_t
        df_Buildings_t = self.get_final_SPs_results(MP_selection, 'df_Buildings_t')
        df_Buildings_t = df_Buildings_t.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
        df_Buildings_t.sort_index(level='Hub')
        df_Results["df_Buildings_t"] = df_Buildings_t

        # df_Unit_t
        df_Unit_t = self.get_final_SPs_results(MP_selection, 'df_Unit_t')
        df_Unit_t = df_Unit_t.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
        if "df_Unit_t" in last_results.keys():
            df_district_units = last_results["df_Unit_t"]
            df_Unit_t = pd.concat([df_Unit_t, df_district_units])
        df_Results["df_Unit_t"] = df_Unit_t

        if self.method["save_streams"]:
            # df_Streams_t
            df_Streams_t = self.get_final_SPs_results(MP_selection, 'df_Streams_t')
            df_Streams_t = df_Streams_t.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
            df_Results["df_Streams_t"] = df_Streams_t

        if self.method["extract_parameters"]:
            # Parameters of the sub-problems selected, per building
            df_Parameters = self.get_final_SPs_results(MP_selection, 'df_Parameters')
            df_Results["df_Parameters"] = df_Parameters.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution'])

        return df_Results

    def get_final_SPs_results(self, MP_selection, df_name):
        """Gather one result DataFrame over the sub-problem solutions selected by the master problem.

        Parameters
        ----------
        MP_selection : pandas.Index
            Selected solutions, as ``(FeasibleSolution, house)`` pairs.
        df_name : str
            Name of the DataFrame to gather, e.g. ``'df_Unit_t'``.

        Returns
        -------
        pandas.DataFrame
            The DataFrames of the selected solutions, indexed as by
            :meth:`~reho.model.master_problem.MasterProblem.return_combined_SP_results`.
        """
        data = self.return_combined_SP_results(self.results_SP, df_name)
        df = pd.DataFrame()
        for idx in MP_selection.values:
            df_idx = data.xs(idx, level=('FeasibleSolution', 'house'), drop_level=False)
            df = pd.concat([df, df_idx])
        return df

    def get_KPIs(self, Scn_ID=0, Pareto_ID=0):
        """Compute the indicators of an optimization, with :func:`~reho.model.postprocessing.KPIs.calculate_KPIs`.

        They are stored in ``results[Scn_ID][Pareto_ID]``, as ``df_KPIs`` and ``df_Economics``.

        Parameters
        ----------
        Scn_ID : str, optional
            Name of the scenario.
        Pareto_ID : int, optional
            Index of the Pareto point. Default is 0.
        """
        df_KPI, df_Economics = calculate_KPIs(self.results[Scn_ID][Pareto_ID], self.infrastructure, self.buildings_data)
        self.results[Scn_ID][Pareto_ID]["df_KPIs"] = df_KPI
        self.results[Scn_ID][Pareto_ID]["df_Economics"] = df_Economics

    def save_results(self, format='pickle', filename='results', erase_file=True, filter=True):
        """
        Saves the results in the desired format: pickle file or Excel sheet.

        The results are indexed on the scenarios and pareto IDs.

        Parameters
        ----------
        format : tuple, optional
            Format(s) in which to save the results. Choose from 'pickle' and 'xlsx'.
            Default is ('pickle').
        filename : str, optional
            Base name of the file to be saved. The extension will be added based on the format.
            Default is 'results'.
        erase_file : bool, optional
            Whether to overwrite existing files with the same name.
            Default is True.
        filter : bool, optional
            Whether to filter out rows with only zeros in Excel sheets.
            Default is True.

        Returns
        -------
        None

        Notes
        -----
        If 'erase_file' is set to False, a unique counter is added to the filename to avoid overwriting existing files.

        A table too large for an xlsx sheet, such as ``df_Parameters`` for a large district, is left
        out of the xlsx files with a warning; the pickle format keeps it.

        """
        try:
            os.makedirs('results')
        except OSError:
            if not os.path.isdir('results'):
                raise

        if 'save_all' in format:
            results = self  # save the whole reho object
        else:
            results = self.results  # save only reho results

        if 'pickle' in format:
            result_file_name = str(filename) + '.pickle'
            counter = 0
            while os.path.isfile('results/' + result_file_name) and not erase_file:
                counter += 1
                result_file_name = str(filename) + '_' + str(counter) + '.pickle'

            result_file_path = 'results/' + result_file_name
            f = open(result_file_path, 'wb')
            pickle.dump(results, f)
            f.close()
            self.logger.info('Results are saved in ' + result_file_path)

        if 'xlsx' in format:

            for Scn_ID in list(results.keys()):
                for Pareto_ID in list(results[Scn_ID].keys()):

                    if Pareto_ID == 0:
                        result_file_path = 'results/' + str(filename) + '_' + str(Scn_ID) + '.xlsx'
                    else:
                        result_file_path = 'results/' + str(filename) + '_' + str(Scn_ID) + str(Pareto_ID) + '.xlsx'

                    writer = pd.ExcelWriter(result_file_path)

                    for df_name, df in results[Scn_ID][Pareto_ID].items():
                        if df is not None:
                            df = df.fillna(0)  # replace all NaN with zeros

                            if filter:
                                # Determine columns to exclude based on df_name
                                exclude_cols = []
                                if df_name == "df_Unit":
                                    exclude_cols = ["lifetime"]
                                elif df_name == "df_Grid_t":
                                    exclude_cols = ["Cost_supply", "Cost_demand", "GWP_supply", "GWP_demand"]
                                elif df_name == "df_Streams_t":
                                    exclude_cols = ["Streams_Tin", "Streams_Tout"]

                                # Columns to consider when checking for zeros
                                cols_to_check = df.columns.difference(exclude_cols)

                                # Drop rows where all considered columns are zeros
                                df = df.loc[~(df[cols_to_check] == 0).all(axis=1)]

                            # The header rows and the index columns take room in the sheet too
                            if (len(df) + df.columns.nlevels + 1 > XLSX_MAX_ROWS
                                    or len(df.columns) + df.index.nlevels > XLSX_MAX_COLUMNS):
                                self.logger.warning(
                                    "%s (%d rows, %d columns) does not fit in an xlsx sheet and is left out of %s: "
                                    "save the results as pickle to keep it.", df_name, len(df), len(df.columns), result_file_path)
                                continue

                            df.to_excel(writer, sheet_name=df_name)
                            write_results.auto_adjust_columns(writer, df, df_name)

                    writer.close()
                    self.logger.info('Results are saved in ' + result_file_path)
