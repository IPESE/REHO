from reho.model.reho import *
from reho.model.preprocessing.mobility_generator import *


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
    scenario['exclude_units'] = ['Battery', 'NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']

    # Initialize available units and grids
    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids,district_data=True)

    # Set method options
    method = {'building-scale': True,
              'external_district' : True
              }
    
    # Set parameters
    ext_districts = [13219 ,13228]
    set_indexed = {"Districts": ext_districts }

    # parameters representing external district demands and supply
    df_rho = pd.DataFrame(columns=['work','travel','leisure'],index=ext_districts).fillna(0.5)
    cost_supply_ext = pd.Series( [0.21, 0.21, 0.21, 0.21, 0.21, 0.17, 0.17, 0.17, 0.17, 0.17, 0.17, 0.17, 0.17, 0.17, 0.17, 0.17, 0.17, 0.17, 0.17, 0.21, 0.21, 0.21, 0.21, 0.21],index = range(1,25))
    cost_demand_ext = pd.DataFrame( {13219 : [0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.17, 0.33, 0.33, 0.17, 0.17, 0.17, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33],
                                     13228 : [0.363, 0.363, 0.363, 0.363, 0.363, 0.187, 0.187, 0.187, 0.187, 0.187, 0.187, 0.187, 0.187, 0.187, 0.187, 0.187, 0.187, 0.187, 0.363, 0.363, 0.363, 0.363, 0.363, 0.363]},index = range(1,25))
    ev_charger_supply_ext = pd.DataFrame({ "leisure" : [0, 0, 0, 0, 0, 0, 0, 0, 0, 47, 51, 0, 203, 79, 78, 146, 123, 0, 22, 0, 0, 0, 0, 0],
                                           "work"    : [0, 11, 12, 0, 0, 46, 859, 1481, 0, 3529, 3729, 0, 0, 0, 0, 0, 2084, 0, 414, 0, 0, 0, 0, 0]},index = range(1,25))
    df_cost_supply_ext = pd.DataFrame()
    df_cost_demand_ext = pd.DataFrame()
    df_ev_charger_supply_ext = pd.DataFrame()
    for p in range(cluster['Periods']):
        df_cost_supply_ext[p+1] = cost_supply_ext
        df_cost_demand_ext[p+1] = cost_demand_ext.stack()
        df_ev_charger_supply_ext[p+1] = ev_charger_supply_ext.stack()
    df_cost_supply_ext = df_cost_supply_ext.stack().reorder_levels((1,0))
    df_cost_demand_ext = df_cost_demand_ext.stack().reorder_levels((1,2,0))
    df_ev_charger_supply_ext = df_ev_charger_supply_ext.stack().reorder_levels((1,2,0))



    era = np.sum([qbuildings_data["buildings_data"][b]['ERA'] for b in qbuildings_data["buildings_data"]])
    parameters = {  "Population": era / 46,
                    "share_activity": rho_param(ext_districts,df_rho),
                    "DailyDist" : {'D0': 25, 'D1': 10},
                    "Cost_supply_ext" : df_cost_supply_ext,
                    "Cost_demand_ext" : df_cost_demand_ext,
                    "EV_charger_supply_ext" : df_ev_charger_supply_ext
                    }
    modal_split = pd.DataFrame({"min_D0" : [0,0,0.4,0.3], "max_D0" : [0.1,0.3,0.7,0.7],"min_D1" : [0,0.2,0.4,0.3], "max_D1" : [0,0.4,0.7,0.7]}, index = ['MD','PT','cars','EV_district'])

    # Run optimization
    reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids,parameters=parameters, cluster=cluster,set_indexed=set_indexed, scenario=scenario, method=method, solver="gurobiasl")
    reho.modal_split = modal_split
    reho.single_optimization()

    # Save results
    reho.save_results(format=['xlsx', 'pickle'], filename='6b')
