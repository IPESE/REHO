import pandas as pd
import numpy as np
import reho.model.preprocessing.emission_matrix_parser as emission
import reho.model.preprocessing.weather as WD


def postcompute_efficiency(df_unit, buildings_data, df_annual, df_annual_network, df_profiles, df_external, df_Time):
    # --------------------------------------------------------------------
    # energy
    # --------------------------------------------------------------------

    demand = df_annual['MWh_el_domestic'] + df_annual['MWh_Qsh'] + df_annual['MWh_Qdhw']
    demand_net = demand.sum()
    supply = df_annual['MWh_imp_el'] - df_annual['MWh_exp'] + df_annual['MWh_resources'] + df_annual['MWh_PV']
    supply_net = df_annual_network['MWh_el_imp'] - df_annual_network['MWh_el_exp'] + df_annual_network['MWh_resources'] + df_annual['MWh_PV'].sum()

    eta_I = demand/supply
    eta_I_net = demand_net/supply_net

    # -----------------------------eta_I including PV
    # annual irradiation density
    irr_p = df_external['I_global'].groupby(level='Period').sum()/1000 # kWh /m2
    irr_a = irr_p.mul(df_Time.dp, axis=0)
    irr_a = irr_a.sum() / 1000  # MWh/m2
    # reference efficiency PV panel - default 0.14 if no value as input

    PV_IRR = pd.DataFrame()
    np_m2_PV = np.array([])
    for i, h in enumerate(buildings_data):
        eff_ref = 0.14
        kWp_PV = df_unit.xs('PV_'+h)['Units_Mult']
        m2_PV = kWp_PV/eff_ref
        np_m2_PV = np.append(np_m2_PV, [m2_PV])

        MWh_IRR = pd.DataFrame([m2_PV*irr_a], columns=['MWh_IRR'], index=[h])
        PV_IRR = pd.concat([PV_IRR, MWh_IRR])
    df_PV_IRR = pd.DataFrame(index=df_annual.index)
    df_PV_IRR['MWh_IRR'] = PV_IRR['MWh_IRR'].values # cheat to get the same index
    df_m2 = pd.DataFrame(index=df_annual.index)
    df_m2['PV'] = np_m2_PV

    supply_PV = df_annual['MWh_imp_el'] - df_annual['MWh_exp'] + df_annual['MWh_resources'] + df_PV_IRR['MWh_IRR'] # bulding
    supply_PV_net = df_annual_network['MWh_el_imp'] - df_annual_network['MWh_el_exp'] + df_annual_network['MWh_resources'] + df_PV_IRR['MWh_IRR'].sum() # network
    eta_Ipv = demand/supply_PV
    eta_Ipv_net = demand_net/supply_PV_net
    # --------------------------------------------------------------------
    # exergy
    # --------------------------------------------------------------------

    LHV_ng = 50.018 /3600 # MJ/kg -> MWh/kg [Favrat book, chapter 11, page 494 (English version)]
    ex_ng = 51.757 /3600 # MJ/kg -> MWh/kg

    Ex_ng = (df_annual['MWh_resources'] / LHV_ng) * ex_ng


    # domestic hot water
    T_dhw = 55 + 273.15
    eta_carnot_dhw = (1 - ((df_external['T_ext'] + 273.15)/(T_dhw+273.15)))
    E_dhw = df_profiles['Q_DHW']*eta_carnot_dhw

    E_dhw_p = E_dhw.groupby(level=['Hub', 'Period']).sum()
    E_dhw_a = E_dhw_p.mul(df_Time.dp, level='Period', axis=0)
    E_dhw_a = E_dhw_a.groupby(level='Hub').sum()/1000


    # space heating
    df_E_sh_a= pd.DataFrame()
    for house in df_profiles.index.unique(level=0):
        eta_carnot_sh = (1 - ((df_external['T_ext'] + 273.15)/(df_profiles['T_in'].xs(house, level=0)+273.15)))

        E_sh = df_profiles['House_Q_heating'].xs(house, level=0)*eta_carnot_sh

        E_sh_p = E_sh.groupby(level='Period').sum()
        E_sh_a = E_sh_p.mul(df_Time.dp, axis=0)
        E_sh_a = E_sh_a.sum()/1000
        df = pd.DataFrame(E_sh_a, index=[house], columns=['E_sh'])
        df_E_sh_a = pd.concat([df_E_sh_a, df])

    df_Exergie = pd.DataFrame(index=df_annual.index)
    df_Exergie['SH'] = df_E_sh_a.values # cheat to get the same index
    df_Exergie['DHW'] = E_dhw_a.values
    exergie_demand = df_annual['MWh_el_domestic'] + df_Exergie['SH'] + df_Exergie['DHW']
    exergie_demand_net = exergie_demand.sum()

    exergie_supply = df_annual['MWh_imp_el'] - df_annual['MWh_exp'] + df_annual['MWh_PV'] + Ex_ng
    exergie_supply_net = df_annual_network['MWh_el_imp'] - df_annual_network['MWh_el_exp'] + df_annual['MWh_PV'].sum() + Ex_ng.sum()

    eta_II = exergie_demand/exergie_supply
    eta_II_net = exergie_demand_net/exergie_supply_net

    # -----------------------------eta_II including PV

    eta_carnot_irr = (1- ((df_external['T_ext'] + 273.15)/(6000)))# Temperature sun 6000k - source: book: McEnvoy: Practical Handbook of Photovoltaics 2nd edition page 64
    E_irr = eta_carnot_irr*df_external['I_global']/1000 # kW/m2
    E_irr_p = E_irr.groupby(level='Period').sum()
    E_irr_a = E_irr_p.mul(df_Time.dp, axis=0)
    E_irr_a = E_irr_a.sum() / 1000 # MWh
    E_irr_a = E_irr_a*df_m2

    exergie_supply_pv = df_annual['MWh_imp_el'] - df_annual['MWh_exp'] + E_irr_a['PV'] + Ex_ng
    exergie_supply_pv_net = df_annual_network['MWh_el_imp'] - df_annual_network['MWh_el_exp'] + E_irr_a['PV'].sum() + Ex_ng.sum()
    eta_IIpv =   exergie_demand/ exergie_supply_pv
    eta_IIpv_net = exergie_demand_net/ exergie_supply_pv_net

    df_eta = pd.concat([eta_I, eta_II, eta_Ipv, eta_IIpv], axis = 1)
    df_eta_net = pd.concat([eta_I_net, eta_II_net, eta_Ipv_net, eta_IIpv_net], axis=1)
    df_eta = pd.concat([df_eta, df_eta_net])
    df_eta.rename(columns={0: 'eta_I', 1: 'eta_II', 2: 'eta_Ipv', 3: 'eta_IIpv'}, inplace=True)

    return df_eta



