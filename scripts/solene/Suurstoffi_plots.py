import pandas as pd

from reho.model.reho import *
from reho.plotting.plotting import *

if __name__ == '__main__':

    run_label = "Suurstoffi_26_0852"
    file = f'results/{run_label}.pickle'

    with open(file, 'rb') as handle:
            reho = pickle.load(handle)


    # PLot and save results ============================================================================================
    additional_costs = {"mobility": [1e5, 1e5, 0]}     # cost of gasoline for each scenario (line 103 of plotting.py)
    fig = plot_performance(reho.results, plot='costs', indexed_on='Scn_ID', label='EN_long', additional_costs=additional_costs)
    fig.write_html(f"Figures/Performance_{run_label}.html")

    fig2 = plot_sankey(reho.results["EV"][0])
    fig2.write_html(f"Figures/Sankey_{run_label}.html")

    fig3 = plot_profiles(reho.results["EV"][0], units_to_plot=[])
    fig3.write_html(f"Figures/Profile_{run_label}.html")
