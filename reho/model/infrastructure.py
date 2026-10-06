import os.path

import numpy as np
import pandas as pd

from reho.paths import file_reader, path_to_infrastructure

__doc__ = """
File for handling infrastructure parameters.
"""

#: Energy layers activated when the caller does not specify any.
DEFAULT_GRIDS = {'Electricity': {}, 'NaturalGas': {}}

#: Units kept even when the scenario excludes them, because excluding a unit is
#: about the *heating system* choice; these are always installable on top of it.
ALWAYS_AVAILABLE_UNIT_TYPES = ["PV", "WaterTankSH", "WaterTankDHW", "Battery", "ThermalSolar"]

#: Units removed from every scenario by default (not yet validated, or superseded), unless the scenario enforces them.
DEFAULT_UNITS_TO_EXCLUDE = ['HeatPump_Lake', 'DataHeat_SH', 'ORC_DC_district', 'HeatPump_Waste_heat']

#: Keys a grid may not hold, with the keys to use instead: their former names, and the capacity decided by the optimization.
FORBIDDEN_GRID_KEYS = {'Network_ext': 'Network_capacity_existing', 'ReinforcementOfNetwork': 'Network_capacity_options',
                       'Network_capacity': 'Network_capacity_existing', 'ReinforcementOfLine': 'Line_capacity_options'}

#: Explains the keys setting the capacity of the networks and of the lines, in the errors raised on a misused key.
CAPACITY_KEYS_HELP = ("The existing capacity of a network is Network_capacity_existing [kW], and the larger capacities it can be "
                      "reinforced to Network_capacity_options, both set in its grid: the optimization decides Network_capacity. "
                      "The lines connecting the buildings follow the same names: Line_capacity_options in the grid, and "
                      "Line_capacity_existing, per building, in the parameters.")

#: Part-load performance of the heat pumps and air conditioners, per ``UnitOfType``: file of
#: ``reho/data/infrastructure/``, indexed by the sink and source temperatures.
PERFORMANCE_MAP_FILES = {'HeatPump': 'HP_parameters.csv', 'AirConditioner': 'AC_parameters.csv', 'HeatPump_WH': 'HP_parameters.csv'}

#: Suffix of the AMPL names filled by a performance map, per ``UnitOfType``: the waste-heat heat pumps share the
#: map of the heat pumps, under names of their own (``HP_Eta_nominal_WH``, ``HP_Tsink_WH``, ...).
PERFORMANCE_MAP_SUFFIXES = {'HeatPump_WH': '_WH'}

#: Performance maps already read, per file and suffix, see :func:`read_performance_map`.
_performance_maps = {}


def read_performance_map(unit_type):
    """Read the part-load performance of a type of heat pump or air conditioner.

    The files are static package data: each of them is read once per process.

    Parameters
    ----------
    unit_type : str
        ``UnitOfType`` of the unit, a key of :data:`PERFORMANCE_MAP_FILES`.

    Returns
    -------
    pandas.DataFrame
        Nominal efficiency and maximum power, e.g. ``HP_Eta_nominal`` and ``HP_Pmax_nominal``, indexed by
        the sink and source temperatures, whose levels are named after the AMPL sets they fill, e.g.
        ``HP_Tsink`` and ``HP_Tsource``. These names carry the suffix of :data:`PERFORMANCE_MAP_SUFFIXES`.
        The DataFrame is shared by every caller: do not modify it in place.
    """
    file = os.path.join(path_to_infrastructure, PERFORMANCE_MAP_FILES[unit_type])
    suffix = PERFORMANCE_MAP_SUFFIXES.get(unit_type, '')
    if (file, suffix) not in _performance_maps:
        performance = pd.read_csv(file, sep=';', index_col=[0, 1]).add_suffix(suffix)
        performance.index.names = [name + suffix for name in performance.index.names]
        _performance_maps[file, suffix] = performance
    return _performance_maps[file, suffix]


