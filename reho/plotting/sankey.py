import re
import pandas as pd
import numpy as np
from reho.paths import *

__doc__ = """
*Builds the dataframe for the visualization of annual flows from REHO results in the form of a Sankey diagram.*
"""

# Colors and labels for units and layers
layout = pd.read_csv(os.path.join(path_to_plotting, 'layout.csv'), index_col='Name').dropna(how='all')

def update_label(source_name, target_name, df_label):
    """
        update labels of df_label if source_name or target_name not in index of df_label

        Parameters:
            source_name (string) : first name to update
            target_name (string) : second name to update
            df_label (df): dataframe with labels

        Returns:
            df_label (df) updated
    """
    if not (source_name in df_label.index):  # create label 'source' if not existing yet
        df_label.loc[source_name, 'pos'] = len(df_label)
    if not (target_name in df_label.index):  # create label 'target' if not existing yet
        df_label.loc[target_name, 'pos'] = len(df_label)
    return df_label

def add_label_value(df_label, df_stv, precision, units):
    """
        add the values from df_stv to the labels of df_labels
        The value of the nodes are thus available in the nodes name for the sankey diagram

        Parameters:
            df_label (df): dataframe of labels
            df_stv (df): dataframe of source, target and value
            precision (int): precision of the displayed numbers (default = 2)
            units (string): unit of the values (default MWh)

        Returns:
            df label updated with the label values
    """
    df_source_value = pd.DataFrame()
    df_source_value.index = df_label.pos

    for i in list(df_source_value.index):
        source_val = df_stv.loc['value', df_stv.loc['source', :] == i].sum()
        target_val = df_stv.loc['value', df_stv.loc['target', :] == i].sum()
        # higher value on the node is displayed, (i.e. size of the box node on the sankey)
        df_source_value.loc[i, 'value'] = max(source_val, target_val)

    df_label = df_label.merge(df_source_value, left_on='pos', right_index=True)
    df_label.label = df_label.label+"\n"+df_label.value.round(precision).astype(str)+units
    return df_label

def add_flow(source, dest, layer, hub, dem_sup, df_annuals, df_label, df_stv, check_dest_2=False, dest_2=None, adjustment=0, fact=1):
    """
        Add an energy flow for the sankey diagramm for 'sankey_plot' according (a) cell(s) of df_annuals if cell not null

        Parameters:
            source (string) : name of the source
            dest (string) : name of the destination
            layer (string) : name of the layer of the considered cell(s)
            hub (string) : name of the hub of the considered cell(s)
            dem_sup (string) : 'Supply_MWh' or 'Demand_MWh', column to take (! no control)
            df_annuals (df) : df_annuals dataframe
            df_label (df) : df_label dataframe of labels
            df_stv (df) : df_stv dataframe of source,target,value
            check_dest_2 (bool) : if True dest_2 substitute dest (default false)
            dest_2 (string) : second possible destination (default none)
            adjustment (float) : offset added to the cell value (default 0)
            fact (float) : factor multiplied to the cell value (default 1)

        Returns:
            df_label updated (df), df_stv updated (df), value added (float, 0 if nothing added)
    """
    source_to_dest = df_annuals.loc[(df_annuals['Layer'] == layer) & (df_annuals['Hub'] == hub)][dem_sup].sum() # .sum() to add all the values of the buildings if multiple buildings
    if source_to_dest != 0:                                                     # if data available
        if check_dest_2:                                                        # if True apply the second dest
            dest = dest_2
        df_label = update_label(source, dest, df_label)                         # update label list
        df_stv[source+'_to_'+dest] = [df_label.loc[source, 'pos'],              # source, create a source to target column
                                      df_label.loc[dest, 'pos'],                # target
                                      float(fact*source_to_dest+adjustment)]    # value

    return df_label, df_stv, fact*source_to_dest+adjustment