def postcompute_security_indicators(df_annual,df_annual_network):

    df_SC = df_annual['MWh_SC'].copy()
    df_SC_net = df_annual['MWh_onsite_el'].sum() - df_annual_network['MWh_el_exp']
    df_gen = df_annual['MWh_onsite_el'].copy()

    SS = df_SC/ (df_annual['MWh_imp_el'] + df_SC)
    SS_net = df_SC_net / (df_annual_network['MWh_el_imp'] + df_SC_net)

    # for no generation set SC to 1
    if (df_SC == 0).any():

        df_SC.iloc[df_SC == 0] = 1
        df_SC_net.iloc[df_SC_net == 0] = 1

        if  (df_gen == 0).all():
            SC = df_SC/1
            SC_net =  df_SC_net/1
        else:
            # one building has PV -> district has a SC neq 1
            SC_net = df_SC_net /  df_gen.sum()
            # make sure to set SC 1 for buildings without PV
            df_gen[df_gen == 0] = 1
            SC = df_SC / df_gen
    else:
        SC = df_SC / df_gen
        SC_net = df_SC_net /  df_gen.sum()


    df= pd.concat([SC,SS], axis=1)
    net = pd.concat([SC_net, SS_net], names = [0,1], axis=1)
    net.rename(columns = {'MWh_el_exp':0, 0:1}, inplace=True)
    df = pd.concat([df, net])
    df.rename(columns ={0:'SC',1:'SS'}, inplace = True)
    return df

def postcompute_pv_penetration_curtail(df_annual, df_annual_network):

    PV_gen = df_annual['MWh_PV']
    PV_gen_net = df_annual['MWh_PV'].sum()

    E_dem = df_annual['MWh_onsite_el'] + df_annual['MWh_imp_el'] - df_annual['MWh_exp']
    E_dem_net = df_annual['MWh_onsite_el'].sum() + df_annual_network['MWh_el_imp'] - df_annual_network['MWh_el_exp']

    PVP = PV_gen/E_dem
    PVP_net = PV_gen_net/E_dem_net

    s_PVP = pd.concat([PVP, PVP_net])
    df_PVP = pd.DataFrame(s_PVP, columns=['PVP']) # series to df with column name
    df_PVP = df_PVP

    # PV curtailmnet
    df_PVP = pd.concat([df_PVP, df_annual['PVC']], axis=1)
    df_PVP.at['Network', 'PVC'] = df_annual.PVC.sum()

    PV_gen_and_PVC = (PV_gen.to_list() + [PV_gen_net]) + df_PVP.PVC / 1000
    for i, values in enumerate(df_PVP.PVC):
        if values != 0:
            df_PVP.PVC[i] = df_PVP.PVC[i]/1000 / PV_gen_and_PVC[i] # MWh/MWh

    return df_PVP

