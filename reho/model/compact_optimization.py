import os
from amplpy import AMPL, Environment
import itertools as itertools
import reho.model.preprocessing.data_generation as DGF
import reho.model.preprocessing.weather as WD
import reho.model.preprocessing.skydome_input_parser as SkyDome
import reho.model.preprocessing.emission_matrix_parser as emission
import reho.model.preprocessing.EV_profile_generator as EV_gen
from reho.model.preprocessing.QBuildings import *


class compact_optimization:
    """
            Collects all the data input and sends it an AMPL model, solves the optimization.

            Parameters
            ----------
            district : district
                Instance of the class district, contains relevant structure in the district such as Units or grids.
            buildings_data : dict
                Dictionary containing relevant Building data.
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
                Chosen solver for AMPL (gurobi, cplex, highs, cbc...).
            qbuildings_data : dict, optional
                Dictionary containing input data for the buildings.

            See also
            --------
            reho.model.reho.reho
            reho.model.district_decomposition.district_decomposition

            """
    def __init__(self, district, buildings_data, parameters, set_indexed, cluster, scenario, method, solver, qbuildings_data=None):

        self.buildings_data_compact = buildings_data
        if method['use_facades']:
            self.facades_compact = qbuildings_data['facades_data']
            self.shadows_compact = qbuildings_data['shadows_data']
        if method['use_pv_orientation']:
           self.roofs_compact = qbuildings_data['roofs_data']
        self.infrastructure_compact = district
        self.parameters_compact = parameters
        self.set_indexed_compact = set_indexed
        self.cluster_compact = cluster
        if 'exclude_units' not in scenario:
            scenario['exclude_units'] = []
        if 'enforce_units' not in scenario:
            scenario['enforce_units'] = []
        self.scenario_compact = scenario
        self.method_compact = method
        self.solver = solver
        self.parameters_to_ampl = dict()

        # print('Execute for building:', self.buildings_data_compact)
        # print('With parameters and sets:', self.parameters_compact, self.set_indexed_compact)
        # print('Cluster settings are:', self.cluster_compact)

    def solve_model(self):
        ampl = self.build_model_without_solving()

        debugging = False
        if debugging:
            # ampl.exportData('loaded_data.dat')
            # ampl.expotModel('loaded_model.mod')
            ampl.eval('suffix iis symbolic OUT;')
            ampl.setOption('presolve', 1)

        # ampl evaluation to speed up the optimization in case we have cogeneration units (since it has many integer variables)
        #ampl.eval("suffix priority IN, integer, >= 0, <= 9999; let {u in Units} Units_Use[u].priority := 9999; "
        #          "let {u in UnitsOfType['NG_Cogeneration'],p in Period,t in Time[p]} Units_Use_t[u,p,t].priority := "
        #          "200*round(max{i in Period,j in Time[i]}(T_ext[i,j])-T_ext[p,t],0);")
        ampl.solve()

        if debugging:
            ampl.eval('display {i in 1.._ncons: _con[i].iis <> "0"} (_conname[i], _con[i].iis);')
            ampl.eval('for {i in 1.._ncons: _con[i].iis <> "0"} expand _con[i]; ')
            ampl.eval('display{j in 1.._nvars: _var[j].iis <> "0"}(_varname[j], _var[j].iis);')

        exitcode = exitcode_from_ampl(ampl)
        return ampl, exitcode

    def build_model_without_solving(self):
        File_ID = WD.get_cluster_file_ID(self.cluster_compact)

        self.initialize_parameters_for_ampl_and_python()
        ampl = self.init_ampl_model()
        ampl = self.set_weather_data(ampl)
        ampl = self.set_ampl_sets(ampl)
        self.set_emissions_profiles(File_ID)
        self.set_gains_and_demands_profiles(ampl, File_ID)
        self.set_HP_parameters(ampl)
        self.set_streams_temperature(ampl)
        if self.method_compact['use_pv_orientation']:
            self.set_PV_models(ampl, File_ID)
        ampl = self.send_parameters_and_sets_to_ampl(ampl)
        ampl = self.set_scenario(ampl)

        return ampl

    def initialize_parameters_for_ampl_and_python(self):
        # -----------------------------------------------------------------------------------------------------#
        # Default methods
        # -----------------------------------------------------------------------------------------------------#
        self.method_compact = initialize_default_methods(self.method_compact)
        # -----------------------------------------------------------------------------------------------------#
        # Input Parameter Preparation
        # -----------------------------------------------------------------------------------------------------#

        # prepare input parameter which are used in AMPL model

        buildings_to_ampl = ['ERA', 'SolarRoofArea',  'U_h', 'HeatCapacity',
                             'T_comfort_min_0', 'Th_supply_0', 'Th_return_0', 'Tc_supply_0', 'Tc_return_0']

        for parameter in buildings_to_ampl:
            self.parameters_to_ampl[parameter] = {}
            for i, b in enumerate(self.buildings_data_compact):
                if parameter not in self.parameters_compact:
                    self.parameters_to_ampl[parameter][b] = self.buildings_data_compact[b][parameter]
                else:
                    self.parameters_to_ampl[parameter][b] = self.parameters_compact[parameter]


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
        # print(ampl.getOption('version'))

        # -AMPL (GNU) OPTIONS
        ampl.setOption('solution_round', 11)

        ampl.setOption('presolve_eps', 1e-4)  # -ignore difference between upper and lower bound by this tolerance
        ampl.setOption('presolve_inteps', 1e-6)  # -tolerance added/substracted to each upper/lower bound
        ampl.setOption('presolve_fixeps', 1e-9)
        ampl.setOption('show_stats', 0)

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
        ampl.read('model.mod')

        # Energy conversion Units
        ampl.cd(path_to_units)
        if 'ElectricalHeater' in self.infrastructure_compact.UnitTypes:
            ampl.read('electrical_heater.mod')
        if 'NG_Boiler' in self.infrastructure_compact.UnitTypes:
            ampl.read('ng_boiler.mod')
        if 'OIL_Boiler' in self.infrastructure_compact.UnitTypes:
            ampl.read('oil_boiler.mod')
        if 'WOOD_Stove' in self.infrastructure_compact.UnitTypes:
            ampl.read('wood_stove.mod')
        if 'HeatPump' in self.infrastructure_compact.UnitTypes:
            ampl.read('heatpump.mod')
        if 'Air_Conditioner' in self.infrastructure_compact.UnitTypes:
            ampl.read('air_conditioner.mod')
        if 'ThermalSolar' in self.infrastructure_compact.UnitTypes:
            ampl.read('thermal_solar.mod')
        if 'DataHeat' in self.infrastructure_compact.UnitTypes:
            ampl.read('data_heat.mod')
        if 'NG_Cogeneration' in self.infrastructure_compact.UnitTypes:
            ampl.read('ng_cogeneration.mod')
        if 'DHN_hex' in self.infrastructure_compact.UnitTypes:
            ampl.read('DHN_HEX.mod')
            ampl.read('DHN_pipes.mod')
        if 'PV' in self.infrastructure_compact.UnitTypes:
            if self.method_compact['use_pv_orientation']:  # Choose the photovoltaics model if PV orientation - give hourly PV electricity profiles
                ampl.read('pv_orientation.mod')
            else:
                ampl.read('pv.mod')

        # district Units
        if 'EV' in self.infrastructure_compact.UnitTypes:
            ampl.cd(path_to_district_units)
            ampl.read('evehicle.mod')
        # Storage Units
        ampl.cd(path_to_units_storage)
        if 'WaterTankSH' in self.infrastructure_compact.UnitTypes:
            ampl.read('heatstorage.mod')
        if 'WaterTankDHW' in self.infrastructure_compact.UnitTypes:
            ampl.read('dhwstorage.mod')
        if 'Battery' in self.infrastructure_compact.UnitTypes:
            ampl.read('battery.mod')
        ampl.cd(path_to_ampl_model)

        # Objectives, epsilon constraints and specific constraints
        ampl.read('scenario.mod')

        # TODO: integrate Jules units into district structure (avoid using ampl eval)
        if self.method_compact['use_Storage_Interperiod']:
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

        ampl.cd(path_to_clustering_results)

        File_ID = WD.get_cluster_file_ID(self.cluster_compact)

        ampl.readData('frequency_' + File_ID + '.dat')
        ampl.readData('index_' + File_ID + '.dat')
        self.parameters_to_ampl['T_ext'] = np.loadtxt(os.path.join(path_to_clustering_results, 'T_' + File_ID + '.dat'))
        self.parameters_to_ampl['I_global'] = np.loadtxt(os.path.join(path_to_clustering_results, 'GHI_' + File_ID + '.dat'))

        ampl.cd(path_to_ampl_model)
        return ampl

    def set_ampl_sets(self, ampl):
        # -----------------------------------------------------------------------------------------------------#
        # Design Structure: Building Cluster, Units and Layers
        # -----------------------------------------------------------------------------------------------------#

        if self.method_compact['use_discrete_units']:
            self.infrastructure_compact.set_discretize_unit_size()

        self.parameters_to_ampl['Units_flowrate'] = self.infrastructure_compact.Units_flowrate
        self.parameters_to_ampl['Grids_flowrate'] = self.infrastructure_compact.Grids_flowrate
        self.parameters_to_ampl['Grids_Parameters'] = self.infrastructure_compact.Grids_Parameters
        self.parameters_to_ampl['Grids_Parameters_lca'] = self.infrastructure_compact.Grids_Parameters_lca
        self.parameters_to_ampl['Units_Parameters'] = self.infrastructure_compact.Units_Parameters
        self.parameters_to_ampl['Units_Parameters_lca'] = self.infrastructure_compact.Units_Parameters_lca
        self.parameters_to_ampl['Streams_H'] = self.infrastructure_compact.Streams_H

        for key in self.infrastructure_compact.HP_parameters:
            self.parameters_to_ampl[key] = self.infrastructure_compact.HP_parameters[key]

        for s in self.infrastructure_compact.Set:
            if isinstance(self.infrastructure_compact.Set[s], np.ndarray):
                ampl.getSet(str(s)).setValues(self.infrastructure_compact.Set[s])
            elif isinstance(self.infrastructure_compact.Set[s], dict):
                for i, instance in ampl.getSet(str(s)):
                    instance.setValues(self.infrastructure_compact.Set[s][i])
            else:
                raise ValueError('Type Error setting AMPLPY Set', s)

        all_units = [unit for unit, value in ampl.getVariable('Units_Use').instances()]
        for i in all_units:
            for u in self.scenario_compact['exclude_units']:
                if 'district' not in i and u in i:  # unit at the building scale
                        ampl.getVariable('Units_Use').get(str(i)).fix(0)
                elif u in all_units:  # unit at the district scale with problem definition at the district scale
                    ampl.getVariable('Units_Use').get(str(u)).fix(0)

            for u in self.scenario_compact['enforce_units']:
                if 'district' not in i and u in i:  # unit at the building scale
                        ampl.getVariable('Units_Use').get(str(i)).fix(1)  # !!Fmin = 0, leaves the option to exclude unit
                elif u in all_units:  # unit at the district scale with problem definition at the district scale
                    ampl.getVariable('Units_Use').get(str(u)).fix(1)

        return ampl

    def set_emissions_profiles(self, File_ID):

        df_em = emission.select_typical_emission_profiles(self.cluster_compact, File_ID, 'GWP100a')
        if self.method_compact['use_dynamic_emission_profiles']:
            self.parameters_to_ampl['GWP_supply'] = df_em
            self.parameters_to_ampl['GWP_demand'] = df_em.rename(columns={'GWP_supply': 'GWP_demand'})
            self.parameters_to_ampl['Gas_emission'] = self.infrastructure_compact.Grids_Parameters.drop('Electricity').drop(
                columns=['Cost_demand_cst', 'Cost_supply_cst'])

    def set_gains_and_demands_profiles(self, ampl, File_ID):

        # Reference temperature
        #self.parameters_to_ampl['T_comfort_min'] = DGF.profile_reference_temperature(self.parameters_to_ampl, self.cluster_compact)

        # Heat gains from solar
        self.parameters_to_ampl['SolarGains'] = DGF.solar_gains_profile(ampl, self.buildings_data_compact, File_ID)

        # Set default EV plug out profile if EVs are allowed
        if "EV_plugged_out" not in self.parameters_to_ampl:
            if len(self.infrastructure_compact.UnitsOfDistrict) != 0:
                if "EV_district" in self.infrastructure_compact.UnitsOfDistrict:
                    self.parameters_to_ampl["EV_plugged_out"], self.parameters_to_ampl["EV_plugging_in"] = EV_gen.generate_EV_plugged_out_profiles_district(self.cluster_compact)

    def set_HP_parameters(self, ampl):
        # --------------- Heat Pump ---------------------------------------------------------------------------#
        # T = 7.5C for Lake, T = 12C for underground, T = 16C for CO2

        df_end = ampl.getParameter('TimeEnd').getValues().toPandas()
        timesteps = int(df_end['TimeEnd'].sum())  # total number of timesteps
        sources = []
        if 'T_source' in self.parameters_compact:
            sources = self.parameters_compact['T_source'].keys()

        T_source = []
        if 'HeatPump' in self.infrastructure_compact.UnitsOfType:
            for unit in self.infrastructure_compact.UnitsOfType['HeatPump']:
                if any([i in unit for i in sources]):   # if T_source defined from script
                    source = list(itertools.compress(sources, [i in unit for i in sources]))[0]
                    T_source = np.concatenate([T_source, np.repeat(self.parameters_compact['T_source'][source], timesteps)])
                elif 'Air' in unit:
                    T_source = np.concatenate([T_source, self.parameters_to_ampl['T_ext']])
                elif 'Lake' in unit:
                    T_source = np.concatenate([T_source, np.repeat(7.5, timesteps)])
                elif 'Geothermal' in unit:
                    T_source = np.concatenate([T_source, np.repeat(8, timesteps)])
                elif 'Anergy' in unit:
                    T_source = np.concatenate([T_source, np.repeat(16, timesteps)])
                elif 'DHN' in unit:
                    if 'T_DHN_supply' and 'T_DHN_return' in self.parameters_compact:
                        T_DHN_mean = (self.parameters_compact["T_DHN_supply"] + self.parameters_compact["T_DHN_return"]) / 2
                    elif 'T_DHN_supply_cst' and 'T_DHN_return_cst' in self.parameters_compact:
                        T_DHN_mean = (self.parameters_compact["T_DHN_supply_cst"] + self.parameters_compact["T_DHN_return_cst"]) / 2
                        T_DHN_mean = np.repeat(T_DHN_mean, timesteps)
                    else:
                        T_DHN_mean = np.repeat(16, timesteps)
                    T_source = np.concatenate([T_source, T_DHN_mean])
                else:
                    raise Exception('HP source undefined')

            self.parameters_to_ampl['T_source'] = T_source
            if 'T_source' in self.parameters_compact:
                del self.parameters_compact["T_source"]

        sources = []
        if 'T_source_cool' in self.parameters_compact:
            sources = self.parameters_compact['T_source_cool'].keys()

        T_source_cool = np.array([])
        if 'Air_Conditioner' in self.infrastructure_compact.UnitsOfType:
            for unit in self.infrastructure_compact.UnitsOfType['Air_Conditioner']:
                # if T_source_cool defined from script
                if any([i in unit for i in sources]):
                    source = list(itertools.compress(sources, [i in unit for i in sources]))[0]
                    T_source_cool = np.concatenate([T_source_cool, np.repeat(self.parameters_compact['T_source_cool'][source], timesteps)])

                elif "DHN" in unit:
                    if 'T_DHN_supply' and 'T_DHN_return' in self.parameters_compact:
                        T_DHN_mean = (self.parameters_compact["T_DHN_supply"] + self.parameters_compact["T_DHN_return"]) / 2
                    elif 'T_DHN_supply_cst' and 'T_DHN_return_cst' in self.parameters_compact:
                        T_DHN_mean = (self.parameters_compact["T_DHN_supply_cst"] + self.parameters_compact["T_DHN_return_cst"]) / 2
                        T_DHN_mean = np.repeat(T_DHN_mean, timesteps)
                    else:
                        T_DHN_mean = np.repeat(16, timesteps)
                    T_source_cool = np.concatenate([T_source_cool, T_DHN_mean])

                elif "Air" in unit:
                    T_source_cool = np.concatenate([T_source_cool, self.parameters_to_ampl['T_ext']])

                else:
                    raise Exception('AC sink undefined')

            self.parameters_to_ampl['T_source_cool'] = T_source_cool
            if 'T_source_cool' in self.parameters_compact:
                del self.parameters_compact["T_source_cool"]

    def set_streams_temperature(self, ampl):

        df_end = ampl.getParameter('TimeEnd').getValues().toPandas()
        timesteps = int(df_end['TimeEnd'].sum())
        df_Streams_T = pd.DataFrame(columns=["Period", "Time", "Streams", "Streams_Tout", "Streams_Tin"])
        df_Streams_T = df_Streams_T.set_index(["Period", "Time", "Streams"])

        index = [[(i, j+1) for j in list(range(int(df_end["TimeEnd"][i])))] for i in df_end.index]
        index = [j for i in index for j in i]
        index = pd.MultiIndex.from_tuples(index, names=["Period", "Time"])

        for bui in self.infrastructure_compact.houses:
            for unit_data in self.infrastructure_compact.houses[bui]["units"]:
                for i, T_level in enumerate(unit_data["StreamsOfUnit"]):
                    stream = unit_data["name"] + '_' + bui + '_' + T_level
                    df = pd.DataFrame(np.repeat(stream, timesteps), index=index, columns=["Streams"])
                    df["Streams_Tout"] = unit_data["stream_Tout"][i]
                    df["Streams_Tin"] = unit_data["stream_Tin"][i]
                    df.set_index("Streams", append=True, inplace=True)
                    df_Streams_T = pd.concat([df_Streams_T, df])
            for stream in self.infrastructure_compact.StreamsOfBuilding[bui]:
                df = pd.DataFrame(np.repeat(stream, timesteps), index=index, columns=["Streams"])
                df["Streams_Tout"] = 40 # default value that is changed in data_stream.dat
                df["Streams_Tin"] = 50  # default value that is changed in data_stream.dat
                df.set_index("Streams", append=True, inplace=True)
                df_Streams_T = pd.concat([df_Streams_T, df])

        self.parameters_to_ampl['streams_T'] = df_Streams_T.reorder_levels([2, 0, 1])



    def set_PV_models(self, ampl, File_ID):
        # --------------- PV Panels ---------------------------------------------------------------------------#

        df_dome = SkyDome.skydome_to_df()
        self.parameters_to_ampl['Sin_a'] = df_dome.Sin_a.values
        self.parameters_to_ampl['Cos_a'] = df_dome.Cos_a.values
        self.parameters_to_ampl['Sin_e'] = df_dome.Sin_e.values
        self.parameters_to_ampl['Cos_e'] = df_dome.Cos_e.values

        df_irr = SkyDome.irradiation_to_df(ampl, total_irradiation_csv, File_ID)
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
        self.set_indexed_compact['Surface'] = np.array([])

        for b in self.buildings_data_compact:

            df_roofs = self.roofs_compact[self.roofs_compact['id_building'] == self.buildings_data_compact[b]['id_building']]
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
        self.set_indexed_compact['Surface'] = np.append(self.set_indexed_compact['Surface'], np_surface)
        self.set_indexed_compact['SurfaceOfHouse'] = dict_SurfaceofHouse

        self.set_indexed_compact['SurfaceTypes'] = np.array(['Flat_roof', 'Tilted_roof', 'Facades'])
        self.set_indexed_compact['SurfaceOfType'] = {'Flat_roof': np_flat_roof, 'Tilted_roof': np_tilted_roof, 'Facades': []}
        self.set_indexed_compact['ConfigOfSurface'] = dict_config

        np_facades = np.array([])
        df_limit_angle = pd.DataFrame()

        if self.method_compact['use_facades']:
            for b in self.buildings_data_compact:
                df_facades = self.facades_compact[self.facades_compact['id_building'] == self.buildings_data_compact[b]['id_building']]
                df_shadows = self.shadows_compact[self.shadows_compact['id_building'] == self.buildings_data_compact[b]['id_building']]
                facades = df_facades['Facades_ID']
                np_facades = np.append(np_facades, facades)
                df_shadow = return_shadows_id_building(self.buildings_data_compact[b]['id_building'], df_shadows)
                df_shadow = pd.concat([df_shadow], keys=[b], names=['House'])
                df_limit_angle = pd.concat([df_limit_angle, df_shadow])
                for fc in facades:
                    az = df_facades.AZIMUTH.loc[(df_facades['Facades_ID'] == fc)].values
                    # Tilt is not available for facades
                    # ti = df_facades.TILT.loc[(df_facades['Facades_ID'] == fc)].values
                    ti = 0
                    self.set_indexed_compact['ConfigOfSurface'][fc] = [az[0], ti]
                self.set_indexed_compact['SurfaceOfHouse'][b] = np.append(
                    self.set_indexed_compact['SurfaceOfHouse'][b],
                    df_facades['Facades_ID'].values)
                index = pd.MultiIndex.from_tuples([(b, f) for f in facades])
                df = pd.DataFrame(df_facades['AREA'].values, index=index, columns=['HouseSurfaceArea'])  # Pq attribuer ici HouseSurfaceArea comme l'aire des facades?
                self.parameters_to_ampl['HouseSurfaceArea'] = pd.concat(
                    [self.parameters_to_ampl['HouseSurfaceArea'], df])
                # self.parameters_to_ampl['HouseSurfaceArea'].sort_index(inplace = True)

            if not df_limit_angle.empty:
                # self.parameters_to_ampl['Limiting_angle_shadow'] = df_limit_angle.rename(columns={0:'Limiting_angle_shadow'})
                self.parameters_to_ampl['Limiting_angle_shadow'] = df_limit_angle
                self.set_indexed_compact['SurfaceOfType']['Facades'] = np_facades
                self.set_indexed_compact['Surface'] = np.append(self.set_indexed_compact['Surface'], np_facades)

    def send_parameters_and_sets_to_ampl(self, ampl):
        # -----------------------------------------------------------------------------------------------------#
        # Load data to AMPLPY depending on their type
        # -----------------------------------------------------------------------------------------------------#

        for key in self.parameters_compact:
            self.parameters_to_ampl[key] = self.parameters_compact[key]

        # set new indexed sets
        for s in self.set_indexed_compact:
            if isinstance(self.set_indexed_compact[s], np.ndarray):
                ampl.getSet(str(s)).setValues(self.set_indexed_compact[s])
            elif isinstance(self.set_indexed_compact[s], dict):
                for i, instance in ampl.getSet(str(s)):
                    try:
                        instance.setValues(self.set_indexed_compact[s][i])
                    except ValueError:
                        instance.setValues([self.set_indexed_compact[s][i]])
            else:
                raise ValueError('Type Error setting AMPLPY Set', s)

        # set new input Parameter
        for i in self.parameters_to_ampl:

            if isinstance(self.parameters_to_ampl[i], np.ndarray):
                Para = ampl.getParameter(i)
                # print('Set Values for ' + str(Para))
                Para.setValues(self.parameters_to_ampl[i])

            elif isinstance(self.parameters_to_ampl[i], list):
                Para = ampl.getParameter(i)
                # print('Set Values for ' + str(Para))
                Para.setValues(np.array(self.parameters_to_ampl[i]))

            elif isinstance(self.parameters_to_ampl[i], pd.DataFrame):
                # print(self.parameters_to_ampl[i].columns)
                ampl.setData(self.parameters_to_ampl[i])

            elif isinstance(self.parameters_to_ampl[i], pd.Series):
                # print('Set values for : '+ i)
                self.parameters_to_ampl[i].name = i
                df = pd.DataFrame(self.parameters_to_ampl[i])
                ampl.setData(df)

            elif isinstance(self.parameters_to_ampl[i], dict):
                # print('Set Values for ' + str(i))
                Para = ampl.getParameter(i)
                # print('Set Values for ' + str(Para))
                Para.setValues(self.parameters_to_ampl[i])

            elif isinstance(self.parameters_to_ampl[i], float):
                Para = ampl.getParameter(i)
                # print('Set Values for ' + str(Para))
                Para.setValues([self.parameters_to_ampl[i]])

            elif isinstance(self.parameters_to_ampl[i], int):
                Para = ampl.getParameter(i)
                # print('Set Values for ' + str(Para))
                Para.setValues([self.parameters_to_ampl[i]])

            else:
                raise ValueError('Type Error setting AMPLPY Parameter', i)

        # TODO remove data_stream.dat
        ampl.readData('data_stream.dat')
        if self.method_compact['use_Storage_Interperiod']:
            ampl.readData('data_stream_storage.dat')

        return ampl

    def set_scenario(self, ampl):

        # Set objective function
        for objective_name, objective_formulation in ampl.getObjectives():
            objective_formulation.drop()

        if 'Objective' in self.scenario_compact:
            try:
                ampl.getObjective(self.scenario_compact['Objective']).restore()
            except KeyError:
                ampl.getObjective('TOTEX').restore()
                print('Objective function "', self.scenario_compact['Objective'],
                      '" was not found in ampl model, TOTEX minimization was set instead.')
        else:
            ampl.getObjective('TOTEX').restore()
            print('No objective function was found in scenario dictionary, TOTEX minimization was set instead.')

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

        if 'EMOO' in self.scenario_compact:
            for epsilon_constraint in self.scenario_compact['EMOO']:
                try:
                    ampl.getConstraint(epsilon_constraint + '_constraint').restore()
                    if isinstance(self.scenario_compact['EMOO'][epsilon_constraint], dict):
                        epsilon_parameter = ampl.getParameter(epsilon_constraint)
                        epsilon_parameter.setValues(self.scenario_compact['EMOO'][epsilon_constraint])
                    else:
                        epsilon_parameter = ampl.getParameter(epsilon_constraint)
                        epsilon_parameter.setValues([self.scenario_compact['EMOO'][epsilon_constraint]])
                except:
                    print('EMOO constraint ', epsilon_constraint, ' was not found in ampl model and was thus ignored.')

        # Set specific constraints
        ampl.getConstraint('disallow_exchanges_1').drop()
        ampl.getConstraint('disallow_exchanges_2').drop()

        if 'PV' in self.infrastructure_compact.UnitsOfType: # Check if HP DHN is used
            ampl.getConstraint('enforce_PV_max').drop()
        if 'HeatPump' in self.infrastructure_compact.UnitsOfType: # Check if HP DHN is used
            ampl.getConstraint('enforce_DHN').drop()
            if not any("DHN" in unit for unit in self.infrastructure_compact.UnitsOfType['HeatPump']):
                ampl.getConstraint('DHN_heat').drop()
        else:
            ampl.getConstraint('TOTAL_design_c11').drop()
        if 'Air_Conditioner' in self.infrastructure_compact.UnitsOfType and "Air_Conditioner_DHN" not in [unit["name"] for unit in self.infrastructure_compact.units]:
            ampl.getConstraint('AC_c3').drop()
        if 'EV' in self.infrastructure_compact.UnitTypes:
            ampl.getConstraint('unidirectional_service').drop()

        if self.method_compact['use_pv_orientation']:
            ampl.getConstraint('enforce_PV_max_fac').drop()
            if not self.method_compact['use_facades']:
                ampl.getConstraint('limits_maximal_PV_to_fac').drop()

        if 'specific' in self.scenario_compact:
            for specific_constraint in self.scenario_compact['specific']:
                try:
                    ampl.getConstraint(specific_constraint).restore()
                except:
                    print('Specific constraint "', specific_constraint,
                          '" was not found in ampl model and was thus ignored.')

        return ampl


