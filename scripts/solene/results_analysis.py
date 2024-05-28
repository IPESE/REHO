import pandas as pd

from reho.model.reho import *
from reho.plotting.plotting import *

import datetime


if __name__ == '__main__':

    # SET-UP =====================================================================================================
    # Results files 
    # run_label = "10buil_14_1640"
    # districts = [277,3658,3112]
    run_label = "1district"
    districts = ["noconstraints","maxshare","maxshare10km","relaxed"]
    districts = ['28_1106']
    pickle_files = [f'results/{run_label}_{d}.pickle' for d in districts] # filename format example : results/10buil_14_1640_277.pickle
    
    # Specifications for the graphs
    Pareto_IDs = [0] # which iteration(s) to generate for graphs that only plot 1 iter (especially for the pkm graphs)

    # PLOTTING =====================================================================================================
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

    ## pkm profiles per typical day p.
    for p in Pareto_IDs:
        for label in districts:
            df_pkm, fig = plot_pkm(vars()[f"results{label}"].results['totex'][p],run_label=f"{run_label} - district {label} - iter {p}")
            fig.write_html(f'plots\pkm{label}{p}.html')
            fig.show()

            df_share = pd.DataFrame()
            df_share['PT']= df_pkm.loc[:,df_pkm.columns.get_level_values(level=0).str.startswith('PT')].sum(axis=1)
            df_share['Bike']= df_pkm.loc[:,df_pkm.columns.get_level_values(level=1).str.startswith('Bike')].sum(axis=1)
            df_share['Total'] = df_pkm.loc[:,df_pkm.columns.get_level_values(level=0) == "Domestic_energy"]

            df_share = df_share.groupby(['Layer',"Period"]).agg('sum')
            df_share = df_share.div(df_share['Total'],axis = 0)

            if "T" and "I" and "W" in vars()[f"results{label}"].cluster['Attributes']:
                attributes = "T_I_W"
                File_ID = "timestamp_{location}_{periods}_{periodduration}_{attributes}".format(
                    location = vars()[f"results{label}"].cluster['Location'],
                    periods = vars()[f"results{label}"].cluster['Periods'],
                    periodduration = vars()[f"results{label}"].cluster['PeriodDuration'],
                    attributes = attributes
                )
            else:
                print("Achtung : check how the timestamp file is label, and especially Attribute TIW? ")
                File_ID = "timestamp_{location}_{periods}_{periodduration}".format(
                    location = vars()[f"results{label}"].cluster['Location'],
                    periods = vars()[f"results{label}"].cluster['Periods'],
                    periodduration = vars()[f"results{label}"].cluster['PeriodDuration']
                )
                print(f"File_ID tested : {File_ID}")

            timestamp = pd.read_table(os.path.join(path_to_clustering, File_ID + '.dat'), usecols=(1, 2, 3))
            timestamp.index = timestamp.index + 1
            timestamp.index.name = 'Period'
            
            modal_shares= df_share.xs('Mobility')[['Bike','PT']].mul(timestamp['Frequency'],axis = 0).sum(axis = 0)/timestamp['Frequency'].sum()
            print(f"District {label} - iteration {p}. The average modal shares are:")
            print(modal_shares)

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