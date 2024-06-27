from reho.model.reho import *
from reho.plotting.plotting import *


if __name__ == '__main__':
    date = datetime.datetime.now().strftime("%d_%H%M")
    run_label = 'Suurstoffi'

    reader = QBuildingsReader()
    qbuildings_data = reader.read_csv(buildings_filename='data/clustering/buildings_suurstoffi.csv', nb_buildings=100)

    cluster = {'Location': 'Lucern', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}
    method = {'building-scale': True}
    parameters = {}

    scenario = dict()
    scenario['Objective'] = 'TOTEX'
    scenario['EMOO'] = {}
    scenario['specific'] = []

    # NO MOBILITY ======================================================================================================

    # SCENARIO 1 Gas boiler
    scenario['name'] = 'B1_Gas'
    scenario['exclude_units'] = ['HeatPump', 'PV', "Battery_district", 'EVcharging_district' , 'NG_Cogeneration']
    scenario['enforce_units'] = ['NG_Boiler']

    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             })
    units = infrastructure.initialize_units(scenario, grids,district_data=True)

    reho = reho(qbuildings_data=qbuildings_data, units=units, grids=grids, parameters=parameters, cluster=cluster,
                scenario=scenario, method=method, solver="gurobiasl")

    reho.single_optimization()

    # SCENARIO 2 HP + PV
    scenario['name'] = 'B2_HP'
    scenario['exclude_units'] = ['Battery_district', 'EVcharging_district', 'NG_Cogeneration']
    scenario['enforce_units'] = []
    scenario['specific'] = ["enforce_PV_max"]
    units = infrastructure.initialize_units(scenario, grids)

    reho.scenario = scenario
    reho.units = units
    reho.infrastructure = infrastructure.infrastructure(qbuildings_data, units, grids)
    reho.single_optimization()

    # WITH MOBILITY ====================================================================================================
    reho.parameters['Population'] = 1500

    grids = infrastructure.initialize_grids({'Electricity': {},
                                             'NaturalGas': {},
                                             'FossilFuel': {},
                                             'Mobility': {},
                                             })

    # SCENARIO 3 Full ICE
    scenario['name'] = 'M1_ICE'
    scenario['specific'] = []
    scenario['exclude_units'] = ['NG_Cogeneration']
    scenario['enforce_units'] = ['EV_district']
    units = infrastructure.initialize_units(scenario, grids, district_data=True)

    reho.parameters['min_share_ICE'] = 0.9
    reho.parameters['n_ICEperhab'] = 10
    reho.parameters['max_share_EBikes'] = 0 # to prevent bug.

    reho.scenario = scenario
    reho.units = units
    reho.grids = grids
    reho.infrastructure = infrastructure.infrastructure(qbuildings_data, units, grids)
    reho.single_optimization()

    # SCENARIO 4 OFS SHARES
    scenario['name'] = 'M2_OFS'

    shares = {  "share_cars" : 0.66,
                "share_PT"  : 0.24,
                "share_MD" : 0.1, # mobilité douce : "soft mobility" ? (from FSO : include biking, walking, electric biking)
                "share_ICE" : 0.66,
                "share_PT_train" : 0.2,
            }
    perc_point_window = 0.03 # the range between the max and the min constraint (in percentage points)
    
    for key in shares.keys():
        reho.parameters[f"max_{key}"] = shares[key] + perc_point_window/2
        reho.parameters[f"min_{key}"] = shares[key] - perc_point_window/2

    reho.parameters['max_share_EBikes'] = 0.02 # only max, perc_point_window relaxation. 

    reho.scenario = scenario
    reho.single_optimization()


    # SCENARIO 5
    scenario['name'] = 'M3_EV10'
    reho.parameters[f"max_share_EV"] = 0.12 * 0.66 + perc_point_window/2
    reho.parameters[f"min_share_EV"] = 0.12 * 0.66 - perc_point_window/2
    reho.parameters[f"max_share_ICE"] = 0.66
    reho.parameters[f"min_share_ICE"] = 0

    # reho.infrastructure.Units_Parameters.loc["EV_district", "Cost_inv1"] = 0 # to change the cost of EVs [CHF]
    # reho.infrastructure.Units_Parameters.loc["EV_district", "Cost_inv2"] = 750 # to change the cost of EVs [CHF/kWh]

    reho.scenario = scenario
    reho.single_optimization()

    # PLot and save results ============================================================================================
    additional_costs = {"mobility": [1e5, 1e5, 0]}     # cost of gasoline for each scenario (line 103 of plotting.py)
    fig = plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', additional_costs=additional_costs)
    fig.write_html("Figures/Performance_suurstoffi.html")

    fig2 = plot_sankey(reho.results["EV"][0])
    fig2.write_html("Figures/Sankey_suurstoffi.html")

    fig3 = plot_profiles(reho.results["EV"][0], units_to_plot=[])
    fig3.write_html("Figures/Profile_suurstoffi.html")


    reho.save_results(format=['pickle','save_all'], filename='Suurstoffi')