def check_grid_keys(keys, where):
    """Reject the keys a grid may not hold, see :data:`FORBIDDEN_GRID_KEYS`.

    Parameters
    ----------
    keys : iterable of str
        Keys of a grid, or columns of a layers file.
    where : str
        What the keys belong to, to locate them in the error message.

    Raises
    ------
    ValueError
        If one of the keys of :data:`FORBIDDEN_GRID_KEYS` is used.
    """
    forbidden = [key for key in FORBIDDEN_GRID_KEYS if key in keys]
    if forbidden:
        raise ValueError(f"{where} sets {', '.join(forbidden)}: use "
                         f"{', '.join(FORBIDDEN_GRID_KEYS[key] for key in forbidden)} instead. {CAPACITY_KEYS_HELP}")


def parse_capacity_options(value):
    """Read the capacities a network, or a line, can be reinforced to.

    Parameters
    ----------
    value : str, float, array-like or None
        A ``/``-separated string as in ``layers.csv`` (``'600/1000/2000'``), a number, a sequence of numbers,
        or nothing (``None``, ``NaN`` or an empty string) when it cannot be reinforced.

    Returns
    -------
    numpy.ndarray
        The capacities [kW], as floats.
    """
    if value is None or isinstance(value, str) and not value.strip():
        return np.array([])
    if isinstance(value, str):
        return np.array(value.split('/'), dtype=float)
    value = np.atleast_1d(np.asarray(value, dtype=float))
    return value[~np.isnan(value)]


def network_capacity_options(grid):
    """Capacities a network can be reinforced to, above its existing capacity.

    Parameters
    ----------
    grid : dict
        A grid, as returned by :func:`initialize_grids`.

    Returns
    -------
    numpy.ndarray
        The capacities of ``grid['Network_capacity_options']`` that exceed ``grid['Network_capacity_existing']``, sorted:
        a reinforcement cannot lower the capacity, so the others are ignored.

    Raises
    ------
    ValueError
        If reinforcements are given without the existing capacity they reinforce.
    """
    options = parse_capacity_options(grid.get('Network_capacity_options'))
    if options.size == 0:
        return options
    if 'Network_capacity_existing' not in grid:
        raise ValueError(f"The grid {grid.get('Grid', '')} sets Network_capacity_options but not Network_capacity_existing, "
                         f"the existing capacity of the network it reinforces.")
    return np.unique(options[options > grid['Network_capacity_existing']])


