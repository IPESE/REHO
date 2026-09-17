"""Building-scale optimization problem.

A :class:`SubProblem` gathers every input of one building (or of the whole
district, in the compact formulation), hands them to AMPL, and solves the MILP.
In the Dantzig-Wolfe decomposition it is the *column generator*: each solve
proposes one more candidate energy-system configuration to the master problem.

See also
--------
reho.model.master_problem.MasterProblem : district-scale problem coordinating the sub-problems.
reho.model.reho.REHO : user-facing entry point.
"""

import os

import numpy as np
import pandas as pd

import reho.model.preprocessing.buildings_profiles as buildings_profiles
import reho.model.preprocessing.weather as weather
from reho.logger import get_logger
from reho.model.ampl_interface import (
    BUILDING_UNIT_MODELS,
    INTERPERIOD_BUILDING_UNIT_MODELS,
    create_ampl_session,
    exitcode_from_ampl,
    read_unit_models,
)
from reho.model.options import initialize_default_methods
from reho.model.preprocessing.QBuildings import return_shadows_id_building
from reho.model.preprocessing.skydome import irradiation_to_df
from reho.paths import path_to_ampl_model, path_to_clustering, path_to_district_units, path_to_skydome

#: Names re-exported for ``from reho.model.sub_problem import *`` and for
#: backwards compatibility: both helpers used to be defined in this module.
__all__ = ["SubProblem", "initialize_default_methods", "exitcode_from_ampl"]

logger = get_logger(__name__)

#: Building characteristics forwarded as-is to the AMPL model.
BUILDING_PARAMETERS_TO_AMPL = [
    "ERA", "SolarRoofArea", "U_h", "HeatCapacity",
    "T_comfort_min_0", "Th_supply_0", "Th_return_0", "Tc_supply_0", "Tc_return_0",
]

#: Constant temperature of a heat source, per source keyword found in the unit name [degC].
#: ``Air`` and ``DHN`` are time-resolved and handled separately.
DEFAULT_HP_SOURCE_TEMPERATURES = {"Lake": 7.5, "Geothermal": 8.0}

#: Heat-pump source keywords, matched against the unit name, most specific first.
HP_SOURCE_KEYWORDS = ("Air", "Lake", "Geothermal", "DHN")

#: Air-conditioner sink keywords. ``DHN`` comes first because 'AirConditioner_DHN'
#: also contains 'Air'.
AC_SINK_KEYWORDS = ("DHN", "Air")

#: Fallback mean district-heating-network temperature when none is given [degC].
DEFAULT_DHN_TEMPERATURE = 16.0

#: Epsilon constraints dropped by default, and restored only when the scenario asks for them.
_EPSILON_CONSTRAINTS = [
    "EMOO_CAPEX_constraint", "EMOO_OPEX_constraint", "EMOO_TOTEX_constraint", "EMOO_GWP_constraint",
    "EMOO_elec_export_constraint", "EMOO_GU_demand_constraint", "EMOO_GU_supply_constraint",
    "EMOO_grid_constraint", "EMOO_network_constraint",
]

