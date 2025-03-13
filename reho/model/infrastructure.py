import os.path

import numpy as np
import pandas as pd

from reho.paths import *

__doc__ = """
File for handling infrastructure parameters.
"""


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
            self.ReinforcementOfNetwork = {}
            self.ReinforcementOfLine = {}
            for l in grids.keys():
                if 'ReinforcementOfNetwork' in grids[l].keys():
                    self.ReinforcementOfNetwork[l] = grids[l]['ReinforcementOfNetwork']
                else:
                    self.ReinforcementOfNetwork[l] = np.array([1e8])

                if 'ReinforcementOfLine' in grids[l].keys():
                    self.ReinforcementOfLine[l] = grids[l]['ReinforcementOfLine']
                else:
                    self.ReinforcementOfLine[l] = np.array([1e8])

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

        # The indexes h_ht, h_mt, h_lt, c_ht state for the discretization of the streams. They are connected to the heat cascade.
        # h_ht: hotstream_hightemperature. h_mt: hotstream_mediumtemperature. h_lt: hotstream_lowtemperature. c_ht: coldstream_hightemperature

        for h in self.House:
            # Units
            for u in self.houses[h]['units']:
                complete_name = u['name'] + '_' + h

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
                    stream = u['name'] + '_' + h + '_' + s
                    self.StreamsOfUnit[complete_name] = np.append(self.StreamsOfUnit[complete_name], stream)

            # Layers
            for l in self.houses[h]['layers']:
                self.HousesOfLayer[l] = np.append(self.HousesOfLayer[l], [h])
                
        # District units
        for u in self.district_units:
            name = u['name']
            self.Units = np.append(self.Units, [name])
            self.UnitsOfDistrict = np.append(self.UnitsOfDistrict, [name])
            self.UnitsOfType[u['UnitOfType']] = np.append(self.UnitsOfType[u['UnitOfType']], [name])
            for l in u['UnitOfLayer']:
                self.UnitsOfLayer[l] = np.append(self.UnitsOfLayer[l], [name])

            for s in u['UnitOfService']:
                self.UnitsOfService[s] = np.append(self.UnitsOfService[s], [name])

            self.StreamsOfUnit[name] = np.array([])
            for s in u['StreamsOfUnit']:
                stream = u['name'] + '_' + s
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

        if 'ReinforcementOfNetwork' in self.__dict__.keys():
            self.Set['ReinforcementOfNetwork'] = self.ReinforcementOfNetwork

        if 'ReinforcementOfLine' in self.__dict__.keys():
            self.Set['ReinforcementOfLine'] = self.ReinforcementOfLine

    def generate_parameter(self):
        # Units Flows -----------------------------------------------------------

        df_out = {unit["name"]: unit["Units_flowrate_out"] for unit in self.houses[self.House[0]]['units']}
        df_out = pd.DataFrame.from_dict(df_out).stack()
        df_in = {unit["name"]: unit["Units_flowrate_in"] for unit in self.houses[self.House[0]]['units']}
        df_in = pd.DataFrame.from_dict(df_in).stack()
        Units_flowrate = pd.concat([df_out, df_in], axis=1)
        Units_flowrate.columns = ['Units_flowrate_out', 'Units_flowrate_in']
        Units_flowrate.index = Units_flowrate.index.remove_unused_levels()

        for h in self.House:
            Units_flowrate_h = Units_flowrate.copy()
            Units_flowrate_h.index = Units_flowrate_h.index.set_levels(Units_flowrate.index.get_level_values(1).unique() + "_" + h, level=1)
            self.Units_flowrate = pd.concat([self.Units_flowrate, Units_flowrate_h])
        self.Units_flowrate.index.names = ['Layer', 'Unit']

        for u in self.district_units:
            df_i = pd.DataFrame()
            df_o = pd.DataFrame()
            name = u['name']
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
            self.add_unit_parameters(u['name'] + '_' + self.House[0], u)

        Units_Parameters_0 = self.Units_Parameters.copy()
        for h in self.House[1:]:
            idx_h = [idx.replace(self.House[0], h) for idx in Units_Parameters_0.index.values]
            Units_Parameters_h = Units_Parameters_0.copy()
            Units_Parameters_h.index = idx_h
            self.Units_Parameters = pd.concat([self.Units_Parameters, Units_Parameters_h])

        for u in self.district_units:
            self.add_unit_parameters(u['name'], u)

        # Grids
        keys = [key for key in self.grids["Electricity"] if key not in ["ref_unit", "name", "ReinforcementOfNetwork"]]

        for g in self.grids:
            df = pd.DataFrame([[self.grids[g][key] for key in keys]], index=[g], columns=keys)
            self.Grids_Parameters = pd.concat([self.Grids_Parameters, df])

        # HP and AC temperatures
        for h in self.House:

            for u in self.houses[h]['units']:
                if u['UnitOfType'] == 'AirConditioner' or u['UnitOfType'] == 'HeatPump':
                    complete_name = u['name'] + '_' + h
                    if u['UnitOfType'] == 'AirConditioner':
                        file = os.path.join(path_to_infrastructure, 'AC_parameters.txt')
                    elif u['UnitOfType'] == 'HeatPump':
                        file = os.path.join(path_to_infrastructure, 'HP_parameters.txt')

                    df = pd.read_csv(file, delimiter=';', index_col=[0, 1])
                    df = pd.concat([df], keys=[complete_name])
                    # get index sets of source and sink of HP
                    name, rest = df.columns[0].split('_', 1)
                    self.TemperatureSets[name + '_Tsink'] = np.array(df.index.get_level_values(1).unique())
                    self.TemperatureSets[name + '_Tsource'] = np.array(df.index.get_level_values(2).unique())

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
                    raise ('Stream ' + str(s) + ' cannot be classified as cold or hot')

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
        keys = ['Units_Fmin', 'Units_Fmax', 'Cost_inv1', 'Cost_inv2', 'lifetime', 'GWP_unit1', 'GWP_unit2']
        df = pd.DataFrame([[unit_param[key] for key in keys]], columns=keys, index=[complete_name])
        self.Units_Parameters = pd.concat([self.Units_Parameters, df])


