from reho.paths import *
import pandas as pd
import numpy as np
import warnings

def U_h_insulation(buildings_data, refurbishment_data):
    years = refurbishment_data.T.loc['period'].tolist()
    buildings_data['period_num'] = next((int(i) for i, year in enumerate(years) if year in buildings_data.get('period', '')),
                                        None)
    if buildings_data['period_num'] is None:
        warnings.warn("Missing 'period_num'.", stacklevel=1)

    U_h_data = buildings_data['U_h']
    period_num = buildings_data['period_num']

    U_h_ins_data = ((buildings_data['area_facade_m2'] * refurbishment_data.iloc[period_num]['U_required_facade']
                    +buildings_data['area_footprint_m2'] * refurbishment_data.iloc[period_num]['U_required_footprint']
                    +buildings_data['SolarRoofArea'] * refurbishment_data.iloc[period_num]['U_required_roof'])
                                   / (buildings_data['ERA']))
    if U_h_ins_data + 0.00001 >= U_h_data:
        U_h_ins_data = U_h_data - 0.00001
    return U_h_ins_data

def refurbishment_cost_co2(buildings_data, refurbishment_data, refurbishment_index):
    """
    Calculate the insulation-adjusted U-value, total refurbishment cost, and CO2-equivalent for one building.

    Parameters
    ----------
    buildings_data : dictionary
        Data of one single building from QBuildings
    refurbishment_data : DataFrame
        Period-specific refurbishment parameters (e.g., requirements, costs and CO₂ factors), loaded from a CSV for parametrization.
    refurbishment_index : DataFrame
        Market, exchange, and price indices

    Returns
    -------
    Uh_ins : float
        Adjusted U-value after insulation (m²·K/W).
    total_cost : float
        Total refurbishment cost converted to CHF.
    total_co2 : float
        Total CO₂-equivalent emissions for the refurbishment.
    """
    Uh_ins = U_h_insulation(buildings_data, refurbishment_data)
    renovation_info = pd.Series({
        'U_h': buildings_data['U_h'],
        'period_num': buildings_data['period_num'],
        'area_facade_m2': buildings_data.get('area_facade_m2', 0),
        'area_footprint_m2': buildings_data.get('area_footprint_m2', 0),
        'SolarRoofArea': buildings_data.get('SolarRoofArea', 0),
        'total_area_m2': (
                buildings_data.get('area_facade_m2', 0)
                + buildings_data.get('area_footprint_m2', 0)
                + buildings_data.get('SolarRoofArea', 0)
        ),
        'ERA': buildings_data.get('ERA')
    })

    de15EUR_ch23CHF = refurbishment_index.loc[0]['price_index'] * \
                      refurbishment_index.loc[0]['market_index'] * \
                      refurbishment_index.loc[0]['fx_index']

    period_num = int(renovation_info['period_num'])

    facade_fixed = refurbishment_data.iloc[period_num]['Cost_fixed_facade']
    facade_var = refurbishment_data.iloc[period_num]['Cost_var_facade']

    footprint_fixed = refurbishment_data.iloc[period_num]['Cost_fixed_footprint']
    footprint_var = refurbishment_data.iloc[period_num]['Cost_var_footprint']

    roof_fixed = refurbishment_data.iloc[period_num]['Cost_fixed_roof']
    roof_var = refurbishment_data.iloc[period_num]['Cost_var_roof']

    cost_functions = {
        'facade_cost': lambda area_facade, d_facade: area_facade * (facade_fixed + facade_var * d_facade) * de15EUR_ch23CHF,
        'footprint_cost': lambda area_footprint, d_footprint: area_footprint * (footprint_fixed + footprint_var * d_footprint) * de15EUR_ch23CHF,
        'roof_cost': lambda area_roof, d_roof: area_roof * (roof_fixed + roof_var * d_roof) * de15EUR_ch23CHF,
    }

    # Extract areas from the data
    area_facade = renovation_info['area_facade_m2']
    area_footprint = renovation_info['area_footprint_m2']
    area_roof = renovation_info['SolarRoofArea']

    insulation_requirement = thickness_of_insulation(refurbishment_data, renovation_info)
    d_facade = insulation_requirement['d_facade']
    d_footprint = insulation_requirement['d_footprint']
    d_roof = insulation_requirement['d_roof']

    # Use the cost functions to calculate costs
    facade_cost = cost_functions['facade_cost'](area_facade, d_facade)
    footprint_cost = cost_functions['footprint_cost'](area_footprint, d_footprint)
    roof_cost = cost_functions['roof_cost'](area_roof, d_roof)

    # Store the calculated costs in the dictionary
    cost_insulation = pd.Series({
        'facade_cost': facade_cost,
        'footprint_cost': footprint_cost,
        'roof_cost': roof_cost,
        'total_cost': (facade_cost + footprint_cost + roof_cost)
    })
    total_cost = cost_insulation['total_cost']

    total_co2 = (area_facade * refurbishment_data.iloc[period_num]['CO2_eq_facade']
                                      + area_footprint * refurbishment_data.iloc[period_num]['CO2_eq_footprint']
                                      + area_roof * refurbishment_data.iloc[period_num]['CO2_eq_roof'])

    if renovation_info['U_h'] - Uh_ins <= 0.00009:
        total_cost = 0
        total_co2 = 0
    return Uh_ins, total_cost, total_co2


