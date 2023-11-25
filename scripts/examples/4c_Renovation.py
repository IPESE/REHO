from reho.model.reho import *
from reho.model.preprocessing.QBuildings import QBuildingsReader

def renovate_buildings(qbuildings_data):

    # U_values are taken from the thesis of Paul Stadler (page 145).
    # Refurbishment costs have to be added manually after optimization. Information on renovation cost are in the page 47 of the thesis.
    u_values = pd.DataFrame([[0.94, 1.02], [1.17, 1.23], [1.11, 1.18], [1.21, 1.27]], index=[1920, 1970, 1980, 2005], columns=["SFH/MFH", "MIX"])/1000 # kW / °C m2

    # tracking dataframe on the renovation status of the buildings
    renovated_bui = pd.DataFrame()

    for bui in qbuildings_data["buildings_data"]:
        if qbuildings_data["buildings_data"][bui]["U_h"] > u_values.max().max(): # check if building need renovation
            year = int(qbuildings_data["buildings_data"][bui]["period"][-4:])

            new_U = u_values[u_values.index >= year]["SFH/MFH"].iloc[0]
            old_U = qbuildings_data["buildings_data"][bui]["U_h"]
            qbuildings_data["buildings_data"][bui]["U_h"] = new_U # change U_h based on the year of the building

            df = pd.DataFrame([[old_U, new_U]], index=[bui], columns=["old_U", "new_U"])
            renovated_bui = pd.concat([renovated_bui, df])

    return qbuildings_data, renovated_bui

if __name__ == '__main__':

    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['EMOO'] = {}
    scenario['specific'] = []
    scenario['name'] = 'totex'

    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(3658, nb_buildings=15)

    #qbuildings_data, renovated_bui = renovate_buildings(qbuildings_data)


    parameters = {}
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = []

    method = {'building-scale': True}

    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    SR.save_results(reho, save=['xlsx', 'pickle'], filename='4c')
