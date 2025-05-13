from reho.paths import *
import pandas as pd
import numpy as np
import warnings

def U_h_insulation(buildings_data):
    buildings_data = period_pair(buildings_data)
    refurbishment_data = pd.read_csv(path_to_refurbishment_data)

    U_h_data = {}
    U_h_ins_data = {}
    for building, data in buildings_data.items():
        U_h_data[building]= data['U_h']
        period_num = data['period_num']
        U_h_ins_data[building] = ((data['area_facade_m2'] * refurbishment_data.iloc[period_num]['U_required_facade']
                                   +data['area_footprint_m2'] * refurbishment_data.iloc[period_num]['U_required_footprint']
                                   + data['SolarRoofArea'] * refurbishment_data.iloc[period_num]['U_required_roof'])
                                                   / (data['ERA']))
        if U_h_ins_data[building] + 0.00001 >= U_h_data[building]:
            U_h_ins_data[building] = U_h_data[building] - 0.00001
    return U_h_ins_data

def refurbishment_cost_co2(buildings_data, Uh_ins):

    buildings_renovation_info = {
        building_name: {
            'U_h': data['U_h'],
            'period_num': data['period_num'],
            'area_facade_m2': data.get('area_facade_m2', 0),
            'area_footprint_m2': data.get('area_footprint_m2', 0),
            'SolarRoofArea': data.get('SolarRoofArea', 0),
            'total_area_m2': data.get('area_facade_m2', 0) + data.get('area_footprint_m2', 0) + data.get('SolarRoofArea',0),
            'ERA': data.get('ERA'),
        }
        for building_name, data in buildings_data.items()
    }

    refurbishment_data = pd.read_csv(path_to_refurbishment_data)

    cost_insulation = {}
    total_cost = {}
    total_co2 = {}

    for building_name, data in buildings_renovation_info.items():
        period_num = data['period_num']

        facade_fixed = refurbishment_data.iloc[period_num]['Cost_fixed_facade']
        facade_var = refurbishment_data.iloc[period_num]['Cost_var_facade']

        footprint_fixed = refurbishment_data.iloc[period_num]['Cost_fixed_footprint']
        footprint_var = refurbishment_data.iloc[period_num]['Cost_var_footprint']

        roof_fixed = refurbishment_data.iloc[period_num]['Cost_fixed_roof']
        roof_var = refurbishment_data.iloc[period_num]['Cost_var_roof']

        cost_functions = {
            'facade_cost': lambda area_facade, d_facade: area_facade * (facade_fixed + facade_var * d_facade),
            'footprint_cost': lambda area_footprint, d_footprint: area_footprint * (footprint_fixed + footprint_var * d_footprint),
            'roof_cost': lambda area_roof, d_roof: area_roof * (roof_fixed + roof_var * d_roof)
        }

        # Extract areas from the data
        area_facade = data['area_facade_m2']
        area_footprint = data['area_footprint_m2']
        area_roof = data['SolarRoofArea']

        insulation_requirement = thickness_of_insulation({building_name: data})
        d_facade = insulation_requirement[building_name]['d_facade']
        d_footprint = insulation_requirement[building_name]['d_footprint']
        d_roof = insulation_requirement[building_name]['d_roof']

        # Use the cost functions to calculate costs
        facade_cost = cost_functions['facade_cost'](area_facade, d_facade)
        footprint_cost = cost_functions['footprint_cost'](area_footprint, d_footprint)
        roof_cost = cost_functions['roof_cost'](area_roof, d_roof)

        # Store the calculated costs in the dictionary
        cost_insulation[building_name] = {
            'facade_cost': facade_cost,
            'footprint_cost': footprint_cost,
            'roof_cost': roof_cost,
            'total_cost': (facade_cost + footprint_cost + roof_cost)
        }
        total_cost[building_name] = cost_insulation[building_name]['total_cost']

        total_co2[building_name] = (data['area_facade_m2'] * refurbishment_data.iloc[period_num]['CO2_eq_facade']
                                          + data['area_footprint_m2'] * refurbishment_data.iloc[period_num]['CO2_eq_footprint']
                                          + data['SolarRoofArea'] * refurbishment_data.iloc[period_num]['CO2_eq_roof'])

    for b in buildings_data:
        if buildings_renovation_info[b]['U_h'] - Uh_ins[b] <= 0.00009:
            total_cost[b] = 0
            total_co2[b] = 0

    return total_cost, total_co2


def thickness_of_insulation(renovation_info):

    refurbishment_data = pd.read_csv(path_to_refurbishment_data)
    buildings_insulation = {}

    for building, data in renovation_info.items():
        period = data['period_num']

        U_req_f = refurbishment_data.iloc[period]['U_required_facade']
        U_req_fp = refurbishment_data.iloc[period]['U_required_footprint']
        U_req_r = refurbishment_data.iloc[period]['U_required_roof']

        U_facade = data['U_h'] * data['ERA'] / (data['SolarRoofArea'] * refurbishment_data.iloc[period]['U_required_facade'] / refurbishment_data.iloc[period]['U_required_roof']
                                                    + data['area_footprint_m2'] * refurbishment_data.iloc[period]['U_required_facade'] / refurbishment_data.iloc[period]['U_required_footprint']
                                                    + data['area_facade_m2'])
        U_roof = U_facade * refurbishment_data.iloc[period]['U_required_facade'] / refurbishment_data.iloc[period]['U_required_roof']
        U_footprint = U_facade * refurbishment_data.iloc[period]['U_required_facade'] / refurbishment_data.iloc[period]['U_required_footprint']

        def calc_thickness(Uc, Ur, comp):
            kappa = refurbishment_data.iloc[period].get(f'kappa_material_{comp}', 0.000035)  # thermal conductivity of the insulation materials (kW/mK)
            d = (1 / Ur - 1 / Uc) * kappa
            return max(d, 0) * 100

        buildings_insulation[building] = {
            'd_facade': calc_thickness(U_facade, U_req_f, 'facade'),
            'd_footprint': calc_thickness(U_footprint, U_req_fp, 'footprint'),
            'd_roof': calc_thickness(U_roof, U_req_r, 'roof'),
        }

    return buildings_insulation

def price_adjustment(c_de_2015_EUR):
    refurbishment_index = pd.read_csv(path_to_refurbishment_index)
    # Price indices (https://ec.europa.eu/eurostat/databrowser/view/sts_copi_q/default/table?lang=en)
    c_de_2023_EUR = c_de_2015_EUR * refurbishment_index.loc[0]['price_index']
    # Munich vs Geneva Construction market metrics (https://publications.turnerandtownsend.com/international-construction-market-survey-2024/europe)
    c_ch_2023_EUR = c_de_2023_EUR * refurbishment_index.loc[0]['market_index']
    # Forgein Exchange (https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-chf.en.html)
    c_ch_2023_CHF = c_ch_2023_EUR * refurbishment_index.loc[0]['fx_index']
    return c_ch_2023_CHF

def period_pair(buildings_data):
    refurbishment_data = pd.read_csv(path_to_refurbishment_data).T
    years = refurbishment_data.loc['period'].tolist()

    for building, data in buildings_data.items():
        data['period_num'] = next((i for i, year in enumerate(years) if year in data.get('period', '')), None)
        if data['period_num'] is None:
            warnings.warn(f"{building} is missing 'period_num'.", stacklevel=1)
    return buildings_data