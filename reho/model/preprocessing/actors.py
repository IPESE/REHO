from reho.paths import *
import pandas as pd
import numpy as np
import sympy as sp
import math
# TODO: add "statsmodels" and "sympy" in to env.
from scipy.optimize import curve_fit

import random

from collections import defaultdict

__doc__ = """
Generate maximum rental values
"""
def generate_renter_expense_max_new(qbuildings, income=None, rent_income_ratio = None):
    #TODO Change name and be Careful: per person or per household!
    renter_expense_max = []
    rent_percentage = pd.read_csv(os.path.join(path_to_actor, 'rent_proportion.csv'))
    income_thresholds_rent = rent_percentage["Income"].to_numpy() * 12
    if rent_income_ratio != None:
        rent_income_ratio =  np.array(rent_income_ratio)
    else:
        rent_income_ratio = rent_percentage["Percentage"].to_numpy()

    power_params, _ = curve_fit(power_law, income_thresholds_rent, rent_income_ratio)
    max_rent_pp = power_law(income, power_params[0], power_params[1]) * income
    for b in qbuildings["buildings_data"].keys():
        renter_expense_max.append(max_rent_pp * qbuildings["buildings_data"][b]['n_p'])
    return np.round(renter_expense_max, 0)

# define dagum function to model income distribution
def dagum_cdf(x, lambda_, delta, beta):
    return (1 + (x / lambda_)**-delta)**(-beta)

def dagum_inverse_cdf(u, lambda_, delta, beta):
    return lambda_ * ((1 / (u**(-1 / beta) - 1)))**(1 / delta)

def dagum_pdf(y, lambda_, delta, beta):
    x = sp.symbols('x')
    function = dagum_cdf(x, lambda_, delta, beta)
    derivative = sp.diff(function, x)
    f_derivative = sp.lambdify(x, derivative, 'numpy')
    return f_derivative(y)

def power_law(x, a, b):
    return (a * x ** b)

def get_actor_parameters(scenario, set_indexed, result, Scn_ID, Pareto_ID, iter = 0, h = str):
    params = {}
    for dual_variable in ['nu_Renters','nu_Utility', 'nu_Owners']:
        dual_value = result[Scn_ID][Pareto_ID][iter - 1]['df_Actors_dual'][dual_variable]
        if dual_variable == 'nu_Utility':
            params[dual_variable] = dual_value.dropna()[0]
        else:
            params[dual_variable] = dual_value[h]

    if scenario["Objective"] == "TOTEX_actor":
        params["nu_" + set_indexed["ActorObjective"][0]] = 1.0

    C_rent_fix = result[Scn_ID][Pareto_ID][iter - 1]['df_District']['C_rent_fix']
    params['C_rent_fix'] = C_rent_fix[h]

    owner_subsidies = result[Scn_ID][Pareto_ID][iter - 1]['df_District']['owner_subsidies']
    renter_subsidies = result[Scn_ID][Pareto_ID][iter - 1]['df_District']['renter_subsidies']
    params['owner_subsidies'] = owner_subsidies[h]
    params['renter_subsidies'] = renter_subsidies[h]

    lambdas = result[Scn_ID][Pareto_ID][iter - 1]["df_DW"]['lambda']
    df_sc_f = result[Scn_ID][Pareto_ID][iter - 1]["df_Actors_tariff_f"]["Cost_self_consumption"]["Electricity"]
    df_sc = df_sc_f * lambdas
    cost_self_consumption = df_sc.groupby(level='Hub').sum()
    params['Cost_self_consumption'] = cost_self_consumption[[h]]

    df_cost_supply_f = result[Scn_ID][Pareto_ID][iter - 1]["df_Actors_tariff_f"]["Cost_supply_district"]
    df_cost_supply = df_cost_supply_f * lambdas
    cost_supply_district = df_cost_supply.groupby(level=('Hub', 'ResourceBalances')).sum()
    params['Cost_supply_district'] = cost_supply_district[[h]]

    df_cost_demand_f = result[Scn_ID][Pareto_ID][iter - 1]["df_Actors_tariff_f"]["Cost_demand_district"]
    df_cost_demand = df_cost_demand_f * lambdas
    cost_demand_district = df_cost_demand.groupby(level=('Hub', 'ResourceBalances')).sum()
    params['Cost_demand_district'] = cost_demand_district[[h]]

    return params

def get_actor_expenses(actor, building, last_MP_results=None, last_SP_results=None):
    last_MP_results = last_MP_results or {}
    last_SP_results = last_SP_results or {}

    # build self-consumption per building
    self_cons = {}
    for b, sp in last_SP_results.items():
        # assume sp['df_Unit_t'] and sp['df_Grid_t'] have MultiIndex: (Layer, Hub, Period, Time)
        prod = sp['df_Unit_t']['Units_supply']['Electricity'].sum()
        grid = sp['df_Grid_t']['Grid_demand']['Electricity'].sum()
        self_cons[b] = prod - grid

    # multiply by cost
    tariff_sc = last_MP_results['df_Actors_tariff']['Cost_self_consumption']['Electricity']
    cost_sc = {b: tariff_sc[b] * sc for b, sc in self_cons.items()}
    cost_sc_series = pd.Series(cost_sc)

    if actor.lower() == "renters":
        renter_expense = last_MP_results['df_District']['renter_expense'][building]
        renter_subsidies = last_MP_results['df_District']['renter_subsidies'][building]
        #rent_fix = last_MP_results['df_District']['C_rent_fix']
        #tariff_supply = last_MP_results['df_Actors_tariff']['Cost_supply_district']['Electricity']
        #supply = {b: tariff_supply[b] * last_SP_results[b]['df_Grid_t']['Grid_supply']['Electricity'].xs(b, level='Hub').sum()
        #         for b in last_SP_results}
        #rent_exp = {b: rent_fix[b] + supply[b] + cost_sc[b] for b in last_SP_results}
        return renter_expense - renter_subsidies

    elif actor.lower() == "owner":
        owner_prof   = last_MP_results['df_District']['owner_profit'][building]
        owner_sub   =  last_MP_results['df_District']['owner_subsidies'][building]
        owner_inv   =  last_MP_results['df_District']['Costs_inv'][building]
        owner_upfront   =  last_MP_results['df_District']['Costs_House_upfront'][building]
        owner_pir_min   = last_MP_results['Samples']['Owner_PIR_min'].iloc[0,0]

        owner_exp = owner_prof + owner_sub - owner_pir_min * (owner_inv + owner_upfront)
        return owner_exp

    elif actor.lower() == "utility":
        tariff_supply = last_MP_results['df_Actors_tariff']['Cost_supply_district']['Electricity'][building]
        tariff_dmd    = last_MP_results['df_Actors_tariff']['Cost_demand_district']['Electricity'][building]
        util_exp = (tariff_supply * last_SP_results[building]['df_Grid_t']['Grid_supply']['Electricity'].xs(building, level='Hub').sum()
                    - tariff_dmd  * last_SP_results[building]['df_Grid_t']['Grid_demand']['Electricity'].xs(building, level='Hub').sum())
        return util_exp

    else:
        raise ValueError(f"Unknown actor: {actor}")