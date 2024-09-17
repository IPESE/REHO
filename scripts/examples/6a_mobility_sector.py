from reho.model.reho import *


if __name__ == '__main__':

    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(transformer=3658, nb_buildings=2)

    # Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']

    parameters = dict()

    # scenario parameters related to mobility
    # Example 1 : if you want to activate a forced charging profile
    scenario['specific'] = ['EV_supplyprofile1',"EV_supplyprofile2"]

    ## Example 2 : if you want to modify the share of some modes in the demand
    shares = {"share_EV": 0.4}
    perc_point_window = 0.03 # the range between the max and the min constraint (in percentage points)

    for key in shares.keys():
        parameters[f"max_{key}"] = shares[key] + perc_point_window/2
        parameters[f"min_{key}"] = shares[key] - perc_point_window/2


    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids,district_data=True)

    # Set method options
    method = {'building-scale': True}
    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids,parameters=parameters, cluster=cluster, scenario=scenario, method=method, solver="gurobiasl")
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='6a')