def postcompute_annual_revenues(df_profiles, df_profiles_net, df_Time):

    RE_SC = df_profiles['Cost_supply'] * df_profiles['SC']
    RE_feedin = df_profiles['Cost_demand'] * df_profiles['Grid_demand']

    # # # Network we count PV consumed by neighbour as SC - assumption RE_gen - Feed-in = RE_SC !! Attention not for priceprofiles
    Cost_supply = df_profiles_net.xs('Electricity', level=0)['Cost_supply']
    Cost_demand = df_profiles_net.xs('Electricity', level=0)['Cost_demand']
    RE_gen_net = df_profiles['onsite_el'].groupby(level=['Period', 'Time']).sum()
    RE_feedin_net = df_profiles_net.xs('Electricity', level=0)['Grid_demand']

    RE_SC_net = Cost_supply*(RE_gen_net-RE_feedin_net)
    RE_feedin_net = Cost_demand*RE_feedin_net

    RE_t = RE_SC + RE_feedin
    RE_t_net = RE_SC_net+RE_feedin_net
    RE_t_net = pd.concat([RE_t_net], keys=['Network'], names=['Hub']) # add network
    RE_t = pd.concat([RE_t, RE_t_net])

    RE_p = RE_t.groupby(level=['Hub', 'Period']).sum()
    RE_a = RE_p.mul(df_Time.dp, axis=0)
    RE_a = RE_a.groupby('Hub', level=0).sum()
    df_AR = pd.DataFrame(RE_a, columns=['AR'])

    return df_AR

def postcompute_levelized_cost_electricity( df_unit,df_annual, df_profiles,  df_Time, infrastructure):

    df_LCoE = pd.DataFrame()

    C_PV_net = 0
    C_BAT_net = 0

    # LCOE1----------------------------------------------------------------------
    C_el1 = -df_profiles['Cost_demand']*df_profiles['Grid_demand'] - df_profiles['Cost_supply'] * df_profiles['SC']
    C_el1 = C_el1.groupby(level=['Hub', 'Period']).sum()
    C_el1 = C_el1.mul(df_Time.dp, axis=0)
    C_el1 = C_el1.groupby(level=['Hub']).sum()

    # LCOE2----------------------------------------------------------------------
    C_el2 = - df_profiles['Cost_supply']*df_profiles['Grid_supply'] + df_profiles['Cost_demand'] * df_profiles['Grid_demand']

    C_el2 = C_el2.groupby(level=['Hub', 'Period']).sum()
    C_el2 = C_el2.mul(df_Time.dp, axis=0)
    C_el2 = C_el2.groupby(level=['Hub']).sum()

    # iterate for each building
    for house in infrastructure.House:
        PVPanel_name = 'default'
        Battery_name = 'default'
        for unit in infrastructure.UnitsOfHouse[house]:
            if unit in infrastructure.UnitsOfType['PV']:
                PVPanel_name = unit
            if  unit in infrastructure.UnitsOfType['Battery']:
                Battery_name = unit
        C_PV = df_unit.xs(PVPanel_name)['Costs_Unit_inv']
        C_BAT = df_unit.xs(Battery_name)['Costs_Unit_inv']

        C_PV_net = C_PV_net +C_PV # network cost
        C_BAT_net = C_BAT_net + C_BAT # network cost battery

        kWh_PV = df_annual.loc[house]['MWh_PV'] *1000
        kWh_house = df_annual.loc[house]['MWh_el_domestic'] *1000

        if kWh_PV == 0:
            LCoE1 = np.nan
        else:
            LCoE1 = (C_PV + C_BAT + C_el1[house] )/ (kWh_PV) # CHF/kWh
        LCoE2 = (C_PV +C_BAT +C_el2[house])/(kWh_house)

        df_LCoE.at[house, 'LCoE1'] = LCoE1
        df_LCoE.at[house, 'LCoE2'] = LCoE2

    # KPI on network
    kWh_house_net = df_annual.MWh_el_domestic.sum() *1000
    kWh_PV_net = df_annual.MWh_PV.sum() *1000

    if kWh_PV_net== 0:
        LCoE1_net = np.nan
    else:
        LCoE1_net = (C_PV_net +C_BAT_net + C_el1.sum()) / kWh_PV_net
    LCoE2_net = (C_PV_net +C_BAT_net + C_el2.sum()) / kWh_house_net

    df_LCoE.at['Network', 'LCoE1'] = LCoE1_net
    df_LCoE.at['Network', 'LCoE2'] = LCoE2_net

    return df_LCoE

