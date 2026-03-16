import re
import pandas as pd
from reho.model.reho import *
from reho.plotting import plotting


def load_lca_impacts_from_dat(dat_file, units, grids=None, max_file=None):
    """
    Reads a techs_lca.dat file and assigns per-indicator LCA impacts to every
    unit and (optionally) every grid layer, using the technology and layer names
    already present in the REHO ``units`` / ``grids`` dicts.

    Mapping from dat file → REHO structures
    ----------------------------------------
    * ``lcia_constr[ind, tech]``  →  ``unit["{ind}_constr"]``  (construction impact)
    * ``lcia_op[ind, tech]``      →  ``unit["{ind}_op"]``  (operation impact)
    * ``lcia_res[ind, layer]``    →  ``grids[layer]["{ind}_demand_cst"]``
                                     ``grids[layer]["{ind}_supply_cst"]``

    The ``{ind}_constr`` / ``{ind}_op`` keys are auto-detected by ``Infrastructure``
    to populate ``lca_kpis``, so no extra argument to ``REHO()`` is needed.
    Technologies or layers absent from the dat file receive a value of 0.0.

    Parameters
    ----------
    dat_file : str
        Path to the .dat file (e.g. ``"lca_results/techs_lca.dat"``).
    units : dict
        As returned by ``infrastructure.initialize_units()``.
        Must contain ``"building_units"`` and ``"district_units"`` lists.
    grids : dict, optional
        As returned by ``infrastructure.initialize_grids()``.
        When provided, ``{ind}_demand_cst`` / ``{ind}_supply_cst`` are set on
        every grid layer from ``lcia_res`` values.
    max_file : str, optional
        Path to the normalization CSV (e.g. ``"lca_results/techs_lca_max.csv"``).
        The CSV must have columns ``Abbrev`` and ``max_unit``.  When provided,
        every parsed impact value is multiplied by the corresponding
        ``max_unit`` factor to reverse the normalization applied before
        writing the dat file.

    Returns
    -------
    list of str
        Ordered list of indicator names (e.g. ``['CC', 'ETF', 'MR', 'PMF']``).
    """
    # -- Load normalization factors (optional) -----------------------------------
    scale = {}  # {indicator: max_unit}  — defaults to 1.0 (no scaling)
    if max_file is not None:
        df_max = pd.read_csv(max_file)
        scale = dict(zip(df_max["Abbrev"], df_max["max_unit"]))

    with open(dat_file, "r") as f:
        content = f.read()

    # -- Extract INDICATORS set --------------------------------------------------
    match = re.search(r"set INDICATORS\s*:=\s*([^;]+);", content)
    if match is None:
        raise ValueError(f"Could not find 'set INDICATORS' in {dat_file}")
    indicators = match.group(1).split()

    _value_re = r"([+-]?[\d.]+(?:[eE][+-]?\d+)?)"

    # -- Parse lcia_constr[indicator, tech] := value ----------------------------
    constr_data = {}  # {tech: {indicator: value}}
    for m in re.finditer(
        rf"let lcia_constr\['(\w+)','(\w+)'\]\s*:=\s*{_value_re}", content
    ):
        indicator, tech, value = m.group(1), m.group(2), float(m.group(3))
        constr_data.setdefault(tech, {})[indicator] = value * scale.get(indicator, 1.0)

    # -- Parse lcia_op[indicator, tech] := value --------------------------------
    op_data = {}  # {tech: {indicator: value}}
    for m in re.finditer(
        rf"let lcia_op\['(\w+)','(\w+)'\]\s*:=\s*{_value_re}", content
    ):
        indicator, tech, value = m.group(1), m.group(2), float(m.group(3))
        op_data.setdefault(tech, {})[indicator] = value * scale.get(indicator, 1.0)

    # -- Parse lcia_res[indicator, layer] := value ------------------------------
    res_data = {}  # {layer: {indicator: value}}
    for m in re.finditer(
        rf"let lcia_res\['(\w+)','(\w+)'\]\s*:=\s*{_value_re}", content
    ):
        indicator, layer, value = m.group(1), m.group(2), float(m.group(3))
        res_data.setdefault(layer, {})[indicator] = value * scale.get(indicator, 1.0)

    # -- Report any units/layers not found in the dat file ----------------------
    all_unit_names = (
        [u["Unit"] for u in units["building_units"]]
        + [u["Unit"] for u in units["district_units"]]
    )
    missing_units = [u for u in all_unit_names if u not in constr_data and u not in op_data]
    if missing_units:
        print(f"[load_lca_impacts] No dat entry for units (set to 0): {missing_units}")

    if grids is not None:
        missing_layers = [l for l in grids if l not in res_data]
        if missing_layers:
            print(f"[load_lca_impacts] No dat entry for layers (set to 0): {missing_layers}")

    # -- Assign construction / operation impacts to every unit ------------------
    for unit_list in [units["building_units"], units["district_units"]]:
        for unit in unit_list:
            tech = unit["Unit"]
            for ind in indicators:
                unit[f"{ind}_constr"] = constr_data.get(tech, {}).get(ind, 0.0)
                unit[f"{ind}_op"] = op_data.get(tech, {}).get(ind, 0.0)

    # -- Assign resource impacts to every grid layer ----------------------------
    if grids is not None:
        for layer in grids:
            for ind in indicators:
                val = res_data.get(layer, {}).get(ind, 0.0)
                grids[layer][f"{ind}_demand_cst"] = val
                grids[layer][f"{ind}_supply_cst"] = val

    return indicators