class Infrastructure:
    """
    Characterizes all the sets and parameters which are connected to buildings, units and grids.

    Parameters
    ----------
    qbuildings_data : dict
        Buildings characterization
    units : dict
        Units characterization
    grids : dict
        Grids characterization
    """

    def __init__(self, qbuildings_data, units, grids):

        for name, grid in grids.items():
            check_grid_keys(grid, f"The grid {name}")

        self.units = units["building_units"]
        self.houses = {h: {'units': self.units, 'layers': grids} for h in qbuildings_data['buildings_data'].keys()}
        self.grids = grids
        if "district_units" in units:
            self.district_units = units["district_units"]
        else:
            self.district_units = []

        # Sets -------------------------------------------
        self.House = np.array(list(self.houses.keys()))
        self.Units = np.array([])
        self.UnitTypes = np.unique(np.array([self.houses[h]['units'][u]['UnitOfType'] for h in self.houses for u in range(len(self.houses[h]['units']))]))

        UnitTypeDistrict = np.array([self.district_units[i]["UnitOfType"] for i in range(len(self.district_units))])
        self.UnitTypes = np.unique(np.concatenate([self.UnitTypes, UnitTypeDistrict]))
        self.LayerTypes = np.array(['HeatCascade', 'ResourceBalance'])

        self.LayersOfType = {'HeatCascade': np.array(['HeatCascade']),  # default: each building has a heat cascade
                             'ResourceBalance': np.array(list(self.grids.keys()))}
        self.Layers = np.array(list(self.grids.keys()) + ['HeatCascade'])

        self.Services = np.array(['DHW', 'SH', 'Cooling'])

        ## Avoid warning if rSOC is not used but defined as a service. Still results are untouched, as the service is simply ignored.
        if 'rSOC' in self.UnitTypes:
            self.Services = np.append(self.Services,'rSOC_heat')

        self.UnitsOfType = {}
        for u in self.UnitTypes:
            self.UnitsOfType[u] = np.array([])

        self.UnitsOfLayer = {}
        for l in self.Layers:
            self.UnitsOfLayer[l] = np.array([])

        self.UnitsOfHouse = {}
        for h in self.House:
            self.UnitsOfHouse[h] = np.array([])

        self.UnitsOfService = {}
        for s in self.Services:
            self.UnitsOfService[s] = np.array([])

        self.UnitsOfDistrict = np.array([])

        self.HousesOfLayer = {}
        for l in self.Layers:
            self.HousesOfLayer[l] = np.array([])

        self.Network_capacity_options = {}
        self.Line_capacity_options = {}
        for l in grids.keys():
            self.Network_capacity_options[l] = network_capacity_options(grids[l])
            # The existing capacity of the lines is set per building, in the parameters: the sub-problem ignores the
            # options that do not exceed it
            self.Line_capacity_options[l] = np.unique(parse_capacity_options(grids[l].get('Line_capacity_options')))

        self.StreamsOfBuilding = {}
        self.StreamsOfUnit = {}
        self.TemperatureSets = {}
        self.Set = {}

        # Parameter --------------------------------
        self.Units_flowrate = pd.DataFrame()
        self.Grids_Parameters = pd.DataFrame()
        self.Units_Parameters = pd.DataFrame()
        self.Streams_H = pd.DataFrame()

        self.HP_parameters = {}

        self.generate_structure()
        self.generate_parameter()

    def generate_structure(self):
        """
        Build the sets describing the district: units, layers, services and heat-cascade streams.

        Each building unit is instantiated once per building as ``<Unit>_<Building>``, and registered in
        ``Units``, ``UnitsOfType``, ``UnitsOfLayer``, ``UnitsOfHouse`` and ``UnitsOfService``. District
        units keep their name and are also listed in ``UnitsOfDistrict``. Each building is listed in
        ``HousesOfLayer`` for the layers it is connected to.

        The streams of a unit are named after the unit, e.g. ``NG_Boiler_Building1_h_ht``. Every building
        has three streams of its own: ``<Building>_c_lt`` and ``<Building>_c_mt`` for space heating, and
        ``<Building>_h_lt`` for cooling.

        All the sets are finally gathered in the dictionary ``Set``, which is passed to AMPL. Called by
        the constructor.
        """

        # The indexes h_ht, h_mt, h_lt, c_ht state for the discretization of the streams. They are connected to the heat cascade.
        # h_ht: hotstream_hightemperature. h_mt: hotstream_mediumtemperature. h_lt: hotstream_lowtemperature. c_ht: coldstream_hightemperature

        for h in self.House:
            # Units
            for u in self.houses[h]['units']:
                complete_name = u['Unit'] + '_' + h

                self.Units = np.append(self.Units, [complete_name])
                self.UnitsOfType[u['UnitOfType']] = np.append(self.UnitsOfType[u['UnitOfType']], [complete_name])
                for l in u['UnitOfLayer']:
                    self.UnitsOfLayer[l] = np.append(self.UnitsOfLayer[l], [complete_name])
                self.UnitsOfHouse[h] = np.append(self.UnitsOfHouse[h], [complete_name])
                for s in u['UnitOfService']:
                    self.UnitsOfService[s] = np.append(self.UnitsOfService[s], [complete_name])

                # Streams
                self.StreamsOfBuilding[h] = np.array(
                    [h + '_c_lt', h + '_c_mt', h + '_h_lt'])  # c_mt  c_lt - space heat demand discretized in 2 streams, _- h_lt for cooling
                self.StreamsOfUnit[complete_name] = np.array([])
                for s in u['StreamsOfUnit']:
                    stream = u['Unit'] + '_' + h + '_' + s
                    self.StreamsOfUnit[complete_name] = np.append(self.StreamsOfUnit[complete_name], stream)

            # Layers
            for l in self.houses[h]['layers']:
                self.HousesOfLayer[l] = np.append(self.HousesOfLayer[l], [h])
                
        # District units
        for u in self.district_units:
            name = u['Unit']
            self.Units = np.append(self.Units, [name])
            self.UnitsOfDistrict = np.append(self.UnitsOfDistrict, [name])
            self.UnitsOfType[u['UnitOfType']] = np.append(self.UnitsOfType[u['UnitOfType']], [name])
            for l in u['UnitOfLayer']:
                self.UnitsOfLayer[l] = np.append(self.UnitsOfLayer[l], [name])

            for s in u['UnitOfService']:
                self.UnitsOfService[s] = np.append(self.UnitsOfService[s], [name])

            self.StreamsOfUnit[name] = np.array([])
            for s in u['StreamsOfUnit']:
                stream = u['Unit'] + '_' + s
                self.StreamsOfUnit[name] = np.append(self.StreamsOfUnit[name], stream)

        self.__generate_set_dict()  # generate dictionary containing all sets for AMPL

    def __generate_set_dict(self):

        self.Set['UnitTypes'] = self.UnitTypes
        self.Set['LayerTypes'] = self.LayerTypes
        self.Set['House'] = np.array(list(self.House))
        self.Set['Services'] = self.Services
        self.Set['Units'] = self.Units
        self.Set['UnitsOfType'] = self.UnitsOfType
        self.Set['UnitsOfHouse'] = self.UnitsOfHouse
        self.Set['UnitsOfService'] = self.UnitsOfService
        self.Set['UnitsOfDistrict'] = self.UnitsOfDistrict

        self.Set['Layers'] = self.Layers
        self.Set['LayersOfType'] = self.LayersOfType
        self.Set['UnitsOfLayer'] = self.UnitsOfLayer
        self.Set['HousesOfLayer'] = self.HousesOfLayer
        self.Set['StreamsOfBuilding'] = self.StreamsOfBuilding
        self.Set['StreamsOfUnit'] = self.StreamsOfUnit

        self.Set['Network_capacity_options'] = self.Network_capacity_options
        self.Set['Line_capacity_options'] = self.Line_capacity_options

    def generate_parameter(self):
        """
        Build the parameters of the units, grids and heat-cascade streams.

        The following attributes are filled:

        - ``Units_flowrate``: upper bound of the flow each unit draws from (``Units_flowrate_in``) and
          delivers to (``Units_flowrate_out``) each layer, indexed by ``(Layer, Unit)``.
        - ``Units_Parameters``: size bounds, investment costs, lifetime and embodied emissions of each
          unit, see :meth:`add_unit_parameters`.
        - ``Grids_Parameters``: tariffs, emission factors and connection parameters of each layer.
        - ``HP_parameters``: nominal efficiency and maximum power of the heat pumps and air conditioners
          for each pair of sink and source temperatures, read from ``HP_parameters.csv`` and
          ``AC_parameters.csv``, see :func:`read_performance_map`. The temperature sets are added to ``Set``.
        - ``Streams_H``: whether each stream is hot (``Streams_Hin`` = 1) or cold (``Streams_Hout`` = 1).
        - ``Streams``: all the streams of the district.

        Called by the constructor, after :meth:`generate_structure`.

        Raises
        ------
        ValueError
            If the name of a stream contains neither ``_h_`` (hot) nor ``_c_`` (cold).
        """
        # Units Flows -----------------------------------------------------------

        all_units_flowrate = []

        for h in self.House:
            units = self.houses[h]['units']
            for unit in units:
                unit_name = unit['Unit'] + "_" + h
                for layer, val in unit['Units_flowrate_out'].items():
                    all_units_flowrate.append({
                        'House': h,
                        'Unit': unit_name,
                        'Layer': layer,
                        'Direction': 'out',
                        'Flowrate': val
                    })
                for layer, val in unit['Units_flowrate_in'].items():
                    all_units_flowrate.append({
                        'House': h,
                        'Unit': unit_name,
                        'Layer': layer,
                        'Direction': 'in',
                        'Flowrate': val
                    })

        df = pd.DataFrame(all_units_flowrate)
        self.Units_flowrate = df.pivot_table(index=['Layer', 'Unit'], columns='Direction', values='Flowrate',
                                             fill_value=0)
        self.Units_flowrate.columns = ['Units_flowrate_in', 'Units_flowrate_out']

        for u in self.district_units:
            df_i = pd.DataFrame()
            df_o = pd.DataFrame()
            name = u['Unit']
            for i in u['Units_flowrate_in']:
                idx = pd.MultiIndex.from_tuples([(i, name)], names=['Layer', 'Unit'])
                df = pd.DataFrame(u['Units_flowrate_in'][i], index=idx, columns=['Units_flowrate_in'])
                df_i = pd.concat([df_i, df])
            for o in u['Units_flowrate_out']:
                idx = pd.MultiIndex.from_tuples([(o, name)], names=['Layer', 'Unit'])
                df = pd.DataFrame(u['Units_flowrate_out'][o], index=idx, columns=['Units_flowrate_out'])
                df_o = pd.concat([df_o, df])

            df = pd.concat([df_o, df_i], axis=1)
            self.Units_flowrate = pd.concat([self.Units_flowrate, df])

        # Units Costs -----------------------------------------------------------
        for u in self.houses[self.House[0]]['units']:
            self.add_unit_parameters(u['Unit'] + '_' + self.House[0], u)

        Units_Parameters_0 = self.Units_Parameters.copy()
        for h in self.House[1:]:
            idx_h = [idx.replace(self.House[0], h) for idx in Units_Parameters_0.index.values]
            Units_Parameters_h = Units_Parameters_0.copy()
            Units_Parameters_h.index = idx_h
            self.Units_Parameters = pd.concat([self.Units_Parameters, Units_Parameters_h])

        for u in self.district_units:
            self.add_unit_parameters(u['Unit'], u)

        # Grids
        keys = [key for key in self.grids["Electricity"] if key not in ["ref_unit", 'Grid', "Network_capacity_options", "Line_capacity_options"]]

        for g in self.grids:
            df = pd.DataFrame([[self.grids[g][key] for key in keys]], index=[g], columns=keys)
            self.Grids_Parameters = pd.concat([self.Grids_Parameters, df])

        # HP and AC temperatures
        for h in self.House:

            for u in self.houses[h]['units']:
                if u['UnitOfType'] in PERFORMANCE_MAP_FILES:
                    complete_name = u['Unit'] + '_' + h
                    df = pd.concat([read_performance_map(u['UnitOfType'])], keys=[complete_name])
                    # the sink and source temperatures fill the sets named after the index, e.g. HP_Tsink and HP_Tsource
                    for temperatures in df.index.names[1:]:
                        self.TemperatureSets[temperatures] = np.array(df.index.get_level_values(temperatures).unique())

                    if u['UnitOfType'] in self.HP_parameters:
                        self.HP_parameters[u['UnitOfType']] = pd.concat([self.HP_parameters[u['UnitOfType']], df])
                    else:
                        self.HP_parameters[u['UnitOfType']] = df

        for key in self.TemperatureSets:  # add additional sets from units to total set
            self.Set[key] = self.TemperatureSets[key]

        # Streams

        Hin = {}
        Hout = {}
        for unitstreams in dict(self.StreamsOfUnit, **self.StreamsOfBuilding).values():  # union of dict
            for s in unitstreams:
                if s.count('_h_') == 1:  # check if it's a hot stream
                    Hin[s] = 1
                    Hout[s] = 0
                elif s.count('_c_') == 1:  # check if it's a cold stream
                    Hin[s] = 0
                    Hout[s] = 1
                else:
                    raise ValueError(
                        f"Stream {s!r} is neither hot nor cold: a stream name must contain exactly one "
                        "'_h_' (hot) or '_c_' marker, e.g. 'NG_Boiler_Building1_h_ht'."
                    )

        dfin = pd.DataFrame.from_dict(Hin, orient='index', columns=['Streams_Hin'])
        dfout = pd.DataFrame.from_dict(Hout, orient='index', columns=['Streams_Hout'])
        self.Streams_H = pd.concat([dfin, dfout], axis=1)

        Streams_set = []
        for h in self.houses:
            for unit in self.UnitsOfHouse[h]:
                Streams_set = np.concatenate([Streams_set, self.StreamsOfUnit[unit]])
            Streams_set = np.concatenate([Streams_set, self.StreamsOfBuilding[h]])
        self.Streams = Streams_set

    def add_unit_parameters(self, complete_name, unit_param):
        """
        Append the size bounds, costs, lifetime and embodied emissions of a unit to ``Units_Parameters``.

        Parameters
        ----------
        complete_name : str
            Name of the unit instance, e.g. ``'PV_Building1'``.
        unit_param : dict
            Characteristics of the unit, with the keys ``Units_Fmin``, ``Units_Fmax``, ``Cost_inv1``,
            ``Cost_inv2``, ``lifetime``, ``GWP_unit1`` and ``GWP_unit2``.
        """
        keys = ['Units_Fmin', 'Units_Fmax', 'Cost_inv1', 'Cost_inv2', 'lifetime', 'GWP_unit1', 'GWP_unit2']
        df = pd.DataFrame([[unit_param[key] for key in keys]], columns=keys, index=[complete_name])
        self.Units_Parameters = pd.concat([self.Units_Parameters, df])


