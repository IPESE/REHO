from reho.model.reho import *
from reho.plotting import plotting

if __name__ == '__main__':
    buildings_filename = str(Path(__file__).parent / 'QBuildings' / 'buildings_lausanne_2_no_hosp.csv')

    # Set building parameters
    reader = QBuildingsReader()
    qbuildings_data = reader.read_csv(buildings_filename=buildings_filename)

    # Select clustering options for weather data
    cluster = {'Location': 'Pully', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'OPEX'
    scenario['name'] = 'pv_max'
    scenario['specific'] = ['enforce_PV_max']
    scenario['exclude_units'] = ['OIL_Boiler', 'WOOD_Stove', 'HeatPump', 'ThermalSolar', 'DataHeat','NG_Cogeneration', 'WaterTankSH', 'Battery','Battery']
    scenario['enforce_units'] = []

    # Set method options
    method = {'building-scale': True, 'parallel_computation': True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids()
    grids['Electricity']['ReinforcementOfNetwork'] = np.array([1E6])
    grids['NaturalGas']['ReinforcementOfNetwork'] = np.array([1E6])
    grids['Electricity']['Network_ext'] = 1E6
    grids['NaturalGas']['Network_ext'] = 1E6
    units = infrastructure.initialize_units(scenario, grids)

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['pickle'], filename='pv_max')
