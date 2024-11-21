from reho.paths import *
import pandas as pd
import numpy as np
import sympy as sp
# TODO: add "statsmodels" and "sympy" in to env.
import statsmodels.api as sm
from scipy.optimize import curve_fit

import random

from collections import defaultdict

__doc__ = """
Generate maximum rental values
"""
# TODO: The risk factor need to be a dictionary with 4 columns

def generate_renter_expense_max(buildings,parameters):
    # check if risk_factor in parameter
    if 'risk_factor' in parameters and 'renter_expense_max' in parameters:
        if parameters['renter_expense_max'] == [1e6] * len(buildings):
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

            # set the definition of risk
            n_samples = sum(building['n_p'] for building in buildings.values())
            # TODO: Activate this code, once the risk factor is implemented, and DEactivate the following one
            # risk_factor = parameters['risk_factor']['SWI_swissSEP_12T']
            risk_factor = parameters['risk_factor']
            # TODO: Validate risk thresholds
            risk_income = 53000

            # sample incomes according to the dagum distribution function
            n_risk = int(n_samples * risk_factor)

            #uni_risk = np.random.uniform(0, dagum_cdf(risk_income, lambda_fit, delta_fit, beta_fit), n_risk)
            #income_risk_samples = dagum_inverse_cdf(uni_risk, lambda_fit, delta_fit, beta_fit)

            income_risk_samples = []
            while len(income_risk_samples) < n_risk:
                # Generate a uniform random number in the range of CDF
                uni_risk = np.random.uniform(0, dagum_cdf(risk_income, lambda_fit, delta_fit, beta_fit))
                # Use the inverse CDF to generate the income sample
                income_sample = dagum_inverse_cdf(uni_risk, lambda_fit, delta_fit, beta_fit)
                # Set to 8850 to insure the percentage of rent regression stayes below 100%
                if income_sample >= 8850:
                    income_risk_samples.append(income_sample)

            n_unrisk = int(n_samples - n_risk)
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

            # get the sorted sequences of available living areas for each
            # in case of same ERA use idx to differenciate
            ERA_pp = [
                ((value['ERA'] + (idx * 10**-6))  / value['n_p'])
                for idx, (key,value) in enumerate(buildings.items())
            ]

            ERA_pp_full = [
                ((value['ERA'] + (idx * 10**-6))  / value['n_p'])
                for idx, (key,value) in enumerate(buildings.items())
                for _ in range(int(value['n_p']))
            ]

            for i in range(ERA_pp_full.__len__()):
                if ERA_pp_full[i] < 20:
                    random.shuffle(ERA_pp_full)

            ERA_pp_sorted = sorted(ERA_pp_full)
            max_rent_person_sorted = sorted(max_rent_person)

            # create defaultdict classified by the different ERA_pp
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
                n_p = int(df['n_p'][i])
                for j in range(1, n_p + 1):
                    if ERA_pp[i] in ERA_rent_mapping:
                        select_income = random.choice(ERA_rent_mapping[ERA_pp[i]])
                        max_rent_building[i] += select_income/2.75
                        ERA_rent_mapping[ERA_pp[i]].remove(select_income)

                        if not ERA_rent_mapping[ERA_pp[i]]:
                            del ERA_rent_mapping[ERA_pp[i]]
            #for index, building in enumerate(buildings.keys()):
            #   buildings[building]['renter_expense_max'] = max_rent_building[index]
            return max_rent_building
        return parameters['renter_expense_max']
    else:
        default_max_rent_building = [1e6] * len(buildings)
        return  default_max_rent_building

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
def power_law_inverse(y, a, b):
    return (y / a) ** (1 / b)


