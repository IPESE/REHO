from reho.plotting import plotting
import pandas as pd


results = pd.read_pickle('results/my_case_study.pickle')

# Performance : Economical, Environmental, and Combined
plotting.plot_performance(results, plot='costs', indexed_on='Scn_ID', title="Economical performance", filename="figures/performance_costs").show()
plotting.plot_performance(results, plot='gwp', indexed_on='Scn_ID', title="Environmental performance", filename="figures/performance_gwp").show()
plotting.plot_performance(results, plot='combined', indexed_on='Scn_ID', title="Combined performance (Economical + Environmental)", filename="figures/performance_combined").show()

# Costs and Revenues
plotting.plot_expenses(results, plot='costs', indexed_on='Scn_ID', title="Costs and Revenues").show()

# Sankey diagram
plotting.plot_sankey(results['totex'][0], label='EN_long', color='ColorPastel', title="Sankey diagram").show()

# Eud-use demands
plotting.plot_sunburst_eud(results, label='EN_long', title="End-use demands").show()

# Energy profiles
units_to_plot = ['ElectricalHeater', 'HeatPump', 'PV', 'NG_Boiler']
plotting.plot_profiles(results['totex'][0], units_to_plot, label='EN_long', color='ColorPastel', resolution='weekly', title="Energy profiles with a weekly moving average").show()