#: Optional constraints dropped by default, and restored only when scenario['specific'] asks for them.
_SPECIFIC_CONSTRAINTS = [
    "disallow_exchanges_1", "disallow_exchanges_2", "no_ElectricalHeater_without_HP",
    "no_NG_boiler_with_HP", "forced_H2_annual_export", "forced_H2_fixed_daily_export",
]


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
    reho.model.reho.REHO
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
        """Build the complete AMPL sub-problem, ready to be solved.

        The steps are, in order: :meth:`initialize_parameters_for_ampl_and_python`,
        :meth:`init_ampl_model`, :meth:`set_weather_data`, :meth:`set_ampl_sets`,
        :meth:`set_temperature_and_EVs_profiles`, :meth:`set_HP_parameters`,
        :meth:`set_streams_temperature`, :meth:`set_skydome_parameters` (only with
        ``method['use_pv_orientation']``), :meth:`send_parameters_and_sets_to_ampl` and
        :meth:`set_scenario`.

        Returns
        -------
        amplpy.AMPL
            Session holding the model, its data and the scenario.
        """
        self.initialize_parameters_for_ampl_and_python()
        ampl = self.init_ampl_model()
        ampl = self.set_weather_data(ampl)
        ampl = self.set_ampl_sets(ampl)
        self.set_temperature_and_EVs_profiles()
        self.set_HP_parameters(ampl)
        self.set_streams_temperature(ampl)
        if self.method_sp['use_pv_orientation']:
            self.set_skydome_parameters()
        ampl = self.send_parameters_and_sets_to_ampl(ampl)
        ampl = self.set_scenario(ampl)
        return ampl

    def initialize_parameters_for_ampl_and_python(self):
        """Complete the method options and collect the per-building AMPL parameters.

        A value given in ``parameters`` overrides the one read from
        ``buildings_data``, and then applies to every building of the sub-problem.
        """
        self.method_sp = initialize_default_methods(self.method_sp)

        for parameter in BUILDING_PARAMETERS_TO_AMPL:
            overridden = parameter in self.parameters_sp
            self.parameters_to_ampl[parameter] = {
                building: (self.parameters_sp[parameter] if overridden else self.buildings_data_sp[building][parameter])
                for building in self.buildings_data_sp
            }

    def init_ampl_model(self):
        """Open an AMPL session and read the sub-problem model plus its technologies.

        Returns
        -------
        amplpy.AMPL
            A session holding ``sub_problem.mod``, ``scenario.mod`` and one
            ``.mod`` file per technology present in the infrastructure.

        See also
        --------
        reho.model.ampl_interface.BUILDING_UNIT_MODELS : registry of technology model files.
        """
        ampl = create_ampl_session(self.solver, print_logs=self.method_sp["print_logs"],
                                   solver_threads=self.method_sp["solver_threads_SP"])

        ampl.read("sub_problem.mod")
        ampl.read("scenario.mod")

        unit_types = self.infrastructure_sp.UnitTypes
        # PV has two formulations; the oriented one also models roof/facade surfaces.
        pv_override = {"PV": "pv_orientation.mod"} if self.method_sp["use_pv_orientation"] else None
        read_unit_models(ampl, BUILDING_UNIT_MODELS, unit_types, overrides=pv_override)

        if self.method_sp["interperiod_storage"]:
            read_unit_models(ampl, INTERPERIOD_BUILDING_UNIT_MODELS, unit_types)

        # Electric vehicles are a district unit, but may also be owned by a single building.
        if "EV" in unit_types:
            ampl.cd(path_to_district_units)
            ampl.read("evehicle.mod")

        return ampl

    def set_weather_data(self, ampl):
        """Read the typical periods of the location into AMPL.

        ``frequency.csv`` (the periods, their frequency ``dp`` and number of timesteps ``TimeEnd``) and
        ``index.csv`` (the typical period and timestep of each hour of the year) are read from the
        clustering directory of the location. The ambient temperature ``T_ext`` and the global
        irradiance ``Irr`` of the typical periods are added to the parameters sent by
        :meth:`send_parameters_and_sets_to_ampl`.

        Parameters
        ----------
        ampl : amplpy.AMPL
            Session holding the sub-problem model.

        Returns
        -------
        amplpy.AMPL
            The same session.
        """
        # -----------------------------------------------------------------------------------------------------#
        # -Setting DATA
        # -----------------------------------------------------------------------------------------------------#

        File_ID = weather.get_cluster_file_ID(self.cluster_sp)
        clustering_directory = os.path.join(path_to_clustering, File_ID)
        ampl.cd(clustering_directory)

        ampl.readData('frequency.csv')
        ampl.readData('index.csv')
        self.parameters_to_ampl['T_ext'] = self.local_data["T_ext"]
        self.parameters_to_ampl['Irr'] = self.local_data["Irr"]

        ampl.cd(path_to_ampl_model)

        return ampl

    def set_ampl_sets(self, ampl):
        """Send the sets of the infrastructure to AMPL, and apply the units excluded or enforced by the scenario.

        The sets of the :class:`~reho.model.infrastructure.Infrastructure` are written at once. Its
        parameters (unit flow rates and characteristics, grid parameters, stream types, heat-pump maps)
        are added to those sent by :meth:`send_parameters_and_sets_to_ampl`.

        The use of the units named in ``scenario['exclude_units']`` is then fixed to 0, and of those
        named in ``scenario['enforce_units']`` to 1. A name designates a building unit either exactly
        or as the prefix of its instances (``'PV'`` designates ``'PV_Building1'``), and a district unit
        exactly. Enforcing a unit forces its installation, not a size above its minimum size.

        Parameters
        ----------
        ampl : amplpy.AMPL
            Session holding the sub-problem model.

        Returns
        -------
        amplpy.AMPL
            The same session.

        Raises
        ------
        ValueError
            If a set of the infrastructure is neither an array nor a dictionary of arrays.
        """
        # -----------------------------------------------------------------------------------------------------#
        # Design Structure: Building Cluster, Units and Layers
        # -----------------------------------------------------------------------------------------------------#

        self.parameters_to_ampl['Units_flowrate'] = self.infrastructure_sp.Units_flowrate
        self.parameters_to_ampl['Grids_Parameters'] = self.infrastructure_sp.Grids_Parameters.drop(["Network_demand_connection", "Network_supply_connection"],
                                                                                                   axis=1)
        self.parameters_to_ampl['Units_Parameters'] = self.infrastructure_sp.Units_Parameters
        self.parameters_to_ampl['Streams_H'] = self.infrastructure_sp.Streams_H

        for key in self.infrastructure_sp.HP_parameters:
            self.parameters_to_ampl[key] = self.infrastructure_sp.HP_parameters[key]

        for s in self.infrastructure_sp.Set:
            if isinstance(self.infrastructure_sp.Set[s], np.ndarray):
                ampl.getSet(str(s)).setValues(self.infrastructure_sp.Set[s])
            elif isinstance(self.infrastructure_sp.Set[s], dict):
                for i, instance in ampl.getSet(str(s)):
                    instance.setValues(self.infrastructure_sp.Set[s][i[0]])
            else:
                raise ValueError('Type Error setting AMPLPY Set', s)

        all_units = [unit for unit, value in ampl.getVariable('Units_Use').instances()]
        for i in all_units:
            for u in self.scenario_sp['exclude_units']:
                # u matches i[0] either as a unit type prefix ('PV' -> 'PV_Building1') or as a fully
                # qualified unit name ('PV_Building1'); startswith(u + '_') avoids 'Building1' matching 'Building10'
                if ('district' not in i[0]) and ('IP' not in i[0]) and (i[0] == u or i[0].startswith(u + '_')):  # unit at the building scale
                    ampl.getVariable('Units_Use').get(str(i[0])).fix(0)
                elif u in all_units:  # unit at the district scale with problem definition at the district scale
                    ampl.getVariable('Units_Use').get(str(u)).fix(0)

            for u in self.scenario_sp['enforce_units']:
                if 'district' not in i[0] and (i[0] == u or i[0].startswith(u + '_')):  # unit at the building scale
                    ampl.getVariable('Units_Use').get(str(i[0])).fix(1)  # !!Fmin = 0, leaves the option to exclude unit
                elif u in all_units:  # unit at the district scale with problem definition at the district scale
                    ampl.getVariable('Units_Use').get(str(u)).fix(1)

        return ampl

    def set_temperature_and_EVs_profiles(self):
        """Build the lower comfort temperature ``T_comfort_min`` of each building at every timestep.

        The constant reference ``T_comfort_min_0`` of each building is repeated over the typical
        periods, see :func:`~reho.model.preprocessing.buildings_profiles.reference_temperature_profile`.
        """

        # Reference temperature
        self.parameters_to_ampl['T_comfort_min'] = buildings_profiles.reference_temperature_profile(self.parameters_to_ampl, self.cluster_sp)

    def _dhn_mean_temperature(self, timesteps):
        """Mean district-heating temperature seen by a DHN-coupled heat pump or chiller.

        A time-resolved pair (``T_DHN_supply``/``T_DHN_return``) wins over a constant
        pair (``*_cst``); when neither is given, :data:`DEFAULT_DHN_TEMPERATURE` is used.

        Parameters
        ----------
        timesteps : int
            Length of the profile to build.

        Returns
        -------
        numpy.ndarray
            Mean network temperature for each timestep [degC].
        """
        if "T_DHN_supply" in self.parameters_sp and "T_DHN_return" in self.parameters_sp:
            return (self.parameters_sp["T_DHN_supply"] + self.parameters_sp["T_DHN_return"]) / 2
        if "T_DHN_supply_cst" in self.parameters_sp and "T_DHN_return_cst" in self.parameters_sp:
            mean = (self.parameters_sp["T_DHN_supply_cst"] + self.parameters_sp["T_DHN_return_cst"]) / 2
            return np.repeat(mean, timesteps)
        logger.debug("No DHN temperature given, using the default of %s degC.", DEFAULT_DHN_TEMPERATURE)
        return np.repeat(DEFAULT_DHN_TEMPERATURE, timesteps)

    def _source_temperature_profiles(self, units, timesteps, custom_key, keywords, role):
        """Build the source-temperature profile of every heat pump or air conditioner.

        The source is deduced from the unit name: a fragment listed in
        ``parameters[custom_key]`` wins, then the first matching keyword of
        ``keywords``.

        Parameters
        ----------
        units : iterable of str
            Unit names, e.g. ``['HeatPump_Air_Building1', 'HeatPump_DHN_Building1']``.
        timesteps : int
            Number of timesteps of a single profile.
        custom_key : str
            ``'T_source'`` or ``'T_source_cool'``: the ``parameters`` entry holding
            user-defined source temperatures, as ``{name fragment: temperature}``.
        keywords : tuple of str
            Source keywords to look for in the unit name, **most specific first**
            (``'AirConditioner_DHN'`` contains both ``DHN`` and ``Air``).
        role : str
            Wording used in the error message ('heat pump source' / 'air conditioner sink').

        Returns
        -------
        numpy.ndarray
            Concatenated profiles, in the order of ``units``.

        Raises
        ------
        ValueError
            If the source of a unit cannot be deduced from its name.
        """
        custom_sources = list(self.parameters_sp.get(custom_key, {}))
        profiles = []

        for unit in units:
            matching = [source for source in custom_sources if source in unit]
            if matching:
                profiles.append(np.repeat(self.parameters_sp[custom_key][matching[0]], timesteps))
                continue

            keyword = next((k for k in keywords if k in unit), None)
            if keyword == "Air":
                profiles.append(np.asarray(self.parameters_to_ampl["T_ext"]))
            elif keyword == "DHN":
                profiles.append(self._dhn_mean_temperature(timesteps))
            elif keyword is not None:
                profiles.append(np.repeat(DEFAULT_HP_SOURCE_TEMPERATURES[keyword], timesteps))
            else:
                raise ValueError(
                    f"Undefined {role} for unit {unit!r}. Name it after a known source "
                    f"({', '.join(keywords)}) or declare its temperature in parameters[{custom_key!r}]."
                )

        return np.concatenate(profiles) if profiles else np.array([])

    def set_HP_parameters(self, ampl):
        """Derive the source temperature of every heat pump and air conditioner.

        The resulting ``T_source`` / ``T_source_cool`` profiles are what the AMPL
        model turns into a Carnot-based, temperature-dependent COP.
        """
        df_end = ampl.getParameter("TimeEnd").getValues().toPandas()
        timesteps = int(df_end["TimeEnd"].sum())

        for unit_type, custom_key, keywords, role in (
            ("HeatPump", "T_source", HP_SOURCE_KEYWORDS, "heat pump source"),
            ("AirConditioner", "T_source_cool", AC_SINK_KEYWORDS, "air conditioner sink"),
        ):
            if unit_type not in self.infrastructure_sp.UnitsOfType:
                continue
            self.parameters_to_ampl[custom_key] = self._source_temperature_profiles(
                self.infrastructure_sp.UnitsOfType[unit_type], timesteps, custom_key, keywords, role
            )
            # The mapping form ({source: temperature}) is not what AMPL expects: drop it
            # now that it has been expanded into a per-timestep profile.
            self.parameters_sp.pop(custom_key, None)

    def set_streams_temperature(self, ampl):
        """Build the inlet and outlet temperatures of the heat-cascade streams, at every timestep.

        The streams of the units take the constant ``stream_Tin`` and ``stream_Tout`` of the unit data.
        The space-heating and cooling streams of the buildings get placeholder values (50 and 40 degC),
        replaced by their supply and return temperatures when :meth:`send_parameters_and_sets_to_ampl`
        reads ``data_stream.dat``. The result, ``streams_T``, is added to the parameters sent to AMPL.

        Parameters
        ----------
        ampl : amplpy.AMPL
            Session holding the sub-problem model, with the number of timesteps of each period
            (``TimeEnd``) already read.
        """

        df_end = ampl.getParameter('TimeEnd').getValues().toPandas()
        timesteps = int(df_end['TimeEnd'].sum())
        index = [[(i, j + 1) for j in list(range(int(df_end["TimeEnd"][i])))] for i in df_end.index]
        index = [j for i in index for j in i]
        index = pd.MultiIndex.from_tuples(index, names=["Period", "Time"])

        streams_frames = []
        for bui in self.infrastructure_sp.houses:
            for unit_data in self.infrastructure_sp.houses[bui]["units"]:
                for i, T_level in enumerate(unit_data["StreamsOfUnit"]):
                    stream = unit_data["Unit"] + '_' + bui + '_' + T_level
                    df = pd.DataFrame(np.repeat(stream, timesteps), index=index, columns=["Streams"])
                    df["Streams_Tout"] = unit_data["stream_Tout"][i]
                    df["Streams_Tin"] = unit_data["stream_Tin"][i]
                    df.set_index("Streams", append=True, inplace=True)
                    streams_frames.append(df)
            for stream in self.infrastructure_sp.StreamsOfBuilding[bui]:
                df = pd.DataFrame(np.repeat(stream, timesteps), index=index, columns=["Streams"])
                df["Streams_Tout"] = 40  # default value that is changed in data_stream.dat
                df["Streams_Tin"] = 50  # default value that is changed in data_stream.dat
                df.set_index("Streams", append=True, inplace=True)
                streams_frames.append(df)

        df_Streams_T = pd.concat(streams_frames)
        self.parameters_to_ampl['streams_T'] = df_Streams_T.reorder_levels([2, 0, 1])

    def set_skydome_parameters(self):
        """Build the data of the PV orientation model: sky patches, surfaces and panel configurations.

        The irradiation of the sky patches (``Irr_patches``) and their position are read from the
        skydome data. Each roof of each building becomes a surface, with its area
        (``HouseSurfaceArea``) and the panel configurations (azimuth, tilt) it allows:

        - on a tilted roof, the panels follow the orientation of the roof;
        - on a flat roof (tilt 0 or 1), the solver chooses among azimuths from 160 to 200 degrees by
          steps of 10, and tilts of 5, 10, 20, 30 and 40 degrees, or panels lying flat (180, 0).

        With ``method['use_facades']``, the facades are surfaces too, with their azimuth and a tilt of
        0, and the limiting angles of the shadows cast by the surrounding buildings
        (``Limiting_angle_shadow``).

        Requires the ``roofs_data`` of ``qbuildings_data``, plus ``facades_data`` and ``shadows_data``
        for the facades.
        """
        # --------------- PV Panels ---------------------------------------------------------------------------#

        df_dome = pd.read_csv(os.path.join(path_to_skydome, 'skydome.csv'))
        self.parameters_to_ampl['Sin_a'] = df_dome.Sin_a.values
        self.parameters_to_ampl['Cos_a'] = df_dome.Cos_a.values
        self.parameters_to_ampl['Sin_e'] = df_dome.Sin_e.values
        self.parameters_to_ampl['Cos_e'] = df_dome.Cos_e.values

        self.parameters_to_ampl['Irr_patches'] = irradiation_to_df(self.local_data)
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
        Configs_flat_roof = np.reshape(Configs_flat_roof, (len(All_azimuth) + 1, 2))

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
                df_shadows = self.shadows_sp[self.shadows_sp['id_building'] == str(self.buildings_data_sp[b]['id_building'])]
                facades = df_facades['Facades_ID']
                np_facades = np.append(np_facades, facades)
                df_shadow = return_shadows_id_building(self.buildings_data_sp[b]['id_building'], df_shadows)
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
                                  columns=['HouseSurfaceArea'])
                self.parameters_to_ampl['HouseSurfaceArea'] = pd.concat(
                    [self.parameters_to_ampl['HouseSurfaceArea'], df])
                # self.parameters_to_ampl['HouseSurfaceArea'].sort_index(inplace = True)

            if not df_limit_angle.empty:
                # self.parameters_to_ampl['Limiting_angle_shadow'] = df_limit_angle.rename(columns={0:'Limiting_angle_shadow'})
                self.parameters_to_ampl['Limiting_angle_shadow'] = df_limit_angle
                self.set_indexed_sp['SurfaceOfType']['Facades'] = np_facades
                self.set_indexed_sp['Surface'] = np.append(self.set_indexed_sp['Surface'], np_facades)

    def send_parameters_and_sets_to_ampl(self, ampl):
        """
        Load data to AMPL depending on their type
        """

        for key in self.parameters_sp:
            self.parameters_to_ampl[key] = self.parameters_sp[key]

        # set new indexed sets
        for s in self.set_indexed_sp:
            if isinstance(self.set_indexed_sp[s], np.ndarray):
                ampl.getSet(str(s)).setValues(self.set_indexed_sp[s])
            elif isinstance(self.set_indexed_sp[s], dict):
                for i, instance in ampl.getSet(str(s)):
                    try:
                        instance.setValues(self.set_indexed_sp[s][i[0]])
                    except ValueError:
                        instance.setValues([self.set_indexed_sp[s][i[0]]])
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

        ampl.readData('data_stream.dat')  # TODO remove data_stream.dat

        return ampl

    def set_scenario(self, ampl):
        """Apply the scenario: objective function, epsilon constraints, specific constraints.

        All optional constraints are dropped first and restored only when the
        scenario asks for them, so that a session always reflects exactly what
        was requested — never a leftover from a previous configuration.
        """
        for _, objective in ampl.getObjectives():
            objective.drop()
        self._restore_objective(ampl)

        for constraint in _EPSILON_CONSTRAINTS:
            ampl.getConstraint(constraint).drop()
        for name, value in self.scenario_sp.get("EMOO", {}).items():
            self._restore_epsilon_constraint(ampl, name, value)

        for constraint in _SPECIFIC_CONSTRAINTS:
            ampl.getConstraint(constraint).drop()
        self._drop_technology_constraints(ampl)

        for name in self.scenario_sp.get("specific", []):
            try:
                ampl.getConstraint(name).restore()
            except Exception:
                logger.warning("Specific constraint %r was not found in the AMPL sub-problem and was ignored.", name)

        return ampl

    def _restore_objective(self, ampl):
        """Activate the objective named in the scenario, falling back on TOTEX."""
        objective = self.scenario_sp.get("Objective")
        if objective is None:
            logger.warning("No objective function in the scenario dictionary, minimizing TOTEX instead.")
        else:
            try:
                ampl.getObjective(objective).restore()
                return
            except Exception:
                logger.warning("Objective function %r was not found in the AMPL model, minimizing TOTEX instead.", objective)
        ampl.getObjective("TOTEX").restore()

    @staticmethod
    def _restore_epsilon_constraint(ampl, name, value):
        """Activate one epsilon constraint and set its right-hand side."""
        try:
            ampl.getConstraint(name + "_constraint").restore()
            ampl.getParameter(name).setValues(value if isinstance(value, dict) else [value])
        except Exception:
            logger.warning("EMOO constraint %r was not found in the AMPL sub-problem and was ignored.", name)

    def _drop_technology_constraints(self, ampl):
        """Drop the optional constraints that only exist for some technologies."""
        units_of_type = self.infrastructure_sp.UnitsOfType

        if "PV" in units_of_type:
            ampl.getConstraint("enforce_PV_max").drop()

        if "HeatPump" in units_of_type:
            ampl.getConstraint("enforce_DHN").drop()
            if not any("DHN" in unit for unit in units_of_type["HeatPump"]):
                ampl.getConstraint("DHN_heat").drop()

        if self.method_sp["use_pv_orientation"]:
            ampl.getConstraint("enforce_PV_max_fac").drop()
            if not self.method_sp["use_facades"]:
                ampl.getConstraint("limits_maximal_PV_to_fac").drop()

    def solve_model(self, diagnose_infeasibility=False):
        """Build and solve the sub-problem.

        Parameters
        ----------
        diagnose_infeasibility : bool, optional
            Ask the solver for an irreducible infeasible subsystem (IIS) and print
            the offending constraints and variables. Useful to understand why a
            building cannot be supplied; noticeably slower. Default is False.

        Returns
        -------
        ampl : amplpy.AMPL
            The solved session, from which results are extracted.
        exitcode : int or str
            ``0`` when solved, else the AMPL ``solve_result``.
        """
        ampl = self.build_model_without_solving()

        if diagnose_infeasibility:
            ampl.eval("suffix iis symbolic OUT;")
            ampl.setOption("presolve", 1)

        ampl.solve()

        if diagnose_infeasibility:
            ampl.eval('display {i in 1.._ncons: _con[i].iis <> "0"} (_conname[i], _con[i].iis);')
            ampl.eval('for {i in 1.._ncons: _con[i].iis <> "0"} expand _con[i]; ')
            ampl.eval('display{j in 1.._nvars: _var[j].iis <> "0"}(_varname[j], _var[j].iis);')

        return ampl, exitcode_from_ampl(ampl)