def postcompute_average_emission(df_annual, df_annual_net, df_profiles, df_profiles_net,  df_Time, cluster, infrastructure):
    # --------------------------------------------------------------------
    # emission
    # --------------------------------------------------------------------

    em_supply_dy = df_profiles_net.GWP_supply.xs('Electricity')
    em_demand_dy = df_profiles_net.GWP_demand.xs('Electricity')

    # Buildings
    em_el_av_bui = em_supply_dy.mean() * df_profiles.Grid_supply - em_demand_dy.mean() * df_profiles.Grid_demand
    em_el_av_bui = em_el_av_bui.mul(df_Time.dp, level='Period', axis=0).groupby('Hub').sum()

    em_el_dy_bui = pd.Series(dtype='float')
    for h in df_annual.index.get_level_values(level='Hub'):
        em_el_dy_bui_h = em_supply_dy * df_profiles.Grid_supply.xs(h, level='Hub') - em_demand_dy * df_profiles.Grid_demand.xs(h, level='Hub')
        em_el_dy_bui_h = em_el_dy_bui_h.mul(df_Time.dp, level='Period', axis=0).sum()
        em_el_dy_bui_h = pd.DataFrame([em_el_dy_bui_h], index=[h])
        em_el_dy_bui = pd.concat([em_el_dy_bui, em_el_dy_bui_h])

    # Network
    em_el_av_net = em_supply_dy.mean() * df_profiles_net.Grid_supply.xs('Electricity') - em_demand_dy.mean() * df_profiles_net.Grid_demand.xs('Electricity')
    em_el_av_net = em_el_av_net.mul(df_Time.dp, level='Period', axis=0).sum()
    em_el_av_net = pd.DataFrame([em_el_av_net], index=['Network'])

    em_el_dy_net = em_supply_dy * df_profiles_net.Grid_supply.xs('Electricity') - em_demand_dy * df_profiles_net.Grid_demand.xs('Electricity')
    em_el_dy_net = em_el_dy_net.mul(df_Time.dp, level='Period', axis=0).sum()
    em_el_dy_net = pd.DataFrame([em_el_dy_net], index=['Network'])

    em_el_dy = pd.concat([em_el_dy_bui, em_el_dy_net])
    em_el_av = pd.concat([em_el_av_bui, em_el_av_net])


    # --------------------------------------------------------------------
    # Renewable energy share
    # --------------------------------------------------------------------
    df_el_net = df_profiles_net.xs('Electricity', level = 0)

    File_ID = WD.get_cluster_file_ID(cluster)
    res_profile = emission.select_typical_emission_profiles(df_Time, File_ID, 'method 1')
    res_av = emission.find_average_value('CH', 'method 1')
    s_RES_dy = pd.Series(dtype='float')
    s_RES_av = pd.Series(dtype='float')

    for h in df_annual.index.get_level_values(level='Hub'):
        res_e = res_profile['GWP_supply'].values * df_profiles.Grid_supply.xs(h, level='Hub', drop_level=False)
        res_e = res_e.groupby(level=['Hub', 'Period']).sum()
        res_e = res_e.mul(df_Time.dp, axis=0).groupby(level='Hub').sum()/1000 # annual emission from elec with dy profiles ton/year
        res_av.index = res_e.index

        df_h = df_annual.loc[h]
        RES_dy = (df_h['MWh_SC'] + res_e) / (df_h['MWh_SC'] + df_h['MWh_resources'] + df_h['MWh_imp_el'])
        RES_av = (df_h['MWh_SC'] + res_av * df_h['MWh_imp_el']) / (df_h['MWh_SC'] + df_h['MWh_resources'] + df_h['MWh_imp_el'])

        RES_dy = RES_dy
        RES_av = RES_av
        s_RES_dy = pd.concat([s_RES_dy, RES_dy])
        s_RES_av = pd.concat([s_RES_av, RES_av])

    # Network
    res_e = res_profile['GWP_supply'].values * df_el_net.Grid_supply
    res_e = res_e.groupby(level=['Period']).sum()
    res_e = res_e.mul(df_Time.dp, axis=0).sum() / 1000
    RES_dy = (df_annual['MWh_SC'].sum() + res_e) / (df_annual['MWh_SC'].sum() + df_annual_net['MWh_resources'] + df_annual_net['MWh_el_imp'])
    RES_av = (df_annual['MWh_SC'].sum() + res_av.values[0] * df_annual_net['MWh_el_imp']) / (df_annual['MWh_SC'].sum() + df_annual_net['MWh_resources'] + df_annual_net['MWh_el_imp'])

    RES_dy = RES_dy
    RES_av = pd.DataFrame(RES_av)
    s_RES_dy = pd.concat([s_RES_dy, RES_dy])
    s_RES_av = pd.concat([s_RES_av, RES_av])

    df = pd.concat([em_el_av, em_el_dy, s_RES_dy, s_RES_av], axis=1)
    df.columns = ['gwp_elec_av', 'gwp_elec_dy', 'RES_dy', 'RES_av']
    return df


