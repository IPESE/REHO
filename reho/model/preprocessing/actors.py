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
def generate_renter_expense_max_new(buildings, income=None, limit=False):
    #TODO Change name and be Careful: per person or per household!
    max_rent_pp = 1e7
    renter_expense_max = []
    if limit:
        rent_percentage = pd.read_csv(path_to_rent)
        income_thresholds_rent = rent_percentage["Income"].to_numpy() * 12
        income_percentage_rent = rent_percentage["Percentage"].to_numpy()

        power_params, _ = curve_fit(power_law, income_thresholds_rent, income_percentage_rent)
        max_rent_pp = power_law(income, power_params[0], power_params[1]) * income
    for b in buildings.keys():
        renter_expense_max.append(max_rent_pp * buildings[b]['n_p'])
    return renter_expense_max

def generate_renter_expense_max_old(buildings,parameters):
    # check if risk_factor in parameter
    if 'risk_factor' in parameters and 'renter_expense_max' in parameters:
        if parameters['renter_expense_max'] == [1e7] * len(buildings):
            income_data = pd.read_csv(path_to_income)
            income_thresholds = income_data["Income"].to_numpy()
            population_percentage = income_data["Population"].to_numpy()

            rent_percentage = pd.read_csv(path_to_rent)
            income_thresholds_rent = rent_percentage["Income"].to_numpy() * 12
            income_percentage_rent = rent_percentage["Percentage"].to_numpy()

            # optimize parameters for the income distribution
            params, covariance = curve_fit(dagum_cdf, income_thresholds, population_percentage,
                                           p0=[20000, 1, 1])
            lambda_fit, delta_fit, beta_fit = params
            n_p = [round(building['n_p']) for building in buildings.values()]
            # set the definition of risk
            n_samples = sum(n_p)

            risk_factor = parameters['risk_factor']
            risk_parameters = pd.read_csv(path_to_risk)
            risk_income = risk_parameters.loc[0,'risk_income'] #risk income threshold
            min_income = risk_parameters.loc[0,'min_income_sample'] # owest income


            # sample incomes according to the dagum distribution function
            n_risk = math.ceil(n_samples * risk_factor)

            income_risk_samples = []
            while len(income_risk_samples) < n_risk:
                # Generate a uniform random number in the range of CDF
                uni_risk = np.random.uniform(0, dagum_cdf(risk_income, lambda_fit, delta_fit, beta_fit))
                # Use the inverse CDF to generate the income sample
                income_sample = dagum_inverse_cdf(uni_risk, lambda_fit, delta_fit, beta_fit)
                # Set to 8850 to insure the percentage of rent regression stays below 100%
                if income_sample >= min_income:
                    income_risk_samples.append(income_sample)

            n_unrisk = n_samples - n_risk
            uni_unrisk = np.random.uniform(dagum_cdf(risk_income, lambda_fit, delta_fit, beta_fit), 1, n_unrisk)
            income_unrisk_samples = dagum_inverse_cdf(uni_unrisk, lambda_fit, delta_fit, beta_fit)

            income_samples = np.concatenate((income_risk_samples, income_unrisk_samples))

            # Power law regression of the income-rent proportion
            power_params, _ = curve_fit(power_law, income_thresholds_rent, income_percentage_rent)

            # calculate the maximum rental cost for each
            max_rent_person = []
            for i in range(len(income_samples)):
                rent_percentage = power_law(income_samples[i], power_params[0], power_params[1])
                max_rent_person.append(rent_percentage * income_samples[i])

            # Calculate ERA per person for each building, add a small offset to differentiate duplicates
            ERA_pp = [
                ((value['ERA'] + (idx * 10**-6))  / round(value['n_p']))
                for idx, (key,value) in enumerate(buildings.items())
            ]
            # Expand ERA_pp to one entry per person
            ERA_pp_full = [
                ((value['ERA'] + (idx * 10**-6))  / round(value['n_p']))
                for idx, (key,value) in enumerate(buildings.items())
                for _ in range(round(value['n_p']))
            ]

            for i in range(ERA_pp_full.__len__()):
                if ERA_pp_full[i] < 20:
                    random.shuffle(ERA_pp_full)

            ERA_pp_sorted = sorted(ERA_pp_full)
            max_rent_person_sorted = sorted(max_rent_person)

            # create default dict classified by the different ERA_pp
            area_groups = defaultdict(list)
            for area in ERA_pp_sorted:
                area_groups[area].append(area)

            # map sorted rent expenses to sorted ERA_pp, or randomly map rents if more than one person has the same ERA_pp
            ERA_rent_mapping = {}
            income_index = 0
            for area in ERA_pp_sorted:
                if area not in ERA_rent_mapping:
                    same_incomes = max_rent_person_sorted[income_index: income_index + len(area_groups[area])]
                    random.shuffle(same_incomes)

                    ERA_rent_mapping[area] = same_incomes
                    income_index += len(area_groups[area])

            # aggregate individual rental expenditures to the building level
            df = pd.DataFrame.from_dict(buildings, orient='index')
            df.reset_index(inplace=True)
            df.rename(columns={'index': 'Building'}, inplace=True)

            max_rent_building = []
            for i in range(len(ERA_rent_mapping)):
                max_rent_building.append(0)
                n_p = round(df['n_p'][i])
                for j in range(1, n_p + 1):
                    if ERA_pp[i] in ERA_rent_mapping:
                        select_income = random.choice(ERA_rent_mapping[ERA_pp[i]])
                        max_rent_building[i] += select_income
                        ERA_rent_mapping[ERA_pp[i]].remove(select_income)

                        if not ERA_rent_mapping[ERA_pp[i]]:
                            del ERA_rent_mapping[ERA_pp[i]]
            return max_rent_building
        else:
            return parameters['renter_expense_max']
    else:
        return [1e7] * len(buildings)

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

