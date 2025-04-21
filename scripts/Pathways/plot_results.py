from reho.model.reho import *
from reho.plotting import plotting
import plotly.graph_objects as go
import pandas as pd
import plotly.express as px

results_path = '/Users/catarina/Documents/REHO/scripts/Pathways/results/pathway_test.pickle'

ev_no_const_res = pd.read_pickle(results_path)

# remove keys from dictionary
ev_no_const_res['pathway'] = {k: v for k, v in ev_no_const_res['pathway'].items() if k not in ['PV_max']}

# Define your year replacements
year_keys = [2025, 2030, 2035, 2040, 2045, 2050]

# Replace keys in ev_no_const_res['pathway']
ev_no_const_res['pathway'] = {
    year_keys[i]: value for i, (old_key, value) in enumerate(ev_no_const_res['pathway'].items())
}

plotting.plot_performance(ev_no_const_res, plot='costs', indexed_on='Pareto_ID', label='EN_long',title="Economical performance").show()