if __name__ == '__main__':
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=234, nb_buildings=5)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}
    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'LCA'
    scenario['exclude_units'] = []
    scenario['enforce_units'] = []

    # scenario['EMOO'] = {"EMOO_lca": {"Impact": 1}} # set an upper bound to

    # Set method options
    method = {'building-scale': True, "save_lca": True, "print_logs": False}
    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Load per-indicator LCA impacts from the dat file.
    # Uses unit["Unit"] names and grids.keys() to look up lcia_constr, lcia_op,
    # and lcia_res; technologies/layers absent from the dat file receive 0.
    
    try:
        indicators = load_lca_impacts_from_dat(
            "lca_results/techs_lca.dat", units, grids,
            max_file="lca_results/techs_lca_max.csv",
        )
    except Exception:
        pass
    try:
        indicators = load_lca_impacts_from_dat(
            "../../lca_results/techs_lca.dat", units, grids,
            max_file="../../lca_results/techs_lca_max.csv",
        )
    except Exception:
        pass

    # print(units)

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobiasl")
    reho.single_optimization()

    print("\nTOTEX: ", reho.results["LCA"][0]["df_Performance"].xs("Network")[["Costs_op", "Costs_inv"]].sum())
    print("Construction & Operational impact: ", np.round(reho.results["LCA"][0]["df_lca_Units"].sum()[0] , 2))
    print("Resources impact: ", np.round(reho.results["LCA"][0]["df_lca_resources"].sum()[0] , 2))
    print("Total impact: ", np.round(reho.results["LCA"][0]["df_lca_Performance"].xs("Network")[0] , 2))
    print("#################################################################")
    print("\nTOTEX: ", reho.results["LCA"][0]["df_Performance"].xs("Network")[["Costs_op", "Costs_inv"]].sum())
    print("Construction & Operational impact [per indicator]:\n", np.round(reho.results["LCA"][0]["df_lca_Units"].sum() , 2))
    print("Resources impact [per indicator]:\n", np.round(reho.results["LCA"][0]["df_lca_resources"].sum() , 2))
    print("Total impact [per indicator]:\n", np.round(reho.results["LCA"][0]["df_lca_Performance"].xs("Network") , 2))


    plotting.plot_sankey(reho.results['LCA'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()

    # Save results
    # reho.save_results(format=['xlsx', 'pickle'], filename='1a')
    reho.save_results(format=['pickle'], filename='9a')