def prepare_units_df(file, exclude_units=None, grids=None):
    """
    Prepares the df that will be used by initialize_units.

    Parameters
    ----------
    file : str
        Name of the file where to find the units' data (building, district or storage).
    exclude_units : list of str
        The units you want to exclude, given through ``initialize_units``.
    grids : dict
        Grids given through ``initialize_grids``.

    Returns
    -------
    pd.DataFrame()
        Representation of the units' data.

    See also
    --------
    initialize_units

    Notes
    -----
    - Make sure the name of the columns you are using are the same as the one from the default files, that can be found
      in ``data/infrastructure``.
    - The name of the units, which will be used as keys, do not matter but the *UnitOfType* must be along a defined
      list of possibilities.
    """

    def transform_into_list(column):
        for idx, row in column.items():
            # Cells hold '/'-separated lists that are numeric ('80/60') or symbolic
            # ('DHW/ SH'); try the numeric reading first and fall back on strings.
            try:
                new_value = [float(el) for el in row.split('/') if el != '']
            except ValueError:
                new_value = [el.strip() for el in row.split('/') if el != '']
            if unit_data.index.get_loc(idx) == 0 and new_value == []:
                unit_data.at[idx, column.name] = ['']
            unit_data.at[idx, column.name] = new_value

    def check_validity(row):
        if len(row['StreamsOfUnit']) > 1 and len(row['stream_Tin']) == 1:
            row['stream_Tin'] = [row['stream_Tin'][0] for el in row['StreamsOfUnit']]
        if len(row['StreamsOfUnit']) > 1 and len(row['stream_Tout']) == 1:
            row['stream_Tout'] = [row['stream_Tout'][0] for el in row['StreamsOfUnit']]
        return row

    def add_flowrate_values(row):

        flow_in = {}
        flow_out = {}

        for layer in row['Units_flowrate_in']:
            flow_in[layer] = 1e6
            if layer not in row['Units_flowrate_out']:
                flow_out[layer] = 0

        for layer in row['Units_flowrate_out']:
            flow_out[layer] = 1e6
            if layer not in row['Units_flowrate_in']:
                flow_in[layer] = 0

        row['Units_flowrate_in'] = flow_in
        row['Units_flowrate_out'] = flow_out

        return row

    exclude_units = [] if exclude_units is None else exclude_units
    unit_data = file_reader(file)

    list_of_columns = ['Unit', 'UnitOfLayer', 'UnitOfService', 'StreamsOfUnit', 'Units_flowrate_in', 'Units_flowrate_out',
                       'stream_Tin', 'stream_Tout']
    try:
        unit_data[list_of_columns] = unit_data[list_of_columns].fillna('').astype(str)
        # Columns from list_of_columns[1:] get their string cells replaced by Python lists
        # (see transform_into_list). Since pandas 3.0 strings are immutable and reject list
        # values, cast these columns to object dtype before the in-place transformation.
        unit_data[list_of_columns[1:]] = unit_data[list_of_columns[1:]].astype(object)
        unit_data[list_of_columns[1:]].apply(transform_into_list)  # keep Unit as str
    except KeyError:
        raise KeyError('There is a name in the columns of your csv. Make sure the columns correspond to the default'
                       ' files in data/infrastructure.')

    # Apply stream validity checks
    unit_data = unit_data.apply(check_validity, axis=1)

    # Determine valid grid layers
    grid_layers = list(grids.keys()) + ['HeatCascade'] if grids else ['Electricity', 'NaturalGas', 'HeatCascade']
    units_to_keep = ALWAYS_AVAILABLE_UNIT_TYPES

    # Filter valid units first
    valid_units = unit_data[
        unit_data['UnitOfLayer'].apply(lambda layers: all(layer in grid_layers for layer in layers)) &
        (~unit_data['Unit'].isin(exclude_units) | unit_data['UnitOfType'].isin(units_to_keep))
        ]

    valid_units = valid_units.apply(add_flowrate_values, axis=1)
    return valid_units