def postcompute_Grid_param(df_Grid):

    df = df_Grid.xs('Electricity', level=0)[['Grid_demand', 'Grid_supply']]
    df_max = df.groupby(level=['Hub', 'Period']).max()
    df_mean = df.groupby(level=['Hub', 'Period']).mean().replace(0, 1) # replace 0 with 1 to avoid div by 0,  profiles >0, in case av = 0- whole profile is 0
    GM = df_max.div(df_mean, level='Hub').groupby('Hub').max()

    GM = GM.rename(columns={ 'Grid_supply': 'GMs', 'Grid_demand':'GMd'})
    GM['GUs'] = GM.GMs
    GM['GUd'] = GM.GMd
    uncontrollable_load = df_Grid.xs('Electricity', level='Layer')['Uncontrollable_load'].drop('Network', level='Hub')
    uncontrollable_load = uncontrollable_load.groupby(level=['Period', 'Time']).sum().max()
    for h in GM.index:
        GUs = df_Grid.xs(('Electricity', h),level=('Layer', 'Hub'))['Grid_supply'][:-2].max()/uncontrollable_load
        GUd = df_Grid.xs(('Electricity', h),level=('Layer', 'Hub'))['Grid_demand'][:-2].max()/uncontrollable_load
        GM.at[h,'GUs'] = GUs
        GM.at[h, 'GUd'] = GUd

    return GM.round(2)

def postcompute_annual_COP(df_annuals, infrastructure):

    df = pd.DataFrame(index=['Network'])
    total_heat_network = 0
    total_HP_el = 0
    for HP in infrastructure.UnitsOfType['HeatPump']:
        # get values for each AW in the district
        df_annuals_HP = df_annuals.xs(HP, level='Hub')

        df_el_all = df_annuals_HP.xs('Electricity')
        df_heat_all = df_annuals_HP.drop('Electricity').sum()
        if df_el_all.Demand_MWh == 0:
            COP = np.nan
        else:
            COP = df_heat_all['Supply_MWh'] / df_el_all.Demand_MWh

        # assign to house and df
        for key, units in infrastructure.UnitsOfHouse.items():
            if HP in units and key not in df.index:
                df.at[key, 'COP'] = COP

        # sum for network average
        total_heat_network = total_heat_network + df_heat_all['Supply_MWh']
        total_HP_el = total_HP_el+df_el_all.Demand_MWh
    if total_HP_el == 0:
        df.at['Network', 'COP'] = np.nan
    else:
        df.at['Network', 'COP'] = total_heat_network/total_HP_el

    return df


def build_df_profiles_house(df_Results, infrastructure):
    """
    Build hourly profiles for demand and consumption of units and buildings
    """

    df_PV = units_power_profiles_per_building(df_Results, infrastructure, 'PV')
    df_BAT = units_power_profiles_per_building(df_Results, infrastructure, 'Battery')

    df_grid_profile = df_Results["df_Grid_t"].xs(('Electricity'), level=('Layer'))

    df_profiles_house = df_grid_profile.drop('Network', level='Hub')
    df_profiles_house['PV'] = df_PV['Units_supply']
    df_profiles_house['PVC'] = df_PV['Units_curtailment']
    df_profiles_house['BA_in'] = df_BAT['Units_demand']
    df_profiles_house['BA_out'] = df_BAT['Units_supply']
    df_profiles_house['House_Q_heating'] = df_Results["df_Buildings_t"]['House_Q_heating']
    df_profiles_house['T_in'] = df_Results["df_Buildings_t"]['T_in']
    df_profiles_house['Q_DHW'] = df_Results["df_Buildings_t"]['House_Q_DHW']

    if 'NG_Cogeneration' in infrastructure.UnitTypes:
        df_NG_Cogeneration = units_power_profiles_per_building(df_Results, infrastructure, 'NG_Cogeneration')
        df_profiles_house['NG_Cogeneration'] = df_NG_Cogeneration['Units_supply']
        df_profiles_house['onsite_el'] = df_profiles_house['PV'] + df_profiles_house['NG_Cogeneration']
        PV_sell = df_profiles_house['Grid_demand'] - df_profiles_house['NG_Cogeneration']
        PV_sell[PV_sell < 0] = 0
        df_profiles_house['PV_SC'] = df_profiles_house['PV'] - PV_sell
    else:
        df_profiles_house['onsite_el'] = df_profiles_house['PV']
        df_profiles_house['PV_SC'] = df_profiles_house['onsite_el'] - df_profiles_house['Grid_demand']
    df_profiles_house['SC'] = df_profiles_house['onsite_el'] - df_profiles_house['Grid_demand']

    return df_profiles_house


