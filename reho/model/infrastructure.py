import os.path

import numpy as np
import pandas as pd
from reho.paths import *


class infrastructure:
    """
    This class characterizes all the sets and parameters which are connected to buildings, units and grids.

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

        # Sets -------------------------------------------------------------------------------------------------------
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

        self.UnitSizes = {}
        self.UnitsOfDistrict = np.array([])

        self.HousesOfLayer = {}
        for l in self.Layers:
            self.HousesOfLayer[l] = np.array([])

        self.StreamsOfBuilding = {}
        self.StreamsOfUnit = {}
        self.TemperatureSets = {}
        self.lca_kpis = []
        self.Set = {}

        # Parameter --------------------------------------------------------------------------------------------
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
        """
        The indexes h_ht, h_mt, h_lt, c_ht state for the discretization of the streams. They are connected to the heat cascade.
        h_ht: hotstream_hightemperature. h_mt: hotstream_mediumtemperature. h_lt: hotstream_lowtemperature. c_ht: coldstream_hightemperature
        :return:
        """

        for h in self.House:
            # Units------------------------------------------------------------
            for u in self.houses[h]['units']:
                complete_name = u['name'] + '_' + h

                self.Units = np.append(self.Units, [complete_name])
                self.UnitsOfType[u['UnitOfType']] = np.append(self.UnitsOfType[u['UnitOfType']], [complete_name])
                for l in u['UnitOfLayer']:
                    self.UnitsOfLayer[l] = np.append(self.UnitsOfLayer[l], [complete_name])
                self.UnitsOfHouse[h] = np.append(self.UnitsOfHouse[h], [complete_name])
                for s in u['UnitOfService']:
                    self.UnitsOfService[s] = np.append(self.UnitsOfService[s], [complete_name])

                # Streams---------------------------------------------------------
                self.StreamsOfBuilding[h] = np.array([h + '_c_lt', h + '_c_mt', h + '_h_lt'])  # c_mt  c_lt - space heat demand discretized in 2 streams, _- h_lt for cooling
                self.StreamsOfUnit[complete_name] = np.array([])
                for s in u['StreamsOfUnit']:
                    stream = u['name'] + '_' + h + '_' + s
                    self.StreamsOfUnit[complete_name] = np.append(self.StreamsOfUnit[complete_name], stream)

            # Layers------------------------------------------------------------
            for l in self.houses[h]['layers']:
                self.HousesOfLayer[l] = np.append(self.HousesOfLayer[l], [h])
        # Districtunits------------------------------------------------------------
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

        lca_kpi_list = np.array(pd.read_csv(os.path.join(path_to_parameters, "building_units.csv")).columns)
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

    def generate_parameter(self):
        # Units Flows -----------------------------------------------------------
        for h in self.House:

            for u in self.houses[h]['units']:
                df_i = pd.DataFrame()
                df_o = pd.DataFrame()
                complete_name = u['name'] + '_' + h
                for i in u['Units_flowrate_in']:
                    idx = pd.MultiIndex.from_tuples([(i, complete_name)], names=['Layer', 'Unit'])
                    df = pd.DataFrame(u['Units_flowrate_in'][i], index=idx, columns=['Units_flowrate_in'])
                    df_i = pd.concat([df_i, df])
                for o in u['Units_flowrate_out']:
                    idx = pd.MultiIndex.from_tuples([(o, complete_name)], names=['Layer', 'Unit'])
                    df = pd.DataFrame(u['Units_flowrate_out'][o], index=idx, columns=['Units_flowrate_out'])
                    df_o = pd.concat([df_o, df])

                df = pd.concat([df_o, df_i], axis=1)
                self.Units_flowrate = pd.concat([self.Units_flowrate, df])
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
        for h in self.House:
            for u in self.houses[h]['units']:
                self.add_unit_parameters(u['name'] + '_' + h, u)

        for u in self.district_units:
            self.add_unit_parameters(u['name'], u)
        self.Units_Parameters_lca.columns = ["lca_kpi_1", "lca_kpi_2"]

        # Grids------------------------------------------------------------
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

        # HP and AC temperatures------------------------------------------------------------
        for h in self.House:

            for u in self.houses[h]['units']:
                if u['HP_parameters'] is not None:
                    complete_name = u['name'] + '_' + h
                    file = os.path.join(path_to_parameters, u['HP_parameters'])
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
        #self.Set['AC_Tsupply'] = np.array(self.units[2]['stream_Tin'])
        #self.Set['HP_Tsupply'] = np.array(self.units[0]['stream_Tin'])

        # Streams------------------------------------------------------------

        Hin = {}
        Hout = {}
        for unitstreams in dict(self.StreamsOfUnit, **self.StreamsOfBuilding).values():  # union of dict
            for s in unitstreams:
                if s.count('_h_') == 1:  # check if its a hot stream
                    Hin[s] = 1
                    Hout[s] = 0
                elif s.count('_c_') == 1:  # check if its a cold stream
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

    def set_discretize_unit_size(self):

        sizes = {}
        sizes['Air_Conditioner'] = [0]
        sizes['HeatPump'] = [0, 2.7, 3.4, 5.5]
        sizes['WaterTankDHW'] = [0, 0.07, 0.125, 0.20, 0.8]
        sizes['WaterTankSH'] = [0, 0.20, 0.40, 0.60, 0.75]
        sizes['ElectricalHeater'] = [0, 3.0, 6.0, 9.0, 12.0, 15, 20, 22]
        sizes['ElectricalHeater'] = [0, 3.0, 6.0, 9.0, 12.0, 15, 20, 22]
        sizes['NG_Boiler'] = [0, 11.8]
        sizes['Battery'] = [0, 2.5, 5, 10]
        sizes['NG_Cogeneration'] = [0, 0.7]
        sizes['EV'] = []
        sizes['PV'] = []
        sizes['ThermalSolar'] = []

        for h in self.House:
            for u in self.houses[h]['units']:
                complete_name = u['name'] + '_' + h
                self.UnitSizes[complete_name] = np.array(sizes[u['UnitOfType']])

        self.Set['UnitSizes'] = self.UnitSizes  # add to all sets

def create_unit(name, ref_unit, UnitOfType, UnitOfLayer, UnitOfService, StreamsOfUnit, Units_flowrate_in,
                Units_flowrate_out, unit_data, HP_parameters, stream_Tin=[], stream_Tout=[]):

    unit = {'name': name, 'ref_unit': ref_unit, 'UnitOfType': UnitOfType, 'UnitOfLayer': UnitOfLayer, 'UnitOfService': UnitOfService,
           'StreamsOfUnit': StreamsOfUnit, 'Units_flowrate_in': {}, 'Units_flowrate_out': {}, 'HP_parameters': HP_parameters,
            'stream_Tin': stream_Tin, 'stream_Tout': stream_Tout}

    for key in unit_data.loc[name].index:
        unit[key] = unit_data.loc[name][key]

    for i in Units_flowrate_in:
        unit['Units_flowrate_in'][i] = 1e6
        if i not in Units_flowrate_out:  # if inflow is initialized of a stream but not the outflow, it needs to be set to 0
            unit['Units_flowrate_out'][i] = 0

    for o in Units_flowrate_out:
        unit['Units_flowrate_out'][o] = 1e6
        if o not in Units_flowrate_in:  # if outflow is initialized of a stream but not the inflow, it needs to be set to 0
            unit['Units_flowrate_in'][o] = 0

    return unit


def return_building_units(exclude_units, grids, file):

    unit_data = file_reader(file)
    unit_data = unit_data.set_index("Unit")

    BO = create_unit('NG_Boiler', 'kWth', 'NG_Boiler', ['NaturalGas', 'HeatCascade'], ['DHW', 'SH'], ['h_ht'],
                     ['NaturalGas'], [], unit_data, None, [80], [60])
    OIL = create_unit('OIL_Boiler', 'kWth', 'OIL_Boiler', ['Oil', 'HeatCascade'], ['DHW', 'SH'], ['h_ht'], ['Oil'],
                      [], unit_data, None, [80], [60])
    WS = create_unit('WOOD_Stove', 'kWth', 'WOOD_Stove', ['Wood', 'HeatCascade'], ['SH'], ['h_ht'], ['Wood'],
                     [], unit_data, None, [80], [60])
    HP_air = create_unit('HeatPump_Air', 'kWe', 'HeatPump', ['HeatCascade', 'Electricity'], ['DHW', 'SH'],
                         ['h_ht', 'h_mt', 'h_lt'], ['Electricity'], [], unit_data, 'HP_parameters.txt', [55, 45, 35], [50, 40, 30])
    HP_lake = create_unit('HeatPump_Lake', 'kWe', 'HeatPump', ['HeatCascade', 'Electricity'], ['DHW', 'SH'],
                          ['h_ht', 'h_mt', 'h_lt'], ['Electricity'], [], unit_data, 'HP_parameters.txt', [55, 45, 35], [50, 40, 30])
    HP_geothermal = create_unit('HeatPump_Geothermal', 'kWe', 'HeatPump', ['HeatCascade', 'Electricity'], ['DHW', 'SH'],
                                ['h_ht', 'h_mt', 'h_lt'], ['Electricity'], [], unit_data, 'HP_parameters.txt', [55, 45, 35], [50, 40, 30])
    HP_dhn = create_unit('HeatPump_DHN', 'kWe', 'HeatPump', ['HeatCascade', 'Electricity', 'Heat'], ['DHW', 'SH'],
                         ['h_ht', 'h_mt', 'h_lt'], ['Electricity', 'Heat'], [], unit_data, 'HP_parameters.txt', [55, 45, 35], [50, 40, 30])
    HP_anergy = create_unit('HeatPump_Anergy', 'kWe', 'HeatPump', ['HeatCascade', 'Electricity'], ['DHW', 'SH'],
                            ['h_ht', 'h_mt', 'h_lt'], ['Electricity'], [], unit_data, 'HP_parameters.txt', [55, 45, 35], [50, 40, 30])
    AC = create_unit('Air_Conditioner_Air', 'kWe', 'Air_Conditioner', ['HeatCascade', 'Electricity'], ['Cooling'],
                     ['c_ht', 'c_mt', 'c_lt'], ['Electricity'], [], unit_data, 'AC_parameters.txt', [13, 15, 18], [14, 16, 19])
    AC_dhn = create_unit('Air_Conditioner_DHN', 'kWe', 'Air_Conditioner', ['Heat', 'HeatCascade', 'Electricity'], ['Cooling'],
                     ['c_ht', 'c_mt', 'c_lt'], ['Electricity'], ['Heat'], unit_data, 'AC_parameters.txt', [13, 15, 18], [14, 16, 19])
    EH_sh = create_unit('ElectricalHeater_SH', 'kWth', 'ElectricalHeater', ['HeatCascade', 'Electricity'], ['SH'],
                        ['h_ht'], ['Electricity'], [], unit_data, None, [80], [60])
    EH_dhw = create_unit('ElectricalHeater_DHW', 'kWth', 'ElectricalHeater', ['HeatCascade', 'Electricity'],
                         ['DHW'], ['h_ht'], ['Electricity'], [], unit_data, None, [80], [60])
    PV = create_unit('PV', 'kWe', 'PV', ['Electricity'], [], [], [], ['Electricity'], unit_data, None, [], [])
    TS = create_unit('ThermalSolar', 'kWth', 'ThermalSolar', ['HeatCascade'], ['DHW'], ['h_ht'], [], [], unit_data, None, [62], [48])
    NG_cogen = create_unit('NG_Cogeneration', 'kWe', 'NG_Cogeneration', ['HeatCascade', 'Electricity', 'NaturalGas'],
                           ['DHW', 'SH'], ['h_ht'], ['NaturalGas'], ['Electricity'], unit_data, None, [60], [40])
    BA = create_unit('Battery', 'kWh', 'Battery', ['Electricity'], [], [], ['Electricity'], ['Electricity'],
                     unit_data, None, [], [])
    SH = create_unit('WaterTankSH', 'm3', 'WaterTankSH', ['HeatCascade'], ['SH'], ['h_lt', 'c_lt'], [], [],
                      unit_data, None, [35, 35], [35, 35])
    DHW = create_unit('WaterTankDHW', 'm3', 'WaterTankDHW', ['HeatCascade'], ['DHW'], ['c_ht'], [], [],
                      unit_data, None, [10], [60])
    DH_sh = create_unit('DataHeat_SH', 'kWth', 'DataHeat', ['Electricity', 'HeatCascade', 'Data'], ['SH'],
                        ['h_ht'], ['Electricity'], ['Data'], unit_data, None, [80], [60])
    DH_dhw = create_unit('DataHeat_DHW', 'kWth', 'DataHeat', ['Electricity', 'HeatCascade', 'Data'], ['DHW'],
                         ['h_ht'], ['Electricity'], ['Data'], unit_data, None, [80], [60])
    DHN_in = create_unit('DHN_hex_in', 'kWth', 'DHN_hex', ['HeatCascade', 'Heat'],
                         ['SH', 'DHW'], ['h_ht'], ['Heat'], [], unit_data, None, [80], [60])
    DHN_out = create_unit('DHN_hex_out', 'm2', 'DHN_hex', ['Heat', 'HeatCascade'], ['Cooling'],
                     ['c_ht'], ['Heat'], ['Heat'], unit_data, None, [18], [19])
    DHN_pipes = create_unit('DHN_pipes', 'kW', 'DHN_pipes', ['Heat'], [], [], [], [], unit_data, None, [], [])

    units_considered = [BO, OIL, WS, HP_air, HP_geothermal, HP_dhn, AC, AC_dhn, PV,
                        BA, SH, DHW, EH_sh, EH_dhw, TS, NG_cogen, DH_dhw, DHN_in, DHN_out, DHN_pipes]
    units_to_keep = ["PV", "WaterTankSH", "WaterTankDHW", "Battery", "ThermalSolar"]
    units = filter_units(grids, units_considered, exclude_units, units_to_keep)

    return units

def filter_units(grids, units_considered, exclude_units, units_to_keep):
    units = []
    if grids is None:
        grid_layers = ['Electricity', 'NaturalGas', 'Oil', 'Wood', 'Data', 'Heat', 'HeatCascade']
    else:
        grid_layers = list(grids.keys()) + ['HeatCascade']

    for unit_dict in units_considered:
        if all([layer in grid_layers for layer in unit_dict["UnitOfLayer"]]):
            if unit_dict['name'] not in exclude_units or unit_dict['name'] in units_to_keep:
                units = np.concatenate([units, [unit_dict]])
    return units


def return_district_units(exclude_units, grids, file):

    unit_district_data = file_reader(file)
    unit_district_data = unit_district_data.set_index("Unit")
    BAT = create_unit('Battery_district', 'kWh', 'Battery', ['Electricity'], [], [], ['Electricity'],
                      ['Electricity'], unit_district_data, None, [], [])
    EV = create_unit('EV_district', '-', 'EV', ['Electricity'], [], [], ['Electricity'], ['Electricity'], unit_district_data, None, [], [])
    NG_cogen = create_unit('NG_Cogeneration_district', 'kWe', 'NG_Cogeneration', ['Heat', 'Electricity', 'NaturalGas'],
                           [], [], ['NaturalGas'], ['Heat', 'Electricity'], unit_district_data, None, [60], [40])
    BO = create_unit('NG_Boiler_district', 'kWth', 'NG_Boiler', ['NaturalGas', "Heat"], [], [], ['NaturalGas'], ["Heat"], unit_district_data, None, [80], [60])
    HP_geothermal = create_unit('HeatPump_Geothermal_district', 'kWe', 'HeatPump', ['Heat', 'Electricity'], [],
                                ['h_ht', 'h_mt', 'h_lt'], ['Electricity'], ['Heat'], unit_district_data, 'HP_parameters.txt', [21, 16, 11], [20, 15, 10])
    DHN_out = create_unit('DHN_out_district', 'm2', 'DHN_direct_cooling', ['Heat'], [], [], ['Heat'], [], unit_district_data, None, [], [])

    units_considered = [BAT, EV, NG_cogen, BO, HP_geothermal, DHN_out]
    units = filter_units(grids, units_considered, exclude_units, units_to_keep=[])
    return units


def return_storage_units(file):
    unit_data = file_reader(file)
    unit_data = unit_data.set_index("Unit")

    BESS_IP = create_unit('BESS_IP', 'kWh', 'Battery_interperiod', ['Electricity'], [], [], ['Electricity'],
                          ['Electricity'], unit_data, None, [0], [0])
    PTES_S_IP = create_unit('PTES_S_IP', 'kWh', 'PTES_storage', [], [], [], [], [], unit_data, None, [0], [0])
    PTES_C_IP = create_unit('PTES_C_IP', 'kW', 'PTES_conversion', ['Electricity', 'HeatCascade'], ['SH', 'DHW'],
                            ['h_ht'], ['Electricity'], ['Electricity'], unit_data, None, [0], [0])
    HC = create_unit('HC', 'kW', 'HeatCurtailment', ['HeatCascade'], ['SH', 'DHW'], ['c_lt'], [], [], unit_data, None, [0], [0])
    CH4S = create_unit('CH4_storage', 'kWh', 'CH4storage', ['Biogas'], [], [], ['Biogas'], ['Biogas'], unit_data, None, [0], [0])
    H2S = create_unit('H2S_storage', 'kWh', 'H2storage', [], [], [], [], [], unit_data, None, [0], [0])
    H2C = create_unit('H2_compression', 'kW', 'H2compression', ['Hydrogen', 'Electricity'], [], [],
                      ['Hydrogen', 'Electricity'], ['Hydrogen', 'Electricity'], unit_data, None, [0], [0])
    SOEFC = create_unit('SOEFC', 'kW', 'SOEFC', ['Electricity', 'HeatCascade', 'Hydrogen', 'Biogas'], ['SH'],
                        ['h_ht'], ['Hydrogen', 'Electricity', 'Biogas'], ['Electricity', 'Hydrogen'], unit_data, None, [0], [0])
    MTZ = create_unit('MTZ', 'kW', 'Methanizer', ['Biogas', 'HeatCascade', 'Hydrogen'], ['SH'], ['h_ht'],
                      ['Hydrogen'], ['Biogas'], unit_data, None, [0], [0])
    FC = create_unit('FC', 'kW', 'FuelCell', ['Electricity', 'Hydrogen', 'HeatCascade'], ['SH'], ['h_ht'],
                     ['Hydrogen'], ['Electricity'], unit_data, None, [0], [0])
    ETZ = create_unit('ETZ', 'kW', 'Electrolyzer', ['Electricity', 'Hydrogen', 'HeatCascade'], ['SH'], ['h_ht'],
                      ['Electricity'], ['Hydrogen'], unit_data, None, [0], [0])
    HS = create_unit('HS_IP', 'm3', 'WaterTankSH_interperiod', ['HeatCascade'], ['SH'], ['h_lt', 'c_lt'], [], [], unit_data, None, [0, 0], [0, 0])
    LHS = create_unit('LHS', 'kWh', 'SolidLiquidLHS', ['HeatCascade'], ['SH'], ['h_ht', 'c_ht'], [], [], unit_data, None, [0, 0], [0, 0])

    #return [BESS_IP, PTES_S_IP, PTES_C_IP, HC, CH4S, H2S, H2C, SOEFC, MTZ, FC, ETZ, HS, LHS] not working
    return [HC, CH4S, MTZ, ETZ, HS, LHS]


def initialize_units(scenario, grids=None, building_data=os.path.join(path_to_parameters, "building_units.csv"),
                     district_data=None, storage_data=None):
    """
    Initialize the available units for the energy system.

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
        If None, district units won't be considered. Default is None.
    storage_data :  str or bool or None, optional
        Path to the CSV file containing storage unit data. If True, storage units are initialized with 'storage_units.csv'.
        If None, storage units won't be considered. Default is None.

    Returns
    -------
    dict
        A dictionary containing building_units and district_units.

    See also
    --------
    initialize_grids

    Notes
    -----
    - The default files are located at *reho/data/parameters*.
    - The custom files can be given as absolute or relative path

    Examples
    --------
    >>> units = infrastructure.initialize_units(scenario, grids, building_data="custom_building_units.csv",
    ...                                         district_data="custom_district_units.csv", storage_data=True)
    """

    default_units_to_exclude = ["DataHeat_DHW", "OIL_Boiler", "Air_Conditioner", "DHN_hex"]
    if scenario is None:
        exclude_units = default_units_to_exclude
    elif "exclude_units" not in scenario:
        exclude_units = default_units_to_exclude
    else:
        exclude_units = scenario["exclude_units"]

    building_units = return_building_units(exclude_units, grids, file=building_data)

    if storage_data is True:
        building_units = np.concatenate([building_units, return_storage_units(file=os.path.join(path_to_parameters, "storage_units.csv"))])
    elif storage_data:
        building_units = np.concatenate([building_units, return_storage_units(file=storage_data)])
    if district_data is True:
        district_units = return_district_units(exclude_units, grids, file=os.path.join(path_to_parameters, "district_units.csv"))
    elif district_data:
        district_units = return_district_units(exclude_units, grids, file=district_data)
    else:
        district_units = []

    units = {"building_units": building_units, "district_units": district_units}

    return units


def create_grid(name, Grids_flowrate_out, Grids_flowrate_in, grid_data):
    grid = {'name': name, 'Grids_flowrate_out': 1e6*Grids_flowrate_out, 'Grids_flowrate_in': 1e6*Grids_flowrate_in}

    for key in grid_data.loc[name].index:
        grid[key] = grid_data.loc[name][key]

    return grid


def initialize_grids(available_grids={'Electricity': {}, 'NaturalGas': {}},
                     file=os.path.join(path_to_parameters, "grids.csv")):
    """
    Initialize grid information for the energy system.

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
        A dictionary containing information about the initialized grids.

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

    # list of all grids implemented in the model
    electricity = create_grid('Electricity', 1, 1, grid_data)
    natural_gas = create_grid('NaturalGas', 1, 0, grid_data)
    oil = create_grid('Oil', 1, 0, grid_data)
    wood = create_grid('Wood', 1, 0, grid_data)
    data = create_grid('Data', 0, 1, grid_data)
    hydrogen = create_grid('Hydrogen', 1, 1, grid_data)
    biogas = create_grid('Biogas', 1, 0, grid_data)
    heat = create_grid('Heat', 1, 1, grid_data)
    all_grids = {'Electricity': electricity, 'NaturalGas': natural_gas, 'Oil': oil, 'Wood': wood, 'Data': data, 'Hydrogen': hydrogen, 'Biogas': biogas, 'Heat': heat}

    # list of available grids for the given optimisation
    grids = dict()
    for name, parameters in available_grids.items():
        if name in all_grids:
            grids[name] = all_grids[name]
        if 'Cost_demand_cst' in parameters:
            grids[name]['Cost_demand_cst'] = parameters['Cost_demand_cst']
        if 'Cost_supply_cst' in parameters:
            grids[name]['Cost_supply_cst'] = parameters['Cost_supply_cst']
        if 'GWP_demand_cst' in parameters:
            grids[name]['GWP_demand_cst'] = parameters['GWP_demand_cst']
        if 'GWP_supply_cst' in parameters:
            grids[name]['GWP_supply_cst'] = parameters['GWP_supply_cst']
        if 'Cost_connection' in parameters:
            grids[name]['Cost_connection'] = parameters['Cost_connection']

    return grids