def _interperiod_unit_files(interperiod_data):
    """Files of the inter-period storage units to read, see ``interperiod_data`` in :func:`initialize_units`.

    Returns
    -------
    tuple of str or None
        The file of the building units and the file of the district units, None when not to read.

    Raises
    ------
    TypeError
        If ``interperiod_data``, or one of its values, has an unsupported type.
    KeyError
        If a dict holds a key other than ``'building'`` and ``'district'``, or their former names
        ``'building_units_IP'`` and ``'district_units_IP'``.
    """
    defaults = {"building": os.path.join(path_to_infrastructure, "building_units_IP.csv"),
                "district": os.path.join(path_to_infrastructure, "district_units_IP.csv")}
    former_keys = {"building_units_IP": "building", "district_units_IP": "district"}
    if interperiod_data is None or interperiod_data is False:
        return None, None
    if interperiod_data is True:
        return defaults["building"], defaults["district"]
    if isinstance(interperiod_data, str) and interperiod_data in defaults:
        return tuple(defaults[scale] if scale == interperiod_data else None for scale in ("building", "district"))
    if not isinstance(interperiod_data, dict):
        raise TypeError(f"interperiod_data must be None, True, 'building', 'district' or a dict, got {interperiod_data!r}.")

    unknown = set(interperiod_data) - set(defaults) - set(former_keys)
    if unknown:
        raise KeyError(f"interperiod_data accepts the keys 'building' and 'district', got {sorted(unknown)}.")
    interperiod_data = {former_keys.get(key, key): value for key, value in interperiod_data.items()}
    files = []
    for scale in ("building", "district"):
        value = interperiod_data.get(scale)
        if value is None or value is False:
            files.append(None)
        elif value is True:
            files.append(defaults[scale])
        elif isinstance(value, (str, os.PathLike)):
            files.append(value)
        else:
            raise TypeError(f"interperiod_data[{scale!r}] must be True or the path of a file, got {value!r}.")
    return tuple(files)


