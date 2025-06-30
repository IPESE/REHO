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

        if 'ReinforcementOfNetwork' in self.__dict__.keys():
            self.Set['ReinforcementOfNetwork'] = self.ReinforcementOfNetwork

        if 'ReinforcementOfLine' in self.__dict__.keys():
            self.Set['ReinforcementOfLine'] = self.ReinforcementOfLine

    def generate_parameter(self):
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
        keys = [key for key in self.grids["Electricity"] if key not in ["ref_unit", 'Grid', "ReinforcementOfNetwork"]]

        for g in self.grids:
            df = pd.DataFrame([[self.grids[g][key] for key in keys]], index=[g], columns=keys)
            self.Grids_Parameters = pd.concat([self.Grids_Parameters, df])

        # HP and AC temperatures
        for h in self.House:
            for u in self.houses[h]['units']:
                unit_type = u['UnitOfType']
                if unit_type in ['AirConditioner', 'HeatPump', 'HeatPump_WH']:
                    complete_name = u['Unit'] + '_' + h

                    # Determine which file to load
                    if unit_type == 'AirConditioner':
                        file = os.path.join(path_to_infrastructure, 'AC_parameters.txt')
                    else:  # HeatPump or HeatPump_WH
                        file = os.path.join(path_to_infrastructure, 'HP_parameters.txt')

                    df = pd.read_csv(file, delimiter=';', index_col=[0, 1])

                    # Modify column names if it's HeatPump_WH
                    if unit_type == 'HeatPump_WH':
                        df.columns = [f"{col}_WH" for col in df.columns]

                        # Prefix with complete unit name (unit + house)
                        df = pd.concat([df], keys=[complete_name])

                        # Extract the index sets for Tsink and Tsource
                        name, rest = df.columns[0].split('_', 1)
                        self.TemperatureSets[name + '_Tsink_WH'] = np.array(df.index.get_level_values(1).unique())
                        self.TemperatureSets[name + '_Tsource_WH'] = np.array(df.index.get_level_values(2).unique())
                    else:
                        # Prefix with complete unit name (unit + house)
                        df = pd.concat([df], keys=[complete_name])

                        # Extract the index sets for Tsink and Tsource
                        name, rest = df.columns[0].split('_', 1)
                        self.TemperatureSets[name + '_Tsink'] = np.array(df.index.get_level_values(1).unique())
                        self.TemperatureSets[name + '_Tsource'] = np.array(df.index.get_level_values(2).unique())
                    # Store in self.HP_parameters
                    if unit_type in self.HP_parameters:
                        self.HP_parameters[unit_type] = pd.concat([self.HP_parameters[unit_type], df])
                    else:
                        self.HP_parameters[unit_type] = df

        # Update the global sets
        for key in self.TemperatureSets:
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



def prepare_units_df(file, exclude_units=[], grids=None):
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

    unit_data = file_reader(file)

    list_of_columns = ['Unit', 'UnitOfLayer', 'UnitOfService', 'StreamsOfUnit', 'Units_flowrate_in', 'Units_flowrate_out',
                       'stream_Tin', 'stream_Tout']
    try:
        unit_data[list_of_columns] = unit_data[list_of_columns].fillna('').astype(str)
        unit_data[list_of_columns[1:]].apply(transform_into_list) # keep Unit as str
    except KeyError:
        raise KeyError('There is a name in the columns of your csv. Make sure the columns correspond to the default'
                       ' files in data/infrastructure.')

    # Apply stream validity checks
    unit_data = unit_data.apply(check_validity, axis=1)

    # Determine valid grid layers
    grid_layers = list(grids.keys()) + ['HeatCascade'] if grids else ['Electricity', 'NaturalGas', 'HeatCascade']
    units_to_keep = ["PV", "WaterTankSH", "WaterTankDHW", "Battery", "ThermalSolar"]

    # Filter valid units first
    valid_units = unit_data[
        unit_data['UnitOfLayer'].apply(lambda layers: all(layer in grid_layers for layer in layers)) &
        (~unit_data['Unit'].isin(exclude_units) | unit_data['UnitOfType'].isin(units_to_keep))
        ]

    valid_units = valid_units.apply(add_flowrate_values, axis=1)
    return valid_units


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
    interperiod_data : dict or bool or str, None, optional TODO A. Waeber
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

    default_units_to_exclude = ['HeatPump_Lake', 'DataHeat_SH', 'HeatPump_Waste_heat']
    default_units_to_exclude = [
        u for u in default_units_to_exclude
        if u not in scenario["enforce_units"]
    ]
    if "exclude_units" not in scenario:
        exclude_units = default_units_to_exclude
    else:
        exclude_units = scenario["exclude_units"] + default_units_to_exclude

    building_units = prepare_units_df(building_data, exclude_units, grids)

    if 'rSOC' not in building_units['Unit'].values:
        building_units['UnitOfService'] = building_units['UnitOfService'].apply(
            lambda services: [s for s in services if s != 'rSOC_heat'])

    building_units= np.array(building_units.to_dict(orient="records"))

    if interperiod_data != 'district' and interperiod_data is not None:
        building_units_IP = np.array(prepare_units_df(os.path.join(path_to_infrastructure, "building_units_IP.csv"), exclude_units=exclude_units, grids=grids).to_dict(orient="records"))
    elif isinstance(interperiod_data, dict) and 'building_units_IP' in interperiod_data:
        building_units_IP = np.array(prepare_units_df(interperiod_data["building_units_IP"], exclude_units=exclude_units, grids=grids).to_dict(orient="records"))
    else:
        building_units_IP = []

    if len(building_units_IP) > 0:
        building_units = np.concatenate([building_units, building_units_IP])

    if district_data is True:
        district_units = np.array(prepare_units_df(os.path.join(path_to_infrastructure, "district_units.csv"), exclude_units, grids=grids).to_dict(orient="records"))
    elif isinstance(district_data, str):
        district_units = np.array(prepare_units_df(district_data, exclude_units, grids=grids).to_dict(orient="records"))
    else:
        district_units = []

    if district_data is not None:
        if interperiod_data != 'building' and interperiod_data is not None:
            district_units_IP = np.array(prepare_units_df(os.path.join(path_to_infrastructure, "district_units_IP.csv"), exclude_units=exclude_units,grids=grids).to_dict(orient="records"))
        elif isinstance(interperiod_data, dict) and 'district_units_IP' in interperiod_data:
            district_units_IP = np.array(prepare_units_df(interperiod_data["district_units_IP"], exclude_units=exclude_units, grids=grids).to_dict(orient="records"))
        else:
            district_units_IP = []

        if len(district_units_IP) > 0:
            district_units = np.concatenate([district_units,district_units_IP])

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
            grid_dict['Grid'] = idx
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
