from reho.model.reho import *
from SALib.sample import sobol as sobol_sample
from SALib.analyze import sobol as sobol_analyze
from SALib.sample import morris as morris_sample
from SALib.analyze import morris as morris_analyze
import pandas as pd
import pickle
import matplotlib.pyplot as plt
from qmcpy import Sobol


class SensitivityAnalysis:
    """
    Perform a sensitivity analysis (SA): sampling, problem, store all optimizations results and the
    sensitivity of each tested parameters.

    Parameters
    ----------
    district_name
    reho_model : reho object
        Model of the district, obtained via the reho class.
    SA_type : str
        Type of SA (Morris or Sobol).
    sampling_parameters : int
        Number of trajectory for the sampling of the solution space.
    upscaling_factor : int
        To represent the effective ERA of the typical districts.

    Notes
    -------
    The framework is designed to be performed using TOTEX minimization but can easily be modified,
    just change the objective function of the reho_model and the KPI saved into OBJ in the function run_SA()
    """

    def __init__(self, district_name, reho_model, SA_type, sampling_parameters=0, upscaling_factor=1):

        self.district_name = district_name
        self.reho_model = reho_model
        self.SA_type = SA_type
        self.upscaling_factor = upscaling_factor
        self.sampling_parameters = sampling_parameters
        self.ID = str(self.district_name) + "_" + str(self.SA_type) + time.strftime("_%d%m%Y@%Hh%M")
        self.parameter = {}
        self.problem = {}
        self.sampling = []
        self.OBJ = []
        self.SA_results = {'num_optimizations': [], 'dict_df_results': [], 'dict_res_ES': []}
        self.sensitivity = []

    def save(self):
        path_to_SA_results = 'results/'
        file_path = os.path.join(path_to_SA_results, self.ID + '.pickle')
        f = open(file_path, 'wb')
        pickle.dump(self, f)
        f.close()

    def get_lists(self):
        unit_list = self.reho_model.infrastructure.UnitTypes.tolist()
        try:
            for excluded_unit in self.reho_model.scenario['exclude_units']:
                unit_list.remove(excluded_unit)
        except ValueError:
            pass
        KPI_list = ['OPEX', 'CAPEX', 'TOTEX', 'GWP']
        return unit_list, KPI_list

    def build_SA(self, unit_parameter=['Cost_inv1', 'Cost_inv2'], SA_parameter={}):
        """
        Description:
        - Generate the list of parameters for the SA, their values and type of variation range
        - Generate the problem of the SA, i.e. define the parameters and theirs bounds
        - Generate the sampling scheme of the SA

        Parameters
        ----------
        unit_parameter [list]: Units parameters wanted in the SA, by default all parameters are included
        SA_parameter [dict]: Parameters with their bounds set by the script

        Returns
        ---------
        parameter : dict
            Parameters
        problem : dict
            Parameters with their bounds
        sampling : array
            Sampling values
        """

        # 1) Generate the list of parameters

        default_units_values = self.reho_model.infrastructure.Units_Parameters  # Extract default unit values of the district
        units = np.unique([unit.split('_Building')[0] for unit in self.reho_model.infrastructure.Units_Parameters.index.to_list()]).tolist()

        for item in self.reho_model.scenario['exclude_units']:  # Removing excluded units
            try:
                units.remove(item)
            except ValueError:
                pass

        if unit_parameter != []:  # Add units parameters
            for unit in units:
                for parameter in unit_parameter:
                    value = default_units_values[default_units_values.index.str.contains(unit)][parameter].iloc[0]
                    name = str(unit) + "___" + str(parameter)
                    SA_parameter[name] = np.array([0.5, 2]) * value

        self.parameter = SA_parameter
        # 2) Generate a dictionary with all parameters and their bounds for the sampling

        problem = {
            'names': list(SA_parameter.keys()),
            'num_vars': len(SA_parameter.keys()),
            'bounds': list(SA_parameter.values())
        }
        self.problem = problem

        # 3) Description: Generate the sampling of the solution space

        if self.SA_type == "Sobol":
            sampling = sobol_sample.sample(self.problem, self.sampling_parameters, calc_second_order=False)  # between 500 and 1000, ideally a power of 2
        elif self.SA_type == "Morris":
            sampling = morris_sample.sample(self.problem,
                                            self.sampling_parameters)  # Sampling of the space, recommended p = 4 (level) r = 10 (trajectories), (Campolongo and Saltelli, 1997; Campolongo et al., 1999b; Saltelli et al., 2000)
        elif self.SA_type == "Monte_Carlo":
            dimension = len(self.problem["bounds"])
            sampler = Sobol(dimension)
            sample = sampler.gen_samples(self.sampling_parameters)
            l_bounds_values = [bound[0] for bound in self.problem["bounds"]]
            u_bounds_values = [bound[1] for bound in self.problem["bounds"]]
            sampling = qmc.scale(sample, l_bounds_values, u_bounds_values)
        else:
            sampling = None
        self.sampling = sampling

    def run_SA(self, save_inter=True, save_inter_nb_iter=50, save_time_opt=True, intermediate_start=0):
        """
        Launch all optimizations of the SA and store their results

        Parameters
        -----------

        save_inter : boolean
            Enable intermediary save
        save_inter_nb_iter : int
            Step at which the intermediary save is done
        save_time_opt : boolean
            Ceates a .txt file and write the time for each optimization
        intermediate_start :int
            Starts the SA from a specific sampling point

        Returns
        ---------
        SA_results : dict
            Contains the number of the optimization and a dictionary regrouping all main results of the optimizations
        OBJ : list
            Values of the objective function for each optimization
        """

        path_to_SA_results = 'results/'
        folder = os.path.join(path_to_SA_results, "computational_results")
        if not os.path.exists(path_to_SA_results):
            os.makedirs(path_to_SA_results)
        if not os.path.exists(folder):
            os.makedirs(folder)

        # Extract all attributs of the reho model
        grids = self.reho_model.infrastructure.grids
        scenario = self.reho_model.scenario
        units = infrastructure.initialize_units(scenario, grids)
        n_houses = len(self.reho_model.buildings_data)

        # Modify the attributs of the model and run SA
        for j in range(intermediate_start, len(self.sampling)):
            print("Optimizations number", str(j + 1) + "/" + str(len(self.sampling)))

            sample = self.sampling[j]
            for s, value in enumerate(sample):
                parameter = list(self.parameter.keys())[s]

                if parameter == 'Elec_retail':
                    grids["Electricity"]["Cost_supply_cst"] = value
                elif parameter == 'Elec_feedin':
                    grids["Electricity"]["Cost_demand_cst"] = value
                elif parameter == 'NG_retail':
                    grids["NaturalGas"]["Cost_supply_cst"] = value
                elif parameter == 'Wood_retail':
                    grids["Wood"]["Cost_supply_cst"] = value
                elif parameter == 'Oil_retail':
                    grids["Oil"]["Cost_supply_cst"] = value

                elif "___" in parameter:
                    for unit_id in range(len(units['building_units'])):
                        if units['building_units'][unit_id]['name'] == parameter.split("___")[0]:
                            units['building_units'][unit_id][parameter.split("___")[1]] = value
                else:
                    self.reho_model.parameters[parameter] = np.array([value] * n_houses)

            self.reho_model.infrastructure = infrastructure.Infrastructure(self.reho_model.qbuildings_data, units, grids)

            try:
                tic = time.perf_counter()
                self.reho_model.single_optimization(Pareto_ID=j)  # Optimize the modified model
                toc = time.perf_counter()
                time_spent = toc - tic

                self.reho_model.initialize_optimization_tracking_attributes()

                if save_time_opt:
                    file_name = os.path.join(folder, str(self.SA_type) + '_time.txt')
                    function = 'w' if not os.path.exists(folder) else 'a+'
                    with open(file_name, function) as f:
                        f.write(str(round(time_spent)) + "\n")

                if save_inter:  # Intermediary save
                    if np.mod(j, save_inter_nb_iter) == 0 or j == (len(self.sampling) - 1):
                        self.save()
                        os.system('cmd /c "ampl_lic restart"')  # restart ampl license to avoid crashes

            except KeyboardInterrupt:
                return

    def calculate_SA(self):
        """
        Description: Compute the sensitivity indices with the objective values and the problem
        """
        if self.SA_type == "Sobol":
            sensitivity = sobol_analyze.analyze(self.problem, np.array(self.OBJ), print_to_console=True, calc_second_order=False)
        if self.SA_type == "Morris":
            sensitivity = morris_analyze.analyze(self.problem, self.sampling, np.array(self.OBJ), print_to_console=True)
        self.sensitivity = sensitivity

    def plot_Morris(self, save=False):
        fig, ax = plt.subplots(figsize=(8, 8))
        df_ = pd.DataFrame(self.sensitivity).sort_values('mu_star', ascending=False).copy()
        df_.reset_index(inplace=True, drop=True)
        for j, row in df_.iterrows():
            plt.scatter(row['mu_star'], y=row['sigma'], label=row["names"], c='blue', alpha=0.3)
            if row.name < 5:
                plt.annotate(row["names"], xy=(row["mu_star"], row["sigma"]), textcoords="offset pixels",
                             xytext=(20, 20), arrowprops=dict(arrowstyle="-", connectionstyle="arc3"), fontsize=15)
        plt.plot(ax.get_xlim(), ax.get_xlim(), linestyle='dotted', color='black')
        plt.xlabel('$\\mu^*$ [-]', fontsize=18)
        plt.ylabel('$\\sigma$ [-]', fontsize=18)
        plt.xticks(fontsize=15)
        plt.yticks(fontsize=15)
        plt.title(self.district_name, fontsize=25)
        plt.axis('square')

        if save:
            path_to_SA_results = 'results/'
            plt.savefig(path_to_SA_results + 'Morris_' + self.district_name + '.png', format='png', dpi=300)
        plt.show()

    def extract_results(self, reho_model, j):
        unit_list, KPI_list = self.get_lists()

        dict_res = {
            'Annual_Network_Exchange': reho_model.results[self.SA_type][0].df_Annuals.xs("Network", level=1).loc[["Electricity", "NaturalGas"]][['Demand_MWh', 'Supply_MWh']],
            'Elec_Network_t': reho_model.results[self.SA_type][0].df_Grid_t.xs("Network", level="Hub").xs("Electricity")[['Grid_demand', 'Grid_supply']],
            'NG_Network_t': reho_model.results[self.SA_type][0].df_Grid_t.xs("Network", level="Hub").xs("NaturalGas")[['Grid_demand', 'Grid_supply']],
            'df_Unit': reho_model.results[self.SA_type][0].df_Unit['Units_Mult'],
            'Performance_Network': reho_model.results[self.SA_type][0].df_Performance.xs("Network")
        }

        self.SA_results['num_optimizations'].append(j)
        self.SA_results['dict_df_results'].append(dict_res)
        self.OBJ.append(reho_model.results[self.SA_type][0].df_Performance['Costs_inv']['Network']
                        + reho_model.results[self.SA_type][0].df_Performance['Costs_op']['Network']
                        + reho_model.results[self.SA_type][0].df_Performance['Costs_rep']['Network'])

        df_Grid_t = reho_model.results[self.SA_type][0].df_Grid_t[['Grid_demand', 'Grid_supply']].groupby(['Layer', 'Hub', 'Period']).sum()
        df_Annuals = reho_model.results[self.SA_type][0].df_Annuals
        df_Unit_t = reho_model.results[self.SA_type][0].df_Unit_t.groupby(['Layer', 'Unit', 'Period']).sum()

        dict_res_ES = {'E_sector': df_Annuals.groupby(['Layer']).sum(),
                       'InAndOutDistrict': df_Grid_t.xs("Network", level="Hub"),
                       'E_unit': {},
                       'E_resource': df_Unit_t[['Units_demand', 'Units_supply']].groupby(['Layer', 'Period']).sum(),
                       'E_unit_PV': df_Unit_t.xs("Electricity", level="Layer").query('Unit.str.startswith("PV")').groupby(['Period']).sum()['Units_supply']}

        for unit in unit_list:
            dict_res_ES['E_unit'][unit] = df_Annuals.query('Hub.str.startswith("' + str(unit) + '")')['Supply_MWh'].values.sum()

        self.SA_results['dict_res_ES'].append(dict_res_ES)
