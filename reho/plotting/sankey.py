import re
import pandas as pd
import numpy as np
from reho.paths import *

__doc__ = """
Builds a dataframe for the visualization of annual flows from REHO results in the form of a Sankey diagram.
"""

# Colors and labels for units and layers
layout = pd.read_csv(os.path.join(path_to_plotting, 'layout.csv'), index_col='Name').dropna(how='all')


def update_label(source_name, target_name, df_label):
    """
    Updates labels of df_label if source_name or target_name not in index of df_label.

    Parameters
    ----------
    source_name: str
        Source to update
    target_name: str
        Target to update
    df_label: pd.DataFrame
        Labels

    Returns
    -------
    pd.DataFrame
        df_label updated with the source and target values
    """
    if not (source_name in df_label.index):  # create label 'source' if not existing yet
        df_label.loc[source_name, 'pos'] = len(df_label)
    if not (target_name in df_label.index):  # create label 'target' if not existing yet
        df_label.loc[target_name, 'pos'] = len(df_label)
    return df_label


def handle_PV_battery_network(df_annuals, df_stv, df_label, elec_storage_list, elec_storage_use, mol_storage_use):
    """
    This function is used to handle the layout of the Sankey diagram when electricity storage is active, to avoid false
    representation of electricity exports to the grid.
    Parameters
    ----------
    df_annuals: pandas.DataFrame, that gathers annual balance for all the layers and the corresponding units
    df_label: Names of layers and units for the Sankey diagram
    df_stv: pandas.DataFrame, containing all information about the streams and the numerical values in the Sankey diagram
    elec_storage_list: list that contains all the units related to electricity storage (interperiod or not)
    elec_storage_use: Boolean to check whether electricity storage is active.
    mol_storage_use: Boolean to check whether molecular storage is active.

    Returns
    -------
    updated: df_label and df_stv
    """
    # Handle exports between PV panels and Battery (long-term storage especially). first calculate total electricity consumed onsite (incl. for storage purpose).
    # Then define PV to elec-onsite as the diff between elec_onsite and Network_supply. Then calculate PV to Network as the difference between PV production and PV cosnumed onsite.
    # Then calculate longterm storage to network as the difference between total Network demand and PV_to_network. This should all be done manually I guess.

    elec_dem_units = df_annuals[df_annuals['Layer'] == "Electricity"]["Hub"].tolist()
    end_use_elec_unit = [item for item in elec_dem_units if (item not in elec_storage_list) and (item != "Network")]
    end_use_elec_demand = df_annuals.loc[(df_annuals['Layer'] == "Electricity") & (df_annuals['Hub'].isin(end_use_elec_unit))]["Demand_MWh"].sum()
    elec_to_storage = df_annuals.loc[(df_annuals['Layer'] == "Electricity") & (df_annuals['Hub'].isin(elec_storage_list))]["Demand_MWh"].sum()
    elec_tot_onsite = end_use_elec_demand + elec_to_storage
    storage_to_Network = elec_tot_onsite - end_use_elec_demand

    PV_to_elec_onsite = df_annuals.loc[(df_annuals['Layer'] == "Electricity") & (df_annuals['Hub'] == "PV")]["Supply_MWh"].sum()
    to_Network = df_annuals.loc[(df_annuals['Layer'] == "Electricity") & (df_annuals['Hub'] == "Network")]["Demand_MWh"].sum()
    from_network_onsite = df_annuals.loc[(df_annuals['Layer'] == "Electricity") & (df_annuals['Hub'] == "Network")]["Supply_MWh"].sum()

    if elec_storage_use:
        dest = "Electrical_consumption"
    else:
        dest = "Electrical_consumption"

    if (not elec_storage_use) and (not mol_storage_use):
        df_label = update_label("PV", dest, df_label)
        df_stv["PV_to_elec_onsite"] = [df_label.loc['PV', 'pos'],  # source, create a source to target column
                                       df_label.loc[dest, 'pos'],  # target
                                       float(PV_to_elec_onsite - to_Network)]  # value

        df_label = update_label("PV", "Electrical_grid_feed_in", df_label)
        df_stv["to_Network"] = [df_label.loc["PV", 'pos'],  # source, create a source to target column
                                df_label.loc['Electrical_grid_feed_in', 'pos'],  # target
                                float(to_Network)]  # value

    else:
        df_label = update_label("PV", dest, df_label)
        df_stv["PV_to_elec_onsite"] = [df_label.loc['PV', 'pos'],  # source, create a source to target column
                                       df_label.loc[dest, 'pos'],  # target
                                       float(PV_to_elec_onsite)]  # value

        df_label = update_label(dest, "Electrical_grid_feed_in", df_label)
        df_stv["to_Network"] = [df_label.loc[dest, 'pos'],  # source, create a source to target column
                                df_label.loc['Electrical_grid_feed_in', 'pos'],  # target
                                float(to_Network)]  # value

    if elec_storage_use:
        energy_stored_loop = 0
        for elec_storage in elec_storage_list:
            # 8 Electrical cons before elec storage to storage device
            df_label, df_stv, dev_flow_in = add_flow('Electrical_consumption', elec_storage, 'Electricity', elec_storage,
                                                     'Demand_MWh', df_annuals, df_label, df_stv)

            df_label, df_stv, dev_stor_out = add_flow(elec_storage, 'Electrical_consumption', 'Electricity',
                                                      elec_storage,
                                                      'Supply_MWh', df_annuals, df_label, df_stv)

            energy_stored_loop += dev_stor_out

        # 10 Electrical cons after elec storage to Electr cons
        rSOC_to_elec_onsite = df_annuals.loc[(df_annuals['Layer'] == "Electricity") & (df_annuals['Hub'] == "rSOC")][
            "Supply_MWh"].sum()  # elec_tot_onsite - df_annuals.loc[(df_annuals['Layer'] == "Electricity") & (df_annuals['Hub'] == "Network")]["Supply_MWh"].sum()

        #df_label = update_label('Electrical_consumption', 'Electrical_consumption', df_label)
        #df_stv['Electrical_consumption_to_Electrical_consumption'] = [
        #    df_label.loc['Electrical_consumption', 'pos'],
        #    df_label.loc['Electrical_consumption', 'pos'],
        #    float(from_network_onsite + PV_to_elec_onsite + rSOC_to_elec_onsite - elec_to_storage - to_Network + energy_stored_loop)]

    return df_stv, df_label