def initialize_default_methods(method):
    if method is None:
        method = {}

    if 'use_facades' not in method:
        method['use_facades'] = False
    if 'use_pv_orientation' not in method:
        method['use_pv_orientation'] = False

    if 'include_stochasticity' not in method:  # https://ipese-web.epfl.ch/lepour/lacorte_pds/index.html
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
    if 'read_electricity_profiles' not in method:
        method['read_electricity_profiles'] = None

    if 'include_all_solutions' not in method:
        method['include_all_solutions'] = False
    if 'save_stream_t' not in method:
        method['save_stream_t'] = False
    if 'save_lca' not in method:
        method['save_lca'] = False
    if 'extract_parameters' not in method:
        method['extract_parameters'] = False

    if 'actors_cost' not in method:
        method['actors_cost'] = False
    if method['actors_cost']:
        method["include_all_solutions"] = True
    if 'DHN_CO2' not in method:
        method['DHN_CO2'] = False

    if 'use_Storage_Interperiod' not in method:
        method['use_Storage_Interperiod'] = False

    if method['building-scale']:
        method['include_all_solutions'] = False # avoid interactions between optimization scenarios
        method['district-scale'] = True  # building-scale approach is also using the decomposition algorithm, but with only 1 MP optimization (DW_params['max_iter'] = 1)

    return method


def exitcode_from_ampl(ampl):
    solve_result = ampl.getData('solve_result').toList()[0]
    return 0 if solve_result == 'solved' else solve_result
