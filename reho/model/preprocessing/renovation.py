from reho.model.preprocessing.QBuildings import *

__doc__ = """
Correct U-values from QBuildings.
"""

def U_h_renovation(buildings_data, df_U_values):

    U_h_data = buildings_data['U_h']
    buildings_data = {"dummy": buildings_data}
    buildings_data = get_Uh_corrected(buildings_data, df_U_values)
    U_h_ins_data = buildings_data["dummy"]["U_h"]

    if buildings_data["dummy"]["U_h"] + 0.00001 >= U_h_data:
        U_h_ins_data = U_h_data - 0.00001
    return U_h_ins_data

def select_renovation_option(local_data, renovation_option):

    options = renovation_option.split("/")
    elements = ["facade", "footprint", "roof", "window"]

    df_U_values = local_data["df_renovation_targets"].copy()
    columns = ["U_" + item for item in elements]
    columns = [item.replace('U_', 'U_required_') if any(x in item for x in options) else item for item in columns]
    df_Uh = df_U_values[columns].copy()
    df_Uh.columns = df_Uh.columns.str.replace(r'^U_required', 'U', regex=True)

    df_costs = local_data["df_renovation"].copy()
    for col in elements:
        if col not in options:
            df_costs.loc[df_costs.index.get_level_values('element') == col, :] = 0

    return df_Uh, df_costs


def renovation_cost_co2(buildings_data, local_data, renovation_option):

    Uh = buildings_data["U_h"]
    df_U_values, df_costs = select_renovation_option(local_data, renovation_option)
    Uh_ins = U_h_renovation(buildings_data.copy(), df_U_values)

    if Uh - Uh_ins < 1e-6:
        impacts = {"cost": 0.0, "gwp": 0.0}
    else:
        mapping = {'<1919': "<1918", '1919-1945': "1919-1948", '1946-1960': "1949-1978", '1961-1970': "1949-1978",
                  '1971-1980': "1949-1978", '1981-1990': "1979-1994", '1991-2000': "1995-2001", '2001-2005': "2002-2006",
                  '2006-2010': '>2006', '>2010': ">2006"}
        df_costs.columns = ["cost", "gwp"]

        impacts = {}
        for col in df_costs:
            periods = buildings_data["period"].split("/")
            ratios = [float(x) for x in buildings_data["ratio"].split("/")]
            id_class = buildings_data["id_class"].split("/")

            if len(periods) < len(ratios):
                periods = periods + [periods[0]] * (len(ratios) - len(periods))
            if len(periods) > len(ratios):
                ratios = ratios + [0] * (len(ratios) - len(periods))

            impacts[col] = 0
            for i in range(len(periods)):
                glass = 0.5
                if id_class[i] in ["I", "II"]:
                    glass = 0.3

                cost = df_costs[col].xs(mapping[periods[i]])
                impacts[col] += ratios[i] * (buildings_data["area_facade_m2"] * ((1-glass) * cost["facade"] + glass * cost["window"])
                               + buildings_data["SolarRoofArea"] * cost["roof"] + buildings_data["area_footprint_m2"] * cost["footprint"])

    return Uh_ins, impacts["cost"]*1.16, impacts["gwp"]
