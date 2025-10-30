from reho.paths import *
import pandas as pd
import numpy as np
import sympy as sp
from scipy.optimize import curve_fit

__doc__ = """
Generate maximum rental values
"""


def generate_renter_expense_max(method='absolute', **kwargs):
    """
    Generate maximum rental expense values for buildings (dispatcher function).

    This function supports two calculation methods:
    1. 'absolute': Calculate based on income and building characteristics
    2. 'increase': Calculate based on baseline optimization with current building setup

    The result serves as input for renter expense constraints in actor-based optimization.

    Parameters
    ----------
    method : str, optional
        Calculation method: 'absolute' or 'increase'. Default is 'absolute'.
    **kwargs : dict
        Method-specific parameters:

        For method='absolute':
            - qbuildings_data (dict, required): Buildings data from QBuildingsReader
            - income (float, required): Annual income value
            - rent_income_ratio (array-like, optional): Custom rent-to-income ratio
            - types (list of str, optional): Rent types to consider. Default ["rent"]

        For method='increase':
            - reho_model (ActorsProblem, required): REHO model instance

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by building ID with column 'renter_expense_max' containing the maximum rental expense for each building.

    Examples
    --------
    - Absolute method (income-based):
    >>> reho.parameters['renter_expense_max'] = generate_renter_expense_max('absolute', qbuildings_data=qbuildings, income=70000)
    >>> # or with positional qbuildings_data (backward compatible)
    >>> reho.parameters['renter_expense_max'] = generate_renter_expense_max(qbuildings_data=qbuildings, income=70000)


    - Increase method (baseline-based):
    >>> reho.parameters['renter_expense_max']= generate_renter_expense_max(method='increase', reho_model=reho)

    See Also
    --------
    generate_renter_expense_max_absolute : Income-based calculation
    generate_renter_expense_max_increase : Baseline optimization calculation
    """
    method_lower = str(method).lower()

    if method_lower == 'absolute':
        return generate_renter_expense_max_absolute(**kwargs)
    elif method_lower == 'increase':
        return generate_renter_expense_max_increase(**kwargs)
    else:
        raise ValueError(f"Unknown method '{method}'. Must be 'absolute' or 'increase'.")


def generate_renter_expense_max_absolute(qbuildings_data, income, rent_income_ratio=None, types=["rent"]):
    """
    Calculate maximum rental expense based on absolute income values and building characteristics.

    Uses a power law relationship fitted from historical rent proportion data to determine
    the maximum rent a household can afford based on their income. The maximum rent is then
    adjusted for each building based on its type (Industrial vs. Other) and Energy Reference Area (ERA).

    Parameters
    ----------
    qbuildings_data : dict
        Buildings data from QBuildingsReader class.
    income : float
        Annual income value in the same currency units as the rent data.
        Used to calculate the maximum affordable rent.
    rent_income_ratio : array-like, optional
        Custom rent-to-income ratio values. If None, defaults to rent_proportion.csv data.
    types : list of str, optional
        Rent types to consider for calculating rent-to-income ratio. Default is ["rent"].

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by building ID with a single column 'renter_expense_max' containing the maximum rental expense for each building.

    Notes
    -----
    - Reads rent proportion data from 'rent_proportion.csv' located in the actor data path.
    - Uses power law curve fitting (scipy.optimize.curve_fit) to model the relationship.
    - Industrial buildings (id_class "I") use ERA/40 for rent calculation.
    - Non-industrial buildings use ERA/60 for rent calculation.

    Examples
    --------
    >>> qbuildings = {'buildings_data': {'Building1': {'id_class': 'R', 'ERA': 1000}}}
    >>> reho.parameters['renter_expense_max'] = generate_renter_expense_max_absolute(qbuildings, income=70000)
    """
    # Validate required parameters
    if qbuildings_data is None:
        raise ValueError("qbuildings_data is required for 'absolute' method")
    if income is None:
        raise ValueError("income is required for 'absolute' method")

    # Load rent proportion data
    rent_percentage = pd.read_csv(os.path.join(path_to_actor, 'rent_proportion.csv'))
    income_thresholds_rent = rent_percentage["Income"].to_numpy() * 12

    # Determine rent-to-income ratio
    if rent_income_ratio is not None:
        rent_income_ratio = np.array(rent_income_ratio)
    else:
        rent_income_ratio = rent_percentage[["Percentage_" + i for i in types]].sum(axis=1).to_numpy()

    # Fit power law relationship and calculate max rent per person
    power_params, _ = curve_fit(power_law, income_thresholds_rent, rent_income_ratio)
    max_rent_pp = power_law(income, power_params[0], power_params[1]) * income

    # Calculate max rent for each building
    renter_expense_max = {}
    for building_id, building_data in qbuildings_data["buildings_data"].items():
        id_class = building_data['id_class'].split("/")
        most_common_class = max(set(id_class), key=id_class.count)

        # Different factors for Industrial vs. other building types
        if most_common_class == "I":
            renter_expense_max[building_id] = max_rent_pp * building_data['ERA'] / 40
        else:
            renter_expense_max[building_id] = max_rent_pp * building_data['ERA'] / 60

    return pd.DataFrame.from_dict(renter_expense_max, orient="Index", columns=["renter_expense_max"])


