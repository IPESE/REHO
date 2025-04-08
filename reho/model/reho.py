import multiprocessing as mp
import os.path
import pickle
import openpyxl

from reho.model.master_problem import *
from reho.model.postprocessing.KPIs import *
from reho.paths import *

from reho.model.postprocessing.write_results import get_ampl_data

__doc__ = """
File for constructing and solving the optimization problem.
"""


class REHO(MasterProblem):
    """
    Performs the single or multi-objective optimization.

    Parameters are inherited from ``MasterProblem``.

    See also
    --------
    reho.model.master_problem.MasterProblem
    """

    def __init__(self, qbuildings_data, units, grids, parameters=None, set_indexed=None, cluster=None, method=None, scenario=None, solver="highs",
                 DW_params=None):

        super().__init__(qbuildings_data, units, grids, parameters, set_indexed, cluster, method, solver, DW_params)
        self.initialize_optimization_tracking_attributes()

        # input attributes
        self.scenario = scenario.copy()
        if 'specific' not in self.scenario:
            self.scenario['specific'] = []
        if 'enforce_units' not in self.scenario:
            self.scenario['enforce_units'] = []
        if 'exclude_units' not in self.scenario:
            self.scenario['exclude_units'] = []
        if 'EMOO' not in self.scenario:
            self.scenario['EMOO'] = {}
        if 'EMOO_grid' not in self.scenario['EMOO']:
            self.scenario['EMOO']['EMOO_grid'] = 0.0
        if 'name' not in self.scenario:
            self.scenario['name'] = 'default_name'
        if 'nPareto' not in self.scenario:
            self.nPareto = 1  # no curve, single execution
            self.total_Pareto = 1
        else:
            self.nPareto = self.scenario['nPareto']  # intermediate points
            self.total_Pareto = self.nPareto * 2 + 2  # total pareto points: both objectives plus boundaries

        self.results = dict()

        self.solver_attributes = pd.DataFrame()
        self.epsilon_constraints = {}

    def single_optimization(self, Pareto_ID=0):
        Scn_ID = self.scenario['name']
        if self.method['district-scale'] or self.method['building-scale']:  # decomposition formulation
            ampl, exitcode = self.execute_dantzig_wolfe_decomposition(self.scenario, Scn_ID, Pareto_ID=Pareto_ID)

        else:  # compact formulation
            if self.method['use_facades'] or self.method['use_pv_orientation']:
                reho = SubProblem(self.infrastructure, self.buildings_data, self.local_data, self.parameters, self.set_indexed, self.cluster, self.scenario, self.method, self.solver, self.qbuildings_data)
            else:
                reho = SubProblem(self.infrastructure, self.buildings_data, self.local_data, self.parameters, self.set_indexed, self.cluster, self.scenario, self.method, self.solver)
            ampl = reho.build_model_without_solving()

            if self.method['fix_units']:
                for unit in self.df_fix_Units.index:
                    if 'PV' in unit:
                        ampl.getVariable('Units_Mult').get(unit).fix(self.df_fix_Units.Units_Mult.loc[unit] * (1 - 1e-9))
                        ampl.getVariable('Units_Use').get(unit).fix(float(self.df_fix_Units.Units_Use.loc[unit]))
                    else:
                        ampl.getVariable('Units_Mult').get(unit).fix(self.df_fix_Units.Units_Mult.loc[unit])
                        ampl.getVariable('Units_Use').get(unit).fix(float(self.df_fix_Units.Units_Use.loc[unit]))

            ampl.solve()

            exitcode = exitcode_from_ampl(ampl)

        self.add_df_Results(ampl, Scn_ID, Pareto_ID, self.scenario)
        self.get_KPIs(Scn_ID, Pareto_ID=Pareto_ID)

        gc.collect()  # free memory
        del ampl
        if exitcode == 'infeasible':
            sys.exit(exitcode)

    def execute_dantzig_wolfe_decomposition(self, scenario, Scn_ID, Pareto_ID=0, epsilon_init=None):

        # Initiation
        self.pool = mp.Pool(mp.cpu_count())
        self.iter = 0  # new scenario has to start at iter = 0
        scenario, SP_scenario, SP_scenario_init = self.select_SP_obj_decomposition(scenario)

        self.logger.info('INITIATION, Iter:' + str(self.iter) + ' Pareto_ID: ' + str(Pareto_ID))
        self.initiate_decomposition(SP_scenario_init, Scn_ID=Scn_ID, Pareto_ID=Pareto_ID, epsilon_init=epsilon_init)
        self.logger.info('MASTER INITIATION, Iter:' + str(self.iter))
        self.MP_iteration(scenario, Scn_ID=Scn_ID, binary=False, Pareto_ID=Pareto_ID)

        # Iteration
        while self.iter < self.DW_params['max_iter'] - 1:  # last iteration is used to run the binary MP.
            self.iter += 1
            self.logger.info('SUB PROBLEM ITERATION, Iter:' + str(self.iter) + ' Pareto_ID: ' + str(Pareto_ID))
            self.SP_iteration(SP_scenario, Scn_ID=Scn_ID, Pareto_ID=Pareto_ID)
            self.logger.info('MASTER ITERATION, Iter:' + str(self.iter) + ' Pareto_ID: ' + str(Pareto_ID))
            self.MP_iteration(scenario, Scn_ID=Scn_ID, binary=False, Pareto_ID=Pareto_ID)

            if self.check_Termination_criteria(SP_scenario, Scn_ID=Scn_ID, Pareto_ID=Pareto_ID) and (self.iter > 3):
                break

        # Finalization
        self.logger.info(self.stopping_criteria)
        self.iter += 1
        self.logger.info('LAST MASTER ITERATION, Iter:' + str(self.iter) + ' Pareto_ID: ' + str(Pareto_ID))
        self.MP_iteration(scenario, Scn_ID=Scn_ID, binary=True, Pareto_ID=Pareto_ID)
        self.pool.close()

        return None, None

    def generate_pareto_curve(self):

        Scn_ID = self.scenario['name']

        def get_objectives_values(ampl, objectives, Pareto_ID):

            obj_values = {}
            surfaces = pd.DataFrame.from_dict({bui: self.buildings_data[bui]["ERA"] for bui in self.buildings_data}, orient="index")
            surfaces.columns = ["ERA"]

            def annualized_investment():
                if self.method['building-scale'] or self.method['district-scale']:
                    df_inv = self.results[Scn_ID][Pareto_ID]["df_Performance"]
                    district = (df_inv.Costs_inv[-1] + df_inv.Costs_rep[-1]) / self.ERA
                    buildings = df_inv.Costs_inv[:-1].div(surfaces.ERA) + df_inv.Costs_rep[:-1].div(surfaces.ERA)
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
                    district = df_op.Costs_op[-1] / self.ERA
                    building = df_op.Costs_op[:-1].div(surfaces.ERA)
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
                if self.method['use_facades'] or self.method['use_pv_orientation']:
                    reho = SubProblem(self.infrastructure, self.buildings_data, self.local_data, self.parameters, self.set_indexed, self.cluster,
                                      scenario, self.method, self.solver, self.qbuildings_data)
                else:
                    reho = SubProblem(self.infrastructure, self.buildings_data, self.local_data, self.parameters, self.set_indexed, self.cluster,
                                      scenario, self.method, self.solver)
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
                if self.method['use_facades'] or self.method['use_pv_orientation']:
                    reho = SubProblem(self.infrastructure, self.buildings_data, self.local_data, self.parameters, self.set_indexed, self.cluster,
                                      scenario, self.method, self.solver, self.qbuildings_data)
                else:
                    reho = SubProblem(self.infrastructure, self.buildings_data, self.local_data, self.parameters, self.set_indexed, self.cluster,
                                      scenario, self.method, self.solver)
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
                if self.method['use_facades'] or self.method['use_pv_orientation']:
                    reho = SubProblem(self.infrastructure, self.buildings_data, self.local_data, self.parameters, self.set_indexed,
                                      self.cluster, scenario, self.method, self.solver, self.qbuildings_data)
                else:
                    reho = SubProblem(self.infrastructure, self.buildings_data, self.local_data, self.parameters, self.set_indexed,
                                      self.cluster, scenario, self.method, self.solver)
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
                    if self.method['use_facades'] or self.method['use_pv_orientation']:
                        reho = SubProblem(self.infrastructure, self.buildings_data, self.local_data, self.parameters,
                                          self.set_indexed, self.cluster, scenario, self.method, self.solver, self.qbuildings_data)
                    else:
                        reho = SubProblem(self.infrastructure, self.buildings_data, self.local_data, self.parameters,
                                          self.set_indexed, self.cluster, scenario, self.method, self.solver)
                    ampl, exitcode = reho.solve_model()

                self.add_df_Results(ampl, Scn_ID, nParetoIT, scenario)
                self.get_KPIs(Scn_ID, Pareto_ID=nParetoIT)

                del ampl
                gc.collect()  # free memory

        sort_pareto_points()

        self.logger.info(str(obj1_min) + " " + str(obj1_max))

    def get_DHN_costs(self):

        self.pool = mp.Pool(mp.cpu_count())
        self.iter = 0  # new scenario has to start at iter = 0
        method = self.method['building-scale']
        self.method['building-scale'] = True
        scenario = self.scenario.copy()
        scenario["specific"] = scenario["specific"] + ["enforce_DHN"]
        scenario_MP, SP_scenario, SP_scenario_init = self.select_SP_obj_decomposition(scenario)

        self.initiate_decomposition(SP_scenario_init, Scn_ID=0, Pareto_ID=0)
        self.MP_iteration(scenario_MP, Scn_ID=0, binary=False, Pareto_ID=0, read_DHN=True)

        if not self.method["DHN_CO2"]:
            if "T_DHN_supply_cst" in self.parameters and "T_DHN_return_cst" in self.parameters:
                delta_enthalpy = np.array(self.parameters["T_DHN_supply_cst"] - self.parameters["T_DHN_return_cst"]).mean() * 4.18
            else:
                delta_enthalpy = 10 * 4.18
        else:
            delta_enthalpy = 179.5

        f = self.feasible_solutions - 1
        heat_flow = self.results_MP[0][0][0]["df_District"]["flowrate_max"] * delta_enthalpy
        dhn_inv = self.results_MP[0][0][0]["df_District"].loc["Network", "DHN_inv"]
        tau = self.results_SP[0][0][0][f]["Building1"]["df_Performance"]["ANN_factor"][0]
        dhn_invh = dhn_inv / (tau * sum(heat_flow[0:-1]))
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

    def get_df_Results_from_MP_and_SPs(self, Scn_ID, Pareto_ID):

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
        df_Performance.loc['Network', 'ANN_factor'] = df_Performance['ANN_factor'][0]

        if self.method["actors_problem"]:
            df_actor = self.results_MP[Scn_ID][Pareto_ID][ids['Iter']]["df_District"][
                ['C_op_renters_to_utility', 'C_op_renters_to_owners', 'C_op_utility_to_owners', 'owner_inv',
                 'owner_portfolio']]
            df_Performance = pd.concat([df_Performance, df_actor], axis=1)
            df_Results["df_Actors_tariff"] = self.results_MP[Scn_ID][Pareto_ID][ids['Iter']]["df_Actors_tariff"]
            df_Results["df_Actors"] = self.results_MP[Scn_ID][Pareto_ID][ids['Iter']]["df_Actors"]

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
                # Only consider PeriodStandard (without extreme days) to compute annual balance
                PeriodStandard = list(range(1, self.results_SP[ids['Scn_ID']][ids['Pareto_ID']][ids['Iter']][
                    ids['FeasibleSolution']][ids["House"]]["df_Index"]["PeriodOfYear"].max() + 1))

                # Filter `df_Time.dp` to include only the selected periods, then apply the calculation
                data = last_results["df_Unit_t"].xs((key, unit), level=('Layer', 'Unit')).mul(
                    df_Time.dp.loc[df_Time.dp.index.get_level_values("Period").isin(PeriodStandard)],
                    level='Period', axis=0).sum() / 1000

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

        # Add interperiod storage to results dictionary
        if self.method["interperiod_storage"]:
            try:
                df_interperiod = self.get_final_SPs_results(MP_selection, 'df_Interperiod')
                df_interperiod = df_interperiod.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
            except:
                df_interperiod = pd.DataFrame()

            try:
                df_interperiod_district = last_results["df_Interperiod"]
            except:
                df_interperiod_district = pd.DataFrame()

            df_interperiod_all = pd.concat([df_interperiod, df_interperiod_district], axis=0)
            df_interperiod_all = df_interperiod_all.sort_index(level=0)

            df_Results["df_Interperiod"] = df_interperiod_all

        if self.method["save_data_input"]:
            df_Results["df_Buildings"] = df_Buildings

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

        return df_Results

    def get_final_SPs_results(self, MP_selection, df_name):
        data = self.return_combined_SP_results(self.results_SP, df_name)
        df = pd.DataFrame()
        for idx in MP_selection.values:
            df_idx = data.xs(idx, level=('FeasibleSolution', 'house'), drop_level=False)
            df = pd.concat([df, df_idx])
        return df

    def get_KPIs(self, Scn_ID=0, Pareto_ID=0):
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

                            df.to_excel(writer, sheet_name=df_name)
                            auto_adjust_columns(writer, df, df_name)

                    writer.close()
                    self.logger.info('Results are saved in ' + result_file_path)


def auto_adjust_columns(writer, df, sheet_name):
    worksheet = writer.sheets[sheet_name]
    for idx, col in enumerate(df.columns, 1):
        # Calculate the width needed based on maximum length in column
        max_length = len(col) + 2  # column header length + extra padding
        worksheet.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = max_length