def initialize_units(scenario, grids=None, building_data=os.path.join(path_to_infrastructure, "building_units.csv"), district_data=None, interperiod_data=None):
    """
    Initializes the available units for the energy system.

    Parameters
    ----------
    scenario : dict or None
        A dictionary containing information about the scenario.
    grids : dict or None, optional
        Information about the energy layers considered. If None, ``['Electricity', 'NaturalGas', 'Oil', 'Wood', 'Data', 'Heat']``.
    building_data : str, optional
        Path to the CSV file containing building unit data. Default is 'building_units.csv'.
    district_data : str or bool or None, optional
        Path to the CSV file containing district unit data. If True, district units are initialized with 'district_units.csv'.
        If None, district units will not be considered. Default is None.
    interperiod_data : bool or str or dict, optional
        Inter-period storage units. True reads ``building_units_IP.csv`` and, with district units,
        ``district_units_IP.csv``; ``'building'`` or ``'district'`` reads only one of them. A dict chooses
        per scale, under the keys ``'building'`` and ``'district'``: True for the default file, or the path of
        a custom one. Default is None, which considers no inter-period storage.

    Returns
    -------
    dict
        Contains building_units and district_units.

    See also
    --------
    initialize_grids

    Notes
    -----
    - The default files are located in ``reho/data/infrastructure/``.
    - The custom files can be given as absolute or relative path.
    - The units of :data:`DEFAULT_UNITS_TO_EXCLUDE` are excluded, unless ``scenario['enforce_units']`` lists them.

    Examples
    --------
    >>> units = infrastructure.initialize_units(scenario, grids, building_data="custom_building_units.csv",
    ...                                        district_data="custom_district_units.csv", interperiod_data=True)
    """

    scenario = scenario or {}
    enforced = set(scenario.get("enforce_units", []))
    exclude_units = list(scenario.get("exclude_units", [])) + [unit for unit in DEFAULT_UNITS_TO_EXCLUDE if unit not in enforced]

    building_units = prepare_units_df(building_data, exclude_units, grids)

    if 'rSOC' not in building_units['Unit'].values:
        building_units['UnitOfService'] = building_units['UnitOfService'].apply(
            lambda services: [s for s in services if s != 'rSOC_heat'])

    building_units = np.array(building_units.to_dict(orient="records"))

    building_IP_file, district_IP_file = _interperiod_unit_files(interperiod_data)
    if building_IP_file is not None:
        building_units_IP = np.array(prepare_units_df(building_IP_file, exclude_units, grids).to_dict(orient="records"))
        if len(building_units_IP) > 0:
            building_units = np.concatenate([building_units, building_units_IP])

    if district_data is True:
        district_units = np.array(prepare_units_df(os.path.join(path_to_infrastructure, "district_units.csv"), exclude_units, grids=grids).to_dict(orient="records"))
    elif isinstance(district_data, str):
        district_units = np.array(prepare_units_df(district_data, exclude_units, grids=grids).to_dict(orient="records"))
    else:
        district_units = []

    if district_data and district_IP_file is not None:
        district_units_IP = np.array(prepare_units_df(district_IP_file, exclude_units, grids).to_dict(orient="records"))
        if len(district_units_IP) > 0:
            district_units = np.concatenate([district_units, district_units_IP])

    units = {"building_units": building_units, "district_units": district_units}

    return units