def get_actor_parameters(result, Scn_ID, Pareto_ID, iter = 0, h = str):
    params = {}
    for dual_variable in ['nu_renters','nu_utility', 'nu_owner']:
        dual_value = result[Scn_ID][Pareto_ID][iter - 1]['df_Actors_dual'][dual_variable]
        if dual_variable == 'nu_utility':
            params[dual_variable] = dual_value.dropna()[0]
        else:
            params[dual_variable] = dual_value[h]

    C_rent_fix = result[Scn_ID][Pareto_ID][iter - 1]['df_District']['C_rent_fix']
    params['C_rent_fix'] = C_rent_fix[h]

    owner_subsidies = result[Scn_ID][Pareto_ID][iter - 1]['df_District']['owner_subsidies']
    renter_subsidies = result[Scn_ID][Pareto_ID][iter - 1]['df_District']['renter_subsidies']
    params['owner_subsidies'] = owner_subsidies[h]
    params['renter_subsidies'] = renter_subsidies[h]


    lambdas = result[Scn_ID][Pareto_ID][iter - 1]["df_DW"]['lambda']
    df_sc_f = result[Scn_ID][Pareto_ID][iter - 1]["df_Actors_tariff_f"]["Cost_self_consumption"][
        "Electricity"]
    df_sc = df_sc_f * lambdas
    cost_self_consumption = df_sc.groupby(level='Hub').sum()
    params['Cost_self_consumption'] = cost_self_consumption[[h]]

    df_cost_supply_f = result[Scn_ID][Pareto_ID][iter - 1]["df_Actors_tariff_f"][
        "Cost_supply_district"]
    df_cost_supply = df_cost_supply_f * lambdas
    cost_supply_district = df_cost_supply.groupby(level=('Hub', 'ResourceBalances')).sum()
    params['Cost_supply_district'] = cost_supply_district[[h]]

    df_cost_demand_f = result[Scn_ID][Pareto_ID][iter - 1]["df_Actors_tariff_f"][
        "Cost_demand_district"]
    df_cost_demand = df_cost_demand_f * lambdas
    cost_demand_district = df_cost_demand.groupby(level=('Hub', 'ResourceBalances')).sum()
    params['Cost_demand_district'] = cost_demand_district[[h]]

    return params

def get_actor_expenses(actor, last_MP_results=None, last_SP_results=None):
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
        rent_fix = last_MP_results['df_District']['C_rent_fix']
        tariff_supply = last_MP_results['df_Actors_tariff']['Cost_supply_district']['Electricity']
        supply = {b: tariff_supply[b] * last_SP_results[b]['df_Grid_t']['Grid_supply']['Electricity'].xs(b, level='Hub').sum()
                  for b in last_SP_results}
        rent_exp = {b: rent_fix[b] + supply[b] + cost_sc[b] for b in last_SP_results}
        return pd.Series(rent_exp)

    elif actor.lower() == "owner":
        total_fix   = last_MP_results['df_District']['C_rent_fix'].sum()
        total_inv   = last_MP_results['df_District']['Costs_inv'].sum()
        tariff_dmd  = last_MP_results['df_Actors_tariff']['Cost_demand_district']['Electricity']
        total_dmd   = sum(
            tariff_dmd[b] * last_SP_results[b]['df_Grid_t']['Grid_demand']['Electricity'].xs(b, level='Hub').sum()
            for b in last_SP_results
        )
        owner_exp = total_fix + cost_sc_series.sum() - total_inv - total_dmd
        return owner_exp

    elif actor.lower() == "utility":
        tariff_supply = last_MP_results['df_Actors_tariff']['Cost_supply_district']['Electricity']
        tariff_dmd    = last_MP_results['df_Actors_tariff']['Cost_demand_district']['Electricity']
        util_exp = sum(
            tariff_supply[b] * last_SP_results[b]['df_Grid_t']['Grid_supply']['Electricity'].xs(b, level='Hub').sum()
            - tariff_dmd[b]    * last_SP_results[b]['df_Grid_t']['Grid_demand']['Electricity'].xs(b, level='Hub').sum()
            for b in last_SP_results
        )
        return util_exp

    else:
        raise ValueError(f"Unknown actor: {actor}")