def prepare_units_array(file, exclude_units=[], grids=None):
    """
    Prepares the array that will be used by initialize_units.

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
    np.array
        Contains one dictionary in each cell, with the parameters for a specific unit.

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
            try:
                new_value = [float(el) for el in row.split('/') if el != '']
            except:
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

    unit_data = file_reader(file)
    unit_data = unit_data.set_index("Unit")

    list_of_columns = ['UnitOfLayer', 'UnitOfService', 'StreamsOfUnit', 'Units_flowrate_in', 'Units_flowrate_out',
                       'stream_Tin', 'stream_Tout']
    try:
        unit_data[list_of_columns] = unit_data[list_of_columns].fillna('').astype(str)
        unit_data[list_of_columns].apply(transform_into_list)
    except KeyError:
        raise KeyError('There is a name in the columns of your csv. Make sure the columns correspond to the default'
                       ' files in data/infrastructure.')

    unit_data = unit_data.apply(check_validity, axis=1)

    units = []
    if grids is None:
        grid_layers = ['Electricity', 'NaturalGas', 'Oil', 'Wood', 'Data', 'Heat', 'HeatCascade']
    else:
        grid_layers = list(grids.keys()) + ['HeatCascade']

    # Some units need to be defined for thermodynamical reasons in the model. They can still be set to 0.
    units_to_keep = ["PV", "WaterTankSH", "WaterTankDHW", "Battery", "ThermalSolar"]

    for idx, row in unit_data.iterrows():
        if all([layer in grid_layers for layer in row["UnitOfLayer"]]):
            if idx not in exclude_units or row['UnitOfType'] in units_to_keep:
                unit_dict = row.to_dict()
                unit_dict['name'] = idx
                flow_in = {}
                flow_out = {}
                for el in row['Units_flowrate_in']:
                    flow_in[el] = 1e6
                    if el not in row['Units_flowrate_out']:
                        flow_out[el] = 0
                for el in row['Units_flowrate_out']:
                    flow_out[el] = 1e6
                    if el not in row['Units_flowrate_in']:
                        flow_in[el] = 0
                unit_dict['Units_flowrate_in'] = flow_in
                unit_dict['Units_flowrate_out'] = flow_out
                units = np.concatenate([units, [unit_dict]])

    return units


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
    interperiod_data : dict or bool or None, optional
        Paths to the CSV file(s) containing inter-period storage units data. If True, units are initialized with 'building_units_IP.csv' and 'district_units_IP.csv'.
        If None, storage units won't be considered. Default is None.

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

    Examples
    --------
    >>> units = infrastructure.initialize_units(scenario, grids, building_data="custom_building_units.csv",
    ...                                         district_data="custom_district_units.csv", interperiod_data=True)
    """

    default_units_to_exclude = ['HeatPump_Lake', 'DataHeat_SH']
    if "exclude_units" not in scenario:
        exclude_units = default_units_to_exclude
    else:
        exclude_units = scenario["exclude_units"] + default_units_to_exclude

    building_units = prepare_units_array(building_data, exclude_units, grids)

    if interperiod_data is True:
        building_units = np.concatenate([building_units, prepare_units_array(os.path.join(path_to_infrastructure, "building_units_IP.csv"), exclude_units=exclude_units, grids=grids)])
    elif isinstance(interperiod_data, dict):
        building_units = np.concatenate([building_units, prepare_units_array(interperiod_data["building_units_IP"], exclude_units=exclude_units, grids=grids)])

    if district_data is True:
        district_units = prepare_units_array(os.path.join(path_to_infrastructure, "district_units.csv"), exclude_units, grids=grids)
    elif isinstance(district_data, str):
        district_units = prepare_units_array(district_data, exclude_units, grids=grids)
    else:
        district_units = []

    if district_data is not None:
        if interperiod_data is True:
            district_units = np.concatenate([district_units, prepare_units_array(os.path.join(path_to_infrastructure, "district_units_IP.csv"), exclude_units=exclude_units, grids=grids)])
        elif isinstance(interperiod_data, dict):
            district_units = np.concatenate([district_units, prepare_units_array(interperiod_data["district_units_IP"], exclude_units=exclude_units, grids=grids)])

    units = {"building_units": building_units, "district_units": district_units}

    return units


