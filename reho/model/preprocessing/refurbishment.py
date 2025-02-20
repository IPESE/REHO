from reho.paths import *
import pandas as pd
import numpy as np
def calculate_refurbishment_cost(buildings_data, Uh_ins):
    buildings_renovation_info = {
        building_name: {
            'U_h': data['U_h'],
            'area_facade': data.get('area_facade_m2', 0),
            'area_footprint': data.get('area_footprint_m2', 0),
            'area_roof': data.get('SolarRoofArea', 0),
            'total_area': data.get('area_facade_m2', 0) + data.get('area_footprint_m2', 0) + data.get('SolarRoofArea',0),
        }
        for building_name, data in buildings_data.items()
    }

    insulation_requirement = thickness_of_insulation(buildings_renovation_info)

    facade_fixed = price_adjustment(96.88) # CHF/m2
    facade_var = price_adjustment(2.7585) # TODO: CHECK cm or m CHF/cm , m^2

    footprint_fixed = price_adjustment(30.754) # underside without cladding
    footprint_var = price_adjustment(1.2463)

    roof_fixed = price_adjustment(33.438) # Pitched roof without dormers
    roof_var = price_adjustment(2.3652)
    cost_functions = {
        'facade_cost': lambda area_facade, d_facade: area_facade * (facade_fixed + facade_var * d_facade),
        'footprint_cost': lambda area_footprint, d_footprint: area_footprint * (footprint_fixed + footprint_var * d_footprint),
        'roof_cost': lambda area_roof, d_roof: area_roof * (roof_fixed + roof_var * d_roof)
    }

    cost_insulation = {}
    total_cost = {}

    for building_name, data in buildings_renovation_info.items():
        # Extract areas from the data
        area_facade = data['area_facade']
        area_footprint = data['area_footprint']
        area_roof = data['area_roof']

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
    for b in buildings_data:
        if buildings_renovation_info[b]['U_h'] - Uh_ins[b] <= 0.00015:
            total_cost[b] = 0

    return total_cost


def thickness_of_insulation(renovation_info):
    # define the required U-Values after retrofit
    U_required_facade = 0.0002
    U_required_footprint = 0.00025
    U_required_roof = 0.00017

    buildings_insulation = {}

    for building, data in renovation_info.items():
        d_facade = thickness_calculation(data['U_h'], U_required_facade)
        d_footprint = thickness_calculation(data['U_h'], U_required_footprint)
        d_roof = thickness_calculation(data['U_h'], U_required_roof)
        U_h_insulation = ((data['area_facade'] * U_required_facade
                           + data['area_footprint'] * U_required_footprint
                           + data['area_roof'] * U_required_roof)
                          / data['total_area'])

        buildings_insulation[building] = {
            'U_h_insulation': U_h_insulation,
            'd_facade': d_facade * 100,
            'd_footprint': d_footprint * 100,
            'd_roof': d_roof * 100
        }
    return buildings_insulation

def thickness_calculation(U_current, U_required):
    th_conductivity = 0.000035 # thermal conductivity of the insulation materials (kW/mK)
    d_insulation = (1 / U_required - 1 / U_current) * th_conductivity
    return d_insulation

def price_adjustment(c_de_2015_EUR):
    # Price indices (https://ec.europa.eu/eurostat/databrowser/view/sts_copi_q/default/table?lang=en)
    c_de_2023_EUR = c_de_2015_EUR * 1.603
    # Construction market metrics (https://publications.turnerandtownsend.com/international-construction-market-survey-2024/europe)
    # Munich vs Geneva
    c_ch_2023_EUR = c_de_2023_EUR * 1.322
    # FX (https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-chf.en.html)
    c_ch_2023_CHF = c_ch_2023_EUR * 0.963
    return c_ch_2023_CHF

def U_h_insulation(buildings_data):
    U_required_facade = 0.0002
    U_required_footprint = 0.00025
    U_required_roof = 0.00017
    U_h_data = {}
    U_h_ins_data = {}
    for building, data in buildings_data.items():
        U_h_data[building]= data['U_h']
        U_h_ins_data[building] = ((data['area_facade_m2'] * U_required_facade + data['area_footprint_m2'] * U_required_footprint + data['SolarRoofArea'] * U_required_roof)
                                                   / (data['ERA']))
        if U_h_ins_data[building] >= U_h_data[building]:
            U_h_ins_data[building] = U_h_data[building] - 0.0001
    return U_h_ins_data


