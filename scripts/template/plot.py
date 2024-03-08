from reho.plotting import plotting
import pandas as pd

results = pd.read_pickle('results/my_case_study.pickle')

# Performance plot : Costs and Global Warming Potential
plotting.plot_performance(results, plot='costs', indexed_on='Scn_ID', filename="figures/performance_costs").show()
plotting.plot_performance(results, plot='gwp', indexed_on='Scn_ID', filename="figures/performance_gwp").show()

# Sankey diagram
plotting.plot_sankey(results['totex'][0], label='EN_long', color='ColorPastel').show()
