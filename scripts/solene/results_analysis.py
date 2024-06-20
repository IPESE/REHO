import pandas as pd

from reho.model.reho import *
from reho.plotting.plotting import *

import datetime

def plot_cost_EV(reho_dict,run_label = "",CS_unit = ['EVcharging_district'],Scn_ID = 'totex'):
    """
    reho_dict : dict
        dictionnary of reho objects. The keys must be the names of the districts (transformer number)
    results : reho.results[Scn_ID] 
        ex: reho.results['totex']
    run_label : str
        used for the title of the graph
    CS_unit : list
        temporary, to get all the types of charging station, ideally this function should fetch in district_units.csv all the UnitsofType[charging station]

    """
    try: # if reho
        Pareto_ID_number = len(rehos_dict[list(rehos_dict.keys())[0]].results[Scn_ID].keys())
        REHO = True
    except: # if reho.results => this can't get the correct results bc we're missing the dual variables. 
        Pareto_ID_number = len(rehos_dict[list(rehos_dict.keys())[0]][Scn_ID].keys())
        REHO = False
        assert("Please provide a reho object and not reho.results for this function")


    # DATA FETCHING    
    # pi
    df_pi = pd.DataFrame()
    for Pareto_ID in range(Pareto_ID_number):
        if REHO:
            for name, reho in rehos_dict.items():
                pi = reho.results_MP[Scn_ID][Pareto_ID][0]["df_Dual_t"]["pi"].xs("Electricity")
                df_pi[name] = pi
    new_columns = pd.MultiIndex.from_product([['pi'], df_pi.columns], names=['activity', 'load'])
    df_pi.columns = new_columns

    # gathering electric load data
    df_costs = pd.DataFrame()
    for name, reho in rehos_dict.items():
        for Pareto_ID in range(Pareto_ID_number):
            df = reho.results[Scn_ID][Pareto_ID]["df_Unit_t"].copy()
            df = df.loc[:,df.columns.str.contains('EV_E_charged_outside')].xs('Electricity').dropna()
            df['demand'] = name
            df['Pareto_ID'] = Pareto_ID
            df.set_index("demand",append=True,inplace=True)
            df.set_index("Pareto_ID",append=True,inplace=True)
            new_columns = [x.split('[')[1].split(']')[0].split(',') for x in df.columns ]
            new_columns = [(x,int(y)) for (x,y) in new_columns]
            df.columns = pd.MultiIndex.from_tuples(new_columns,names=('activity','load'))
            df = df.merge(df_pi,left_index = True,right_index = True)
            df = df.reorder_levels(['load','activity'],axis=1)
            for l in df.columns.get_level_values('load').unique():
                results = df.loc[:,l].mul(df.loc[:,l]['pi'],axis = 0)
                results.columns = pd.MultiIndex.from_product([[l],results.columns])
                df.loc[:,l] = results
            df = df.loc[:, df.columns.get_level_values('activity') != 'pi']
            df_costs = pd.concat([df_costs,df])   


    df_home = pd.DataFrame()
    for name, reho in rehos_dict.items():
        for Pareto_ID in range(Pareto_ID_number):

            df_costNetwork = reho.results[Scn_ID][Pareto_ID]['df_Grid_t'].xs(('Electricity','Network'))[['Cost_supply']]
            df_CSdemand = reho.results[Scn_ID][Pareto_ID]['df_Unit_t'].xs('Electricity')
            df_CSdemand = df_CSdemand[df_CSdemand.index.get_level_values('Unit').isin(CS_unit)][['Units_demand']]
            df_CSdemand = df_CSdemand.join(df_costNetwork)
            df_CSdemand['CS_cost'] = df_CSdemand['Units_demand'].mul(df_CSdemand['Cost_supply'])
            df_CSdemand['demand'] = name
            df_CSdemand['Pareto_ID'] = Pareto_ID
            df_CSdemand.set_index("demand",append=True,inplace=True)
            df_CSdemand.set_index("Pareto_ID",append=True,inplace=True)
            df_CSdemand.columns = pd.MultiIndex.from_product([df_CSdemand.columns,['home']],names=('activity','load'))
            df_home = pd.concat([df_home,df_CSdemand[[('CS_cost','home')]]])

    df_costs = df_costs.merge(df_home,left_index=True,right_index=True,how='outer')

    # the finalized df is df_costs

    # PLOTTING
    tot = df_costs.groupby(['demand','Pareto_ID']).agg('sum')
    tot = tot.sum(axis = 1)


    return df_costs


if __name__ == '__main__':

    # SET-UP =====================================================================================================
    # Results files 
    # run_label = "10buil_14_1640"
    # districts = [277,3658,3112]
    # run_label = "EBIKE"
    # run_label = "EVactivity"
    # districts = ["noconstraints","maxshare","maxshare10km","relaxed"]
    # districts = ["calibrage","calibrated"]

    run_label = "lucerne_11_1000"
    districts = [ 7724,8538,13569 ,13219,13228]
    districts = [ 8538,13569 ,13219,13228]

    # pickle_files = [f'results/{run_label}_{d}.pickle' for d in districts] # filename format example : results/10buil_14_1640_277.pickle
    # from Cedric's folder :     
    pickle_files = [rf"Z:\data\Swice\Mobility\results\{run_label}_{d}.pickle" for d in districts]

    # Specifications for the graphs
    Pareto_IDs = [0,2] # which iteration(s) to generate for graphs that only plot 1 iter (especially for the pkm graphs)

    # PLOTTING =====================================================================================================
    for file,label in zip(pickle_files,districts):
        with open(file, 'rb') as handle:
            vars()[f"results{label}"] = pickle.load(handle)

    # from plotting library
    rehos_dict = dict()
    for label in districts:
        rehos_dict[label] = vars()[f"results{label}"]

    plot_cost_EV(rehos_dict)

    fig = plot_EVexternalloadandprice(rehos_dict,scenario = 'totex', run_label =  run_label)
    fig.write_html('plots\plot.html')
    fig.show()



    ## pkm profiles per typical day p.
    for label in districts:
        for p in Pareto_IDs:
            df_pkm, fig = plot_pkm(vars()[f"results{label}"].results['totex'][p],run_label=f"{run_label} - district {label} - iter {p}")
            fig.write_html(f'plots\pkm_{run_label[-7:]}_{label}_i{p}.html')
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