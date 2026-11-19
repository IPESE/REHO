from reho.model.reho import *


if __name__ == '__main__':

    buildings_filename = str(Path(__file__).parent / 'data' / 'buildings.csv')

    # Set building parameters
    # Load your buildings from a csv file instead of reading the database
    reader = QBuildingsReader()
    qbuildings_data = reader.read_csv(buildings_filename=buildings_filename, nb_buildings=2)

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = []
    scenario['enforce_units'] = ['HeatPump_DWW']

    # Set method options
    method = {'building-scale': True,}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()

    grids['Electricity']['ReinforcementOfNetwork'] = np.array([1E6])
    grids['NaturalGas']['ReinforcementOfNetwork'] = np.array([1E6])
    grids['Electricity']['Network_ext'] = 1E6
    grids['NaturalGas']['Network_ext'] = 1E6

    units = infrastructure.initialize_units(scenario, grids, building_wastewater_hp=True)

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx'], filename='3a_WW_HP')
