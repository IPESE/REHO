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
            self.ReinforcementTrOfLayer={}
            self.ReinforcementLineOfLayer = {}
            for l in grids.keys():
                if 'ReinforcementTrOfLayer' in grids[l].keys():
                    self.ReinforcementTrOfLayer[l] = grids[l]['ReinforcementTrOfLayer']
                else:
                    self.ReinforcementTrOfLayer[l] = np.array([1e8])

                if 'ReinforcementLineOfLayer' in grids[l].keys():
                    self.ReinforcementLineOfLayer[l] = grids[l]['ReinforcementLineOfLayer']
                else:
                    self.ReinforcementLineOfLayer[l] = np.array([1e8])

        self.StreamsOfBuilding = {}
        self.StreamsOfUnit = {}
        self.TemperatureSets = {}
        self.lca_kpis = []
        self.Set = {}

        # Parameter --------------------------------
        self.Units_flowrate = pd.DataFrame()
        self.Grids_flowrate = pd.DataFrame()
        self.Grids_Parameters = pd.DataFrame()
        self.Grids_Parameters_lca = pd.DataFrame()
        self.Units_Parameters = pd.DataFrame()
        self.Units_Parameters_lca = pd.DataFrame()
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

        lca_kpi_list = np.array(file_reader(os.path.join(path_to_infrastructure, "building_units.csv")).columns)
        lca_kpi_list = [key for key in lca_kpi_list if "_1" in key]
        self.lca_kpis = np.array([key.replace("_1", "") for key in lca_kpi_list])
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
        self.Set['Lca_kpi'] = self.lca_kpis

        if 'ReinforcementTrOfLayer' in self.__dict__.keys():
            self.Set['ReinforcementTrOfLayer']=self.ReinforcementTrOfLayer

        if 'ReinforcementLineOfLayer' in self.__dict__.keys():
            self.Set['ReinforcementLineOfLayer']=self.ReinforcementLineOfLayer

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
        Units_Parameters_lca_0 = self.Units_Parameters_lca.copy()
        for h in self.House[1:]:
            idx_h = [idx.replace(self.House[0], h) for idx in Units_Parameters_0.index.values]
            Units_Parameters_h = Units_Parameters_0.copy()
            Units_Parameters_h.index = idx_h
            self.Units_Parameters = pd.concat([self.Units_Parameters, Units_Parameters_h])

            Units_Parameters_lca_h = Units_Parameters_lca_0.copy()
            idx_h_lca = [idx.replace(self.House[0], h) for idx in Units_Parameters_lca_0.index.get_level_values(1).unique()]
            Units_Parameters_lca_h.index = Units_Parameters_lca_h.index.set_levels(idx_h_lca, level=1)
            self.Units_Parameters_lca = pd.concat([self.Units_Parameters_lca, Units_Parameters_lca_h])

        for u in self.district_units:
            self.add_unit_parameters(u['name'], u)
        self.Units_Parameters_lca.columns = ["lca_kpi_1", "lca_kpi_2"]

        # Grids
        keys = ['Cost_demand_cst', 'Cost_supply_cst', 'GWP_demand_cst', 'GWP_supply_cst', 'Cost_connection']
        lca_impact_demand = [key + "_demand_cst" for key in self.lca_kpis]
        lca_impact_supply = [key + "_supply_cst" for key in self.lca_kpis]
        for g in self.grids:
            for h in self.House:
                idx = pd.MultiIndex.from_tuples([(g, h)], names=['Layer', 'House'])
                df = pd.DataFrame([[self.grids[g]['Grids_flowrate_out'], self.grids[g]['Grids_flowrate_in']]],
                                  index=idx, columns=['Grids_flowrate_out', 'Grids_flowrate_in'])
                self.Grids_flowrate = pd.concat([self.Grids_flowrate, df])

            df = pd.DataFrame([[self.grids[g][key] for key in keys]], index=[g], columns=keys)
            self.Grids_Parameters = pd.concat([self.Grids_Parameters, df])

            df_lca_demand = pd.DataFrame([[float(self.grids[g][key]) for key in lca_impact_demand]], columns=self.lca_kpis).transpose()
            df_lca_supply = pd.DataFrame([[float(self.grids[g][key]) for key in lca_impact_supply]], columns=self.lca_kpis).transpose()
            df_lca = pd.concat([df_lca_demand, df_lca_supply], axis=1)
            df_lca.index.names = ["Lca_kpi"]
            df_lca["ResourceBalances"] = g
            df_lca = df_lca.set_index("ResourceBalances", append=True)
            self.Grids_Parameters_lca = pd.concat([self.Grids_Parameters_lca, df_lca])
        self.Grids_Parameters_lca.columns = ["lca_kpi_demand_cst", "lca_kpi_supply_cst"]

        # HP and AC temperatures
        for h in self.House:

            for u in self.houses[h]['units']:
                if not u['HP_parameters'] in ['nan', 'None', None]:
                    complete_name = u['name'] + '_' + h
                    file = os.path.join(path_to_infrastructure, u['HP_parameters'])
                    if u['UnitOfType'] == 'Air_Conditioner' or u['UnitOfType'] == 'HeatPump':
                        df = pd.read_csv(file, delimiter=';', index_col=[0, 1])
                        df = pd.concat([df], keys=[complete_name])
                        # get index sets of source and sink of HP
                        name, rest = df.columns[0].split('_', 1)
                        self.TemperatureSets[name + '_Tsink'] = np.array(df.index.get_level_values(1).unique())
                        self.TemperatureSets[name + '_Tsource'] = np.array(df.index.get_level_values(2).unique())
                    else:
                        df = pd.read_csv(file, delimiter=';')
                        df.index = [complete_name]

                    if u['HP_parameters'] in self.HP_parameters:

                        self.HP_parameters[u['HP_parameters']] = pd.concat(
                            [self.HP_parameters[u['HP_parameters']], df])
                    else:
                        self.HP_parameters[u['HP_parameters']] = df

        for key in self.TemperatureSets:  # add additional sets from units to total set
            self.Set[key] = self.TemperatureSets[key]

        # TODO select the AC and HP units without number place in the self.units array
        # self.Set['AC_Tsupply'] = np.array(self.units[2]['stream_Tin'])
        # self.Set['HP_Tsupply'] = np.array(self.units[0]['stream_Tin'])

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
        lca_impact_1 = [key + "_1" for key in self.lca_kpis]
        lca_impact_2 = [key + "_2" for key in self.lca_kpis]
        df = pd.DataFrame([[unit_param[key] for key in keys]], columns=keys, index=[complete_name])
        self.Units_Parameters = pd.concat([self.Units_Parameters, df])
        df_lca_1 = pd.DataFrame([[unit_param[key] for key in lca_impact_1]], columns=self.lca_kpis).transpose()
        df_lca_2 = pd.DataFrame([[unit_param[key] for key in lca_impact_2]], columns=self.lca_kpis).transpose()
        df_lca = pd.concat([df_lca_1, df_lca_2], axis=1)
        df_lca.index.names = ["Lca_kpi"]
        df_lca["Units"] = complete_name
        df_lca = df_lca.set_index("Units", append=True)
        self.Units_Parameters_lca = pd.concat([self.Units_Parameters_lca, df_lca])


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
        Grids given through ``initialize_units``.

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
    unit_data['HP_parameters'] = unit_data['HP_parameters'].astype(str)

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