def build_df_annual(df_Results, df_profiles_house, infrastructure, df_Time):
    """
    Transform profiles to annual values, convert to MWh and insert additional values (costs, net resource exchanges)
    Outputs: Annual parameter for each building and for the network
    """

    df_period = df_profiles_house.groupby(level=['Hub', 'Period']).sum()  # 'daily' sum
    df_period = df_period.mul(df_Time.dp, level='Period', axis=0)  # multiply by frequency

    df_annual = df_period.groupby(level=['Hub']).sum()  # annuals
    df_annual['Cost_supply'] = df_annual['Cost_supply'] / 8760  # average price
    df_annual['Cost_demand'] = df_annual['Cost_demand'] / 8760

    # pass from kWh to MWh
    keys = ['Grid_supply', 'Grid_demand', 'PV', 'Q_DHW', 'House_Q_heating', 'BA_out', 'BA_in', 'onsite_el', 'SC', 'PV_SC']
    for key in keys:
        df_annual[key] = df_annual[key].div(1000)

    df_annual = df_annual.drop(columns=['T_in', 'GWP_demand', 'GWP_supply'])

    df_annual.rename(columns={'BA_out': 'MWh_BAT_out', 'BA_in': 'MWh_BAT_in',
                              'onsite_el': 'MWh_onsite_el', 'PV': 'MWh_PV', 'Grid_demand': 'MWh_exp', 'Grid_supply': 'MWh_imp_el',
                              'House_Q_heating': 'MWh_Qsh', 'Q_DHW': 'MWh_Qdhw', 'SC': 'MWh_SC', 'PV_SC': 'MWh_PV_SC'}, inplace=True)

    # get Annual values from ampl results
    df_power = df_Results["df_Annuals"].xs('Electricity', level=0)
    df_Building_el = df_power.loc[df_annual.index]  # index: all houses
    df_annual['MWh_el_domestic'] = df_Building_el['Demand_MWh']

    df_annual_network = pd.DataFrame(index=['Network'])
    for resource in infrastructure.grids.keys():
        if resource == 'Electricity':
            df_annual_network['MWh_el_exp'] = df_power.xs('Network')['Demand_MWh']
            df_annual_network['MWh_el_imp'] = df_power.xs('Network')['Supply_MWh']
        else:
            df_resource = df_Results["df_Annuals"].xs(resource, level=0)
            df_annual_network['MWh_' + resource] = df_resource.xs('Network')['Supply_MWh']
            df_resource_houses = split_units_to_buildings(infrastructure, df_resource, 'Demand_MWh')
            df_annual['MWh_' + resource] = df_resource_houses

    resource_list = list(x for x in infrastructure.grids if x not in ['Electricity'])  # all resources except electricity
    df_annual['MWh_resources'] = sum([df_annual['MWh_' + x] for x in resource_list])
    df_annual_network['MWh_resources'] = sum([df_annual_network['MWh_' + x] for x in resource_list])


    df_Building_performance = df_Results["df_Performance"].loc[df_annual.index]
    df_annual['Costs_House_op'] = df_Building_performance['Costs_op']
    df_annual['Costs_House_inv'] = df_Building_performance['Costs_inv']
    df_annual['Costs_House_rep'] = df_Building_performance['Costs_rep']

    for key in ['Costs_op', 'Costs_inv', 'Costs_rep']:
        df_annual_network[key] = df_Results["df_Performance"].iloc[0][key]

    return df_annual, df_annual_network


