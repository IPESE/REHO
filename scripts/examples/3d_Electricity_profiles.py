from reho.model.reho import *
from reho.model.preprocessing.QBuildings import QBuildingsReader


if __name__ == '__main__':

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'

    reader = QBuildingsReader()
    qbuildings_data = reader.read_csv('multiple_buildings.csv', nb_buildings=1)

    parameters = {}

    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration', 'DataHeat_DHW', 'DHN_hex', 'HeatPump_DHN']
    scenario['enforce_units'] = []

    #method = {"read_electricity_profiles": 'typical_profiles.csv'}
    method = {}

    grids = infrastructure.initialize_grids()
    units = infrastructure.initialize_units(scenario, grids)

    # Run optimization
    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    SR.save_results(reho, save=['xlsx', 'pickle'], filename='3d')