from reho.model.preprocessing.QBuildings import *

def U_h_insulation(buildings_data, local_data):

    U_h_data = buildings_data['U_h']
    buildings_data = {"dummy": buildings_data}
    df_Uh = local_data["df_Refurbishment_targets"][["U_required_facade", "U_required_footprint", "U_required_roof"]].transpose()
    df_Uh.index = ["facade", "footprint", "roof"]
    df_Uh.columns = local_data["df_Refurbishment_targets"]["period"]
    df_Uh.loc["window"] = 0.001 # SIA 380/1
    mapping = {i: i for i in df_Uh.columns}

    buildings_data = get_Uh_corrected(buildings_data, df_Uh, mapping)
    U_h_ins_data = buildings_data["dummy"]["U_h"]

    if buildings_data["dummy"]["U_h"] + 0.00001 >= U_h_data:
        U_h_ins_data = U_h_data - 0.00001
    return U_h_ins_data

def refurbishment_cost_co2(buildings_data, local_data):
    Uh = buildings_data["U_h"]
    Uh_ins = U_h_insulation(buildings_data.copy(), local_data)

    if Uh - Uh_ins < 1e-6:
        impacts = {"cost": 0.0, "gwp": 0.0}
    else:
        maping = {'<1919': "<1918", '1919-1945': "1919-1948", '1946-1960': "1949-1978", '1961-1970': "1949-1978",
                  '1971-1980': "1949-1978", '1981-1990': "1979-1994", '1991-2000': "1995-2001", '2001-2005': "2002-2006",
                  '2006-2010': '>2006', '>2010': ">2006"}
        data = local_data["df_Refurbishment"].copy().set_index(["year", "element"])
        data.columns = ["cost", "gwp"]

        impacts = {}
        for col in data:
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

                cost = data[col].xs(maping[periods[i]])
                impacts[col] += ratios[i] * (buildings_data["area_facade_m2"] * ((1-glass) * cost["facade"] + glass * cost["windows"])\
                               + buildings_data["SolarRoofArea"] * cost["roof"] + buildings_data["area_footprint_m2"] * cost["ground"])

    return Uh_ins, impacts["cost"], impacts["gwp"]