def add_mol_storages_to_sankey(df_annuals, df_label, df_stv, FC_or_ETZ_use):
    """
    This function is called to add all the streams/units that are related to molecule (interperiod storage) to the sankey diagram.

    Parameters
    ----------
    df_annuals: pandas.DataFrame, that gathers annual balance for all the layers and the corresponding units
    df_label: Names of layers and units for the Sankey diagram
    df_stv: pandas.DataFrame, containing all information about the streams and the numerical values in the Sankey diagram
    FC_or_ETZ_use: Variable to check whether other electrolyzer types (than the usual) are considered

    Returns
    -------
    updated: df_label and df_stv
    """
    if FC_or_ETZ_use:
        H2_stor_to_FC = df_annuals.loc[(df_annuals['Layer'] == "Hydrogen") & (df_annuals['Hub'] == "FC")][
            "Demand_MWh"].sum()
        ETZ_to_H2_stor = df_annuals.loc[(df_annuals['Layer'] == "Hydrogen") & (df_annuals['Hub'] == "ETZ")][
            "Supply_MWh"].sum()
    else:
        H2_stor_to_FC = 0
        ETZ_to_H2_stor = 0
        # 8 rSOC to H2_grid or storage  (=Before Phase, bp) if present
    df_label, df_stv, _ = add_flow('H2_storage_IP', 'rSOC', 'Hydrogen', 'H2_storage_IP', 'Supply_MWh',
                                   df_annuals, df_label, df_stv, False, None, -H2_stor_to_FC)

    # 8 rSOC to H2_grid or storage  (=Before Phase, bp) if present
    df_label, df_stv, _ = add_flow('rSOC', 'H2_storage_IP', 'Hydrogen', 'H2_storage_IP', 'Demand_MWh',
                                   df_annuals, df_label, df_stv, False, None, -ETZ_to_H2_stor)

    # Electricity consumption for H2 storage
    df_label, df_stv, _ = add_flow('Electrical_consumption', 'H2_storage_IP', 'Electricity', 'H2_storage_IP',
                                   'Demand_MWh',
                                   df_annuals, df_label, df_stv)

    # 8 rSOC to CH4_grid or storage  (=Before Phase, bp) if present
    df_label, df_stv, _ = add_flow('CH4_storage_IP', 'rSOC', 'Biomethane', 'CH4_storage_IP', 'Supply_MWh',
                                   df_annuals, df_label, df_stv)

    # 9 Device to H2
    df_label, df_stv, _ = add_flow('rSOC', 'MTR', 'Hydrogen', 'MTR', 'Demand_MWh',
                                   df_annuals, df_label, df_stv)

    # 10 Device to CH4
    df_label, df_stv, _ = add_flow('MTR', 'CH4_storage_IP', 'Biomethane', 'MTR', 'Supply_MWh',
                                   df_annuals, df_label, df_stv)

    df_label, df_stv, _ = add_flow('H2_storage_IP_district', 'rSOC_district', 'Hydrogen', 'H2_storage_IP_district','Supply_MWh',
                                   df_annuals, df_label, df_stv, False, None, -H2_stor_to_FC)

    # 8 rSOC to H2_grid or storage  (=Before Phase, bp) if present
    df_label, df_stv, _ = add_flow('rSOC_district', 'H2_storage_IP_district', 'Hydrogen', 'H2_storage_IP_district','Demand_MWh',
                                   df_annuals, df_label, df_stv, False, None, -ETZ_to_H2_stor)

    # 8 rSOC to CH4_grid or storage  (=Before Phase, bp) if present
    df_label, df_stv, _ = add_flow('CH4_storage_IP_district', 'rSOC_district', 'Biomethane', 'CH4_storage_IP_district', 'Supply_MWh',
                                   df_annuals, df_label, df_stv)

    # 9 Device to H2
    df_label, df_stv, _ = add_flow('rSOC_district', 'MTR_district', 'Hydrogen', 'MTR_district', 'Demand_MWh',
                                   df_annuals, df_label, df_stv)

    # 10 Device to CH4
    df_label, df_stv, _ = add_flow('MTR_district', 'CH4_storage_IP_district', 'Biomethane', 'MTR_district', 'Supply_MWh',
                                   df_annuals, df_label, df_stv)

    # 10 Device to CH4
    df_label, df_stv, _ = add_flow('Biomethane_grid', 'rSOC_district', 'Biomethane', 'Network','Supply_MWh',
                                   df_annuals, df_label, df_stv)

    # 10 Device to CH4
    df_label, df_stv, _ = add_flow('Hydrogen_grid', 'rSOC_district', 'Hydrogen', 'Network', 'Supply_MWh',
                                   df_annuals, df_label, df_stv)

    # 10 Device to CH4
    df_label, df_stv, _ = add_flow('rSOC_district', 'Hydrogen_grid_feed_in', 'Hydrogen', 'Network', 'Demand_MWh',
                                   df_annuals, df_label, df_stv)

    # 10 Device to CH4
    df_label, df_stv, _ = add_flow('MTR_district', 'Biomethane_grid_feed_in', 'Biomethane', 'Network', 'Demand_MWh',
                                   df_annuals, df_label, df_stv)

    if df_annuals.loc[(df_annuals['Layer'] == "NaturalGas") & (df_annuals['Hub'] == "MTR")]["Supply_MWh"].sum() > 0:

        units_on_bio_CH4_1 = df_annuals.loc[(df_annuals['Layer'] == "NaturalGas") & (df_annuals["Demand_MWh"] > 0)]["Hub"]
        NG_use = 0
        for u in units_on_bio_CH4_1:
            df_label, df_stv, _ = add_flow('MTR', u, 'NaturalGas', 'MTR',
                                           'Demand_MWh', df_annuals, df_label, df_stv, adjustment=NG_use)

            NG_use = NG_use + df_annuals.loc[(df_annuals['Layer'] == "NaturalGas") & (df_annuals['Hub'] == u)][
                "Demand_MWh"].sum()

    if df_annuals.loc[(df_annuals['Layer'] == "NaturalGas") & (df_annuals['Hub'] == "MTR_district")]["Supply_MWh"].sum() > 0:

        units_on_bio_CH4_2 = df_annuals.loc[(df_annuals['Layer'] == "NaturalGas") & (df_annuals["Demand_MWh"] > 0)]["Hub"]
        NG_use = 0
        for u in units_on_bio_CH4_2:
            df_label, df_stv, _ = add_flow('MTR_district', u, 'NaturalGas', 'MTR_district',
                                           'Supply_MWh',df_annuals, df_label, df_stv, adjustment=NG_use)

            NG_use = NG_use + df_annuals.loc[(df_annuals['Layer'] == "NaturalGas") & (df_annuals['Hub'] == u)]["Demand_MWh"].sum()

    return df_label, df_stv