def df_sankey(df_results, label='FR_long', color='ColorPastel', precision=2, units='MWh', display_label_value=True, scaling_factor=1):
    # Hypothèses :
    # 1. DHW demand taken as the supply of the watertank DHW
    # 2. no flow: electrical storage system to grid feed in, all to 'feed in electrical grid ' is from PV
    # 3. Small losses of NG, heat, wood,... between network and devices not accounted
    # 4. Electricity for 'Data heat' fully accounted as electricity consumption (Layer Data: not in sankey)
    # 5. Electricity produced by technologies can be stored (eg. NG_cogen elec -> battery)

    # Multi building :
    # supported

    # !! MAKE SURE : all the possible technologies/sources/demands are in the list below (if not, risk that sth will be
    # not displayed, there is no check provided by this function for that)
    # List of supported technologies/sources/demands
    # Electrical storage device
    elec_storage_list = ['Battery']
    # EV and their charging station are handled together
    EV_device = ['EV_district', "EVshared_district", "EV_charger_district"]
    # Manual handled devices (list below not used, just here for the information)
    manual_device     = ['PV', 'WaterTankSH']
    # Semi automatic handled devices
    semi_auto_device  = ['HeatPump_Air', 'HeatPump_DHN', 'NG_Boiler', 'ThermalSolar', 'OIL_Boiler',
                         'ElectricalHeater_DHW', 'ElectricalHeater_SH', 'NG_Cogeneration', 'DHN_in',
                         'HeatPump_Lake', 'WOOD_Stove', 'HeatPump_Geothermal', 'Air_Conditioner',
                         'DataHeat_DHW','ICE_district','Bike_district'] # name must be the same as used by REHO
    # Network (electrical grid, oil network...) and end use demand (DHW, SH, elec appliances) handled automatically



    # Select only not null lines in df_annuals
    df_annuals = scaling_factor*df_results['df_Annuals']
    df_annuals = df_annuals.replace(0, np.nan)
    df_annuals = df_annuals.loc[df_annuals['Demand_MWh'].notnull() | df_annuals['Supply_MWh'].notnull()]
    df_annuals = df_annuals.replace(np.nan, 0).reset_index()

    # "Building" string management in data to deal with data uniformly regarding buildings
    for x in list(df_annuals.index):
        if df_annuals.loc[x, "Hub"].startswith('Building'): #all Buildingx -> Building
            df_annuals.loc[x, "Hub"] = "Building"
        else:                                               #else remove '_Buildingx' of the hub name
            df_annuals.loc[x, "Hub"] = re.sub("_Building\d+", "", df_annuals.loc[x, "Hub"])

    # Creating the dataframe for the following
    df_label = pd.DataFrame(columns=['pos'])                      # df for labels, position number (pos) and colors
    df_stv   = pd.DataFrame(index=['source', 'target', 'value'])  # df for source,target,value

    # check if electricity storage
    elec_storage_use = False
    for elec_storage in elec_storage_list:
        if len(df_annuals.loc[(df_annuals['Layer'] == 'Electricity') & (df_annuals['Hub'] == elec_storage)]) != 0:
            elec_storage_use = True

    # check if watertank SH
    watertank_sh = False
    if len(df_annuals.loc[(df_annuals['Layer'] == 'SH') & (df_annuals['Hub'] == 'WaterTankSH')]) != 0:
        watertank_sh = True

    # 1 Elec Grid to Elec Consumption of the building(s) or before electricity storage (=Before Phase, bp) if present
    df_label, df_stv, _ = add_flow('Electrical_grid', 'Electrical_consumption', 'Electricity', 'Network', 'Supply_MWh',
                                   df_annuals, df_label, df_stv, elec_storage_use, 'Electrical_consumption_bp')

    # 2 Elec Cons to Elec Appliances
    df_label, df_stv, _ = add_flow('Electrical_consumption', 'Electrical_appliances', 'Electricity', 'Building',
                                   'Demand_MWh', df_annuals, df_label, df_stv)

    # 3 PV to Electrical Grid feed in
    df_label, df_stv, pv_to_egf = add_flow('PV', 'Electrical_grid_feed_in', 'Electricity', 'Network',
                                           'Demand_MWh', df_annuals, df_label, df_stv)

    # 4 PV to Electrical cons (before battery if present)
    df_label, df_stv, _ = add_flow('PV', 'Electrical_consumption', 'Electricity', 'PV',
                                   'Supply_MWh', df_annuals, df_label, df_stv, elec_storage_use, 'Electrical_consumption_bp',
                                   -pv_to_egf)

    # 5 WaterTankSH to SH
    df_label, df_stv, wtsh_to_sh = add_flow('WaterTankSH', 'SH', 'SH', 'WaterTankSH', 'Supply_MWh',
                                            df_annuals, df_label, df_stv)

    # Calculation of Losses in the watertank
    heat_tot_sh  = df_annuals.loc[(df_annuals['Layer'] == 'SH') & (df_annuals['Hub'] == 'Building')].Demand_MWh.sum()
    heat_tot_sup = df_annuals.loc[(df_annuals['Layer'] == 'SH')].Supply_MWh.sum() - wtsh_to_sh
    heat_loss_wt = heat_tot_sup - heat_tot_sh

    # 6 SH Heat to Watertank SH if watertank
    df_label, df_stv, _ = add_flow('SH_heat', 'WaterTankSH', 'SH', 'WaterTankSH', 'Supply_MWh',
                                   df_annuals, df_label, df_stv, adjustment=heat_loss_wt)

    # 7 SH Heat to SH if watertank
    df_label, df_stv, _ = add_flow('SH_heat', 'SH', 'SH', 'WaterTankSH', 'Supply_MWh',
                                   df_annuals, df_label, df_stv, adjustment=heat_tot_sup-heat_loss_wt, fact=-1)

    elec_storage_energy_in  = 0
    elec_storage_energy_out = 0
    for elec_storage in elec_storage_list:
        # 8 Electrical cons before elec storage to storage device
        df_label, df_stv, dev_flow_in = add_flow('Electrical_consumption_bp', elec_storage, 'Electricity', elec_storage,
                                                 'Demand_MWh', df_annuals, df_label, df_stv)
        elec_storage_energy_in += dev_flow_in

        # 9 storage device to Electrical cons
        df_label, df_stv, dev_flow_out = add_flow(elec_storage, 'Electrical_consumption', 'Electricity', elec_storage,
                                                  'Supply_MWh', df_annuals, df_label, df_stv)
        elec_storage_energy_out += dev_flow_out

    # 10 Electrical cons before elec storage to Electr cons
    if elec_storage_use:
        df_label = update_label('Electrical_consumption_bp', 'Electrical_consumption', df_label)
        Ec_after_bp =  df_annuals.loc[(df_annuals['Layer'] == 'Electricity') & (df_annuals['Hub'] != 'Network')].Demand_MWh.sum()
        Ec_after_bp -= elec_storage_energy_out
        df_stv['Electrical_consumption_bp_to_Electrical_consumption'] = [df_label.loc['Electrical_consumption_bp', 'pos'],
                                                                         df_label.loc['Electrical_consumption', 'pos'],
                                                                         float(Ec_after_bp-elec_storage_energy_in)]

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
        abr_hp = device
        # 1 Ele Cons to Device
        df_label, df_stv, _ = add_flow('Electrical_consumption', device, 'Electricity', device, 'Demand_MWh',
                                       df_annuals, df_label, df_stv)

        # 2 Heat to Device
        df_label, df_stv, _ = add_flow('Heat', device, 'Heat', device, 'Demand_MWh',
                                       df_annuals, df_label, df_stv)

        # 3 NG to Device
        df_label, df_stv, _ = add_flow('NaturalGas', device, 'NaturalGas', device, 'Demand_MWh',
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
                                       df_annuals, df_label, df_stv, elec_storage_use, 'Electrical_consumption_bp')

        # 8 Device to Cooling
        df_label, df_stv, _ = add_flow(device, 'Cooling', 'Cooling', device, 'Supply_MWh',
                                       df_annuals, df_label, df_stv)
        
        # 9 Device to Mobility 
        df_label, df_stv, _ = add_flow(device, 'Mobility (0.1 kWh/pkm)', 'Mobility', device, 'Supply_MWh',
                                       df_annuals, df_label, df_stv,fact=1/9.37)        

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