def generate_renter_expense_max_increase(reho_model):
    """
    Calculate maximum rental expense relative to a baseline optimization scenario.

    Runs a baseline optimization with a boiler-only configuration to determine current
    rental expenses, which are then used as the maximum rent expenses for renters.
    This approach calculates rent increase limits based on existing building operations.

    Parameters
    ----------
    reho_model : ActorsProblem
        An initialized REHO ActorsProblem model instance. The model's configuration
        will be temporarily modified to run a baseline optimization, then restored.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by building ID with a single column 'renter_expense_max' containing the maximum rental expense for each building.

    Examples
    --------
    >>> reho = ActorsProblem(qbuildings_data, units, grids, ...)
    >>> reho.parameters['renter_expense_max'] = generate_renter_expense_max_increase(reho)
    """
    import copy

    if reho_model is None:
        raise ValueError("reho_model is required for 'increase' method")

    # Save original configuration
    scenario_original = copy.deepcopy(reho_model.scenario)
    method_original = copy.deepcopy(reho_model.method)
    dw_params_original = copy.deepcopy(reho_model.DW_params)

    # Configure baseline scenario (boiler-only, no advanced technologies)
    reho_model.DW_params["max_iter"] = 1
    reho_model.scenario["name"] = "boiler"
    reho_model.scenario["exclude_units"] = ['ThermalSolar', 'NG_Cogeneration', "PV", "HeatPump"]
    reho_model.scenario["enforce_units"] = ["NG_Boiler"]
    reho_model.method['building-scale'] = True
    reho_model.method['district-scale'] = False
    reho_model.method['renovation'] = None
    reho_model.samples = pd.DataFrame([0.0], columns=["owner_PIR_min"])

    # Run baseline optimization
    reho_model.actor_decomposition_optimization()

    # Extract renter expenses from baseline scenario
    renter_expense_max = (
        reho_model.results["boiler"][0]["df_Performance"][["renter_expense"]]
        .drop("Network")
        .rename(columns={"renter_expense": "renter_expense_max"})
    )

    # Restore original configuration
    reho_model.initialize_optimization_tracking_attributes()
    reho_model.scenario = scenario_original
    reho_model.method = method_original
    reho_model.DW_params = dw_params_original

    # Clean up baseline results
    del reho_model.results["boiler"]

    return renter_expense_max

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
    """
    Extract actor-related parameters from optimization results for a specific iteration.

    This function retrieves dual variables, costs, and subsidies from previous optimization
    iterations to construct a parameter dictionary used in actor-based optimization problems.
    It handles three types of actors: Tenants, Landlords, and ECM.

    Parameters
    ----------
    scenario : dict
        Scenario configuration dictionary containing optimization settings.
        Must include 'Objective' key specifying the objective function type.
    set_indexed : dict
        Dictionary of indexed sets, including 'ActorObjective' which specifies
        the primary actor for the objective function.
    result : dict
        Nested dictionary containing optimization results with structure:
        result[Scn_ID][Pareto_ID][iter-1] containing DataFrames:
        - 'df_Actors_dual': dual variables for actors
        - 'df_District': district-level costs and subsidies
        - 'df_DW': dual weights (lambda values)
        - 'df_Actors_tariff_f': tariff structures for self-consumption and supply/demand
    Scn_ID : str or int
        Scenario identifier for accessing results.
    Pareto_ID : str or int
        Pareto solution identifier for accessing results.
    iter : int, optional
        Iteration number (default=0). Uses results from iteration (iter-1).
    h : str
        Hub or building identifier for filtering location-specific parameters.

    Returns
    -------
    params : dict
        Dictionary containing extracted parameters:
        - 'nu_Renters': dual variable for Renters actor
        - 'nu_Utility': dual variable for Utility actor
        - 'nu_Owners': dual variable for Owners actor
        - 'C_rent_fix': fixed rent costs for building h
        - 'owner_subsidies': subsidies for owners in building h
        - 'renter_subsidies': subsidies for renters in building h
        - 'Cost_self_consumption': aggregated self-consumption costs for hub h
        - 'Cost_supply_district': aggregated district supply costs for hub h
        - 'Cost_demand_district': aggregated district demand costs for hub h

    """
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
    """
    Calculate expenses for a specific actor and building based on optimization results.

    This function computes the financial expenses or profits for different actor types
    (Renters, Owner, Utility) by extracting and combining relevant cost components from
    master problem (MP) and subproblem (SP) optimization results.

    Parameters
    ----------
    actor : str
        Actor type identifier (case-insensitive). Must be one of:
        - "renters": residential tenants
        - "owner": building owner/landlord
        - "utility": energy utility provider
    building : str or int
        Building identifier for which to calculate expenses.
    last_MP_results : dict, optional
        Master problem results dictionary containing DataFrames:
        - 'df_District': district-level economic metrics (expenses, profits, costs, subsidies)
        - 'df_Actors_tariff': tariff structures for supply and demand
        - 'Samples': actor parameters including 'Owner_PIR_min'
        If None, an empty dictionary is used.
    last_SP_results : dict, optional
        Subproblem results dictionary indexed by building, containing:
        - 'df_Unit_t': temporal unit operation data (electricity production)
        - 'df_Grid_t': temporal grid interaction data (electricity import/export)
        If None, an empty dictionary is used.

    Returns
    -------
    float
    Calculated expense value for the specified actor and building:
        - Renters: net rental expense after subsidies
        - Owner: net profit after accounting for subsidies and minimum profit requirements
        - Utility: net revenue from grid interactions and tariffs
    """
    last_MP_results = last_MP_results or {}
    last_SP_results = last_SP_results or {}

    # build self-consumption per building
    self_cons = {}
    for b, sp in last_SP_results.items():
        # assume sp['df_Unit_t'] and sp['df_Grid_t'] have MultiIndex: (Layer, Hub, Period, Time)
        prod = sp['df_Unit_t']['Units_supply']['Electricity'].sum()
        grid = sp['df_Grid_t']['Grid_demand']['Electricity'].sum()
        self_cons[b] = prod - grid

    if actor.lower() == "renters":
        renter_expense = last_MP_results['df_District']['renter_expense'][building]
        renter_subsidies = last_MP_results['df_District']['renter_subsidies'][building]
        return renter_expense - renter_subsidies

    elif actor.lower() == "owner":
        owner_prof = last_MP_results['df_District']['owner_profit'][building]
        owner_sub = last_MP_results['df_District']['owner_subsidies'][building]
        owner_inv = last_MP_results['df_District']['Costs_inv'][building]
        owner_upfront = last_MP_results['df_District']['Costs_House_yearly'][building]
        owner_pir_min = last_MP_results['Samples']['Owner_PIR_min'].iloc[0,0]

        owner_exp = owner_prof + owner_sub - owner_pir_min * (owner_inv + owner_upfront)
        return owner_exp

    elif actor.lower() == "utility":
        tariff_supply = last_MP_results['df_Actors_tariff']['Cost_supply_district']['Electricity'][building]
        tariff_dmd = last_MP_results['df_Actors_tariff']['Cost_demand_district']['Electricity'][building]
        util_exp = (tariff_supply * last_SP_results[building]['df_Grid_t']['Grid_supply']['Electricity'].xs(building, level='Hub').sum()
                    - tariff_dmd * last_SP_results[building]['df_Grid_t']['Grid_demand']['Electricity'].xs(building, level='Hub').sum())
        return util_exp

    else:
        raise ValueError(f"Unknown actor: {actor}")