def initialize_units(scenario, grids=None, building_data=os.path.join(path_to_infrastructure, "building_units.csv"),
                     district_data=None, storage_data=None):
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
    storage_data :  str or bool or None, optional
        Path to the CSV file containing storage unit data. If True, storage units are initialized with 'storage_units.csv'.
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
    - The default files are located in ``reho/data/parameters``.
    - The custom files can be given as absolute or relative path.

    Examples
    --------
    >>> units = infrastructure.initialize_units(scenario, grids, building_data="custom_building_units.csv",
    ...                                         district_data="custom_district_units.csv", storage_data=True)
    """

    default_units_to_exclude = ['HeatPump_Anergy', 'HeatPump_Lake']
    if "exclude_units" not in scenario:
        exclude_units = default_units_to_exclude
    else:
        exclude_units = scenario["exclude_units"] + default_units_to_exclude

    building_units = prepare_units_array(building_data, exclude_units, grids)

    # TODO: these storage units are not fully working
    storage_units_to_exclude = ['BESS_IP', 'PTES_S_IP', 'PTES_C_IP', 'H2S_storage', 'H2_compression', 'SOEFC', 'FC']

    exclude_units = exclude_units + storage_units_to_exclude
    if storage_data is True:
        default_storage_units = os.path.join(path_to_infrastructure, "storage_units.csv")
        building_units = np.concatenate([building_units, prepare_units_array(default_storage_units, exclude_units=exclude_units)])
    elif storage_data:
        building_units = np.concatenate([building_units, prepare_units_array(storage_data, exclude_units=exclude_units)])

    if district_data is True:
        district_units = prepare_units_array(os.path.join(path_to_infrastructure, "district_units.csv"), exclude_units, grids)
    elif district_data:
        district_units = prepare_units_array(district_data, exclude_units, grids)
    else:
        district_units = []

    units = {"building_units": building_units, "district_units": district_units}

    return units


def initialize_grids(available_grids={'Electricity': {}, 'NaturalGas': {}},
                     file=os.path.join(path_to_infrastructure, "grids.csv")):
    """
    Initializes grid information for the energy system.

    Parameters
    ----------
    available_grids : dict, optional
        A dictionary specifying the available grids and their parameters. The keys represent grid names,
        and the values are dictionaries containing optional parameters ['Cost_demand_cst',
        'Cost_supply_cst', 'GWP_demand_cst', 'GWP_supply_cst'].
    file : str, optional
        Path to the CSV file containing grid data. Default is 'grids.csv' in the parameters folder.

    Returns
    -------
    dict
        Contains information about the initialized grids.

    See also
    --------
    initialize_units

    Notes
    -----
    - If one wants to use its one custom grid file, he should pay attention that the name of the layer and
      the parameters correspond.
    - Adding a layer in a custom file will not add it to the model as it is not modelized.

    Examples
    --------
    >>> available_grids = {'Electricity': {'Cost_demand_cst': 0.1, 'GWP_supply_cst': 0.05}, 'NaturalGas': {'Cost_supply_cst': 0.15}}
    >>> grids = initialize_grids(available_grids, file="custom_grids.csv")
    """

    grid_data = file_reader(file)
    grid_data = grid_data.set_index("Grid")

    grids = dict()
    for idx, row in grid_data.iterrows():
        if idx in available_grids.keys():
            grid_dict = row.to_dict()
            grid_dict['name'] = idx
            grid_dict['Grids_flowrate_in'] = 1e6 * grid_dict['Grids_flowrate_in']
            grid_dict['Grids_flowrate_out'] = 1e6 * grid_dict['Grids_flowrate_out']
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
