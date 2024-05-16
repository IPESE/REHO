import itertools as itertools
import logging

from amplpy import AMPL, Environment

import reho.model.preprocessing.EV_profile_generator as EV_gen
import reho.model.preprocessing.buildings_profiles as buildings_profiles
import reho.model.preprocessing.emissions_parser as emissions
import reho.model.preprocessing.weather as weather
from reho.model.preprocessing.QBuildings import *


__doc__ = """
File for handling data and optimization for an AMPL sub-problem.
"""


class SubProblem:
    """
    Collects all the data input and sends it an AMPL model, solves the optimization.

    Parameters
    ----------
    district : district
        Instance of the class district, contains relevant structure in the district such as Units or grids.
    buildings_data : dict
        Building-specific data.
    local_data : dict
        Location-specific data.
    parameters : dict, optional
        Dictionary containing 'new' parameters for the AMPL model. If incomplete, uses data from buildings_data.
    set_indexed : dict, optional
        Dictionary containing new data which are indexed sets in the AMPL model.
    cluster : dict, optional
        Dictionary containing information about clustering.
    scenario : dict, optional
        Dictionary containing the objective function, EMOO constraints, and additional constraints.
    method : dict, optional
        Dictionary containing different options for methodology choices.
    solver : str, optional
        Chosen solver for AMPL (gurobi, cplex, HiGHS, cbc...).
    qbuildings_data : dict, optional
        Input data for the buildings.

    See also
    --------
    reho.model.reho.reho
    reho.model.master_problem.MasterProblem

    """

    def __init__(self, district, buildings_data, local_data, parameters, set_indexed, cluster, scenario, method, solver, qbuildings_data=None):

        self.buildings_data_sp = buildings_data
        if method['use_facades']:
            self.facades_sp = qbuildings_data['facades_data']
            self.shadows_sp = qbuildings_data['shadows_data']
        if method['use_pv_orientation']:
            self.roofs_sp = qbuildings_data['roofs_data']
        self.infrastructure_sp = district
        self.local_data = local_data
        self.parameters_sp = parameters
        self.set_indexed_sp = set_indexed
        self.cluster_sp = cluster
        if 'exclude_units' not in scenario:
            scenario['exclude_units'] = []
        if 'enforce_units' not in scenario:
            scenario['enforce_units'] = []
        self.scenario_sp = scenario
        self.method_sp = method
        self.solver = solver
        self.parameters_to_ampl = dict()

    def build_model_without_solving(self):
        File_ID = weather.get_cluster_file_ID(self.cluster_sp)

        self.initialize_parameters_for_ampl_and_python()
        ampl = self.init_ampl_model()
        ampl = self.set_weather_data(ampl)
        ampl = self.set_ampl_sets(ampl)
        self.set_emissions_profiles(File_ID)
        self.set_temperature_and_EVs_profiles()
        self.set_HP_parameters(ampl)
        self.set_streams_temperature(ampl)
        if self.method_sp['use_pv_orientation']:
            self.set_PV_models(ampl)
        ampl = self.send_parameters_and_sets_to_ampl(ampl)
        ampl = self.set_scenario(ampl)

        return ampl

    def initialize_parameters_for_ampl_and_python(self):
        # -----------------------------------------------------------------------------------------------------#
        # Default methods
        # -----------------------------------------------------------------------------------------------------#
        self.method_sp = initialize_default_methods(self.method_sp)
        # -----------------------------------------------------------------------------------------------------#
        # Input Parameter Preparation
        # -----------------------------------------------------------------------------------------------------#

        # prepare input parameter which are used in AMPL model

        buildings_to_ampl = ['ERA', 'SolarRoofArea', 'U_h', 'HeatCapacity',
                             'T_comfort_min_0', 'Th_supply_0', 'Th_return_0', 'Tc_supply_0', 'Tc_return_0']

        for parameter in buildings_to_ampl:
            self.parameters_to_ampl[parameter] = {}
            for i, b in enumerate(self.buildings_data_sp):
                if parameter not in self.parameters_sp:
                    self.parameters_to_ampl[parameter][b] = self.buildings_data_sp[b][parameter]
                else:
                    self.parameters_to_ampl[parameter][b] = self.parameters_sp[parameter]

    def init_ampl_model(self):
        if os.getenv('USE_AMPL_MODULES', False):
            from amplpy import modules
            modules.load()
            ampl = AMPL()
        else:
            try:
                ampl = AMPL(Environment(os.environ["AMPL_PATH"]))
            except:
                raise Exception("AMPL_PATH is not defined. Please include a .env file at the project root (e.g., AMPL_PATH='C:/AMPL')")

        # -AMPL (GNU) OPTIONS
        ampl.setOption('solution_round', 11)

        ampl.setOption('presolve_eps', 1e-4)  # -ignore difference between upper and lower bound by this tolerance
        ampl.setOption('presolve_inteps', 1e-6)  # -tolerance added/substracted to each upper/lower bound
        ampl.setOption('presolve_fixeps', 1e-9)
        if not self.method_sp['print_logs']:
            ampl.setOption('show_stats', 0)
            ampl.setOption('solver_msg', 0)

        # -SOLVER OPTIONS
        ampl.setOption('solver', self.solver)
        if self.solver == "gurobi":
            ampl.eval("option gurobi_options 'NodeFileStart=0.5';")
        if self.solver == "cplex":
            ampl.eval("option cplex_options 'bestbound mipgap=5e-7 integrality=1e-09 timing=1 timelimit=3000';")

        # -----------------------------------------------------------------------------------------------------#
        #  MODEL FILES
        # -----------------------------------------------------------------------------------------------------#
        ampl.cd(path_to_ampl_model)
        ampl.read('sub_problem.mod')

        # Energy conversion Units
        ampl.cd(path_to_units)
        if 'ElectricalHeater' in self.infrastructure_sp.UnitTypes:
            ampl.read('electrical_heater.mod')
        if 'NG_Boiler' in self.infrastructure_sp.UnitTypes:
            ampl.read('ng_boiler.mod')
        if 'OIL_Boiler' in self.infrastructure_sp.UnitTypes:
            ampl.read('oil_boiler.mod')
        if 'WOOD_Stove' in self.infrastructure_sp.UnitTypes:
            ampl.read('wood_stove.mod')
        if 'HeatPump' in self.infrastructure_sp.UnitTypes:
            ampl.read('heatpump.mod')
        if 'Air_Conditioner' in self.infrastructure_sp.UnitTypes:
            ampl.read('air_conditioner.mod')
        if 'ThermalSolar' in self.infrastructure_sp.UnitTypes:
            ampl.read('thermal_solar.mod')
        if 'DataHeat' in self.infrastructure_sp.UnitTypes:
            ampl.read('data_heat.mod')
        if 'NG_Cogeneration' in self.infrastructure_sp.UnitTypes:
            ampl.read('ng_cogeneration.mod')
        if 'DHN_hex' in self.infrastructure_sp.UnitTypes:
            ampl.read('DHN_HEX.mod')
            ampl.read('DHN_pipes.mod')
        if 'PV' in self.infrastructure_sp.UnitTypes:
            if self.method_sp['use_pv_orientation']:
                ampl.read('pv_orientation.mod')
            else:
                ampl.read('pv.mod')

        # district Units
        if 'EV' in self.infrastructure_sp.UnitTypes:
            ampl.cd(path_to_district_units)
            ampl.read('evehicle.mod')
        # Storage Units
        ampl.cd(path_to_units_storage)
        if 'WaterTankSH' in self.infrastructure_sp.UnitTypes:
            ampl.read('heatstorage.mod')
        if 'WaterTankDHW' in self.infrastructure_sp.UnitTypes:
            ampl.read('dhwstorage.mod')
        if 'Battery' in self.infrastructure_sp.UnitTypes:
            ampl.read('battery.mod')
        ampl.cd(path_to_ampl_model)

        # Objectives, epsilon constraints and specific constraints
        ampl.read('scenario.mod')

        # TODO: integrate Jules units into district structure (avoid using ampl eval)
        if self.method_sp['use_Storage_Interperiod']:
            ampl.eval(
                'set UnitsOfStorage := setof{u in UnitsOfType["Battery_interperiod"] union UnitsOfType["PTES_storage"]'
                'union UnitsOfType["PTES_conversion"] union UnitsOfType["CH4storage"]'
                'union UnitsOfType["H2storage"] union UnitsOfType["SOEFC"]'
                'union UnitsOfType["Methanizer"] union UnitsOfType["FuelCell"]'
                'union UnitsOfType["Electrolyzer"] union UnitsOfType["WaterTankSH_interperiod"]'
                'union UnitsOfType["SolidLiquidLHS"]'
                '} u;')

            # Storage Units
            ampl.cd(path_to_units_storage)
            ampl.read('h2_storage.mod')
            ampl.read('heatstorage_interperiod.mod')
            ampl.read('LHS_storage.mod')
            ampl.read('battery_interperiod.mod')
            # ampl.read('PTES_aggregated.mod')
            ampl.read('PTES_split.mod')
            ampl.read('CH4_tank.mod')

            # H2 Units
            ampl.cd(path_to_units_h2)
            ampl.read('fuel_cell.mod')
            ampl.read('electrolyser.mod')
            ampl.read('SOEFC.mod')
            ampl.read('methanizer.mod')

            ampl.cd(path_to_units)
            ampl.read('heat_curtailment.mod')
            ampl.cd(path_to_ampl_model)

        return ampl

    def set_weather_data(self, ampl):
        # -----------------------------------------------------------------------------------------------------#
        # -Setting DATA
        # -----------------------------------------------------------------------------------------------------#

        ampl.cd(path_to_clustering)

        File_ID = weather.get_cluster_file_ID(self.cluster_sp)

        ampl.readData('frequency_' + File_ID + '.dat')
        ampl.readData('index_' + File_ID + '.dat')
        self.parameters_to_ampl['T_ext'] = np.loadtxt(os.path.join(path_to_clustering, 'T_' + File_ID + '.dat'))
        self.parameters_to_ampl['I_global'] = np.loadtxt(os.path.join(path_to_clustering, 'Irr_' + File_ID + '.dat'))

        ampl.cd(path_to_ampl_model)

        return ampl

    def set_ampl_sets(self, ampl):
        # -----------------------------------------------------------------------------------------------------#
        # Design Structure: Building Cluster, Units and Layers
        # -----------------------------------------------------------------------------------------------------#

        if self.method_sp['use_discrete_units']:
            self.infrastructure_sp.set_discretize_unit_size()

        self.parameters_to_ampl['Units_flowrate'] = self.infrastructure_sp.Units_flowrate
        self.parameters_to_ampl['Grids_flowrate'] = self.infrastructure_sp.Grids_flowrate
        self.parameters_to_ampl['Grids_Parameters'] = self.infrastructure_sp.Grids_Parameters
        self.parameters_to_ampl['Grids_Parameters_lca'] = self.infrastructure_sp.Grids_Parameters_lca
        self.parameters_to_ampl['Units_Parameters'] = self.infrastructure_sp.Units_Parameters
        self.parameters_to_ampl['Units_Parameters_lca'] = self.infrastructure_sp.Units_Parameters_lca
        self.parameters_to_ampl['Streams_H'] = self.infrastructure_sp.Streams_H

        for key in self.infrastructure_sp.HP_parameters:
            self.parameters_to_ampl[key] = self.infrastructure_sp.HP_parameters[key]

        for s in self.infrastructure_sp.Set:
            if isinstance(self.infrastructure_sp.Set[s], np.ndarray):
                ampl.getSet(str(s)).setValues(self.infrastructure_sp.Set[s])
            elif isinstance(self.infrastructure_sp.Set[s], dict):
                for i, instance in ampl.getSet(str(s)):
                    instance.setValues(self.infrastructure_sp.Set[s][i])
            else:
                raise ValueError('Type Error setting AMPLPY Set', s)

        all_units = [unit for unit, value in ampl.getVariable('Units_Use').instances()]
        for i in all_units:
            for u in self.scenario_sp['exclude_units']:
                if 'district' not in i and u in i:  # unit at the building scale
                    ampl.getVariable('Units_Use').get(str(i)).fix(0)
                elif u in all_units:  # unit at the district scale with problem definition at the district scale
                    ampl.getVariable('Units_Use').get(str(u)).fix(0)

            for u in self.scenario_sp['enforce_units']:
                if 'district' not in i and u in i:  # unit at the building scale
                    ampl.getVariable('Units_Use').get(str(i)).fix(1)  # !!Fmin = 0, leaves the option to exclude unit
                elif u in all_units:  # unit at the district scale with problem definition at the district scale
                    ampl.getVariable('Units_Use').get(str(u)).fix(1)

        return ampl

    def set_emissions_profiles(self, File_ID):

        df_em = emissions.return_typical_emission_profiles(self.cluster_sp, File_ID, 'GWP100a', self.local_data["df_Timestamp"],
                                                           self.local_data["df_Emissions"])
        if self.method_sp['use_dynamic_emission_profiles']:
            self.parameters_to_ampl['GWP_supply'] = df_em
            self.parameters_to_ampl['GWP_demand'] = df_em.rename(columns={'GWP_supply': 'GWP_demand'})
            self.parameters_to_ampl['Gas_emission'] = self.infrastructure_sp.Grids_Parameters.drop('Electricity').drop(
                columns=['Cost_demand_cst', 'Cost_supply_cst'])

    def set_temperature_and_EVs_profiles(self):

        # Reference temperature
        self.parameters_to_ampl['T_comfort_min'] = buildings_profiles.reference_temperature_profile(self.parameters_to_ampl, self.cluster_sp)

        # Set default EV plug out profile if EVs are allowed
        if "EV_plugged_out" not in self.parameters_to_ampl:
            if len(self.infrastructure_sp.UnitsOfDistrict) != 0:
                if "EV_district" in self.infrastructure_sp.UnitsOfDistrict:
                    self.parameters_to_ampl["EV_plugged_out"], self.parameters_to_ampl["EV_plugging_in"] = EV_gen.generate_EV_plugged_out_profiles_district(
                        self.cluster_sp, self.local_data["df_Timestamp"])

    def set_HP_parameters(self, ampl):
        # --------------- Heat Pump ---------------------------------------------------------------------------#
        # T = 7.5C for Lake, T = 12C for underground, T = 16C for CO2

        df_end = ampl.getParameter('TimeEnd').getValues().toPandas()
        timesteps = int(df_end['TimeEnd'].sum())  # total number of timesteps
        sources = []
        if 'T_source' in self.parameters_sp:
            sources = self.parameters_sp['T_source'].keys()

        T_source = []
        if 'HeatPump' in self.infrastructure_sp.UnitsOfType:
            for unit in self.infrastructure_sp.UnitsOfType['HeatPump']:
                if any([i in unit for i in sources]):  # if T_source defined from script
                    source = list(itertools.compress(sources, [i in unit for i in sources]))[0]
                    T_source = np.concatenate([T_source, np.repeat(self.parameters_sp['T_source'][source], timesteps)])
                elif 'Air' in unit:
                    T_source = np.concatenate([T_source, self.parameters_to_ampl['T_ext']])
                elif 'Lake' in unit:
                    T_source = np.concatenate([T_source, np.repeat(7.5, timesteps)])
                elif 'Geothermal' in unit:
                    T_source = np.concatenate([T_source, np.repeat(8, timesteps)])
                elif 'Anergy' in unit:
                    T_source = np.concatenate([T_source, np.repeat(16, timesteps)])
                elif 'DHN' in unit:
                    if 'T_DHN_supply' and 'T_DHN_return' in self.parameters_sp:
                        T_DHN_mean = (self.parameters_sp["T_DHN_supply"] + self.parameters_sp["T_DHN_return"]) / 2
                    elif 'T_DHN_supply_cst' and 'T_DHN_return_cst' in self.parameters_sp:
                        T_DHN_mean = (self.parameters_sp["T_DHN_supply_cst"] + self.parameters_sp["T_DHN_return_cst"]) / 2
                        T_DHN_mean = np.repeat(T_DHN_mean, timesteps)
                    else:
                        T_DHN_mean = np.repeat(16, timesteps)
                    T_source = np.concatenate([T_source, T_DHN_mean])
                else:
                    raise Exception('HP source undefined')

            self.parameters_to_ampl['T_source'] = T_source
            if 'T_source' in self.parameters_sp:
                del self.parameters_sp["T_source"]

        sources = []
        if 'T_source_cool' in self.parameters_sp:
            sources = self.parameters_sp['T_source_cool'].keys()

        T_source_cool = np.array([])
        if 'Air_Conditioner' in self.infrastructure_sp.UnitsOfType:
            for unit in self.infrastructure_sp.UnitsOfType['Air_Conditioner']:
                # if T_source_cool defined from script
                if any([i in unit for i in sources]):
                    source = list(itertools.compress(sources, [i in unit for i in sources]))[0]
                    T_source_cool = np.concatenate([T_source_cool, np.repeat(self.parameters_sp['T_source_cool'][source], timesteps)])

                elif "DHN" in unit:
                    if 'T_DHN_supply' and 'T_DHN_return' in self.parameters_sp:
                        T_DHN_mean = (self.parameters_sp["T_DHN_supply"] + self.parameters_sp["T_DHN_return"]) / 2
                    elif 'T_DHN_supply_cst' and 'T_DHN_return_cst' in self.parameters_sp:
                        T_DHN_mean = (self.parameters_sp["T_DHN_supply_cst"] + self.parameters_sp["T_DHN_return_cst"]) / 2
                        T_DHN_mean = np.repeat(T_DHN_mean, timesteps)
                    else:
                        T_DHN_mean = np.repeat(16, timesteps)
                    T_source_cool = np.concatenate([T_source_cool, T_DHN_mean])

                elif "Air" in unit:
                    T_source_cool = np.concatenate([T_source_cool, self.parameters_to_ampl['T_ext']])

                else:
                    raise Exception('AC sink undefined')

            self.parameters_to_ampl['T_source_cool'] = T_source_cool
            if 'T_source_cool' in self.parameters_sp:
                del self.parameters_sp["T_source_cool"]

    def set_streams_temperature(self, ampl):

        df_end = ampl.getParameter('TimeEnd').getValues().toPandas()
        timesteps = int(df_end['TimeEnd'].sum())
        df_Streams_T = pd.DataFrame(columns=["Period", "Time", "Streams", "Streams_Tout", "Streams_Tin"])
        df_Streams_T = df_Streams_T.set_index(["Period", "Time", "Streams"])

        index = [[(i, j + 1) for j in list(range(int(df_end["TimeEnd"][i])))] for i in df_end.index]
        index = [j for i in index for j in i]
        index = pd.MultiIndex.from_tuples(index, names=["Period", "Time"])

        for bui in self.infrastructure_sp.houses:
            for unit_data in self.infrastructure_sp.houses[bui]["units"]:
                for i, T_level in enumerate(unit_data["StreamsOfUnit"]):
                    stream = unit_data["name"] + '_' + bui + '_' + T_level
                    df = pd.DataFrame(np.repeat(stream, timesteps), index=index, columns=["Streams"])
                    df["Streams_Tout"] = unit_data["stream_Tout"][i]
                    df["Streams_Tin"] = unit_data["stream_Tin"][i]
                    df.set_index("Streams", append=True, inplace=True)
                    df_Streams_T = pd.concat([df_Streams_T, df])
            for stream in self.infrastructure_sp.StreamsOfBuilding[bui]:
                df = pd.DataFrame(np.repeat(stream, timesteps), index=index, columns=["Streams"])
                df["Streams_Tout"] = 40  # default value that is changed in data_stream.dat
                df["Streams_Tin"] = 50  # default value that is changed in data_stream.dat
                df.set_index("Streams", append=True, inplace=True)
                df_Streams_T = pd.concat([df_Streams_T, df])

        self.parameters_to_ampl['streams_T'] = df_Streams_T.reorder_levels([2, 0, 1])

    def set_PV_models(self, ampl):
        # --------------- PV Panels ---------------------------------------------------------------------------#

        df_dome = skydome.skydome_to_df(self.local_data)
        self.parameters_to_ampl['Sin_a'] = df_dome.Sin_a.values
        self.parameters_to_ampl['Cos_a'] = df_dome.Cos_a.values
        self.parameters_to_ampl['Sin_e'] = df_dome.Sin_e.values
        self.parameters_to_ampl['Cos_e'] = df_dome.Cos_e.values

        df_irr = skydome.irradiation_to_df(ampl, self.local_data["df_Irradiation"], self.local_data["df_Timestamp"])
        self.parameters_to_ampl['Irr'] = df_irr
        # On Flat Roofs optimal Orientation of PV panel is chosen by the solver, Construction of possible Configurations
        # Azimuth = np.array([])
        # Tilt = np.array([])
        Azimuth = np.array(range(160, 210, 10))
        Tilt = np.array([5, 10, 20, 30, 40])

        All_azimuth = np.repeat(Azimuth, len(Tilt))
        All_tilt = np.tile(Tilt, len(Azimuth))

        Configs_flat_roof = [None] * (len(All_azimuth) + len(All_tilt))
        Configs_flat_roof[::2] = All_azimuth
        Configs_flat_roof[1::2] = All_tilt
        Configs_flat_roof.append(180)
        Configs_flat_roof.append(0)

        np_surface = np.array([])
        np_flat_roof = np.array([])
        np_tilted_roof = np.array([])
        dict_SurfaceofHouse = {}
        dict_config = {}
        df_SurfaceArea = pd.DataFrame()
        self.set_indexed_sp['Surface'] = np.array([])

        for b in self.buildings_data_sp:

            df_roofs = self.roofs_sp[self.roofs_sp['id_building'] == self.buildings_data_sp[b]['id_building']]
            # df_profiles is not used, but precalculated by the ampl model
            #  Surface/ Roof Area Values are selected matching to egid
            np_surface = np.append(np_surface, df_roofs['ROOF_ID'].values)
            dict_SurfaceofHouse[b] = df_roofs['ROOF_ID'].values

            # Flat roof if Tilt of Roof is either 1 or 0/ Tilted Roofs are all opposite to flat roofs
            Flat_roofs = df_roofs.ROOF_ID.loc[(df_roofs['TILT'] == 1) | (df_roofs['TILT'] == 0)].values
            Tilted_roofs = df_roofs.ROOF_ID.loc[(df_roofs['TILT'] != 1) & (df_roofs['TILT'] != 0)].values
            np_flat_roof = np.append(np_flat_roof, Flat_roofs)
            np_tilted_roof = np.append(np_tilted_roof, Tilted_roofs)

            # PV Panels are orientated flat on tilted roof --> one configuration possibility
            for tr in Tilted_roofs:
                az = df_roofs.AZIMUTH.loc[(df_roofs['ROOF_ID'] == tr)].values
                ti = df_roofs.TILT.loc[(df_roofs['ROOF_ID'] == tr)].values
                dict_config[tr] = [az[0], ti[0]]

            for fr in Flat_roofs:
                dict_config[fr] = Configs_flat_roof

            # get area of surface
            index = pd.MultiIndex.from_tuples([(b, s) for s in df_roofs['ROOF_ID'].values])
            df = pd.DataFrame(df_roofs['AREA'].values, index=index, columns=['HouseSurfaceArea'])
            df_SurfaceArea = pd.concat([df_SurfaceArea, df])

        self.parameters_to_ampl['HouseSurfaceArea'] = df_SurfaceArea
        self.set_indexed_sp['Surface'] = np.append(self.set_indexed_sp['Surface'], np_surface)
        self.set_indexed_sp['SurfaceOfHouse'] = dict_SurfaceofHouse

        self.set_indexed_sp['SurfaceTypes'] = np.array(['Flat_roof', 'Tilted_roof', 'Facades'])
        self.set_indexed_sp['SurfaceOfType'] = {'Flat_roof': np_flat_roof, 'Tilted_roof': np_tilted_roof, 'Facades': []}
        self.set_indexed_sp['ConfigOfSurface'] = dict_config

        np_facades = np.array([])
        df_limit_angle = pd.DataFrame()

        if self.method_sp['use_facades']:
            for b in self.buildings_data_sp:
                df_facades = self.facades_sp[self.facades_sp['id_building'] == self.buildings_data_sp[b]['id_building']]
                df_shadows = self.shadows_sp[self.shadows_sp['id_building'] == self.buildings_data_sp[b]['id_building']]
                facades = df_facades['Facades_ID']
                np_facades = np.append(np_facades, facades)
                df_shadow = return_shadows_id_building(self.buildings_data_sp[b]['id_building'], df_shadows, self.local_data)
                df_shadow = pd.concat([df_shadow], keys=[b], names=['House'])
                df_limit_angle = pd.concat([df_limit_angle, df_shadow])
                for fc in facades:
                    az = df_facades.AZIMUTH.loc[(df_facades['Facades_ID'] == fc)].values
                    # Tilt is not available for facades
                    # ti = df_facades.TILT.loc[(df_facades['Facades_ID'] == fc)].values
                    ti = 0
                    self.set_indexed_sp['ConfigOfSurface'][fc] = [az[0], ti]
                self.set_indexed_sp['SurfaceOfHouse'][b] = np.append(
                    self.set_indexed_sp['SurfaceOfHouse'][b],
                    df_facades['Facades_ID'].values)
                index = pd.MultiIndex.from_tuples([(b, f) for f in facades])
                df = pd.DataFrame(df_facades['AREA'].values, index=index,
                                  columns=['HouseSurfaceArea'])  # Pq attribuer ici HouseSurfaceArea comme l'aire des facades?
                self.parameters_to_ampl['HouseSurfaceArea'] = pd.concat(
                    [self.parameters_to_ampl['HouseSurfaceArea'], df])
                # self.parameters_to_ampl['HouseSurfaceArea'].sort_index(inplace = True)

            if not df_limit_angle.empty:
                # self.parameters_to_ampl['Limiting_angle_shadow'] = df_limit_angle.rename(columns={0:'Limiting_angle_shadow'})
                self.parameters_to_ampl['Limiting_angle_shadow'] = df_limit_angle
                self.set_indexed_sp['SurfaceOfType']['Facades'] = np_facades
                self.set_indexed_sp['Surface'] = np.append(self.set_indexed_sp['Surface'], np_facades)

    def send_parameters_and_sets_to_ampl(self, ampl):
        # -----------------------------------------------------------------------------------------------------#
        # Load data to AMPLPY depending on their type
        # -----------------------------------------------------------------------------------------------------#

        for key in self.parameters_sp:
            self.parameters_to_ampl[key] = self.parameters_sp[key]

        # set new indexed sets
        for s in self.set_indexed_sp:
            if isinstance(self.set_indexed_sp[s], np.ndarray):
                ampl.getSet(str(s)).setValues(self.set_indexed_sp[s])
            elif isinstance(self.set_indexed_sp[s], dict):
                for i, instance in ampl.getSet(str(s)):
                    try:
                        instance.setValues(self.set_indexed_sp[s][i])
                    except ValueError:
                        instance.setValues([self.set_indexed_sp[s][i]])
            else:
                raise ValueError('Type Error setting AMPLPY Set', s)

        # set new input Parameter
        for i in self.parameters_to_ampl:

            if isinstance(self.parameters_to_ampl[i], np.ndarray):
                Para = ampl.getParameter(i)
                Para.setValues(self.parameters_to_ampl[i])

            elif isinstance(self.parameters_to_ampl[i], list):
                Para = ampl.getParameter(i)
                Para.setValues(np.array(self.parameters_to_ampl[i]))

            elif isinstance(self.parameters_to_ampl[i], pd.DataFrame):
                ampl.setData(self.parameters_to_ampl[i])

            elif isinstance(self.parameters_to_ampl[i], pd.Series):
                self.parameters_to_ampl[i].name = i
                df = pd.DataFrame(self.parameters_to_ampl[i])
                ampl.setData(df)

            elif isinstance(self.parameters_to_ampl[i], dict):
                Para = ampl.getParameter(i)
                Para.setValues(self.parameters_to_ampl[i])

            elif isinstance(self.parameters_to_ampl[i], float):
                Para = ampl.getParameter(i)
                Para.setValues([self.parameters_to_ampl[i]])

            elif isinstance(self.parameters_to_ampl[i], int):
                Para = ampl.getParameter(i)
                Para.setValues([self.parameters_to_ampl[i]])

            else:
                raise ValueError('Type Error setting AMPLPY Parameter', i)

        # TODO remove data_stream.dat
        ampl.readData('data_stream.dat')
        if self.method_sp['use_Storage_Interperiod']:
            ampl.readData('data_stream_storage.dat')

        return ampl

    def set_scenario(self, ampl):

        # Set objective function
        for objective_name, objective_formulation in ampl.getObjectives():
            objective_formulation.drop()

        if 'Objective' in self.scenario_sp:
            try:
                ampl.getObjective(self.scenario_sp['Objective']).restore()
            except KeyError:
                ampl.getObjective('TOTEX').restore()
                logging.warning('Objective function "' + str(self.scenario_sp['Objective']) +
                                '" was not found in ampl model, TOTEX minimization was set instead.')
        else:
            ampl.getObjective('TOTEX').restore()
            logging.warning('No objective function was found in scenario dictionary, TOTEX minimization was set instead.')

        # Set epsilon constraints
        ampl.getConstraint('EMOO_CAPEX_constraint').drop()
        ampl.getConstraint('EMOO_OPEX_constraint').drop()
        ampl.getConstraint('EMOO_TOTEX_constraint').drop()
        ampl.getConstraint('EMOO_GWP_constraint').drop()
        ampl.getConstraint('EMOO_lca_constraint').drop()

        ampl.getConstraint('EMOO_GU_demand_constraint').drop()
        ampl.getConstraint('EMOO_GU_supply_constraint').drop()
        ampl.getConstraint('EMOO_grid_constraint').drop()
        ampl.getConstraint('EMOO_network_constraint').drop()

        if 'EMOO' in self.scenario_sp:
            for epsilon_constraint in self.scenario_sp['EMOO']:
                try:
                    ampl.getConstraint(epsilon_constraint + '_constraint').restore()
                    if isinstance(self.scenario_sp['EMOO'][epsilon_constraint], dict):
                        epsilon_parameter = ampl.getParameter(epsilon_constraint)
                        epsilon_parameter.setValues(self.scenario_sp['EMOO'][epsilon_constraint])
                    else:
                        epsilon_parameter = ampl.getParameter(epsilon_constraint)
                        epsilon_parameter.setValues([self.scenario_sp['EMOO'][epsilon_constraint]])
                except:
                    logging.warning('EMOO constraint ' + str(epsilon_constraint) + ' was not found in ampl model and was thus ignored.')

        # Set specific constraints
        ampl.getConstraint('disallow_exchanges_1').drop()
        ampl.getConstraint('disallow_exchanges_2').drop()
        ampl.getConstraint('no_ElectricalHeater_without_HP').drop()

        if 'PV' in self.infrastructure_sp.UnitsOfType:
            ampl.getConstraint('enforce_PV_max').drop()
        if 'HeatPump' in self.infrastructure_sp.UnitsOfType:
            ampl.getConstraint('enforce_DHN').drop()
            if not any("DHN" in unit for unit in self.infrastructure_sp.UnitsOfType['HeatPump']):
                ampl.getConstraint('DHN_heat').drop()
        if 'Air_Conditioner' in self.infrastructure_sp.UnitsOfType and "Air_Conditioner_DHN" not in [unit["name"] for unit in self.infrastructure_sp.units]:
            ampl.getConstraint('AC_c3').drop()
        if 'EV' in self.infrastructure_sp.UnitTypes:
            ampl.getConstraint('unidirectional_service').drop()

        if self.method_sp['use_pv_orientation']:
            ampl.getConstraint('enforce_PV_max_fac').drop()
            if not self.method_sp['use_facades']:
                ampl.getConstraint('limits_maximal_PV_to_fac').drop()

        if 'specific' in self.scenario_sp:
            for specific_constraint in self.scenario_sp['specific']:
                try:
                    ampl.getConstraint(specific_constraint).restore()
                except:
                    logging.warning('Specific constraint "' + str(specific_constraint) + '" was not found in ampl model and was thus ignored.')

        return ampl

    def solve_model(self):
        ampl = self.build_model_without_solving()

        debugging = False
        if debugging:
            # ampl.exportData('loaded_data.dat')
            # ampl.expotModel('loaded_model.mod')
            ampl.eval('suffix iis symbolic OUT;')
            ampl.setOption('presolve', 1)

        # ampl evaluation to speed up the optimization in case we have cogeneration units (since it has many integer variables)
        # ampl.eval("suffix priority IN, integer, >= 0, <= 9999; let {u in Units} Units_Use[u].priority := 9999; "
        #          "let {u in UnitsOfType['NG_Cogeneration'],p in Period,t in Time[p]} Units_Use_t[u,p,t].priority := "
        #          "200*round(max{i in Period,j in Time[i]}(T_ext[i,j])-T_ext[p,t],0);")
        ampl.solve()

        if debugging:
            ampl.eval('display {i in 1.._ncons: _con[i].iis <> "0"} (_conname[i], _con[i].iis);')
            ampl.eval('for {i in 1.._ncons: _con[i].iis <> "0"} expand _con[i]; ')
            ampl.eval('display{j in 1.._nvars: _var[j].iis <> "0"}(_varname[j], _var[j].iis);')

        exitcode = exitcode_from_ampl(ampl)
        return ampl, exitcode


