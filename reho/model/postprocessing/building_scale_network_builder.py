import pandas as pd
import numpy as np

__doc__ = """
Manipulates results to have consistency between the building-scale and district-scale optimizations.
"""


def correct_network_values(reho, scn_id=0, pareto_id=0):
    """
    This function is only useful to find KPIs from the district perspective with a building scale optimization.
    It takes results from the reho object and correct df_KPI, df_Annuals and df_Performance.
    """
    df_grid = reho.results[scn_id][pareto_id]["df_Grid_t"].xs(("Electricity", "Network"), level=("Layer", "Hub"))
    df_export, df_import = get_transformer_import_exports(df_grid)
    nb_periods = reho.cluster["Periods"]

    df = reho.results[scn_id][pareto_id]["df_Grid_t"].sort_index()
    df.loc[("Electricity", "Network"), 'Grid_demand'] = df_export['Grid_profile'].values
    df.loc[("Electricity", "Network"), 'Grid_supply'] = df_import['Grid_profile'].values
    reho.results[scn_id][pareto_id]["df_Grid_t"] = df

    df_grid = reho.results[scn_id][pareto_id]["df_Grid_t"]
    df_time = reho.results[scn_id][pareto_id]["df_Time"]
    surface = reho.ERA
    df_unit_t = reho.results[scn_id][pareto_id]["df_Unit_t"]
    df_KPI = reho.results[scn_id][pareto_id]["df_KPIs"]

    OPEX_m2 = return_correct_OPEX(df_grid, df_time, surface)
    SS_SC = correct_SS_SC(df_grid, df_unit_t, df_time, nb_periods)
    GWP = return_BUI_GWPop(df_grid, surface, df_time, df_KPI)
    GM_GU = correct_grid_param(df_grid)
    results = correct_data_in_reho(reho.results[scn_id][pareto_id], OPEX_m2, SS_SC, GWP, GM_GU, surface)
    return results


def get_transformer_import_exports(df_grid):
    typical_profile = df_grid.Grid_demand - df_grid.Grid_supply  # attention! Supply is negative, feed in is positive
    df = pd.DataFrame(typical_profile, columns=['Grid_profile'])
    df_export = df.copy()
    df_import = df.copy()
    df_export[df_export.Grid_profile < 0] = 0
    df_import[df_import.Grid_profile > 0] = 0
    df_import = -df_import
    return df_export, df_import


def return_annual_exports_imports(df_el, df_t):
    df_aim = {}
    df_export = df_el.Grid_demand.mul(df_t.dp, level='Period', axis=0)
    df_import = df_el.Grid_supply.mul(df_t.dp, level='Period', axis=0)
    df_aim['MWh_imp_el'] = df_import.sum() / 1000  # MWh
    df_aim['MWh_exp'] = df_export.sum() / 1000  # MWh
    return df_aim['MWh_imp_el'], df_aim['MWh_exp']


def get_unit_use_annual_profile(df_unit, df_t, unit, nb_periods):
    df_PV = df_unit[df_unit.index.get_level_values('Unit').str.contains(unit)]
    df_PV = df_PV.groupby('Period').sum()
    df_PV = df_PV.mul(df_t.dp, level='Period', axis=0)
    df_PV = df_PV.loc[0:nb_periods].sum()
    return df_PV


def return_correct_OPEX(df_grid, df_time, total_area):
    opex = 0
    for layer in df_grid.groupby(level=[0]).nunique().index:
        df = df_grid.xs((layer, 'Network'), level=('Layer', 'Hub'))
        df_imp, df_exp = return_annual_exports_imports(df, df_time)
        opex = opex + 1000 * (df.Cost_supply.mean() * df_imp - df.Cost_demand.mean() * df_exp)

    OPEX_m2 = {'opex_m2': opex / total_area}
    return OPEX_m2


def correct_grid_param(df_Grid):
    GM_GU = {}
    df_grid = df_Grid.xs(('Electricity', "Network"), level=('Layer', 'Hub'))[:-2]
    uncontrollable_load = df_Grid.xs("Electricity", level="Layer")["Uncontrollable_load"].drop("Network", level="Hub")
    uncontrollable_load = uncontrollable_load.groupby(level=["Period", "Time"]).sum().max()
    GM_GU['GUd'] = np.round(np.max(df_grid['Grid_demand'] - df_grid['Grid_supply']) / uncontrollable_load, 2)
    GM_GU['GUs'] = np.round(np.max(df_grid['Grid_supply'] - df_grid['Grid_demand']) / uncontrollable_load, 2)

    df = df_Grid.xs('Electricity', level=0)[['Grid_demand', 'Grid_supply']].xs("Network", level="Hub", drop_level=False)
    df_max = df.groupby(level=['Hub', 'Period']).max()
    df_mean = df.groupby(level=['Hub', 'Period']).mean().replace(0, 1)  # replace 0 with 1 to avoid div by 0,  profiles >0, in case av = 0- whole profile is 0
    GM = df_max.div(df_mean, level='Hub').max()

    GM_GU['GMd'] = np.round(GM["Grid_demand"], 2)
    GM_GU['GMs'] = np.round(GM["Grid_supply"], 2)

    return GM_GU


