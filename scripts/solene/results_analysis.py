import pandas as pd

from reho.model.reho import *
from reho.plotting.plotting import *

import datetime


if __name__ == '__main__':

    run_label = "10buil_14_1640"
    districts = [277,3658,3112]
    pickle_files = [f'results/{run_label}_{d}.pickle' for d in districts] # filename format example : results/10buil_14_1640_277.pickle
    
    if len(pickle_files) == 1:
        with open(pickle_files[0], 'rb') as handle:
            results = pickle.load(handle)
    else:
        for file,label in zip(pickle_files,districts):
            with open(file, 'rb') as handle:
                vars()[f"results{label}"] = pickle.load(handle)

    # from plotting library
    rehos_dict = dict()
    for label in districts:
        rehos_dict[label] = vars()[f"results{label}"]

    fig = plot_EVexternalloadandprice(rehos_dict,scenario = 'totex', run_label =  run_label)
    fig.write_html('plots\plot.html')
    fig.show()

    df_pkm, fig = plot_pkm(results3112.results['totex'][4])
    fig.write_html('plots\plot2.html')
    fig.show()

    # TOTEX and CAPEXes
    fig, axs = plt.subplots(3, 1, figsize=(15, 15))
    variables = {"TOTEX":['Costs_op', "Costs_inv"],
                 "CAPEX" : ["Costs_inv"],
                 "OPEX" : ['Costs_op']
                 }
    try:  # if reho
        Pareto_ID_number = len(rehos_dict[list(rehos_dict.keys())[0]].results['totex'].keys())
    except:  # if reho.results
        Pareto_ID_number = len(rehos_dict[list(rehos_dict.keys())[0]]['totex'].keys())

    for axe, var in zip(axs.ravel(), variables):
        var_list = list()
        for i in range(Pareto_ID_number):
            total = 0
            for tr in districts:
                total += vars()['results' + str(tr)].results['totex'][i]["df_Performance"][variables[var]].xs(
                    "Network").sum()
            var_list.append(total)
        print(var_list)
        axe.plot(var_list)
        axe.set_title(f'{var} for each iteration')
    plt.show()


    print(results)