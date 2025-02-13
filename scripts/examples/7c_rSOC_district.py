from reho.model.reho import *
from reho.plotting import plotting


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Geneva')
    qbuildings_data = reader.read_db(district_id=5, egid=['2034144/2034143/2749579/2034146/2034145'])

    # Select clustering options for weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['enforce_units'] = ["rSOC_district"]
    scenario['exclude_units'] = ['NG_Cogeneration', 'ThermalSolar', 'ElectricalHeater_SH', "EV_district", 'HeatPump', 'rSOC', "NG_Boiler"]
    scenario['specific'] = ['enforce_DHN']

    # Set method
    method = {"building-scale": True}

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({
        'Electricity': {},
        'NaturalGas': {},
        'Hydrogen': {},
        'Biomethane': {},
        'CO2': {},
        'Heat': {},
    })
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    # Set the parameter
    parameters = {}
    parameters = {"Network_ext": np.array([100, 100, 100, 100, 0, 0])}
    """
    grids["Electricity"]["ReinforcementOfNetwork"] = np.array(
        [0])  # available capacities of networks [Electricity]
    grids["NaturalGas"]["ReinforcementOfNetwork"] = np.array(
        [0])  # available capacities of networks [Electricity]
    """
    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobi")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='7c')

    # Plot results
    plotting.plot_sankey(reho.results['totex'][0]).show()
