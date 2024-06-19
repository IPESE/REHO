from reho.plotting import plotting
import pandas as pd


#plotting.yearly_demand_plot("results/epfl_campus_totex.xlsx")


results = pd.read_pickle('/Users/ravi/Desktop/PhD/My_Reho_Qgis_files/Reho_Sai_Fork/scripts/template/results/epfl_campus.pickle')

# Performance plot : Costs and Global Warming Potential
plotting.plot_performance(results, plot='costs', indexed_on='Scn_ID', filename="figures/performance_costs").show()
plotting.plot_performance(results, plot='gwp', indexed_on='Scn_ID', filename="figures/performance_gwp").show()
plotting.plot_performance(results, plot='combined', indexed_on='Scn_ID', filename="figures/performance_combined").show()

# Sankey diagram
plotting.plot_sankey(results['totex'][0], label='EN_long', color='ColorPastel').show()