def add_ETZ_FC_to_sankey(df_annuals, df_label, df_stv):
    # 8 rSOC to H2_grid or storage  (=Before Phase, bp) if present
    df_label, df_stv, _ = add_flow('H2_storage', 'FC', 'Hydrogen', 'FC', 'Demand_MWh',
                                   df_annuals, df_label, df_stv)

    # 8 rSOC to H2_grid or storage  (=Before Phase, bp) if present
    df_label, df_stv, _ = add_flow('ETZ', 'H2_storage', 'Hydrogen', 'ETZ', 'Supply_MWh',
                                   df_annuals, df_label, df_stv)

    return df_label, df_stv

def add_DHN_units(df_annuals, DHN_units, df_label, df_stv):
    for unit in DHN_units:
        df_label, df_stv, _ = add_flow(unit, 'DHN', 'Heat', unit, 'Supply_MWh',
                                       df_annuals, df_label, df_stv)


    df_label, df_stv, _ = add_flow('Heat_grid', 'DHN', 'Heat', 'Network', 'Supply_MWh',
                                   df_annuals, df_label, df_stv)

    df_label, df_stv, _ = add_flow('DHN', 'DHN_hex_in', 'Heat', 'DHN_hex_in', 'Demand_MWh',
                                   df_annuals, df_label, df_stv)

    df_label, df_stv, _ = add_flow('DHN','Heat_grid_feed_in', 'Heat', 'Network', 'Demand_MWh',
                                   df_annuals, df_label, df_stv)
    return df_label, df_stv

