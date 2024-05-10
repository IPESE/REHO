import pandas as pd
import numpy as np
import logging

__doc__ = """
Extracts the results from the AMPL model and converts it to Python dictionary and pandas dataframes.
"""

def get_df_Results_from_SP(ampl, scenario, method, buildings_data, filter=True):

    def set_df_performance(ampl, scenario):
        df1 = get_ampl_data(ampl, 'Costs_House_op')  # without the comfort penalty costs
        df1 = df1.rename(columns={'Costs_House_op': 'Costs_op'})

        df2 = get_ampl_data(ampl, 'Costs_House_inv')
        df2 = df2.rename(columns={'Costs_House_inv': 'Costs_inv'})
        tau = ampl.getParameter('tau').getValues().toList()
        df2['Costs_inv'] = df2['Costs_inv'] * tau[0]
        df2['ANN_factor'] = tau[0]

        df2['Costs_grid_connection'] = get_ampl_data(ampl, 'Costs_grid_connection_House', multi_index=True).groupby(level=1).sum()  # yearly cost for grid connection

        df3 = get_ampl_data(ampl, 'Costs_House_rep')
        df3['Costs_House_rep'] = df3['Costs_House_rep'] * tau[0]
        df3 = df3.rename(columns={'Costs_House_rep': 'Costs_rep'})

        df4 = get_ampl_data(ampl, 'Costs_House_cft')
        df4 = df4.rename(columns={'Costs_House_cft': 'Costs_ft'})

        df5 = get_ampl_data(ampl, 'GWP_house_op')
        df5 = df5.rename(columns={'GWP_house_op': 'GWP_op'})

        df6 = get_ampl_data(ampl, 'GWP_house_constr')
        df6 = df6.rename(columns={'GWP_house_constr': 'GWP_constr'})

        df71 = get_ampl_data(ampl, 'EMOO_CAPEX')
        df72 = get_ampl_data(ampl, 'EMOO_OPEX')
        df73 = get_ampl_data(ampl, 'EMOO_TOTEX')
        df75 = get_ampl_data(ampl, 'EMOO_GWP')
        df76 = get_ampl_data(ampl, 'EMOO_grid')

        df_N1 = get_ampl_data(ampl, 'Costs_op')  # without the comfort penalty costs
        df_N2 = get_ampl_data(ampl, 'Costs_inv')
        df_N2['Costs_inv'] = df_N2['Costs_inv'] * tau[0]
        df_N2['ANN_factor'] = tau[0]
        df_N2['Costs_grid_connection'] = get_ampl_data(ampl, 'Costs_grid_connection').sum().values/2  # TODO enhance
        df_N3 = get_ampl_data(ampl, 'Costs_rep')
        df_N3['Costs_rep'] = df_N3['Costs_rep'] * tau[0]
        df_N4 = pd.DataFrame({'Costs_ft': [df4.sum()['Costs_ft']]})
        df_N5 = get_ampl_data(ampl, 'GWP_op')
        df_N6 = get_ampl_data(ampl, 'GWP_constr')

        df_PerformanceBuilding = pd.concat([df1, df2, df3, df4, df5, df6], axis=1)
        df_PerformanceNetwork = pd.concat([df_N1, df_N2, df_N3, df_N4, df_N5, df_N6], axis=1)
        df_PerformanceNetwork = df_PerformanceNetwork.rename(index={0: 'Network'})

        df_Performance = pd.concat([df_PerformanceBuilding, df_PerformanceNetwork], axis=0)

        df_Epsilon = pd.concat([df71, df72, df73, df75, df76], axis=1)
        df_Epsilon['Objective'] = get_ampl_data(ampl, scenario["Objective"]).values[0][0]- df_N4.values[0][0]
        df_Epsilon = df_Epsilon.rename(index={0: 'Network'})

        df_Performance = pd.concat([df_Performance, df_Epsilon], axis=1)
        df_Performance.index.names = ['Hub']
        if method['print_logs']:
            print(df_Performance)

        return df_Performance.sort_index()

    def set_df_annuals(ampl):
        # Annuals
        df1 = get_ampl_data(ampl, 'AnnualNetwork_demand')
        df1.columns = ['Demand_MWh']
        df1 = pd.concat([df1], keys=['Network'])
        df1.index = df1.index.reorder_levels([1, 0])
        df2 = get_ampl_data(ampl, 'AnnualNetwork_supply')
        df2.columns = ['Supply_MWh']
        df2 = pd.concat([df2], keys=['Network'])
        df2.index = df2.index.reorder_levels([1, 0])
        df12 = pd.concat([df1, df2], axis=1, sort=False)

        df3 = get_ampl_data(ampl, 'AnnualDomestic_electricity')
        df3 = df3.set_index([pd.Index(["Electricity"]*df3.index.size), df3.index])
        df3.columns = ['Demand_MWh']
        df4 = get_ampl_data(ampl, 'AnnualHouse_Q')
        df4.columns = ['Demand_MWh']
        df5 = get_ampl_data(ampl, 'AnnualHeatGainHouse')
        df5.columns = ['Supply_MWh']
        df5 = pd.concat([df5], keys=['HeatGains'])
        df6 = get_ampl_data(ampl, 'AnnualSolarGainHouse')
        df6.columns = ['Supply_MWh']
        df6 = pd.concat([df6], keys=['SolarGains'])
        df3456 = pd.concat([df3, df4, df5, df6], sort=False)

        df7 = get_ampl_data(ampl, 'AnnualUnit_in')
        df7.columns = ['Demand_MWh']
        df8 = get_ampl_data(ampl, 'AnnualUnit_out')
        df8.columns = ['Supply_MWh']
        df78 = pd.concat([df7, df8], axis=1, sort=False)
        df9 = get_ampl_data(ampl, 'AnnualUnit_Q')
        df9.columns = ['Supply_MWh']
        df789 = pd.concat([df78, df9], sort=False)

        df_Annuals = pd.concat([df12, df3456, df789], sort=False)
        df_Annuals.index.names = ['Layer', 'Hub']

        # Correction of DHW layer
        hubs = [s for s in df_Annuals.index.levels[1] if s.startswith("Building")]
        for h in hubs:
            df_Annuals.loc[('DHW', h), 'Demand_MWh'] = df_Annuals.loc[('DHW', 'WaterTankDHW_' + h), 'Supply_MWh']

        return df_Annuals

    def set_df_buildings(buildings_data):
        # Building
        df_Buildings = pd.DataFrame.from_dict(buildings_data, orient='index')
        df_Buildings.index.names = ['Hub']
        for item in ['x', 'y', 'z', 'geometry']:
            if item in df_Buildings.columns:
                df_Buildings.drop([item], axis=1)

        return df_Buildings.sort_index()

    def set_df_unit(ampl):
        # Unit
        tau = ampl.getParameter('tau').getValues().toList()
        df1 = get_ampl_data(ampl, 'Units_Use')
        df2 = get_ampl_data(ampl, 'Units_Mult')

        df3 = tau[0] * get_ampl_data(ampl, 'Costs_Unit_inv')
        df4 = get_ampl_data(ampl, 'GWP_Unit_constr')  # per year! For total, multiply with lifetime
        df5 = get_ampl_data(ampl, 'lifetime')
        df_Unit = pd.concat([df1, df2, df3, df4, df5], axis=1)
        df_Unit.index.names = ['Unit']
        df_Unit = df_Unit.sort_index()
        if method['print_logs']:
            print(df_Unit)

        # Unit_t
        df1 = get_ampl_data(ampl, 'Units_demand', multi_index=True)
        df2 = get_ampl_data(ampl, 'Units_supply', multi_index=True)
        df3 = get_ampl_data(ampl, 'Units_curtailment', multi_index=True)
        df4 = get_ampl_data(ampl, 'BAT_E_stored', multi_index=True)
        df4 = pd.concat([df4], keys=['Electricity'], names=['Layer'])
        if "EV_district" in [unit for unit, value in ampl.getVariable('Units_Use').instances()]:
            df5 = get_ampl_data(ampl, 'EV_E_stored', multi_index=True)
            df5 = pd.concat([df5], keys=['Electricity'], names=['Layer'])
            df6 = get_ampl_data(ampl, "EV_displacement", multi_index=True)
            df6 = pd.concat([df6], keys=['Electricity'], names=['Layer'])
            df_Unit_t = pd.concat([df1, df2, df3, df4, df5, df6], axis=1)
        else:
            df_Unit_t = pd.concat([df1, df2, df3, df4], axis=1)
        df_Unit_t.index.names = ['Layer', 'Unit', 'Period', 'Time']
        df_Unit_t = df_Unit_t.sort_index()

        return df_Unit, df_Unit_t

    def set_df_grid(ampl, method):
        # Grid_t
        df1 = get_ampl_data(ampl, 'Grid_demand', multi_index=True)
        df2 = get_ampl_data(ampl, 'Grid_supply', multi_index=True)

        df_cs = get_ampl_data(ampl, 'Cost_supply', multi_index=True)
        df_cs = df_cs.reorder_levels((1, 0, 2, 3))
        df_cd = get_ampl_data(ampl, 'Cost_demand', multi_index=True)
        df_cd = df_cd.reorder_levels((1, 0, 2, 3))

        df_electricity = get_ampl_data(ampl, 'Domestic_electricity', multi_index=True)
        df_electricity.columns = ['Uncontrollable_load']
        df_electricity = df_electricity.set_index([pd.Index(["Electricity"]*df_electricity.index.size), df_electricity.index])

        df_es = get_ampl_data(ampl, 'GWP_supply', multi_index=True)
        df_ed = get_ampl_data(ampl, 'GWP_demand', multi_index=True)
        df_em = pd.concat([df_es, df_ed], axis=1)
        df_em_tot = pd.DataFrame()
        for bui in df1.index.get_level_values(1).unique():
            df = df_em
            df["Hub"] = bui
            df_em_tot = pd.concat([df_em_tot, df])
        df_em_tot.set_index('Hub', append=True, inplace=True)
        df_em_tot = df_em_tot.reorder_levels((0, 3, 1, 2))

        df_Grid_t = pd.concat([df1, df2, df_cs, df_cd, df_em_tot, df_electricity], axis=1)

        if not method["district-scale"] or not method["district-scale"]:
            df3 = get_ampl_data(ampl, 'Network_demand', multi_index=True)
            df3.columns = ['Grid_demand']
            df4 = get_ampl_data(ampl, 'Network_supply', multi_index=True)
            df4.columns = ['Grid_supply']
            df_cs_net = get_ampl_data(ampl, 'Cost_supply_network', multi_index=True)
            df_cs_net.columns = ['Cost_supply']
            df_cd_net = get_ampl_data(ampl, 'Cost_demand_network', multi_index=True)
            df_cd_net.columns = ['Cost_demand']

            df_electricity_net = df_electricity.groupby(level=(0, 2, 3)).sum()
            df34 = pd.concat([df3, df4, df_cs_net, df_cd_net, df_es, df_ed, df_electricity_net], axis=1)
            df34['Hub'] = 'Network'
            df34.set_index('Hub', append=True, inplace=True)
            df34 = df34.reorder_levels((0, 3, 1, 2))
            df_Grid_t = pd.concat([df_Grid_t, df34])

        df_Grid_t.index.names = ['Layer', 'Hub', 'Period', 'Time']
        return df_Grid_t.sort_index()

    def set_df_buildings_t(ampl):
        # Building_t
        df1 = get_ampl_data(ampl, 'Domestic_electricity', multi_index=True)

        m_DWH = get_ampl_data(ampl, 'DHW_flowrate', multi_index=True)
        delta_T = get_ampl_data(ampl, 'DHW_dT').iloc[0,0]
        df2 = 4.18*m_DWH*delta_T/3600
        df2 = df2.rename(columns={'DHW_flowrate': 'House_Q_DHW'})

        df31 = get_ampl_data(ampl, 'T_in', multi_index=True)
        df32 = get_ampl_data(ampl, 'House_Q_heating')
        df33 = get_ampl_data(ampl, 'House_Q_cooling')
        df34 = get_ampl_data(ampl, 'Th_supply', multi_index=True)
        df35 = get_ampl_data(ampl, 'Th_return', multi_index=True)

        df4 = get_ampl_data(ampl, 'HeatGains', multi_index=True)
        df5 = get_ampl_data(ampl, 'SolarGains', multi_index=True)

        df_Buildings_t = pd.concat([df1, df2, df31, df32, df33, df34, df35, df4, df5], axis=1)
        df_Buildings_t.index.names = ['Hub', 'Period', 'Time']

        return df_Buildings_t.sort_index()

    def set_df_streams_t(ampl):

        df_Q = get_ampl_data(ampl, 'Streams_Q', multi_index=True)
        df_Q.index.set_names(['Service', 'Stream', 'Period', 'Time'], inplace=True)

        df1 = get_ampl_data(ampl, 'HC_Streams_Mult', multi_index=True)
        df1.index.set_names(['Service', 'Stream', 'Period', 'Time'], inplace=True)
        df2 = get_ampl_data(ampl, 'Streams_Mcp', multi_index=True)
        df2.index.set_names(['Stream', 'Period', 'Time'], inplace=True)
        df_mcp = df1['HC_Streams_Mult'].mul(df2['Streams_Mcp'])
        df_mcp = pd.DataFrame(df_mcp, columns=['Streams_Mcp_kW/K']).sort_index()

        dict = {}
        for a, b in ampl.getSet('StreamsOfUnit').instances():
            dict[a] = b.getValues().toPandas().index.to_list()
        df_dict = pd.DataFrame.from_dict(dict, orient='index')

        df_Tin = get_ampl_data(ampl, 'Streams_Tin', multi_index=True)
        df_Tout = get_ampl_data(ampl, 'Streams_Tout', multi_index=True)

        df_Tin.index.set_names(['Stream', 'Period', 'Time'], inplace=True)
        df_Tout.index.set_names(['Stream', 'Period', 'Time'], inplace=True)

        df_Tmin = get_ampl_data(ampl, 'dTmin')
        df_Tmin.index.set_names('Stream', inplace=True)

        df_Q = df_Q.reset_index('Service', drop=False)
        df_Q = df_Q.join([df_Tin, df_Tout]).set_index('Service', append=True)
        df_Q = df_Q.merge(df_mcp, left_index=True, right_on=['Stream', 'Period', 'Time', 'Service'])
        df_Q = df_Q.reorder_levels([3, 0, 1, 2]).sort_index()

        df_dict = df_dict.unstack()
        df_dict.dropna(inplace=True)
        df_dict = df_dict.reset_index().set_index(0)
        df_dict.drop(columns='level_0', inplace=True)
        df_dict.index.set_names(['Stream'], inplace=True)
        df_dict.rename(columns={'level_1': 'Unit'}, inplace=True)

        df_Streams_t = df_Q.reset_index().set_index('Stream')
        df_Streams_t = df_Streams_t.join([df_dict, df_Tmin]).set_index(['Service', 'Unit', 'Period', 'Time'], append=True)

        return df_Streams_t.sort_index()

    def set_dfs_lca(ampl):

        LCA_units = get_ampl_data(ampl, 'lca_units')
        LCA_units = LCA_units.stack().unstack(level=0).droplevel(level=1)

        LCA_tot = get_ampl_data(ampl, 'lca_tot')
        LCA_tot = LCA_tot.stack().unstack(level=0)
        LCA_tot.index = ["Network"]
        LCA_tot_house = get_ampl_data(ampl, 'lca_tot_house')
        LCA_tot_house = LCA_tot_house.stack().unstack(level=0).droplevel(1)
        LCA_tot = pd.concat([LCA_tot_house, LCA_tot], axis=0)
        LCA_tot.index.names = ['Hub']

        LCA_op = get_ampl_data(ampl, 'lca_op')
        LCA_op = LCA_op.stack().unstack(level=0).droplevel(level=1)

        return LCA_units, LCA_tot, LCA_op

    def set_dfs_pv(ampl):

        # PV_Surface
        df_PV_Surface = get_ampl_data(ampl, "HouseSurfaceArea", multi_index=True)
        df_PV_Surface.index.names = ['Hub', 'Surface']
        df_PV_Surface.rename(columns={'HouseSurfaceArea': 'Area'})
        df_PV_Surface = df_PV_Surface.sort_index()

        # ["df_PV_orientation"]
        df_PVA_module_nbr = get_ampl_data(ampl, 'PVA_module_nbr', multi_index=True)
        df_PVA_module_nbr = df_PVA_module_nbr.droplevel(4)
        df_PVA_module_nbr.index.names = ['Hub', 'Surface', 'Azimuth', 'Tilt']
        #int_index = df_PVA_module_nbr.index.get_level_values('Surface').astype(int)
        #df_PVA_module_nbr.index.set_levels(int_index, level="Surface", inplace=True)

        df_PVA_module_coverage = get_ampl_data(ampl, "PVA_module_coverage", multi_index=True)
        df_PVA_module_coverage = df_PVA_module_coverage.droplevel(1)
        df_PVA_module_coverage.index.names = ['Hub', 'Surface', 'Azimuth', 'Tilt']

        pd.concat([df_PVA_module_coverage, df_PVA_module_nbr], axis=1)


        df_unshaded_share = get_ampl_data(ampl, 'unshaded_share', multi_index=True)
        df_unshaded_share = df_unshaded_share.groupby(level=[0, 1, 2, 3]).sum()
        df_unshaded_share = df_unshaded_share.div(145)  # 145 patches in skydome
        df_unshaded_share.index.names = ['Hub', 'Surface', 'Azimuth', 'Tilt']

        df_PV_orientation = pd.concat([df_PVA_module_coverage, df_unshaded_share, df_PVA_module_nbr], axis=1)
        # df_PV_Surface_profiles
        # centralized optimization PV_electricity takes a lot of memory -> TODO move to annuals profiles are not needed
        # df_PV_Surface_profiles = get_ampl_data(ampl, "PV_electricity")
        # df_PV_Surface_loss = get_ampl_data(ampl, "PV_electricity_without_loss")
        # df_PV_Surface_profiles = pd.concat([df_PV_Surface_profiles, df_PV_Surface_loss], axis=1)
        # df_PV_Surface_profiles.index.names = ['Hub','Unit','Surface', 'Azimuth','Tilt', 'Period', 'Time']
        # df_Results["df_PV_Surface"]_profiles = df_PV_Surface_profiles.sort_index()

        return df_PV_Surface, df_PV_orientation

    def set_dfs_other(ampl):
        # Time
        df1 = get_ampl_data(ampl, 'dp')
        df2 = get_ampl_data(ampl, 'TimeEnd')
        df3 = get_ampl_data(ampl, 'dt')
        df_Time = pd.concat([df1, df2, df3], axis=1)
        df_Time.index.names = ['Period']
        df_Time = df_Time.sort_index()

        # External
        df1 = get_ampl_data(ampl, 'T_ext', multi_index=True)
        df2 = get_ampl_data(ampl, 'I_global', multi_index=True)
        df_External = pd.concat([df1, df2], axis=1)
        df_External.index.names = ['Period', 'Time']
        df_External = df_External.sort_index()

        # Index
        df_Index = get_ampl_data(ampl, 'PeriodOfYear')
        df_Index.index.names = ['HourOfYear']
        df_Index = df_Index.sort_index()

        return df_Time, df_External, df_Index

    df_Results = dict()
    df_Results["df_Performance"] = set_df_performance(ampl, scenario)
    df_Results["df_Annuals"] = set_df_annuals(ampl)
    df_Results["df_Unit"], df_Unit_t = set_df_unit(ampl)
    df_Results["df_Grid_t"] = set_df_grid(ampl, method)
    df_Results["df_Time"], df_External, df_Index = set_dfs_other(ampl)

    if method['save_data_input']:
        df_Results["df_Buildings"] = set_df_buildings(buildings_data)
        df_Results["df_External"] = df_External
        df_Results["df_Index"] = df_Index

    if method["save_timeseries"]:
        df_Results["df_Buildings_t"] = set_df_buildings_t(ampl)
        df_Results["df_Unit_t"] = df_Unit_t
    else:
        for i in ['Cost_demand', 'Cost_supply', 'GWP_demand', 'GWP_supply', "Uncontrollable_load"]:
            del df_Results["df_Grid_t"][i]

    if method["save_streams"]:
        df_Results["df_Streams_t"] = set_df_streams_t(ampl)

    if method['save_lca']:
        df_Results["df_lca_Units"], df_Results["df_lca_Performance"], df_Results["df_lca_operation"] = set_dfs_lca(ampl)
    if method['use_pv_orientation'] or method['use_facades']:
        df_Results["df_PV_Surface"], df_Results["df_PV_orientation"] = set_dfs_pv(ampl)
    if method["extract_parameters"]:
        parameters_record = {}
        for p, ampl_obj in ampl.getParameters():
            try:
                parameters_record[p] = ampl.getData(p).toPandas()
            except:
                logging.info(p)

    if filter:
        for df_name, df in df_Results.items():
            df = df.fillna(0)  # replace all NaN with zeros
            df = df.loc[~(df == 0).all(axis=1)]  # drop all lines with only zeros

    return df_Results


