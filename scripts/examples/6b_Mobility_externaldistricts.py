from reho.model.reho import *
from reho.model.preprocessing.mobility_generator import *
from reho.plotting import plotting

if __name__ == '__main__':
    # Set building parameters
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(district_id=13569, nb_buildings=2)

    # Select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T', 'W'], 'Periods': 10, 'PeriodDuration': 24}

    # Set scenario
    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['name'] = 'totex'
    scenario['EMOO'] = {}
    scenario['exclude_units'] = []
    scenario['enforce_units'] = ['EV_district']

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'Gasoline': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    # Set method options
    method = {'building-scale': True, 'external_district': True}

    # Set parameters
    ext_districts = ["district_1", "district_2"]
    set_indexed = {"Districts": ext_districts}

    # 46m²/person on average, 2 categories of distance (D0 : short and D1 : long)
    era = np.sum([qbuildings_data["buildings_data"][b]['ERA'] for b in qbuildings_data["buildings_data"]])
    parameters = {"Population": era / 46, "DailyDist": {'D0': 25, 'D1': 10}}

    # min max share for each mobility mode and each distance
    modal_split = pd.DataFrame({"min_D0": [0, 0, 0.4, 0.3], "max_D0": [0.1, 0.3, 0.7, 0.7],
                                "min_D1": [0, 0.2, 0.4, 0.3], "max_D1": [0, 0.4, 0.7, 0.7]},
                               index=['MD', 'PT', 'cars', 'EV_district'])

    # Scenario 1: no external charging demands
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster, set_indexed=set_indexed, scenario=scenario, method=method, solver="gurobi")
    reho.modal_split = modal_split
    reho.single_optimization()

    # Scenario 2: with charging demands from external districts
    df_rho = pd.DataFrame(columns=['work', 'travel', 'leisure'], index=ext_districts).fillna(0.33)
    id_days = list(range(1, 11))
    id_hours = list(range(1, 25))

    # ratio of each building category in external districts
    reho.parameters["share_activity"] = rho_param(ext_districts, df_rho)

    # Charging tariff for external districts (revenue to the district): 0.2 CHF/kWh
    reho.parameters["Cost_supply_ext"] = pd.Series([0.2] * 240, index=pd.MultiIndex.from_product([id_days, id_hours]))

    # Charging tariff in external districts (expense to the district): 0.3 CHF/kWh
    reho.parameters["Cost_demand_ext"] = pd.Series([0.3] * 480, index=pd.MultiIndex.from_product([ext_districts, id_days, id_hours]))

    # The external districts have a charging demand for 1.5 kWh_el each hour to the district
    reho.parameters["EV_supply_ext"] = pd.Series([1.5] * 480, index=pd.MultiIndex.from_product([["leisure", "work"], id_days, id_hours]))

    reho.scenario['name'] = 'totex_external_load'
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='6b')

    # Plot results
    plotting.plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', title="Economical performance").show()
