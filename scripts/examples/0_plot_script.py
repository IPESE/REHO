import pandas as pd
from plotting import plotting, sankey

pareto = pd.read_pickle('results/1b.pickle')

# # Performance plot : costs and gwp
plotting.plot_performance(pareto, plot='costs', indexed_on='Pareto_ID', label='FR_long', auto_open=True)
plotting.plot_performance(pareto, plot='gwp', indexed_on='Pareto_ID', label='FR_long', auto_open=True)

# Pareto curve
plotting.plot_pareto(pareto, label='FR_long', color='ColorPastel', auto_open=True)

# Sankey diagram
# for key in pareto['pareto'].keys():
#     source, target, value, label_, color_ = sankey.df_sankey(pareto['pareto'][key], label='EN_long', color='ColorPastel')
#     sankey.plot_sankey(source, target, value, label_, color_)
source, target, value, label_, color_ = sankey.df_sankey(pareto['pareto'][3], label='EN_long', color='ColorPastel')
sankey.plot_sankey(source, target, value, label_, color_)

# Hourly profiles (matplotlib ou plotly)
units_to_plot = ['ElectricalHeater', 'HeatPump', 'PV', 'Battery', 'EV_district']
plotting.plot_profiles(pareto['pareto'][4], units_to_plot, style='plotly', label='EN_long', color='ColorPastel', resolution='weekly')