def calculate_KPIs(df_Results, infrastructure, buildings_data, cluster):
    df_profiles = build_df_profiles_house(df_Results, infrastructure)
    df_profiles_network = df_Results["df_Grid_t"].xs('Network', level='Hub').copy()

    df_Time = df_Results["df_Time"]
    df_Time.dp.iloc[-1] = 0  # exclude extreme periods
    df_Time.dp.iloc[-2] = 0

    # ------------------------------------------------------------------------------------------------------
    # Construct Economics dataframe
    # ------------------------------------------------------------------------------------------------------
    df_Economics = build_df_Economics(df_Results, df_profiles)
    df_annual, df_annual_network = build_df_annual(df_Results, df_profiles, infrastructure, df_Time)

    # ------------------------------------------------------------------------------------------------------
    # Construct KPI-Dataframe
    # ------------------------------------------------------------------------------------------------------
    df_KPI = pd.DataFrame()
    # get heated surface for normalization
    df_hsA = pd.DataFrame()
    for h in buildings_data:
        df = pd.DataFrame([buildings_data[h]['ERA']], columns=['ERA'], index=[h])
        df_hsA = pd.concat([df_hsA, df])
    network = pd.DataFrame(df_hsA.sum().values, index=['Network'], columns=['ERA'])
    df_hsA = pd.concat([df_hsA, network])

    # ------------------------------------------------------------------------------------------------------
    # Costs
    # ------------------------------------------------------------------------------------------------------
    df_cost = df_Results["df_Performance"][['Costs_op', 'Costs_inv', 'Costs_rep', 'Costs_ft']]
    df_cost = df_cost.rename(columns={'Costs_op': 'opex_m2', 'Costs_inv': 'capex_m2', 'Costs_rep': 'cost_rep_m2', 'Costs_ft': 'cost_ft_m2'})
    df_KPI = pd.concat([df_KPI, df_cost.div(df_hsA.ERA, axis=0)], axis=1)  # [CHF/m2/yr]

    df_AR = postcompute_annual_revenues(df_profiles, df_profiles_network, df_Time)
    df_KPI = pd.concat([df_KPI, df_AR.div(df_hsA.ERA, axis=0)], axis=1)

    df_LCoE = postcompute_levelized_cost_electricity(df_Results["df_Unit"], df_annual, df_profiles, df_Time, infrastructure)
    df_KPI['LCoE1'] = df_LCoE.LCoE1
    df_KPI['LCoE2'] = df_LCoE.LCoE2

    # ------------------------------------------------------------------------------------------------------
    # PV related KPIs
    # ------------------------------------------------------------------------------------------------------
    df_SC = postcompute_security_indicators(df_annual, df_annual_network)
    df_KPI = pd.concat([df_KPI, df_SC], axis=1)  # SC  SS

    df_PVP = postcompute_pv_penetration_curtail(df_annual, df_annual_network)
    df_KPI = pd.concat([df_KPI, df_PVP], axis=1)  # PVP [-] PVC [MWh]

    df_GM = postcompute_Grid_param(df_Results["df_Grid_t"])
    df_KPI = pd.concat([df_KPI, df_GM], axis=1)  # GMd GMs GUd GUs

    # ------------------------------------------------------------------------------------------------------
    # GWP
    # ------------------------------------------------------------------------------------------------------
    df_KPI['gwp_op_m2'] = df_Results["df_Performance"]['GWP_op'].div(df_hsA.ERA)
    df_KPI['gwp_constr_m2'] = df_Results["df_Performance"]['GWP_constr'].div(df_hsA.ERA)
    df_KPI['gwp_tot_m2'] = df_KPI['gwp_op_m2'] + df_KPI['gwp_constr_m2']  # [kgCO2-eq/m2/yr]

    df_G_RES = postcompute_average_emission(df_annual, df_annual_network, df_profiles, df_profiles_network, df_Time, cluster, infrastructure)
    df_KPI = pd.concat([df_KPI, df_G_RES[['gwp_elec_av', 'gwp_elec_dy']].div(df_hsA.ERA, axis=0)], axis=1)
    df_KPI = df_KPI.rename(columns={'gwp_elec_av': 'gwp_elec_av_m2', 'gwp_elec_dy': 'gwp_elec_dy_m2'})  # gwp_elec_av_m2    gwp_elec_dy_m2
    df_KPI = pd.concat([df_KPI, df_G_RES[['RES_dy', 'RES_av']]], axis=1)  # RES_dy    RES_av

    # ------------------------------------------------------------------------------------------------------
    # Technical KPIs
    # ------------------------------------------------------------------------------------------------------
    df_eta = postcompute_efficiency(df_Results["df_Unit"], buildings_data, df_annual, df_annual_network, df_profiles, df_Results["df_External"], df_Time)
    df_KPI = pd.concat([df_KPI, df_eta], axis=1)  # eta_I    eta_II   eta_Ipv  eta_IIpv

    if 'HeatPump' in infrastructure.UnitsOfType:  # Check if HP DHN is used
        df_COP = postcompute_annual_COP(df_Results["df_Annuals"], infrastructure)
        df_KPI = pd.concat([df_KPI, df_COP], axis=1)

    df_KPI.index.names = ['Hub']

    return df_KPI, df_Economics


def split_units_to_buildings(infrastructure, df, aim):
    df_h = pd.DataFrame(index=infrastructure.House, columns=[aim])
    for h in infrastructure.House:
        value = np.array([])
        for idx in df.index:
            unit = idx.split('_')
            if h in unit:
                value = np.append(value, df.loc[idx, aim])
        df_h.loc[h, aim] = value.sum()
    return df_h


def units_power_profiles_per_building(df_Results, infrastructure, unittype):
    df = pd.DataFrame()
    for house in infrastructure.House:
        for unit in infrastructure.UnitsOfType[unittype]:
            if unit in infrastructure.UnitsOfHouse[house]:
                df_profile = df_Results["df_Unit_t"].xs(('Electricity', unit), level=('Layer', 'Unit'))
                df_profile = pd.concat([df_profile], keys=[(house, unit)], names=['Hub', 'Unit'])
                df = pd.concat([df, df_profile])
    df = df.groupby(level=['Hub', 'Period', 'Time']).sum()
    return df