def add_label_value(df_label, df_stv, precision, units):
    """
    Adds the values from df_stv to the labels of df_labels.
    The value of the nodes are thus available in the nodes name for the Sankey diagram.

    Parameters
    __________
    df_label: pd.DataFrame
        Labels
    df_stv: pd.DataFrame
        Source, target and value
    precision: int
        Precision of the displayed numbers (default = 2)
    units: str
        Unit of the values (default MWh)

    Returns
    _______
    pd.DataFrame
        df_label pdated with the label values
    """
    df_source_value = pd.DataFrame()
    df_source_value.index = df_label.pos

    for i in list(df_source_value.index):
        source_val = df_stv.loc['value', df_stv.loc['source', :] == i].sum()
        target_val = df_stv.loc['value', df_stv.loc['target', :] == i].sum()
        # higher value on the node is displayed, (i.e. size of the box node on the sankey)
        df_source_value.loc[i, 'value'] = max(source_val, target_val)

    df_label = df_label.merge(df_source_value, left_on='pos', right_index=True)
    df_label.label = df_label.label + "\n" + df_label.value.round(precision).astype(str) + units
    return df_label


def add_flow(source, dest, layer, hub, dem_sup, df_annuals, df_label, df_stv, check_dest_2=False, dest_2=None, adjustment=0, fact=1):
    """
    Adds an energy flow for the sankey diagram according cell(s) of df_annuals if cell not null

    Parameters
    ----------

    source: str
        name of the source
    dest: str
        name of the destination
    layer: str
        name of the layer of the considered cell(s)
    hub: str
        name of the hub of the considered cell(s)
    dem_sup: str
        'Supply_MWh' or 'Demand_MWh', column to take (! no control)
    df_annuals: pd.DataFrame

    df_label: pd.DataFrame

    df_stv: pd.DataFrame

    check_dest_2: bool
        if True dest_2 substitute dest (default False)
    dest_2: str
        second possible destination (default None)
    adjustment: float
        offset added to the cell value (default 0)
    fact: float
        factor multiplied to the cell value (default 1)

    Returns
    -------
    pd.DataFrame
        df_label updated
    pd.DataFrame
        df_stv updated
    float
        value added (0 if nothing added)
    """
    source_to_dest = df_annuals.loc[(df_annuals['Layer'] == layer) & (df_annuals['Hub'] == hub)][
        dem_sup].sum()  # .sum() to add all the values of the buildings if multiple buildings
    if source_to_dest != 0:  # if data available
        if check_dest_2:  # if True apply the second dest
            dest = dest_2
        df_label = update_label(source, dest, df_label)  # update label list
        df_stv[source + '_to_' + dest] = [df_label.loc[source, 'pos'],  # source, create a source to target column
                                          df_label.loc[dest, 'pos'],  # target
                                          float(fact * source_to_dest + adjustment)]  # value

    return df_label, df_stv, fact * source_to_dest + adjustment


