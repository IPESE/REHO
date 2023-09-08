# -------------------------------------------------------------------------------------------------------------------------
# Renewable Energy Hub Optimizer (REHO) is an open-source energy model suitable for the optimization of energy systems at building-scale or district-scale.
# It considers simultaneously the optimal design as well as optimal scheduling of capacities.
# It allows to investigate the deployment of energy conversion and energy storage capacities to ensure the energy balance of a specified territory,
# through multi-objective optimization and KPIs parametric studies. It is based on an hourly resolution.
#
# Copyright (C) <2021-2023> <Ecole Polytechnique Fédérale de Lausanne (EPFL), Switzerland>
#
# Licensed under the Apache License, Version0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Description and complete License: see LICENSE file.
# -------------------------------------------------------------------------------------------------------------------------
#
# Version 1.0 of the model.
# See documentation : https://reho.readthedocs.io/en/main/
# See repo :  https://github.com/Renewable-Energy-Hub-Optimizer


from model.postprocessing.KPIs import *
from model.postprocessing.postcompute_decentralized_districts import *
from model.district_decomposition import *
import model.postprocessing.write_results as WR
import model.postprocessing.save_results as SR
from scipy.stats import qmc


class reho(district_decomposition):

    def __init__(self, qbuildings_data, units, grids, parameters=None, set_indexed=None,
                 cluster=None, method=None, scenario=None, DW_params=None):

        super().__init__(qbuildings_data, units, grids, parameters, set_indexed, cluster, method, DW_params)
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
        if self.method["decentralized"] and 'EV' not in self.district.UnitTypes:
            self.scenario['specific'] = self.scenario['specific'] + ["disallow_exchanges_1", "disallow_exchanges_2"]

        # output attributes
        self.results = WR.encapsulation()
        self.ampl_lib = WR.encapsulation()

        self.solver_attributes = pd.DataFrame()
        self.epsilon_constraints = {}
        os.system('cmd /c ' + os.environ["AMPL_PATH"] + "/ampl_lic restart")  # restart ampl license to avoid crashes

    def add_constraints_from_self_scenario(self):
        scenario = {}
        scenario['EMOO'] = {}
        scenario['EMOO']['EMOO_grid'] = self.scenario['EMOO']['EMOO_grid']
        scenario['specific'] = self.scenario['specific']
        scenario['exclude_units'] = self.scenario['exclude_units']
        scenario['enforce_units'] = self.scenario['enforce_units']
        return scenario

    def return_epsilon_init(self, C_max, C_min, pareto_max, pareto, objective):
        if self.method['decentralized']:
            if objective == self.scenario["Objective"][0]:
                epsilon_init = (C_max - C_min) / (pareto_max + 1) * (pareto - 1) + C_min
            elif objective == self.scenario["Objective"][1]:
                epsilon_init = (C_max - C_min) / (pareto_max + 1) * (pareto + 1) + C_min
            else:
                epsilon_init = None
        else:
            epsilon_init = None
        return epsilon_init

    def remove_all_ampl_lib(self):
        self.ampl_lib.clear()

    def __annualized_investment(self, ampl, surfaces, Scn_ID, Pareto_ID):

        if self.method["decomposed"] or self.method['decentralized']:
            df_inv = self.results[Scn_ID][Pareto_ID].df_Performance
            district = (df_inv.Costs_inv[-1] + df_inv.Costs_rep[-1]) / self.ERA
            buildings = df_inv.Costs_inv[:-1].div(surfaces.ERA) + df_inv.Costs_rep[:-1].div(surfaces.ERA)
        else:
            tau = ampl.getParameter('tau').getValues().toList()  # annuality factor
            df_h = WR.get_parameter_in_pandas(ampl, 'Costs_House_inv', multi_index=False)
            df1_h = WR.get_parameter_in_pandas(ampl, 'Costs_House_rep', multi_index=False)
            df = WR.get_parameter_in_pandas(ampl, 'Costs_inv', multi_index=False)
            df1 = WR.get_parameter_in_pandas(ampl, 'Costs_rep', multi_index=False)
            # annualized investment costs with replacements (important for BAT and NG_Cogeneration)
            district = (df.sum()[0] + df1.sum()[0]) * tau[0] / surfaces.sum()[0]  # for compact models
            buildings = (df_h.Costs_House_inv.div(surfaces.ERA) + df1_h.Costs_House_rep.div(surfaces.ERA)) * tau[0]  # for decomposed models
        return district, buildings


    def __opex_per_house(self, ampl, surfaces, Scn_ID, Pareto_ID):
        if self.method["decomposed"] or self.method["decentralized"]:
            df_op = self.results[Scn_ID][Pareto_ID].df_Performance
            district = df_op.Costs_op[-1] / self.ERA
            building = df_op.Costs_op[:-1].div(surfaces.ERA)
        else:
            df_h = WR.get_parameter_in_pandas(ampl, 'Costs_House_op', multi_index=False)
            df = WR.get_parameter_in_pandas(ampl, 'Costs_op', multi_index=False)

            district = df.sum()[0] / surfaces.sum()[0]  # normalized OPEX CHF/m2, for compact models
            building = df_h.Costs_House_op.div(surfaces.ERA)
        return district, building

    def __totex_per_house(self, ampl, surfaces, Scn_ID, Pareto_ID):
        capex_district, capex_building = self.__annualized_investment(ampl, surfaces, Scn_ID, Pareto_ID)
        opex_district, opex_building = self.__opex_per_house(ampl, surfaces, Scn_ID, Pareto_ID)
        totex_district = capex_district + opex_district
        totex_house = capex_building + opex_building
        return totex_district, totex_house

    def __gwp_per_house(self, surfaces, Scn_ID, Pareto_ID):
        df_perf = self.results[Scn_ID][Pareto_ID].df_Performance
        df_GWP = (df_perf["GWP_op"] + df_perf["GWP_constr"])

        GWP_district = df_GWP["Network"] / surfaces.sum()[0]
        GWP_house = df_GWP.drop("Network").div(surfaces.ERA)
        return GWP_district, GWP_house

    def get_objectives_values(self, ampl, objectives, Scn_ID, Pareto_ID):

        obj_values = {}
        surfaces = pd.DataFrame.from_dict({bui: self.buildings_data[bui]["ERA"] for bui in self.buildings_data}, orient="index")
        surfaces.columns = ["ERA"]
        for i, obj in enumerate(objectives):
            if "CAPEX" == obj:
                obj_values["district_obj" + str(i+1)], obj_values["building_obj" + str(i+1)] = self.__annualized_investment(ampl, surfaces, Scn_ID, Pareto_ID)
            elif "OPEX" == obj:
                obj_values["district_obj" + str(i+1)], obj_values["building_obj" + str(i+1)] = self.__opex_per_house(ampl, surfaces, Scn_ID, Pareto_ID)
            elif "TOTEX" == obj:
                obj_values["district_obj" + str(i+1)], obj_values["building_obj" + str(i+1)] = self.__totex_per_house(ampl, surfaces, Scn_ID, Pareto_ID)
            elif "GWP" == obj:
                obj_values["district_obj" + str(i+1)], obj_values["building_obj" + str(i+1)] = self.__gwp_per_house(surfaces, Scn_ID, Pareto_ID)
            else:
                obj_values["district_obj" + str(i+1)] = self.results[Scn_ID][Pareto_ID].df_lca_Performance[obj]["Network"] / np.sum(surfaces)[0]
                obj_values["building_obj" + str(i+1)] = self.results[Scn_ID][Pareto_ID].df_lca_Performance[obj].drop("Network").div(surfaces.ERA)


        return obj_values

    def __find_obj1_lower_bound(self, Scn_ID):

        scenario = self.add_constraints_from_self_scenario()
        objective1 = self.scenario["Objective"][0]
        scenario['Objective'] = objective1

        if self.method['decomposed']:
            ampl, exitcode = self.execute_dantzig_wolfe_decomposition(scenario, Scn_ID, Pareto_ID=1)
        else:
            if self.method['use_facades'] or self.method['use_pv_orientation']:
                REHO = compact_optimization(self.district, self.buildings_data, self.parameters, self.set_indexed, self.cluster, scenario, self.method, self.qbuildings_data)
            else:
                REHO = compact_optimization(self.district, self.buildings_data, self.parameters, self.set_indexed, self.cluster, scenario, self.method)
            ampl, exitcode = REHO.solve_model()

        scenario = {'Objective': objective1}
        df_Results = self.get_results_attributes(ampl, Scn_ID, 1, scenario)
        self.results.add_item(Scn_ID, 1, df_Results)
        self.get_KPIs(Scn_ID, Pareto_ID=1)

        obj_values = self.get_objectives_values(ampl, self.scenario["Objective"], Scn_ID, Pareto_ID=1)
        self.remove_all_ampl_lib()
        gc.collect()  # free memory
        print('The lower bound of the', objective1, 'value is: ', obj_values["district_obj1"])
        return obj_values



    def __find_obj2_lower_bound(self, Scn_ID):
        scenario = self.add_constraints_from_self_scenario()
        objective2 = self.scenario["Objective"][1]
        scenario['Objective'] = objective2

        if not self.method["switch_off_second_objective"]:
            Pareto_ID = self.total_Pareto
        else:
            Pareto_ID = self.nPareto + 2

        if self.method['decomposed']:
            ampl, exitcode = self.execute_dantzig_wolfe_decomposition(scenario, Scn_ID, Pareto_ID=Pareto_ID)
        else:
            if self.method['use_facades'] or self.method['use_pv_orientation']:
                REHO = compact_optimization(self.district, self.buildings_data, self.parameters, self.set_indexed, self.cluster, scenario, self.method, self.qbuildings_data)
            else:
                REHO = compact_optimization(self.district, self.buildings_data, self.parameters, self.set_indexed, self.cluster, scenario, self.method)
            ampl, exitcode = REHO.solve_model()

        scenario = {'Objective': objective2}
        df_Results = self.get_results_attributes(ampl, Scn_ID, Pareto_ID, scenario)
        self.results.add_item(Scn_ID, Pareto_ID, df_Results)
        self.get_KPIs(Scn_ID, Pareto_ID=Pareto_ID)

        obj_values = self.get_objectives_values(ampl, self.scenario["Objective"], Scn_ID, Pareto_ID=Pareto_ID)

        self.remove_all_ampl_lib()
        gc.collect()  # free memory
        print('The upper bound of the', self.scenario["Objective"][0], 'value is: ', obj_values["district_obj1"])
        return obj_values


    def generate_pareto_curve(self):

        Scn_ID = self.scenario['name']
        ################################################################################################
        # Bounds Paretocurve
        obj1_lower_bound = self.__find_obj1_lower_bound(Scn_ID)  # lower bound
        obj1_upper_bound = self.__find_obj2_lower_bound(Scn_ID)  # upper bound capex

        obj1_max = obj1_upper_bound["district_obj1"]
        obj1_min = obj1_lower_bound["district_obj1"]
        obj1_house_max = obj1_upper_bound["building_obj1"]
        obj1_house_min = obj1_lower_bound["building_obj1"]

        ################################################################################################
        # Intermediate Pareto points nParetoIT CAPEX constraint Opex optimization
        scenario = self.add_constraints_from_self_scenario()
        scenario['Objective'] = self.scenario["Objective"][1]
        self.epsilon_constraints['EMOO_obj1'] = np.array([])

        for nParetoIT in range(2, self.nPareto + 2):
            # Computation of the intermediate RES values
            obj1_eps_lim = (obj1_max - obj1_min) / (self.nPareto + 1) * (nParetoIT - 1) + obj1_min
            epsilon_init = self.return_epsilon_init(obj1_house_max, obj1_house_min, self.nPareto, nParetoIT, self.scenario["Objective"][0])

            if self.scenario["Objective"][0] in ["OPEX", "CAPEX", "TOTEX", "GWP"]:
                scenario['EMOO']['EMOO_' + self.scenario["Objective"][0]] = obj1_eps_lim
            else:
                scenario['EMOO']['EMOO_lca'] = {self.scenario["Objective"][0]: obj1_eps_lim}

            self.epsilon_constraints['EMOO_obj1'] = np.append(self.epsilon_constraints['EMOO_obj1'], obj1_eps_lim)
            print('---------------> ', self.scenario["Objective"][0], ' LIMIT: ', obj1_eps_lim)

            # results computation
            if self.method['decomposed']:
                ampl, exitcode = self.execute_dantzig_wolfe_decomposition(scenario, Scn_ID, Pareto_ID=nParetoIT, epsilon_init=epsilon_init)
            else:
                if self.method['use_facades'] or self.method['use_pv_orientation']:
                    REHO = compact_optimization(self.district, self.buildings_data, self.parameters, self.set_indexed,
                                                self.cluster, scenario, self.method, self.qbuildings_data)
                else:
                    REHO = compact_optimization(self.district, self.buildings_data, self.parameters, self.set_indexed,
                                                self.cluster, scenario, self.method)
                ampl, exitcode = REHO.solve_model()

            df_Results = self.get_results_attributes(ampl, Scn_ID, nParetoIT, scenario)
            self.results.add_item(Scn_ID, nParetoIT, df_Results)
            self.get_KPIs(Scn_ID, Pareto_ID=nParetoIT)
            self.remove_all_ampl_lib()
            del ampl
            gc.collect()  # free memory

        if not self.method['switch_off_second_objective']:
            ################################################################################################
            # Intermediate Pareto points nParetoIT OPEX constraint CAPEX optimization
            scenario = self.add_constraints_from_self_scenario()
            scenario['Objective'] = self.scenario["Objective"][0]
            self.epsilon_constraints['EMOO_obj2'] = np.array([])

            obj2_min = obj1_upper_bound["district_obj2"]
            obj2_max = obj1_lower_bound["district_obj2"]
            obj2_house_min = obj1_upper_bound["building_obj2"]
            obj2_house_max = obj1_lower_bound["building_obj2"]

            for point, nParetoIT in enumerate(range(self.nPareto + 2, self.total_Pareto)):

                # Computation of the intermediate RES values
                obj2_eps_lim = (obj2_max - obj2_min) / (self.nPareto + 1) * (point + 1) + obj2_min
                epsilon_init = self.return_epsilon_init(obj2_house_max, obj2_house_min, self.nPareto, point, self.scenario["Objective"][1])

                if self.scenario["Objective"][1] in ["OPEX", "CAPEX", "TOTEX", "GWP"]:
                    scenario['EMOO']['EMOO_' + self.scenario["Objective"][1]] = obj2_eps_lim
                else:
                    scenario['EMOO']['EMOO_lca'] = {self.scenario["Objective"][1]: obj2_eps_lim}

                self.epsilon_constraints['EMOO_obj2'] = np.append(self.epsilon_constraints['EMOO_obj2'], obj2_eps_lim)
                print('---------------> ', self.scenario["Objective"][1], ' LIMIT: ', obj2_eps_lim)
                # results computation
                if self.method['decomposed']:
                    ampl, exitcode = self.execute_dantzig_wolfe_decomposition(scenario, Scn_ID, Pareto_ID=nParetoIT, epsilon_init=epsilon_init)
                else:
                    if self.method['use_facades'] or self.method['use_pv_orientation']:
                        REHO = compact_optimization(self.district, self.buildings_data, self.parameters,
                                                    self.set_indexed, self.cluster,
                                                    scenario, self.method, self.qbuildings_data)
                    else:
                        REHO = compact_optimization(self.district, self.buildings_data, self.parameters,
                                                    self.set_indexed,
                                                    self.cluster,
                                                    scenario, self.method)
                    ampl, exitcode = REHO.solve_model()

                df_Results = self.get_results_attributes(ampl, Scn_ID, nParetoIT, scenario)
                self.results.add_item(Scn_ID, nParetoIT, df_Results)
                self.get_KPIs(Scn_ID, Pareto_ID=nParetoIT)
                self.remove_all_ampl_lib()
                del ampl
                gc.collect()  # free memory

        self.sort_pareto_points(Scn_ID)

        print(obj1_min, obj1_max)

    def sort_pareto_points(self, Scn_ID):

        df = pd.DataFrame()
        for i in self.results[Scn_ID].keys():
            if self.scenario["Objective"][0] in self.district.lca_kpis:
                df2 = pd.DataFrame([self.results[Scn_ID][i].df_lca_Performance[self.scenario["Objective"][0]].xs("Network")], index=[i])
            else:
                df2 = pd.DataFrame([self.results[Scn_ID][i].df_Performance['Costs_op'].xs("Network")], index=[i])
            df = pd.concat([df, df2])
        df = df.sort_values([0], ascending=False).reset_index()

        new_order_results = {}
        new_order_ampl = {}
        rename_dict = {}
        for n, idx in enumerate(df['index'].values):
            new_order_results[n + 1] = self.results[Scn_ID][idx]
            new_order_ampl[n + 1] = self.ampl_lib[Scn_ID][idx]
            rename_dict[idx] = n + 1

        self.results[Scn_ID] = new_order_results
        self.ampl_lib[Scn_ID] = new_order_ampl

        if self.method['decomposed']:
            self.sort_decomp_result(Scn_ID, df['index'].values)


    def fix_utilities_OPEX_curve(self):
        Scn_ID = self.scenario['name']
        scenario = self.add_constraints_from_self_scenario()

        for Pareto_ID in range(1, self.total_Pareto + 1):
            df_u = self.results[Scn_ID][Pareto_ID].df_Unit

            scenario['Objective'] = 'OPEX'
            # -----------------------------------------------------------------------------------------------------#
            # -Execution
            # -----------------------------------------------------------------------------------------------------#

            # REHOExecution, returns ampl library containing the whole model
            if self.method['use_facades'] or self.method['use_pv_orientation']:
                REHO = compact_optimization(self.district, self.buildings_data, self.parameters, self.set_indexed,
                                            self.cluster,
                                            scenario, self.method, self.qbuildings_data)
            else:
                REHO = compact_optimization(self.district, self.buildings_data, self.parameters, self.set_indexed,
                                            self.cluster,
                                            scenario, self.method)
            ampl = REHO.build_model_without_solving()

            for i, value in ampl.getVariable('Units_Mult').instances():
                ampl.getVariable('Units_Mult').get(str(i)).fix(1.00001 * df_u.Units_Mult.loc[i])  ## To avoid  infeasibilities caused by  numerical issues - Be care ful  with integer Mult

            for i, value in ampl.getVariable('Units_Use').instances():
                ampl.getVariable('Units_Use').get(str(i)).fix(df_u.Units_Use.loc[i])

            ampl.solve()
            exitcode = exitcode_from_ampl(ampl)
            if exitcode == 'infeasible':
                sys.exit(exitcode)

            df_Results = WR.dataframes_results(ampl, scenario, self.method, self.buildings_data)

            self.results.add_item(Scn_ID, Pareto_ID + 100, df_Results)
            self.ampl_lib.add_item(Scn_ID, Pareto_ID + 100, ampl)
            self.get_KPIs(Scn_ID, Pareto_ID=self.total_Pareto)
            self.remove_all_ampl_lib()
            del ampl
            gc.collect() # free memory


    def fix_utilities(self, Pareto_ID, Scn_ID, cluster, df_Unit=None, scenario=None):

        if self.method['decomposed']:
            if 'FeasibleSolution' in df_Unit.index.names:
                df_unit = df_Unit.reset_index(level=['FeasibleSolution','Hub'], drop=True)
            else:
                df_unit = df_Unit
        else:
            if df_Unit.empty:
                df_unit = self.results[Scn_ID][Pareto_ID].df_Unit
            else:
                df_unit = df_Unit

        scenario_fix_uti = scenario.copy()
        if 'Objective' in scenario_fix_uti:
            if 'GWP' in scenario_fix_uti['Objective'] or 'GWP_Dantzig' in scenario_fix_uti['Objective']:
                scenario_fix_uti['Objective'] = 'GWP'
            else:
                scenario_fix_uti['Objective'] = 'OPEX'
        else:
            scenario_fix_uti['Objective'] = 'OPEX'

        #scenario_fix_uti = self.remove_emoo_constraints(scenario_fix_uti)

        parameters_district = {}
        for key in self.parameters:
            parameters_district[key] = self.parameters[key]

        # -----------------------------------------------------------------------------------------------------#
        # -Execution
        # -----------------------------------------------------------------------------------------------------#
        # REHOExecution, returns ampl library containing the whole model
        if self.method['use_facades'] or self.method['use_pv_orientation']:
            REHO = compact_optimization(self.district, self.buildings_data, self.parameters, self.set_indexed,
                                        self.cluster, scenario_fix_uti, self.method, self.qbuildings_data)
        else:
            REHO = compact_optimization(self.district, self.buildings_data, self.parameters, self.set_indexed,
                                        self.cluster, scenario_fix_uti, self.method)
        ampl = REHO.build_model_without_solving()

        for i, value in ampl.getVariable('Units_Mult').instances():
            # ## To avoid  infeasibilities caused by  numerical issues - increase unitsize, if not HP or already Fmax -Be care ful  with integer Mult
            if i in self.district.UnitsOfType['HeatPump']:
                ampl.getVariable('Units_Mult').get(str(i)).fix(df_unit.Units_Mult.loc[i])
            elif i in self.district.UnitsOfType['PV']:
                ampl.getVariable('Units_Mult').get(str(i)).fix(0.999*df_unit.Units_Mult.loc[i])
            elif i in self.district.UnitsOfType['WaterTankDHW']:
                ampl.getVariable('Units_Mult').get(str(i)).fix(0.999*df_unit.Units_Mult.loc[i])
            elif df_unit.Units_Mult.loc[i] == self.district.Units_Parameters.loc[i].Units_Fmax:
                ampl.getVariable('Units_Mult').get(str(i)).fix(df_unit.Units_Mult.loc[i])
            else:
                ampl.getVariable('Units_Mult').get(str(i)).fix(1.00001 * df_unit.Units_Mult.loc[i])

        for i, value in ampl.getVariable('Units_Use').instances():
            ampl.getVariable('Units_Use').get(str(i)).fix(df_unit.Units_Use.loc[i])

        # constraints_to_drop =['DHW_c1','DHW_c2','DHW_c3','DHW_c4','DHW_c5','PVO_c3']
        constraints_to_drop = ['EMOO_grid_constraint', "DHW_c2"]
        for constr in constraints_to_drop:
            ampl.getConstraint(constr).drop()

        ampl.solve()
        exitcode = exitcode_from_ampl(ampl)
        if exitcode == 'infeasible':
            sys.exit(exitcode)

        return ampl, exitcode

    def execute_dantzig_wolfe_decomposition(self, scenario, Scn_ID, Pareto_ID=0, epsilon_init=None):
        # -----------------------------------------------------------------------------------------------------------
        # INITIATION
        # -----------------------------------------------------------------------------------------------------------
        self.pool = mp.Pool(mp.cpu_count())
        self.iter = 0  # new scenario has to start at iter = 0
        scenario, SP_scenario, SP_scenario_init = self.select_SP_obj_decomposition(scenario)

        print('INITIATION, ', 'Iter:', self.iter, 'Pareto_ID: ', Pareto_ID)
        self.initiate_decomposition(SP_scenario_init, Scn_ID=Scn_ID, Pareto_ID=Pareto_ID, epsilon_init=epsilon_init)
        print('MASTER INITIATION, ', 'Iter:', self.iter)
        self.MP_iteration(scenario, Scn_ID=Scn_ID, binary=False, Pareto_ID=Pareto_ID)

        # -----------------------------------------------------------------------------------------------------------
        # ITERATION
        # -----------------------------------------------------------------------------------------------------------
        while (self.iter < self.DW_params['max_iter'] - 1):  # last iteration is used to run the binary MP.
            self.iter += 1
            print('SUB PROBLEM ITERATION, ', 'Iter:', self.iter, 'Pareto_ID: ', Pareto_ID)
            self.SP_iteration(SP_scenario, Scn_ID=Scn_ID, Pareto_ID=Pareto_ID)
            print('MASTER ITERATION, ', 'Iter:', self.iter, 'Pareto_ID: ', Pareto_ID)
            self.MP_iteration(scenario, Scn_ID=Scn_ID, binary=False, Pareto_ID=Pareto_ID)

            if self.check_Termination_criteria(SP_scenario, Scn_ID=Scn_ID, Pareto_ID=Pareto_ID) and (self.iter > 3):
                break

        # -----------------------------------------------------------------------------------------------------------
        # FINALIZATION
        # -----------------------------------------------------------------------------------------------------------
        print(self.stopping_criteria)
        self.iter += 1
        print('LAST MASTER ITERATION, ', 'Iter:', self.iter, 'Pareto_ID: ', Pareto_ID)
        self.MP_iteration(scenario, Scn_ID=Scn_ID, binary=True, Pareto_ID=Pareto_ID)
        self.pool.close()

        return None, None


    def single_optimization(self, Pareto_ID=0, Third_ID=None):
        Scn_ID = self.scenario['name']
        if self.method['decomposed']:
            ampl, exitcode = self.execute_dantzig_wolfe_decomposition(self.scenario, Scn_ID, Pareto_ID=Pareto_ID)

        else:
            if self.method['use_facades'] or self.method['use_pv_orientation']:
                REHO = compact_optimization(self.district, self.buildings_data, self.parameters, self.set_indexed,
                                            self.cluster, self.scenario, self.method, self.qbuildings_data)
            else:
                REHO = compact_optimization(self.district, self.buildings_data, self.parameters, self.set_indexed,
                                            self.cluster, self.scenario, self.method)
            ampl = REHO.build_model_without_solving()

            if self.method['fix_units']:
                for unit in self.fix_units_list:
                    for h in self.district.House:
                        if unit == 'PV':
                            ampl.getVariable('Units_Mult').get('PV_' + h).fix(self.df_fix_Units.Units_Mult.loc['PV_' + h] * 0.999)
                            ampl.getVariable('Units_Use').get('PV_' + h).fix(float(self.df_fix_Units.Units_Use.loc['PV_' + h]))
                        else:
                            ampl.getVariable('Units_Mult').get(unit + '_' + h).fix(self.df_fix_Units.Units_Mult.loc[unit + '_' + h])
                            ampl.getVariable('Units_Use').get(unit + '_' + h).fix(float(self.df_fix_Units.Units_Use.loc[unit + '_' + h]))

            ampl.solve()
            exitcode = exitcode_from_ampl(ampl)

        df_Results = self.get_results_attributes(ampl, Scn_ID, Pareto_ID, self.scenario)
        if Third_ID is None:
            self.results.add_item(Scn_ID, Pareto_ID, df_Results)
            self.get_KPIs(Scn_ID, Pareto_ID=Pareto_ID)
        else:
            self.results.add_item(Scn_ID, Pareto_ID, df_Results, Third_ID)
        self.remove_all_ampl_lib()
        gc.collect()  # free memory
        del ampl
        if exitcode == 'infeasible':
            sys.exit(exitcode)


    def generate_pareto_actors(self, n_sample=10, bounds=None, actor="Owner"):
        self.method["actors_cost"] = True
        self.method["include_all_solutions"] = True
        self.method["decentralized"] = True
        self.scenario["Objective"] = "TOTEX_bui"
        self.set_indexed["ActorObjective"] = np.array([actor])
        if bounds != None:
            sampler = qmc.LatinHypercube(d=3)
            sample = sampler.random(n=n_sample)
            l_bound = [bounds[key][0] for key in bounds]
            u_bound = [bounds[key][1] for key in bounds]
            samples = pd.DataFrame(qmc.scale(sample, l_bound, u_bound), columns=['utility_portfolio', 'owner_portfolio', 'epsilon'])
            self.samples = samples.round(4)
        else:
            self.samples = pd.DataFrame([[None, None, None]]*n_sample, columns=['utility_portfolio', 'owner_portfolio', 'epsilon'])

        Scn_ID = self.scenario['name']
        self.pool = mp.Pool(mp.cpu_count())
        results = {ids: self.pool.apply_async(self.run_actors_opti, args=(self.samples, ids)) for ids in self.samples.index}
        while len(results[list(self.samples.index)[-1]].get()) != 2:
            time.sleep(1)
        for ids in self.samples.index:
            df_Results, df_Results_MP = results[ids].get()
            self.results.add_item(Scn_ID, ids, df_Results)
            self.results_MP[Scn_ID][ids] = df_Results_MP

        self.samples["objective"] = None
        for i in self.results_MP[self.scenario["name"]]:
            if self.results_MP[self.scenario["name"]][i] != None:
                self.samples.loc[i, "objective"] = self.results_MP[self.scenario["name"]][i][0].df_District["Objective"]["Network"]

        self.pool.close()
        self.remove_all_ampl_lib()
        gc.collect()  # free memory

    def run_actors_opti(self, samples, ids):

        if any([samples[col][0] for col in samples]): # if samples contain values
            param = samples.iloc[ids] # TODO pass epsilon constraints in EMOO scenario
            self.parameters = {'utility_portfolio_min': param['utility_portfolio'], 'owner_portfolio_min': param['owner_portfolio'], 'EMOO_totex_lodger': param['epsilon']}
        scenario, SP_scenario, SP_scenario_init = self.select_SP_obj_decomposition(self.scenario)
        try:
            scn = self.scenario["name"]
            self.MP_iteration(scenario, Scn_ID=scn, binary=True, Pareto_ID=0)
            df_Results = self.get_results_attributes(None, scn, 0, self.scenario)
            return df_Results, self.results_MP[scn][0]
        except:
            return None, None

    def generate_configurations(self, n_sample=5, tariffs_ranges=None, path=None):
        if tariffs_ranges == None:
            tariffs_ranges = {'Electricity': {"Cost_demand_cst": [0.05, 0.20], "Cost_supply_cst": [0.15, 0.30]},
                              'NaturalGas': {"Cost_supply_cst": [0.1, 0.30]}}
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
        idx_removed = samples[samples["Electricity_Cost_supply_cst"] - samples["Electricity_Cost_demand_cst"] < 0].index
        samples = samples.drop(idx_removed)

        self.pool = mp.Pool(mp.cpu_count())
        for s in samples.index:
            for layer in tariffs_ranges:
                for param in tariffs_ranges[layer]:
                    self.district.grids[layer][param] = samples.loc[s, layer + "_" + param]

            scenario, SP_scenario, SP_scenario_init = self.select_SP_obj_decomposition(self.scenario)
            Scn_ID = self.scenario['name']
            init_beta = [10, 5, 2, 1, 0.5, 0.2, 0.1]

            for beta in init_beta: # execute SP for MP initialization
                if self.method['parallel_computation']:
                    results = {h: self.pool.apply_async(self.SP_initiation_execution, args=(SP_scenario_init, Scn_ID, s, h, None, beta)) for h in self.district.houses}
                    while len(results[list(self.buildings_data.keys())[-1]].get()) != 2:
                        time.sleep(1)
                    for h in self.district.houses:
                        (df_Results, attr) = results[h].get()
                        self.add_Result_SP(Scn_ID, s, self.iter, h, df_Results, attr)
                self.feasible_solutions += 1  # after each 'round' of SP execution the number of feasible solutions increase
        self.pool.close()

        try:
            os.makedirs('results')
            os.makedirs('results/configurations')
        except OSError:
            if not os.path.isdir('results'):
                raise

            file_name = 'config_' + str(len(self.buildings_data)) + '_' + str(self.buildings_data["Building1"]["transformer"]) + '.pickle'
            path = os.path.join('results/configurations', file_name)
        f = open(path, 'wb')
        pickle.dump([self.results_SP, self.feasible_solutions, self.number_SP_solutions], f)

        return

    def read_configurations(self, path=None):
         if path is None:
             file_name = 'config_' + str(len(self.buildings_data)) + '_' + str(self.buildings_data["Building1"]["transformer"]) + '.pickle'
             path = os.path.join('results/configurations', file_name)
         with open(path, 'rb') as f:
             [self.results_SP, self.feasible_solutions, self.number_SP_solutions] = pickle.load(f)

    def get_DHN_costs(self):

        self.pool = mp.Pool(mp.cpu_count())
        self.iter = 0  # new scenario has to start at iter = 0
        method = self.method['decentralized']
        self.method['decentralized'] = True
        scenario = self.scenario.copy()
        scenario["specific"] = scenario["specific"] + ["enforce_DHN"]
        scenario_MP, SP_scenario, SP_scenario_init = self.select_SP_obj_decomposition(scenario)

        self.initiate_decomposition(SP_scenario_init, Scn_ID=0, Pareto_ID=0)
        self.MP_iteration(scenario_MP, Scn_ID=0, binary=False, Pareto_ID=0, read_DHN=True)

        if not self.method["DHN_CO2"]:
            delta_enthalpy = np.array(self.parameters["T_DHN_supply_cst"] - self.parameters["T_DHN_return_cst"]).mean() * 4.18
        else:
            delta_enthalpy = 179.5
        heat_flow = self.results_MP[0][0][0].df_District["flowrate_max"] * delta_enthalpy
        dhn_inv = self.results_MP[0][0][0].df_District.loc["Network", "DHN_inv"]
        tau = self.results_SP[0][0][0][0]["Building1"].df_Performance["ANN_factor"][0]
        dhn_invh = dhn_inv / (tau * sum(heat_flow[0:-1]))
        for bui in self.district.houses.keys():
            self.district.Units_Parameters.loc["DHN_pipes_" + bui, ["Units_Fmax", "Cost_inv2"]] = [heat_flow[bui]*1.001, dhn_invh]

        self.pool.close()
        self.method['decentralized'] = method
        self.initialize_optimization_tracking_attributes()

    def get_results_attributes(self, ampl, Scn_ID, ParetoID, scenario):
        if self.method["decomposed"] or self.method['decentralized']:
            df_Results = self.get_df_results_from_MP_and_SPs(Scn_ID, ParetoID)
        else:
            df_Results = WR.dataframes_results(ampl, scenario, self.method, self.buildings_data)
            self.get_solver_attributes(Scn_ID, ParetoID, ampl)
            # self.ampl_lib.add_item(Scn_ID, nParetoIT, ampl)
        return df_Results


    def get_KPIs(self, Scn_ID=0, Pareto_ID=0):
        df_KPI, df_eco = calculate_KPIs(self.results[Scn_ID][Pareto_ID], self.district, self.buildings_data, self.cluster)
        self.results[Scn_ID][Pareto_ID].df_KPI = df_KPI
        self.results[Scn_ID][Pareto_ID].df_economics = df_eco
        if self.method["decentralized"]:
            self.results[Scn_ID][Pareto_ID] = correct_network_values(self, Scn_ID, Pareto_ID)


    def get_final_SPs_results(self, MP_selection, attribute):
        data = self.return_combined_SP_results(self.results_SP, attribute)
        df = pd.DataFrame()
        for idx in MP_selection.values:
            if attribute == "df_Grid_t":
                df_idx = data.xs((idx), level=("FeasibleSolution", "house"), drop_level=False).xs(idx[1], level="Hub", drop_level=False)
                df_idx_net = data.xs((idx), level=("FeasibleSolution", "house"), drop_level=False).xs("Network", level="Hub", drop_level=False)
                df_idx["GWP_demand"] = np.array(df_idx_net["GWP_demand"])
                df_idx["GWP_supply"] = np.array(df_idx_net["GWP_supply"])
            else:
                df_idx = data.xs((idx), level=('FeasibleSolution', 'house'), drop_level=False)
            df = pd.concat([df, df_idx])
        return df

    def get_df_results_from_MP_and_SPs(self, Scn_ID, Pareto_ID):

        df_Results = WR.encapsulation()

        # get the indexes of the SPs selected by the last MP
        last_results = self.results_MP[Scn_ID][Pareto_ID][self.iter]
        lambdas = last_results.df_DW['lambda']
        MP_selection = lambdas[lambdas >= 0.999].index

        # df_Time
        ids = self.number_SP_solutions.iloc[0]
        df_Time = self.results_SP[ids['Scn_ID']][ids['Pareto_ID']][ids['Iter']][ids['FeasibleSolution']][ids['House']].df_Time

        # df_Performance
        df_Performance = self.get_final_SPs_results(MP_selection, 'df_Performance')
        df_Performance = df_Performance.groupby('Hub').sum()

        for column in ["Costs_op", "Costs_inv", "Costs_cft", "GWP_op", "GWP_constr"]:
            df_Performance.loc[:, column] = last_results.df_District[column]
        df_Performance.loc['Network', 'ANN_factor'] = df_Performance['ANN_factor'][0]

        if self.method["actors_cost"]:
            df_actor = self.results_MP[Scn_ID][Pareto_ID][ids['Iter']].df_District[['C_op_lod_dist', 'C_op_lod_own', 'C_op_dist_own', 'owner_inv', 'owner_portfolio']]
            df_Performance = pd.concat([df_Performance, df_actor], axis=1)
            df_Results.df_actors_tariff = self.results_MP[Scn_ID][Pareto_ID][ids['Iter']].df_actors_tariff
            df_Results.df_actors = self.results_MP[Scn_ID][Pareto_ID][ids['Iter']].df_actors

        # df_Grid_t
        df = self.get_final_SPs_results(MP_selection, 'df_Grid_t')
        df = df.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
        df = df.sort_index(level='Hub')
        uncontrollable_load = df.groupby(["Layer", "Period", "Time"]).sum()["Uncontrollable_load"]

        h_op = df_Time.dp
        h_op.iloc[-2:] = 1
        df_network = last_results.df_District_t.copy()
        df_network[["Network_supply", "Network_demand"]] = df_network[["Network_supply", "Network_demand"]].divide(h_op, axis=0, level='Period')
        df_network["Uncontrollable_load"] = uncontrollable_load
        df_network = pd.concat([df_network], keys=['Network'], names=['Hub']).reorder_levels(['Layer', 'Hub', 'Period', 'Time'])
        df_network = df_network.rename(columns={"Cost_demand_network": "Cost_demand", "Cost_supply_network": "Cost_supply",
                                                "Network_demand": "Grid_demand", "Network_supply": "Grid_supply"})
        for h in self.buildings_data.keys():
            for column in ["Cost_demand", "Cost_supply", "GWP_demand",  "GWP_supply"]:
                df.loc[pd.IndexSlice[:, h, :, :], column] = df_network[column].values
        df_Grid_t = pd.concat([df, df_network])


        # df_Unit
        df_Unit = self.get_final_MP_results(Pareto_ID=Pareto_ID, Scn_ID=Scn_ID)
        df_Unit = df_Unit.droplevel(['FeasibleSolution', 'Hub'])
        df_Unit = df_Unit.sort_index(level='Unit')

        # df_Unit_t
        df_Unit_t = self.get_final_SPs_results(MP_selection, 'df_Unit_t')
        df_Unit_t = df_Unit_t.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
        df_district_units = last_results.df_Unit_t
        df_Unit_t = pd.concat([df_Unit_t, df_district_units])

        # df_Annuals
        df = self.get_final_SPs_results(MP_selection, 'df_Annuals')
        df = df.sort_index(level='house')
        df = df.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
        df = df.sort_index(level='Layer')
        df = df.drop('Network', level='Hub')

        df_network = pd.DataFrame(self.district.grids.keys(), columns=["Layer"]) # build a df template to work on it
        df_network["Hub"] = "Network"
        df_network = df_network.set_index(["Layer", "Hub"])
        df_network[df.columns] = float("nan")

        for key in self.district.grids.keys():
            data = df_Grid_t.xs((key, "Network"), level=("Layer", "Hub"))[["Grid_demand", "Grid_supply"]]
            data = data.mul(df_Time.dp, level='Period', axis=0)
            df_network.loc[key, ['Demand_MWh', 'Supply_MWh']] = data.sum().values / 1000

        for i, unit in enumerate(self.district.UnitsOfDistrict):
            for key in self.district.district_units[i]["UnitOfLayer"]:
                data = df_Unit_t.xs((key, unit), level=('Layer','Unit')).mul(df_Time.dp, level='Period', axis=0).sum()/1000
                df_network.loc[(key, unit), :] = float('nan')
                df_network.loc[(key, unit), ['Demand_MWh', 'Supply_MWh']] = data[['Units_demand', 'Units_supply']].values
        df_Annuals = pd.concat([df, df_network]).sort_index()

        # df_Buildings_t
        df_Buildings_t = self.get_final_SPs_results(MP_selection, 'df_Buildings_t')
        df_Buildings_t = df_Buildings_t.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
        df_Buildings_t.sort_index(level='Hub')

        # df_External
        ids = self.number_SP_solutions.iloc[0]
        df_External = self.results_SP[ids["Scn_ID"]][ids["Pareto_ID"]][ids["Iter"]][ids["FeasibleSolution"]][ids["House"]].df_External

        # df_Index
        ids = self.number_SP_solutions.iloc[0]
        df_Index = self.results_SP[ids["Scn_ID"]][ids["Pareto_ID"]][ids["Iter"]][ids["FeasibleSolution"]][ids["House"]].df_Index

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
            df_PV_orientation = df_PV_orientation.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
            df_PV_orientation.sort_index(level='Hub')
            df_Results.df_PV_Surface = df_PV_Surface
            df_Results.df_PV_orientation = df_PV_orientation


        # set results
        df_Results.df_Performance = df_Performance
        df_Results.df_Annuals = df_Annuals
        df_Results.df_Buildings = df_Buildings
        df_Results.df_Unit = df_Unit
        df_Results.df_Unit_t = df_Unit_t
        df_Results.df_Grid_t = df_Grid_t
        df_Results.df_Buildings_t = df_Buildings_t

        if self.method["save_stream_t"]:
            df_Stream_t = self.get_final_SPs_results(MP_selection, 'df_Stream_t')
            df_Stream_t = df_Stream_t.droplevel(['Scn_ID', 'Pareto_ID', 'Iter', 'FeasibleSolution', 'house'])
            df_Results.df_Stream_t = df_Stream_t

        df_Results.df_Time = df_Time
        df_Results.df_External = df_External
        df_Results.df_Index = df_Index

        # df_lca
        df_lca_Units = self.get_final_SPs_results(MP_selection, 'df_lca_Units')
        df_lca_Units = df_lca_Units.droplevel(level=["Scn_ID", "Pareto_ID", "Iter", "FeasibleSolution", "house"])
        df_Results.df_lca_Units = pd.concat([df_lca_Units, last_results.df_lca_Units]).sort_index()
        df_Results.df_lca_Performance = last_results.df_lca_Performance
        df_Results.df_lca_operation = last_results.df_lca_operation

        return df_Results
