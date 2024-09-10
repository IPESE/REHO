from reho.plotting import plotting
import pandas as pd


results = pd.read_pickle('/Users/ravi/Desktop/PhD/My_Reho_Qgis_files/Reho_Sai_Fork/scripts/template/results/ALL_EPFL_BAU.pickle')

#plotting.plot_performance(results, plot='costs', indexed_on='Scn_ID', label='EN_long').show()
#plotting.plot_performance(results, plot='gwp', indexed_on='Scn_ID', label='EN_long').show()
plotting.plot_sankey_1(results['gwp'][0], label='EN_long', color='ColorPastel').show()


'''
# Performance plot : Costs, Global Warming Potential, and Social Costs including Carbon Impact
plotting.plot_performance(results, plot='costs', indexed_on='Scn_ID', filename="figures/performance_costs").show()
plotting.plot_performance(results, plot='gwp', indexed_on='Scn_ID', filename="figures/performance_gwp").show()
plotting.plot_performance(results, plot='combined', indexed_on='Scn_ID', filename="figures/performance_combined").show()

# Expenses and Income plot
plotting.plot_expenses(results, plot='costs', indexed_on='Scn_ID').show()

# Sankey diagram
plotting.plot_sankey(results['totex'][0], label='EN_long', color='ColorPastel').show()

# Eud-use demand
plotting.plot_sunburst_eud(results, label='EN_long').show()

# Hourly profiles
units_to_plot = ['ElectricalHeater', 'HeatPump', 'PV', 'NG_Boiler']
plotting.plot_profiles(results['totex'][0], units_to_plot, label='EN_long', color='ColorPastel', resolution='weekly').show()
'''