def df_sankey(df_Results, label='EN_long', color='ColorPastel', precision=2, units='MWh', display_label_value=True, scaling_factor=1):
    """
    Builds the Sankey dataframe.

    Parameters
    ----------
    df_Results: pd.DataFrame
        DataFrame coming from REHO results (already extracted from the desired *Scn_ID* and *Pareto_ID*).
    label: str
        Indicate the language to use for the plot. Choose among 'FR_long', 'FR_short', 'EN_long', 'EN_short'.
    color: str
        Indicate the color set to use for the plot. Choose among 'ColorPastel', 'ColorFlash'.
    precision: int
        Precision of the displayed numbers (default = 2).
    units: str
        Unit of the values (default MWh).
    display_label_value: bool
        Numerical values are printed.
    scaling_factor: int/float
        Scales linearly the REHO results for the plot.

    Returns
    ----------
    pd.DataFrame
        Sankey dataframe.

    """

    # Hypotheses :
    #   1. DHW demand is taken as the supply of the watertank DHW
    #   2. no flow: electrical storage system to grid feed in, all to 'feed in electrical grid ' is from PV
    #   3. Small losses of NG, heat, wood,... between network and devices not accounted
    #   4. Electricity for 'Data heat' fully accounted as electricity consumption (Layer Data: not in sankey)
    #   5. Electricity produced by technologies can be stored (e.g. NG_cogen elec -> battery)
    # ! Make sure that all the possible technologies/sources/demands are in the list below.
    # If not, risk that something will be not displayed, there is no check provided by this function for that.

    # Manual handled devices (list below not used, just here for the information)
    # manual_device = ['PV', 'WaterTankSH']

    # Electrical storage device
    elec_storage_list = ['Battery', "Battery_district", "Battery_IP", "Battery_IP_district", 'EV_district']

    EV_device = ["EV_district", "EV_charger_district"]

    mol_storage_list = ['H2_storage_IP', 'CH4_storage_IP']
    # Semi automatic handled devices
    semi_auto_device = [
        'NG_Boiler', 'NG_Cogeneration', 'OIL_Boiler', 'WOOD_Stove', 'ThermalSolar',
        'ElectricalHeater_DHW', 'ElectricalHeater_SH',
        'HeatPump_Air', 'HeatPump_Geothermal', 'HeatPump_Lake', 'HeatPump_DHN', 'Air_Conditioner',
        'DHN_hex_in', 'DHN_hex_out', 'DataHeat_DHW', 'DataHeat_SH', 'rSOC', 'MTR', 'ETZ', 'FC','rSOC_district',
        'MTR_district', 'NG_Boiler_district', 'HeatPump_Geothermal_district'
    ]

    DHN_units = ["HeatPump_Geothermal_district", "rSOC_district", "NG_Boiler_district", "MTR_district"]

    # Network (electrical grid, oil network...) and end use demand (DHW, SH, elec appliances) handled automatically

    # Select only not null lines in df_annuals
    df_annuals = scaling_factor * df_Results['df_Annuals']
    df_annuals = df_annuals.replace(0, np.nan)
    df_annuals = df_annuals.loc[df_annuals['Demand_MWh'].notnull() | df_annuals['Supply_MWh'].notnull()]
    df_annuals = df_annuals.replace(np.nan, 0).reset_index()

    # "Building" string management in data to deal with data uniformly regarding buildings
    for x in list(df_annuals.index):
        if df_annuals.loc[x, "Hub"].startswith('Building'):  # all Buildingx -> Building
            df_annuals.loc[x, "Hub"] = "Building"
        else:  # else remove '_Buildingx' of the hub name
            df_annuals.loc[x, "Hub"] = re.sub("_Building\d+", "", df_annuals.loc[x, "Hub"])

    # Creating the dataframe for the following
    df_label = pd.DataFrame(columns=['pos'])  # df for labels, position number (pos) and colors
    df_stv = pd.DataFrame(index=['source', 'target', 'value'])  # df for source,target,value

    # check if electricity storage
    elec_storage_use = False
    for elec_storage in elec_storage_list:
        if len(df_annuals.loc[(df_annuals['Layer'] == 'Electricity') & (df_annuals['Hub'] == elec_storage)]) != 0:
            elec_storage_use = True

    # check if molecule storage
    mol_storage_use = False
    for mol_storage in mol_storage_list:
        if len(df_annuals.loc[(df_annuals['Layer'] == 'Hydrogen') | (df_annuals['Layer'] == 'Biomethane')]) != 0:
            mol_storage_use = True

    FC_or_ETZ_use = False
    if len(df_annuals.loc[(df_annuals['Layer'] == 'Hydrogen') & ((df_annuals['Hub'] == "ETZ") | (df_annuals['Hub'] == "FC"))]) != 0:
        FC_or_ETZ_use = True

    # check if watertank SH
    watertank_sh = False
    if len(df_annuals.loc[(df_annuals['Layer'] == 'SH') & (df_annuals['Hub'] == 'WaterTankSH')]) != 0:
        watertank_sh = True

    # 1 Elec Grid to Elec Consumption of the building(s) or before electricity storage (=Before Phase, bp) if present
    df_label, df_stv, _ = add_flow('Electrical_grid', 'Electrical_consumption', 'Electricity', 'Network', 'Supply_MWh',
                                   df_annuals, df_label, df_stv, elec_storage_use, 'Electrical_consumption')

    # 2 Elec Cons to Elec Appliances
    df_label, df_stv, _ = add_flow('Electrical_consumption', 'Electrical_appliances', 'Electricity', 'Building',
                                   'Demand_MWh', df_annuals, df_label, df_stv)

    # Handle PV, electricity storage and Network
    df_stv, df_label = handle_PV_battery_network(df_annuals, df_stv, df_label, elec_storage_list, elec_storage_use, mol_storage_use)

    # 5 WaterTankSH to SH
    df_label, df_stv, wtsh_to_sh = add_flow('WaterTankSH', 'SH', 'SH', 'WaterTankSH', 'Supply_MWh',
                                            df_annuals, df_label, df_stv)

    # Calculation of Losses in the watertank
    heat_tot_sh = df_annuals.loc[(df_annuals['Layer'] == 'SH') & (df_annuals['Hub'] == 'Building')].Demand_MWh.sum()
    heat_tot_sup = df_annuals.loc[(df_annuals['Layer'] == 'SH')].Supply_MWh.sum() - wtsh_to_sh
    heat_loss_wt = heat_tot_sup - heat_tot_sh

    # 6 SH Heat to Watertank SH if watertank
    df_label, df_stv, _ = add_flow('SH_heat', 'WaterTankSH', 'SH', 'WaterTankSH', 'Supply_MWh',
                                   df_annuals, df_label, df_stv, adjustment=heat_loss_wt)

    # 7 SH Heat to SH if watertank
    df_label, df_stv, _ = add_flow('SH_heat', 'SH', 'SH', 'WaterTankSH', 'Supply_MWh',
                                   df_annuals, df_label, df_stv, adjustment=heat_tot_sup - heat_loss_wt, fact=-1)

    elec_storage_energy_in = 0
    elec_storage_energy_out = 0
    for elec_storage in elec_storage_list:
        # 8 Electrical cons before elec storage to storage device
        df_label, df_stv, dev_flow_in = add_flow('Electrical_consumption', elec_storage, 'Electricity', elec_storage,
                                                 'Demand_MWh', df_annuals, df_label, df_stv)
        elec_storage_energy_in += dev_flow_in

        # 9 storage device to Electrical cons
        df_label, df_stv, dev_flow_out = add_flow(elec_storage, 'Electrical_consumption', 'Electricity', elec_storage,
                                                  'Supply_MWh', df_annuals, df_label, df_stv)
        elec_storage_energy_out += dev_flow_out

    # 10 Electrical cons before elec storage to Electr cons
    #if elec_storage_use:
    #    df_label = update_label('Electrical_consumption', 'Electrical_consumption', df_label)
    #    Ec_after_bp = df_annuals.loc[(df_annuals['Layer'] == 'Electricity') & (df_annuals['Hub'] != 'Network')].Demand_MWh.sum()
    #    Ec_after_bp -= elec_storage_energy_out
    #    df_stv['Electrical_consumption_to_Electrical_consumption'] = [df_label.loc['Electrical_consumption', 'pos'],
    #                                                                     df_label.loc['Electrical_consumption', 'pos'],
    #                                                                     float(Ec_after_bp - elec_storage_energy_in)]

    # 11 EV and charging station infrastructure
    # check if EV device
    EV_device_use = False
    for device in EV_device:
        if len(df_annuals.loc[(df_annuals['Layer'] == 'Electricity') & (df_annuals['Hub'] == device)]) != 0:
            EV_device_use = True

    if EV_device_use:
        for device in EV_device:
            # 1 Ele Cons to Device (for charging stations)
            df_label, df_stv, _ = add_flow('Electrical_consumption', "Total_EV_fleet", 'Electricity', device, 'Demand_MWh',
                                        df_annuals, df_label, df_stv)
            # 2 Device to Ele Cons
            df_label, df_stv, _ = add_flow('Total_EV_fleet', "Electrical_consumption", 'Electricity', device, 'Supply_MWh',
                                        df_annuals, df_label, df_stv)
            # 3 Device to Mobility
            df_label, df_stv, _ = add_flow("Total_EV_fleet", 'Mobility (0.1 kWh/pkm)', 'Mobility', device, 'Supply_MWh',
                                       df_annuals, df_label, df_stv,fact=1/9.37)


    # Semi-Auto for the followings devices
    for device in semi_auto_device:
        # 1 Ele Cons to Device
        df_label, df_stv, _ = add_flow('Electrical_consumption', device, 'Electricity', device, 'Demand_MWh',
                                       df_annuals, df_label, df_stv)

        # 2 Heat to Device
        #df_label, df_stv, _ = add_flow('Heat', device, 'Heat', device, 'Demand_MWh',
        #                               df_annuals, df_label, df_stv)

        # 3 NG to Device
        df_label, df_stv, _ = add_flow('NaturalGas_grid', device, 'NaturalGas', device, 'Demand_MWh',
                                       df_annuals, df_label, df_stv)

        # 3 Wood to Device
        df_label, df_stv, _ = add_flow('Wood', device, 'Wood', device, 'Demand_MWh',
                                       df_annuals, df_label, df_stv)

        # 4 Oil to Device
        df_label, df_stv, _ = add_flow('Oil', device, 'Oil', device, 'Demand_MWh',
                                       df_annuals, df_label, df_stv)

        # 4.1 FossilFuel to Device
        df_label, df_stv, _ = add_flow('FossilFuel', device, 'FossilFuel', device, 'Demand_MWh',
                                       df_annuals, df_label, df_stv)

        # 5 Device to DHW
        df_label, df_stv, _ = add_flow(device, 'DHW', 'DHW', device, 'Supply_MWh',
                                       df_annuals, df_label, df_stv)

        # 6 Device to SH Heat (if watertank) or to SH (if no watertank)
        df_label, df_stv, _ = add_flow(device, 'SH', 'SH', device, 'Supply_MWh',
                                       df_annuals, df_label, df_stv, watertank_sh, 'SH_heat')

        # 7 Device to Elec Consumption (or before electricity storage if present)
        df_label, df_stv, _ = add_flow(device, 'Electrical_consumption', 'Electricity', device, 'Supply_MWh',
                                       df_annuals, df_label, df_stv, elec_storage_use, 'Electrical_consumption')

        # 8 Device to Cooling
        df_label, df_stv, _ = add_flow(device, 'Cooling', 'Cooling', device, 'Supply_MWh',
                                       df_annuals, df_label, df_stv)

        # 9 Device to Mobility
        df_label, df_stv, _ = add_flow(device, 'Mobility (0.1 kWh/pkm)', 'Mobility', device, 'Supply_MWh',
                                       df_annuals, df_label, df_stv,fact=1/9.37)

    if mol_storage_use:
        df_label, df_stv = add_mol_storages_to_sankey(df_annuals, df_label, df_stv, FC_or_ETZ_use)

    if FC_or_ETZ_use:
        df_label, df_stv = add_ETZ_FC_to_sankey(df_annuals, df_label, df_stv)

    if df_annuals["Layer"].isin(["Heat"]).sum() > 0:
        add_DHN_units(df_annuals, DHN_units, df_label, df_stv)

    # df_label : add the label to display, the color and the label (node) values if selected
    df_label['label'] = layout[label]
    df_label['color'] = layout[color]
    if display_label_value:
        df_label = add_label_value(df_label, df_stv, precision, units)

    # data to export
    source = list(df_stv.loc['source'])
    target = list(df_stv.loc['target'])
    value = list(df_stv.loc['value'])
    value = [round(x, precision) for x in value]  # precision
    label = list(df_label.label)
    color = list(df_label.color)

    return source, target, value, label, color
