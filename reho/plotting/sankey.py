import re
import pandas as pd
import numpy as np

from reho.paths import *
from reho.plotting.utils import *

__doc__ = """
Builds a dataframe for the visualization of annual flows from REHO results in the form of a Sankey diagram.
"""


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
        df_label updated with the label values
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


def add_base_flows(df_annuals, df_label, df_stv):
    # Check if WaterTankSH is used
    watertank_sh = len(df_annuals[(df_annuals['Layer'] == 'SH') & (df_annuals['Hub'] == 'WaterTankSH')]) != 0

    # Base flows
    df_label, df_stv, _ = add_flow('Electricity_import', 'Electrical_consumption', 'Electricity', 'Network', 'Supply_MWh',
                                   df_annuals, df_label, df_stv)

    # Base flows
    df_label, df_stv, _ = add_flow('Electrical_consumption', 'Electricity_export', 'Electricity', 'Network',
                                   'Demand_MWh',
                                   df_annuals, df_label, df_stv)

    df_label, df_stv, _ = add_flow('Electrical_consumption', 'Electrical_appliances', 'Electricity', 'Building',
                                   'Demand_MWh', df_annuals, df_label, df_stv)

    df_label, df_stv, _ = add_flow('PV', 'Electrical_consumption', 'Electricity', 'PV',
                                   'Supply_MWh', df_annuals, df_label, df_stv)

    df_label, df_stv, wtsh_to_sh = add_flow('WaterTankSH', 'SH', 'SH', 'WaterTankSH', 'Supply_MWh',
                                            df_annuals, df_label, df_stv)

    heat_tot_sh = df_annuals[(df_annuals['Layer'] == 'SH') & (df_annuals['Hub'] == 'Building')].Demand_MWh.sum()
    heat_tot_sup = df_annuals[df_annuals['Layer'] == 'SH'].Supply_MWh.sum() - wtsh_to_sh
    heat_loss_wt = heat_tot_sup - heat_tot_sh

    df_label, df_stv, _ = add_flow('SH_heat', 'WaterTankSH', 'SH', 'WaterTankSH', 'Supply_MWh',
                                   df_annuals, df_label, df_stv, adjustment=heat_loss_wt)

    df_label, df_stv, _ = add_flow('SH_heat', 'SH', 'SH', 'WaterTankSH', 'Supply_MWh',
                                   df_annuals, df_label, df_stv, adjustment=heat_tot_sup - heat_loss_wt, fact=-1)

    return df_label, df_stv, watertank_sh


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
        Indicate the color set to use for the plot. 'ColorPastel' is default.
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

    # Select and clean data
    df_annuals = scaling_factor * df_Results['df_Annuals']
    df_annuals = df_annuals.replace(0, np.nan)
    df_annuals = df_annuals.loc[df_annuals['Demand_MWh'].notnull() | df_annuals['Supply_MWh'].notnull()]
    df_annuals = df_annuals.replace(np.nan, 0).reset_index()

    for x in list(df_annuals.index):
        if df_annuals.loc[x, "Hub"].startswith('Building'):
            df_annuals.loc[x, "Hub"] = "Building"
        else:
            df_annuals.loc[x, "Hub"] = re.sub("_Building\d+", "", df_annuals.loc[x, "Hub"])

    df_label = pd.DataFrame(columns=['pos'])
    df_stv = pd.DataFrame(index=['source', 'target', 'value'])

    df_label, df_stv, watertank_sh = add_base_flows(df_annuals, df_label, df_stv)

    # Semi-automatically handled devices
    semi_auto_device = [
        'NG_Boiler', 'OIL_Boiler', 'WOOD_Stove', 'ThermalSolar', 'ElectricalHeater_DHW', 'ElectricalHeater_SH', 'ElectricalHeater_other',
        'DataHeat_DHW', 'DataHeat_SH', 'HeatPump_Air','HeatPump_Waste_heat', 'HeatPump_Geothermal', 'HeatPump_Lake', 'HeatPump_DHN',
        'AirConditioner', 'NG_Boiler_district', 'NG_Cogeneration_district', 'HeatPump_Geothermal_district',
        'DHN_hex', 'rSOC', 'MTR', 'ETZ', 'FC', 'rSOC_district', 'MTR_district', 'ElectricalHeater_other_district',
    ]

    # Services that can be provided by the devices: ['SH', 'DHW', 'Cooling', 'rSOC_heat']

    flow_templates = [
        # EXAMPLE #
        # ('Source_in_sankey', 'Destination_in_sankey', 'Layer_in_df_annuals', 'Hub_in_df_annuals 'Supply/Demand_MWh_in_df_annuals', bool_second_destination, second_destination_sankey, offset, mult_factor),

        # Handle all imports
        ("NaturalGas_import", "{device}", "NaturalGas", "{device}", "Demand_MWh", False, None, 0, 1),
        ("Wood_import", "{device}", "Wood", "{device}", "Demand_MWh", False, None, 0, 1),
        ("Oil_import", "{device}", "Oil", "{device}", "Demand_MWh", False, None, 0, 1),
        ("Gasoline_import", "{device}", "Gasoline", "{device}", "Demand_MWh", False, None, 0, 1),

        ("Electrical_consumption", "{device}", "Electricity", "{device}", "Demand_MWh", False, None, 0, 1),
        ("{device}", "DHW", "DHW", "{device}", "Supply_MWh", False, None, 0, 1),
        ("{device}", "SH", "SH", "{device}", "Supply_MWh", watertank_sh, "SH_heat", 0, 1),
        ("{device}", "Electrical_consumption", "Electricity", "{device}", "Supply_MWh", False, None, 0, 1),
        ("{device}", "Cooling", "Cooling", "{device}", "Supply_MWh", False, None, 0, 1),
        ("{device}", "rSOC", "rSOC_heat", "{device}", "Supply_MWh", False, None, 0, 1),

    ]

    for device in semi_auto_device:
        for flow in flow_templates:
            if device == 'rSOC_district' or device == 'MTR_district' or device == 'ElectricalHeater_other_district':
                device_sankey = device.removesuffix('_district')
            else:
                device_sankey = device
            src, dst, layer, hub, dem_sup, check_dest_2, dest_2, offset, factor = flow
            df_label, df_stv, _ = add_flow(
                src.format(device=device_sankey),
                dst.format(device=device_sankey),
                layer,
                hub.format(device=device),
                dem_sup,
                df_annuals,
                df_label,
                df_stv,
                check_dest_2=check_dest_2,
                dest_2=dest_2.format(device=dest_2) if dest_2 else None,
                adjustment=offset,
                fact=factor
            )

    # Manually merge the heatpump_waste_heat as a heatpump_air to avoid duplication in the plots
    #df_label, df_stv, _ = add_flow('Electrical_consumption', 'HeatPump_Air', 'Electricity', 'HeatPump_Waste_heat',
    #                               'Demand_MWh', df_annuals, df_label, df_stv)

    #df_label, df_stv, _ = add_flow('HeatPump_Air', 'SH', 'SH', 'HeatPump_Waste_heat',
    #                               'Supply_MWh', df_annuals, df_label, df_stv)

    #df_label, df_stv, _ = add_flow('HeatPump_Air', 'DHW', 'DHW', 'HeatPump_Waste_heat',
    #                               'Supply_MWh', df_annuals, df_label, df_stv)

    electrical_storage_devices = ['Battery', 'Battery_IP', 'Battery_district', 'Battery_IP_district', 'EV_district']  # example list
    # Flow templates for electrical storage
    storage_flow_templates = [
        # Charging flow: electricity used to charge the battery
        ("Electrical_consumption", "{device}", "Electricity", "{device}", "Demand_MWh", False, None, 0, 1),

        # Discharging flow: battery supplies electricity back
        ("{device}", "Electrical_consumption", "Electricity", "{device}", "Supply_MWh", False, None, 0, 1),
    ]

    for device in electrical_storage_devices:
        for flow in storage_flow_templates:
            source, target, layer, hub, dem_sup, check_dest_2, dest_2, offset, factor = [f.format(device=device) if isinstance(f, str) else f for f in flow]
            df_label, df_stv, _ = add_flow(
                source,
                target,
                layer,
                hub,
                dem_sup,
                df_annuals,
                df_label,
                df_stv,
                check_dest_2=check_dest_2,
                dest_2=dest_2 if check_dest_2 else None,
                adjustment=offset,
                fact=factor
            )

    rSOC_distr_heat_need = df_annuals.loc[(df_annuals['Layer'] == "Heat") & (df_annuals['Hub'] == "rSOC_district")]["Demand_MWh"].sum()
    elec_heater_to_rSOC_distr = df_annuals.loc[(df_annuals['Layer'] == "Heat") & (df_annuals['Hub'] == "ElectricalHeater_other_district")]["Supply_MWh"].sum()

    # keys are layers, and then same structured information as above
    non_default_layers = {
        'Heat': {
            'flows': [
                # EXAMPLE #
                # ('Source_in_sankey', 'Destination_in_sankey', 'Hub_in_df_annuals 'Supply/Demand_MWh_in_df_annuals', bool_second_destination, second_destination_sankey, offset, mult_factor),

                # Network imports/exports
                ('Heat_import', 'DHN', 'Network', 'Supply_MWh', False, None, 0, 1),
                ('DHN', 'Heat_export', 'Network', 'Demand_MWh', False, None, 0, 1),

                # Internal flows
                ('DHN', 'DHN_hex', 'DHN_hex', 'Demand_MWh', False, None, 0, 1),
                ('DHN', 'HeatPump_DHN', 'HeatPump_DHN', 'Demand_MWh', False, None, 0, 1),
                ('HeatPump_Geothermal_district', 'DHN', 'HeatPump_Geothermal_district', 'Supply_MWh', False, None, 0, 1),
                ('rSOC', 'DHN', 'rSOC_district', 'Supply_MWh', False, None, 0, 1),
                ('NG_Boiler_district', 'DHN', 'NG_Boiler_district', 'Supply_MWh', False, None, 0, 1),
                ('MTR', 'rSOC', 'rSOC_district', 'Demand_MWh', False, None, -elec_heater_to_rSOC_distr, 1),
                ('MTR', 'DHN', 'MTR_district', 'Supply_MWh', False, None, -rSOC_distr_heat_need + elec_heater_to_rSOC_distr, 1),
                ('ElectricalHeater_other', 'rSOC', 'ElectricalHeater_other_district', 'Supply_MWh', False, None, 0, 1),
            ],
            'electricity_consumption': [
            ]
        },
        'Hydrogen': {
            'flows': [
                # Network imports/exports
                ('Hydrogen_import', 'rSOC', 'Network', 'Supply_MWh', False, None, 0, 1),
                ('rSOC', 'Hydrogen_export', 'Network', 'Demand_MWh', False, None, 0, 1),

                # Internal flows
                ('H2_storage_IP', 'rSOC', 'H2_storage_IP', 'Supply_MWh', False, None, 0, 1),
                ('rSOC', 'H2_storage_IP', 'H2_storage_IP', 'Demand_MWh', False, None, 0, 1),
                ('rSOC', 'MTR', 'MTR', 'Demand_MWh', False, None, 0, 1),
                ('H2_storage_IP', 'rSOC', 'H2_storage_IP_district', 'Supply_MWh', False, None, 0, 1),
                ('rSOC', 'H2_storage_IP', 'H2_storage_IP_district', 'Demand_MWh', False, None, 0, 1),
                ('rSOC', 'MTR', 'MTR_district', 'Demand_MWh', False, None, 0, 1),
            ],
            'electricity_consumption': [
                ('Electrical_consumption', 'H2_storage_IP', 'Electricity', 'H2_storage_IP', 'Demand_MWh', False, None, 0, 1),
                ('Electrical_consumption', 'H2_storage_IP', 'Electricity', 'H2_storage_IP_district', 'Demand_MWh', False, None, 0, 1),
            ],
        },
        'Biomethane': {
            'flows': [
                # Network imports/exports
                ('Biomethane_import', 'rSOC', 'Network', 'Supply_MWh', False, None, 0, 1),
                ('rSOC', 'Biomethane_export', 'Network', 'Demand_MWh', False, None, 0, 1),

                # internal flows
                ('CH4_storage_IP', 'rSOC', 'CH4_storage_IP', 'Supply_MWh', False, None, 0, 1),
                ('MTR', 'CH4_storage_IP', 'CH4_storage_IP', 'Demand_MWh', False, None, 0, 1),
                ('CH4_storage_IP', 'rSOC', 'CH4_storage_IP_district', 'Supply_MWh', False, None, 0, 1),
                ('MTR', 'CH4_storage_IP', 'CH4_storage_IP_district', 'Demand_MWh', False, None, 0, 1),
            ],
            'electricity_consumption': [
                # from CO2 storage electricity logic
                ('Electrical_consumption', 'CH4_storage_IP', 'Electricity', 'CH4_storage_IP', 'Demand_MWh', False, None, 0, 1),
                ('Electrical_consumption', 'CH4_storage_IP', 'Electricity', 'CH4_storage_IP_district', 'Demand_MWh', False, None, 0, 1),
            ]
        },
        'CO2': {
            'electricity_consumption': [
                ('Electrical_consumption', 'CH4_storage_IP', 'Electricity', 'CO2_storage_IP', 'Demand_MWh', False, None, 0, 1),
                ('Electrical_consumption', 'CH4_storage_IP', 'Electricity', 'CO2_storage_IP_district', 'Demand_MWh', False, None, 0, 1),
            ]
        },
        'Mobility': {
            'flows': [
                # Only include if the device exists (done in logic block below)
                ('Total_EV_fleet', 'Mobility', 'EV_district', 'Supply_MWh', False, None, 0, 1 / 9.37),
                ('Total_EV_fleet', 'Mobility', 'EV_charger_district', 'Supply_MWh', False, None, 0, 1 / 9.37),
            ],
            'electricity_consumption': [
                ('Electrical_consumption', 'Total_EV_fleet', 'Electricity', 'EV_district', 'Demand_MWh', False, None, 0, 1),
                ('Total_EV_fleet', 'Electrical_consumption', 'Electricity', 'EV_district', 'Supply_MWh', False, None, 0, 1),
                ('Electrical_consumption', 'Total_EV_fleet', 'Electricity', 'EV_charger_district', 'Demand_MWh', False, None, 0, 1),
                ('Total_EV_fleet', 'Electrical_consumption', 'Electricity', 'EV_charger_district', 'Supply_MWh', False, None, 0, 1)

            ]

        }
    }

    df_label, df_stv = apply_non_default_layers(df_annuals, df_label, df_stv, non_default_layers)

    # Final label formatting
    df_label['label'] = layout[label]
    df_label['color'] = layout[color]
    if display_label_value:
        df_label = add_label_value(df_label, df_stv, precision, units)

    source = list(df_stv.loc['source'])
    target = list(df_stv.loc['target'])
    value = [round(v, precision) for v in df_stv.loc['value']]
    label = list(df_label.label)
    color = list(df_label.color)

    return source, target, value, label, color


def apply_non_default_layers(df_annuals, df_label, df_stv, molecule_flows):
    for layer, data in molecule_flows.items():
        # Add basic flows
        for src, dst, hub, column, check_dest_2, dest_2, offset, factor in data.get('flows', []):
            df_label, df_stv, _ = add_flow(
                src, dst, layer, hub, column, df_annuals, df_label, df_stv,
                check_dest_2=check_dest_2, dest_2=dest_2 if check_dest_2 else None, adjustment=offset, fact=factor)

        # Add electricity consumption if defined
        for elec in data.get('electricity_consumption', []):
            src, dst, elec_layer, hub, column, check_dest_2, dest_2, offset, factor = elec
            df_label, df_stv, _ = add_flow(
                src, dst, elec_layer, hub, column, df_annuals, df_label, df_stv,
                check_dest_2=check_dest_2, dest_2=dest_2 if check_dest_2 else None, adjustment=offset, fact=factor)

    return df_label, df_stv