def remove_building_from_index(df):
    def filter_building_str(str):
        str_split = str.split("_")
        if len(str_split) > 2:
            new_idx = "_".join(str.split("_", 2)[:2])
        else:
            new_idx = str_split[0]
        hub = str_split[-1]
        return new_idx, hub

    new_index = []
    index_frame = df.index.to_frame()
    if 'Unit' in index_frame.columns:
        for idx in index_frame['Unit']:
            new_index.append(filter_building_str(idx))
        new_index = pd.DataFrame.from_records(new_index, columns=['Unit', 'Hub'])
        index_frame[['Unit', 'Hub']] = new_index.values
    elif 'Hub' in index_frame.columns:
        for idx in index_frame['Hub']:
            new_index.append(filter_building_str(idx)[0])
        index_frame['Hub'] = new_index

    index_modified = pd.MultiIndex.from_frame(index_frame)

    return df.set_index(index_modified)


def build_df_Economics(df_Results, df_profiles):
    
    period_duration = df_Results["df_Time"].dp
    df_unit_t = remove_building_from_index(df_Results["df_Unit_t"])
    df_unit = remove_building_from_index(df_Results["df_Unit"])
    df_grid_t = df_Results["df_Grid_t"]

    col_to_calc = ['PV', 'PVC', 'BA_out', 'onsite_el', 'PV_SC', 'SC']
    # Avoided from profiles
    df_cost = pd.DataFrame()
    df_impact = pd.DataFrame()
    for col in col_to_calc:
        df_cost['avoided_' + col] = df_profiles.loc[:, col] * df_profiles.loc[:, 'Cost_demand']
        df_impact['avoided_' + col] = df_profiles.loc[:, col] * df_profiles.loc[:, 'GWP_demand']

    df_cost = df_cost.mul(period_duration, level='Period', axis=0).groupby(level='Hub').sum()
    df_impact = df_impact.mul(period_duration, level='Period', axis=0).groupby(level='Hub').sum()

    # Grid
    df_grid_cost = pd.DataFrame()
    df_grid_impact = pd.DataFrame()
    df_grid_cost['price_demand'] = df_profiles.Cost_demand * df_grid_t.Grid_demand
    df_grid_cost['price_supply'] = df_profiles.Cost_supply * df_grid_t.Grid_supply
    df_grid_impact['impact_demand'] = df_profiles.GWP_demand * df_grid_t.Grid_demand
    df_grid_impact['impact_supply'] = df_profiles.GWP_supply * df_grid_t.Grid_supply

    curtailment = df_unit_t['Units_curtailment'].groupby(['Layer', 'Period', 'Time', 'Hub']).sum()
    df_grid_cost['price_curtailment'] = curtailment * df_grid_t.Cost_demand
    df_grid_impact['impact_curtailment'] = curtailment * df_grid_t.GWP_demand

    df_grid_cost = df_grid_cost.mul(period_duration, level='Period', axis=0).groupby(level=['Hub', 'Layer']).sum()
    df_grid_impact = df_grid_impact.mul(period_duration, level='Period', axis=0).groupby(level=['Hub', 'Layer']).sum()

    # Unit
    df_unit = df_unit.groupby(level=['Unit', 'Hub']).sum()
    df_unit_cost = df_unit.reset_index().pivot(index='Hub', values='Costs_Unit_inv', columns='Unit')
    df_unit_impact = df_unit.reset_index().pivot(index='Hub', values='GWP_Unit_constr', columns='Unit')

    hubs = df_unit_cost.index.tolist()

    dict_to_keep = {'demand': 'revenues_', 'supply': 'costs_', 'curtailment': 'curtailment_'}
    idx = pd.Index(hubs, name='Hub')
    pivot_df_grid_cost = pd.DataFrame(index=idx)
    pivot_df_grid_impact = pd.DataFrame(index=idx)
    for col, val in dict_to_keep.items():
        cost = df_grid_cost.reset_index().pivot(index='Hub', columns='Layer', values='price_' + col)
        impact = df_grid_impact.reset_index().pivot(index='Hub', columns='Layer', values='impact_' + col)
        rename_col = {key: val + key for key in cost.columns}
        cost = cost.rename(columns=rename_col)
        impact = impact.rename(columns=rename_col)
        pivot_df_grid_cost = pivot_df_grid_cost.merge(cost, on='Hub')
        pivot_df_grid_impact = pivot_df_grid_impact.merge(impact, on='Hub')

    # Final dfs
    df_op = pd.concat([df_cost.merge(pivot_df_grid_cost, on='Hub')], keys=['costs'], names=['Perf_type'])
    df_op_impact = pd.concat([df_impact.merge(pivot_df_grid_impact, on='Hub')], keys=['impact'], names=['Perf_type'])
    df_op = pd.concat([df_op, df_op_impact])
    df_inv = pd.concat([df_unit_cost, df_unit_impact], keys=['costs', 'impact'], names=['Perf_type'])

    df_eco = pd.concat([df_op, df_inv], keys=['operation', 'investment'], names=['Category'], axis=1)

    return df_eco