def initialize_grids(available_grids={'Electricity': {}, 'NaturalGas': {}},
                     file=os.path.join(path_to_infrastructure, "layers.csv")):
    """
    Initializes grid information for the energy system.

    Parameters
    ----------
    available_grids : dict, optional
        A dictionary specifying the available grids and their parameters. The keys represent grid names,
        and the values are dictionaries containing optional parameters ['Cost_demand_cst',
        'Cost_supply_cst', 'GWP_demand_cst', 'GWP_supply_cst'].
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
    """

    grid_data = file_reader(file)
    grid_data = grid_data.set_index("Grid")

    grids = dict()
    for idx, row in grid_data.iterrows():
        if idx in available_grids.keys():
            grid_dict = row.to_dict()
            grid_dict['name'] = idx
            grid_dict['Network_demand_connection'] = 1e6 * grid_dict['Network_demand_connection']
            grid_dict['Network_supply_connection'] = 1e6 * grid_dict['Network_supply_connection']
            grid_dict["ReinforcementOfNetwork"] = np.array(grid_dict["ReinforcementOfNetwork"].split("/")).astype(float)

            if 'Cost_demand_cst' in available_grids[idx]:
                grid_dict['Cost_demand_cst'] = available_grids[idx]['Cost_demand_cst']
            if 'Cost_supply_cst' in available_grids[idx]:
                grid_dict['Cost_supply_cst'] = available_grids[idx]['Cost_supply_cst']
            if 'GWP_demand_cst' in available_grids[idx]:
                grid_dict['GWP_demand_cst'] = available_grids[idx]['GWP_demand_cst']
            if 'GWP_supply_cst' in available_grids[idx]:
                grid_dict['GWP_supply_cst'] = available_grids[idx]['GWP_supply_cst']
            if 'Cost_connection' in available_grids[idx]:
                grid_dict['Cost_connection'] = available_grids[idx]['Cost_connection']
            grids[idx] = grid_dict

    return grids