def get_df_Results_from_MP(ampl, binary=False, method=None, district=None, read_DHN=False, scenario={}):

    df_Results = dict()

    # Dantzig Wolfe algorithm
    df1 = get_ampl_data(ampl, 'lambda', multi_index=True)
    df_DW = pd.concat([df1], axis=1)
    df_DW.index.names = ['FeasibleSolution', 'Hub']
    df_Results["df_DW"] = df_DW.sort_index()

    if method["save_data_input"] or binary:
        # Building_t
        df1 = get_ampl_data(ampl, 'Grid_supply', multi_index=True)
        df2 = get_ampl_data(ampl, 'Grid_demand', multi_index=True)
        df_Buildings_t = pd.concat([df1, df2], axis=1)
        if read_DHN:
            df3 = get_ampl_data(ampl, 'flowrate_out', multi_index=True)
            df3 = pd.concat({'Heat': df3})
            df4 = get_ampl_data(ampl, 'flowrate_in', multi_index=True)
            df4 = pd.concat({'Heat': df4})
            df_Buildings_t = pd.concat([df_Buildings_t, df3, df4], axis=1)
        df_Buildings_t.index.names = ['Layer', 'FeasibleSolution', 'Hub', 'Period', 'Time']
        df_Results["df_Buildings_t"] = df_Buildings_t.sort_index()

        # Building
        df1 = get_ampl_data(ampl, 'Costs_inv_rep_SPs', multi_index=True)
        df2 = get_ampl_data(ampl, 'Costs_ft_SPs', multi_index=True)
        df_Buildings = pd.concat([df1, df2], axis=1)
        df_Buildings.index.names = ['FeasibleSolution', 'Hub']
        df_Results["df_Buildings"] = df_Buildings.sort_index()

    # District
    df1 = get_ampl_data(ampl, 'Costs_House_op')
    df2 = get_ampl_data(ampl, 'Costs_House_inv')
    df3 = get_ampl_data(ampl, 'Costs_House_cft')
    df4 = df1.values + df2
    df4.columns = ["Costs_House_tot"]
    df5 = get_ampl_data(ampl, 'GWP_House_op')
    df6 = get_ampl_data(ampl, 'GWP_House_constr')
    df_House = pd.concat([df1, df2, df3, df4, df5, df6], axis=1)
    df_House.columns = ["Costs_op", "Costs_inv", "Costs_cft", "Costs_tot", "GWP_op", "GWP_constr"]
    if read_DHN:
        df7 = get_ampl_data(ampl, 'diameter_max')
        df8 = get_ampl_data(ampl, 'DHN_inv_house')
        df8.columns = ["DHN_inv"]
        df9 = get_ampl_data(ampl, 'flowrate_max')
        df_House = pd.concat([df_House, df7, df8, df9], axis=1)


    df1 = get_ampl_data(ampl, 'Costs_op')
    df2 = get_ampl_data(ampl, 'Costs_inv')  # with comfort costs
    df3 = get_ampl_data(ampl, 'Costs_cft')  # with comfort costs
    df4 = get_ampl_data(ampl, 'Costs_tot')  # with comfort costs
    df5 = get_ampl_data(ampl, 'GWP_op')
    df6 = get_ampl_data(ampl, 'GWP_constr')
    df_District = pd.concat([df1, df2, df3, df4, df5, df6], axis=1)
    if read_DHN:
        df7 = np.sqrt(np.sum(df_House[["diameter_max"]]**2)).to_frame().transpose()
        df8 = get_ampl_data(ampl, 'DHN_inv')
        df_District = pd.concat([df_District, df7, df8], axis=1)
    df_District = df_District.set_index(pd.Index(["Network"]))
    df_District = pd.concat([df_House, df_District], axis=0)
    df_District.index.names = ['Hub']
    df_Results["df_District"] = df_District.sort_index()

    # df_beta
    emoo_keys = ["EMOO_CAPEX", "EMOO_OPEX", "EMOO_GWP", "EMOO_TOTEX", "EMOO_lca"]
    list_keys = [i for i in scenario["EMOO"].keys() if i in emoo_keys]
    if not list_keys:
        df = pd.DataFrame([0.0] * 16)
        df.index = ['CAPEX', 'OPEX', 'GWP', 'TOTEX'] + list(get_ampl_data(ampl, 'Lca_kpi').index)
        df.columns = ["beta"]
        df_Results["df_beta"] = df
    else:
        df1 = get_ampl_dual_values_in_pandas(ampl, 'EMOO_CAPEX_constraint', False)
        df1.columns = ['CAPEX']
        df2 = get_ampl_dual_values_in_pandas(ampl, 'EMOO_OPEX_constraint', False)
        df2.columns = ['OPEX']
        df3 = get_ampl_dual_values_in_pandas(ampl, 'EMOO_GWP_constraint', False)
        df3.columns = ['GWP']
        df4 = get_ampl_dual_values_in_pandas(ampl, 'EMOO_TOTEX_constraint', False)
        df4.columns = ['TOTEX']
        df_beta = pd.concat([df1, df2, df3, df4], axis=1).stack().droplevel(0)
        df_beta = pd.DataFrame(df_beta, columns=['beta'])
        df5 = get_ampl_dual_values_in_pandas(ampl, 'EMOO_lca_constraint', False)
        df5.columns = ['beta']
        df_Results["df_beta"] = pd.concat([df_beta, df5])

    # District_t
    df1 = get_ampl_data(ampl, 'Cost_demand_network', multi_index=True)
    df2 = get_ampl_data(ampl, 'Cost_supply_network', multi_index=True)
    df3 = get_ampl_data(ampl, 'GWP_demand', multi_index=True)
    df4 = get_ampl_data(ampl, 'GWP_supply', multi_index=True)
    df5 = get_ampl_data(ampl, 'Network_supply', multi_index=True)
    df6 = get_ampl_data(ampl, 'Network_demand', multi_index=True)

    if binary:
        df_District_t = pd.concat([df1, df2, df3, df4, df5, df6], axis=1).sort_index()
    else:
        df_District_t = pd.concat([df5, df6], axis=1)
    df_District_t.index.names = ['Layer', 'Period', 'Time']
    df_Results["df_District_t"] = df_District_t.sort_index()

    # df_Dual
    df1 = get_ampl_dual_values_in_pandas(ampl, 'convexity_1', False)
    df1.columns = ['mu']
    df_Dual = pd.concat([df1], axis=1)
    df_Dual.index.names = ['Hub']
    df_Results["df_Dual"] = df_Dual.sort_index()

    # df_Dual_t
    df1 = get_ampl_dual_values_in_pandas(ampl, 'complicating_cst', True)
    df1.columns = ['pi']
    df2 = get_ampl_dual_values_in_pandas(ampl, 'complicating_cst_GWP', True)
    df2.columns = ['pi_GWP']
    df3 = get_ampl_dual_values_in_pandas(ampl, 'complicating_cst_lca', True).stack().unstack(0).droplevel(3)
    df4 = get_ampl_dual_values_in_pandas(ampl, 'EMOO_grid_constraint', False)
    df4.columns = ['gamma_supply']
    df_Dual_t = pd.concat([df1, df2, df3, df4], axis=1)
    df_Dual_t.index.names = ['Layer', 'Period', 'Time']
    df_Results["df_Dual_t"] = df_Dual_t.sort_index()

    # Unit
    tau = ampl.getParameter('tau').getValues().toList()  # annuality factor
    df1 = get_ampl_data(ampl, 'Units_Use')
    df2 = get_ampl_data(ampl, 'Units_Mult')
    df3 = tau[0] * get_ampl_data(ampl, 'Costs_Unit_inv')
    df4 = get_ampl_data(ampl, 'GWP_Unit_constr')  # per year! For total - multiply with lifetime
    df5 = get_ampl_data(ampl, 'lifetime')
    df_Unit = pd.concat([df1, df2, df3, df4, df5], axis=1)
    if read_DHN:
        df_DHN = pd.DataFrame([[1, 1, get_ampl_data(ampl, 'DHN_inv')["DHN_inv"][0], 0, 0]], index=["DHN"], columns=df_Unit.columns)
        df_Unit = pd.concat([df_Unit, df_DHN], axis=0)
    df_Unit.index.names = ['Unit']
    df_Results["df_Unit"] = df_Unit.sort_index()

    # Unit_t
    df1 = get_ampl_data(ampl, 'Units_demand', multi_index=True)
    df2 = get_ampl_data(ampl, 'Units_supply', multi_index=True)
    df3 = get_ampl_data(ampl, 'BAT_E_stored', multi_index=True)
    df3 = pd.concat([df3], keys=['Electricity'], names=['Layer'])
    df_Unit_t = pd.concat([df1, df2, df3], axis=1)

    if len(district.UnitsOfDistrict) > 0:
        if "EV_district" in district.UnitsOfDistrict:
            df4 = get_ampl_data(ampl, 'EV_E_stored', multi_index=True)
            df4 = pd.concat([df4], keys=['Electricity'], names=['Layer'])
            df5 = get_ampl_data(ampl, 'EV_displacement', multi_index=True)
            df5 = pd.concat([df5], keys=['Electricity'], names=['Layer'])
            df6 = get_ampl_data(ampl, 'EV_V2V', multi_index=True)
            df6 = pd.concat([df6], keys=['Electricity'], names=['Layer'])
            df_Unit_t = pd.concat([df_Unit_t, df4, df5, df6], axis=1)
    df_Unit_t.index.names = ['Layer', 'Unit', 'Period', 'Time']

    units_districts = district.UnitsOfDistrict
    district_l_u = []
    for l, units in district.UnitsOfLayer.items():
        [district_l_u.append((l, unit)) for unit in units if unit in units_districts]
    df_Unit_t = df_Unit_t.reset_index(level=['Period', 'Time']).loc[district_l_u, :]
    df_Results["df_Unit_t"] = df_Unit_t.reset_index().set_index(['Layer', 'Unit', 'Period', 'Time']).sort_index()

    # df_lca
    if method["save_lca"]:
        LCA_units = get_ampl_data(ampl, 'lca_units', multi_index=True)
        LCA_units = LCA_units.stack().unstack(level=0).droplevel(level=1)
        df_Results["df_lca_Units"] = LCA_units

        LCA_tot = get_ampl_data(ampl, 'lca_tot')
        LCA_tot = LCA_tot.stack().unstack(level=0)
        LCA_tot.index = ["Network"]
        LCA_tot_house = get_ampl_data(ampl, 'lca_tot_house', multi_index=True)
        LCA_tot_house = LCA_tot_house.stack().unstack(level=0).droplevel(1)
        df_Results["df_lca_Performance"] = pd.concat([LCA_tot_house, LCA_tot], axis=0)
        df_Results["df_lca_Performance"].index.names = ['Hub']

        LCA_op = get_ampl_data(ampl, 'lca_op', multi_index=True)
        LCA_op = LCA_op.stack().unstack(level=0).droplevel(level=1)
        df_Results["df_lca_operation"] = LCA_op

    if method["actors_cost"]:
        df1 = get_ampl_data(ampl, 'Cost_demand_district', multi_index=True).groupby(level=(0,2)).sum()
        df2 = get_ampl_data(ampl, 'Cost_supply_district', multi_index=True).groupby(level=(0,2)).sum()
        df3 = get_ampl_data(ampl, 'Cost_self_consumption', multi_index=True).groupby(level=1).sum()
        df3 = pd.concat({'Electricity': df3})
        df_Results["df_Actors_tariff"] = pd.concat([df1, df2, df3], axis=1)

        df_Results["df_Actors"] = get_ampl_data(ampl, 'objective_functions')

        df1 = get_ampl_data(ampl, 'C_op_renters_to_utility')
        df2 = get_ampl_data(ampl, 'C_op_renters_to_owners')
        df3 = get_ampl_data(ampl, 'C_op_utility_to_owners')
        df4 = get_ampl_data(ampl, 'Costs_House_inv')
        df4.columns = ["owner_inv"]
        df5 = get_ampl_data(ampl, 'owner_portfolio')
        df_Actors = pd.concat([df1, df2, df3, df4, df5], axis=1)
        df_6 = df_Actors.sum(axis=0).to_frame().T.set_index(pd.Index(["Network"]))
        df_Actors = pd.concat([df_Actors, df_6], axis=0)
        df_Results["df_District"] = pd.concat([df_Results["df_District"], df_Actors], axis=1)
        df_Results["df_District"].loc["Network", "Objective"] = ampl.getObjective("TOTEX_bui").getValues().toList()[0]

    return df_Results

def get_ampl_data(ampl, ampl_name, multi_index=False):
    # AMPl data in AMPLPY Dataframe
    df = ampl.getData(ampl_name)
    # transform to Pandas Dataframe
    df = df.toPandas()
    # Change index from tuple to multi index
    if multi_index:
        df.index = pd.MultiIndex.from_tuples(df.index)

    return df


def get_ampl_dual_values_in_pandas(ampl, ampl_name, multi_index):
    # AMPl data in AMPLPY Dataframe
    df = ampl.getConstraint(ampl_name).getValues().toPandas()
    # Change index from tuple to multi index
    if multi_index:
        df.index = pd.MultiIndex.from_tuples(df.index)

    return df