def correct_SS_SC(df_grid, df_unit, df_t, nb_periods=10):
    df_PV = get_unit_use_annual_profile(df_unit, df_t, "PV", nb_periods)
    df_cogen = get_unit_use_annual_profile(df_unit, df_t, "Cogeneration", nb_periods)
    onsite_elec = df_cogen.Units_supply + df_PV.Units_supply

    df_el = df_grid.xs(('Electricity', 'Network'), level=('Layer', 'Hub'))
    df_imp, df_exp = return_annual_exports_imports(df_el, df_t)

    df_aim = {'SC': (onsite_elec - df_exp * 1000) / onsite_elec,
              'SS': (onsite_elec - df_exp * 1000) / (onsite_elec - df_exp * 1000 + df_imp * 1000),
              "PVP": df_PV.Units_supply / (df_PV.Units_supply - df_exp * 1000 + df_imp * 1000),
              "MWh_imp_el": df_imp,
              "MWh_exp": df_exp}

    return df_aim


def return_BUI_GWPop(df_grid, surface, df_time, df_KPI):
    df_el = df_grid.xs(('Electricity', 'Network'), level=('Layer', 'Hub'))
    emissions_el_dy = df_el.GWP_supply * df_el.Grid_supply - df_el.GWP_demand * df_el.Grid_demand
    emissions_el_dy = emissions_el_dy.mul(df_time.dp, level='Period', axis=0).sum() / surface
    emissions_el_av = df_el.GWP_supply.mean() * df_el.Grid_supply - df_el.GWP_demand.mean() * df_el.Grid_demand
    emissions_el_av = emissions_el_av.mul(df_time.dp, level='Period', axis=0).sum() / surface

    df_resource = df_grid.xs("Network", level="Hub")
    emissions = df_resource.GWP_supply * df_resource.Grid_supply - df_resource.GWP_demand * df_resource.Grid_demand
    emissions = emissions.mul(df_time.dp, level='Period', axis=0).sum()

    gwp_op_m2 = emissions / surface
    gwp_constr_m2 = df_KPI["gwp_constr_m2"].xs("Network")
    gwp_tot_m2 = gwp_op_m2 + gwp_constr_m2

    df_aim = {'gwp_elec_av': emissions_el_av,
              'gwp_elec_dy': emissions_el_dy,
              'gwp_op_m2': gwp_op_m2,
              'gwp_constr_m2': gwp_constr_m2,
              'gwp_tot_m2': gwp_tot_m2}

    return df_aim


def correct_data_in_reho(results, OPEX_m2, SS_SC, GWP, GM_GU, surface):
    df_KPI = results["df_KPIs"]
    df_KPI.at["Network", "SS"] = SS_SC["SS"]
    df_KPI.at["Network", "SC"] = SS_SC["SC"]
    df_KPI.at["Network", "PVP"] = SS_SC["PVP"]
    df_KPI.at["Network", "opex_m2"] = OPEX_m2["opex_m2"]

    df_KPI.at["Network", "gwp_elec_av"] = GWP["gwp_elec_av"]
    df_KPI.at["Network", "gwp_elec_dy"] = GWP["gwp_elec_dy"]
    df_KPI.at["Network", "gwp_op_m2"] = GWP["gwp_op_m2"]
    df_KPI.at["Network", "gwp_constr_m2"] = GWP["gwp_constr_m2"]
    df_KPI.at["Network", "gwp_tot_m2"] = GWP["gwp_tot_m2"]

    df_KPI.at["Network", "GUd"] = GM_GU["GUd"]
    df_KPI.at["Network", "GUs"] = GM_GU["GUs"]
    df_KPI.at["Network", "GMd"] = GM_GU["GMd"]
    df_KPI.at["Network", "GMs"] = GM_GU["GMs"]
    results["df_KPIs"] = df_KPI

    df_perf = results["df_Performance"]
    df_perf.at["Network", "Costs_op"] = OPEX_m2["opex_m2"] * surface
    df_perf.at["Network", "GWP_op"] = GWP["gwp_op_m2"] * surface

    results["df_Annuals"].at[("Electricity", "Network"), "Demand_MWh"] = SS_SC["MWh_exp"]
    results["df_Annuals"].at[("Electricity", "Network"), "Supply_MWh"] = SS_SC["MWh_imp_el"]

    return results
