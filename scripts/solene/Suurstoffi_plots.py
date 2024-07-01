import pandas as pd

from reho.model.reho import *
from reho.plotting.plotting import *

if __name__ == '__main__':

    run_label = "Suurstoffi_baseline"
    files = ['results/Suurstoffi_26_0752.pickle', 'results/Suurstoffi_26_0826.pickle']
    files = ['results/Suurstoffi_chargingprofiletest.pickle' ]
    results = dict()

    for file in files:
        with open(file, 'rb') as handle:
                reho = pickle.load(handle)
                # results = results | reho

    results = reho.results

    # PLot and save results ============================================================================================
    # additional_costs = {"mobility": [1e5, 1e5, 0]}     # cost of gasoline for each scenario (line 103 of plotting.py)
    report_folder = "C:/masterthesis/images/"

    # TOTEX
    fig = plot_performance(results, plot='costs', indexed_on='Scn_ID', label='EN_long' ) # , additional_costs=additional_costs)
    fig.write_html(f"{report_folder}C1_performance_{run_label}.html")
    fig.write_html(f"plots/C1_performance_{run_label}.html")
    fig.write_image(f"{report_folder}C1_performance_{run_label}.png")

    # GWP
    fig = plot_performance(results, plot='gwp', indexed_on='Scn_ID', label='EN_long' )
    fig.write_html(f"plots/C1_GWPperformance_{run_label}.html")

    for scn_ID in results.keys():
        fig2, df2 = plot_sankey(results[scn_ID][0], return_df=True)
        fig2.write_html(f"plots/C1_sankey{scn_ID}_{run_label}.html")

    fig3 = plot_profiles(results["M3_EV10"][0], units_to_plot=["EV_district","ICE_district"])
    fig3.write_html(f"plots/Profile_M3_EV10_{run_label}.html")

    fig5 = plot_profiles(results["ICE"][0], units_to_plot=["EV_district","ICE_district"])
    fig5.write_html(f"plots/Profile_ICE_{run_label}.html")