def initialize_grids(available_grids=None, file=os.path.join(path_to_infrastructure, "layers.csv")):
    """
    Initializes grid information for the energy system.

    Parameters
    ----------
    available_grids : dict, optional
        A dictionary specifying the available grids and their parameters. The keys represent grid names,
        and the values are dictionaries containing optional parameters ['Cost_demand_cst',
        'Cost_supply_cst', 'GWP_demand_cst', 'GWP_supply_cst', 'Cost_connection', 'Network_capacity_existing',
        'Network_capacity_options'], which override the values of the file.
    file : str, optional
        Path to the CSV file containing grid data. Default is 'layers.csv' in the data/infrastructure/ folder.

    Returns
    -------
    dict
        Contains information about the initialized grids.

    See also
    --------
    initialize_units

    Notes
    -----
    - If one wants to use its one custom grid file, he should pay attention that the name of the layer and the parameters correspond.
    - Adding a layer in a custom file will not add it to the model as it is not modelized.

    Examples
    --------
    >>> available_grids = {'Electricity': {'Cost_demand_cst': 0.1, 'GWP_supply_cst': 0.05}, 'NaturalGas': {'Cost_supply_cst': 0.15}}
    >>> grids = initialize_grids(available_grids, file="custom_layers.csv")

    The existing capacity of a network [kW], and the larger capacities it can be reinforced to:

    >>> grids = initialize_grids({'Electricity': {'Network_capacity_existing': 100, 'Network_capacity_options': [150, 200, 250]},
    ...                           'NaturalGas': {}})
    """

    available_grids = DEFAULT_GRIDS.copy() if available_grids is None else available_grids

    grid_data = file_reader(file)
    grid_data = grid_data.set_index("Grid")
    check_grid_keys(grid_data.columns, f"The file {file}")

    grids = dict()
    for idx, row in grid_data.iterrows():
        if idx in available_grids.keys():
            grid_dict = row.to_dict()
            grid_dict['Grid'] = idx
            grid_dict['Network_demand_connection'] = 1e6 * grid_dict['Network_demand_connection']
            grid_dict['Network_supply_connection'] = 1e6 * grid_dict['Network_supply_connection']
            check_grid_keys(available_grids[idx], f"The grid {idx}")

            for key in ['Cost_demand_cst', 'Cost_supply_cst', 'GWP_demand_cst', 'GWP_supply_cst', 'Cost_connection',
                        'Network_capacity_existing', 'Network_capacity_options', 'Line_capacity_options']:
                if key in available_grids[idx]:
                    grid_dict[key] = available_grids[idx][key]
            grid_dict['Network_capacity_options'] = parse_capacity_options(grid_dict.get('Network_capacity_options'))
            if 'Line_capacity_options' in grid_dict:
                grid_dict['Line_capacity_options'] = parse_capacity_options(grid_dict['Line_capacity_options'])
            grids[idx] = grid_dict

    return grids