def initialize_default_methods(method):
    if method is None:
        method = {}

    if 'use_facades' not in method:
        method['use_facades'] = False
    if 'use_pv_orientation' not in method:
        method['use_pv_orientation'] = False

    if 'include_stochasticity' not in method:
        method['include_stochasticity'] = False
    if 'sd_stochasticity' not in method:
        method['sd_stochasticity'] = [0.1, 1]

    if 'building-scale' not in method:
        method['building-scale'] = False
    if 'district-scale' not in method:
        method['district-scale'] = False
    if 'parallel_computation' not in method:
        method['parallel_computation'] = True
    if 'switch_off_second_objective' not in method:
        method['switch_off_second_objective'] = False

    if 'use_discrete_units' not in method:
        method['use_discrete_units'] = False
    if 'fix_units' not in method:
        method['fix_units'] = False

    if 'use_dynamic_emission_profiles' not in method:
        method['use_dynamic_emission_profiles'] = False
    if 'use_custom_profiles' not in method:
        method['use_custom_profiles'] = False

    if 'include_all_solutions' not in method:
        method['include_all_solutions'] = False
    if 'save_data_input' not in method:
        method['save_data_input'] = True
    if 'save_timeseries' not in method:
        method['save_timeseries'] = True
    if 'save_streams' not in method:
        method['save_streams'] = False
    if 'save_lca' not in method:
        method['save_lca'] = False
    if 'extract_parameters' not in method:
        method['extract_parameters'] = False
    if 'print_logs' not in method:
        method['print_logs'] = True

    if 'actors_problem' not in method:
        method['actors_problem'] = False
    if method['actors_problem']:
        method["include_all_solutions"] = True
    if 'DHN_CO2' not in method:
        method['DHN_CO2'] = False

    if 'use_Storage_Interperiod' not in method:
        method['use_Storage_Interperiod'] = False

    if method['building-scale']:
        method['include_all_solutions'] = False  # avoid interactions between optimization scenarios
        method[
            'district-scale'] = True  # building-scale approach is also using the decomposition algorithm, but with only 1 MP optimization (DW_params['max_iter'] = 1)

    return method


def exitcode_from_ampl(ampl):
    solve_result = ampl.getData('solve_result').toList()[0]
    return 0 if solve_result == 'solved' else solve_result