def thickness_of_insulation(refurbishment_data, renovation_info):
    period = int(renovation_info['period_num'])

    U_req_f = refurbishment_data.iloc[period]['U_required_facade']
    U_req_fp = refurbishment_data.iloc[period]['U_required_footprint']
    U_req_r = refurbishment_data.iloc[period]['U_required_roof']

    U_facade = renovation_info['U_h'] * renovation_info['ERA'] / (renovation_info['SolarRoofArea'] * refurbishment_data.iloc[period]['U_required_facade'] / refurbishment_data.iloc[period]['U_required_roof']
                                                + renovation_info['area_footprint_m2'] * refurbishment_data.iloc[period]['U_required_facade'] / refurbishment_data.iloc[period]['U_required_footprint']
                                                + renovation_info['area_facade_m2'])
    U_roof = U_facade * refurbishment_data.iloc[period]['U_required_facade'] / refurbishment_data.iloc[period]['U_required_roof']
    U_footprint = U_facade * refurbishment_data.iloc[period]['U_required_facade'] / refurbishment_data.iloc[period]['U_required_footprint']

    def calc_thickness(Uc, Ur, comp):
        kappa = refurbishment_data.iloc[period].get(f'kappa_material_{comp}', 0.000035)  # thermal conductivity of the insulation materials (kW/mK)
        d = (1 / Ur - 1 / Uc) * kappa
        return max(d, 0) * 100

    buildings_insulation = pd.Series({
        'd_facade': calc_thickness(U_facade, U_req_f, 'facade'),
        'd_footprint': calc_thickness(U_footprint, U_req_fp, 'footprint'),
        'd_roof': calc_thickness(U_roof, U_req_r, 'roof'),
    })
    return buildings_insulation

def price_adjustment(c_de_2015_EUR):
    refurbishment_index = pd.read_csv(os.path.join(path_to_infrastructure, 'refurbishment_index.csv'))
    # Price indices (https://ec.europa.eu/eurostat/databrowser/view/sts_copi_q/default/table?lang=en)
    c_de_2023_EUR = c_de_2015_EUR * refurbishment_index.loc[0]['price_index']
    # Munich vs Geneva Construction market metrics (https://publications.turnerandtownsend.com/international-construction-market-survey-2024/europe)
    c_ch_2023_EUR = c_de_2023_EUR * refurbishment_index.loc[0]['market_index']
    # Forgein Exchange (https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-chf.en.html)
    c_ch_2023_CHF = c_ch_2023_EUR * refurbishment_index.loc[0]['fx_index']
    return c_ch_2023_CHF