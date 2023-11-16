import pandas as pd
import pickle
from reho.paths import *

def save_reho(reho, filename='results', erase_file=True):
    """
    Save the whole REHO object
    """
    try:
        os.makedirs('results')
    except OSError:
        if not os.path.isdir('results'):
            raise

    result_file_name = str(filename) + '.pickle'
    counter = 0
    while os.path.isfile('results/' + result_file_name) and not erase_file:
        counter += 1
        result_file_name = str(filename) + '_' + str(counter) + '.pickle'

    result_file_path = 'results/' + result_file_name
    f = open(result_file_path, 'wb')
    pickle.dump(reho, f)
    f.close()
    print('REHO object is saved in ' + result_file_path)

def save_results(reho, save=('pickle'), filename='results' , erase_file=True, filter=True):
    """
    Save the dataframes contained in results (dataframes_results object) in the desired format: dictionary or excel sheet
    """
    try:
        os.makedirs('results')
    except OSError:
        if not os.path.isdir('results'):
            raise

    result_file_name = str(filename) + '.pickle'
    counter = 0
    while os.path.isfile('results/' + result_file_name) and not erase_file:
        counter += 1
        result_file_name = str(filename) + '_' + str(counter) + '.pickle'

    if 'pickle_all' in save:
        results = reho

    if 'pickle' in save:
        # translate into dictionary for Rmarkdown
        results = dict()
        for Scn_ID in list(reho.results.keys()):
            for Pareto_ID in list(reho.results[Scn_ID].keys()):
                reho.results[Scn_ID][Pareto_ID] = reho.results[Scn_ID][Pareto_ID].__dict__
                if filter:
                    for df_name, df in reho.results[Scn_ID][Pareto_ID].items():
                        df = df.fillna(0)  # replace all NaN with zeros
                        df = df.loc[~(df == 0).all(axis=1)]  # drop all lines with only zeros

            results[Scn_ID] = {Pareto_ID: reho.results[Scn_ID][Pareto_ID] for Pareto_ID in reho.results[Scn_ID]}

    if 'pickle3d' in save:
        # translate into dictionary for Rmarkdown
        results = dict()
        for Scn_ID in list(reho.results.keys()):
            results[Scn_ID] = dict()
            for Pareto_ID in list(reho.results[Scn_ID].keys()):
                for Third_ID in list(reho.results[Scn_ID][Pareto_ID].keys()):
                    reho.results[Scn_ID][Pareto_ID][Third_ID] = reho.results[Scn_ID][Pareto_ID][Third_ID].__dict__
                    if filter:
                        for df_name, df in reho.results[Scn_ID][Pareto_ID][Third_ID].items():
                            df = df.fillna(0)  # replace all NaN with zeros
                            df = df.loc[~(df == 0).all(axis=1)]  # drop all lines with only zeros

                results[Scn_ID][Pareto_ID] = {Third_ID: reho.results[Scn_ID][Pareto_ID][Third_ID]
                                             for Third_ID in reho.results[Scn_ID][Pareto_ID]}

    # save results
    result_file_path = 'results/' + result_file_name
    f = open(result_file_path, 'wb')
    pickle.dump(results, f)
    f.close()
    print('results are saved in ' + result_file_path)

    if 'xlsx' in save:

        for Scn_ID in list(reho.results.keys()):

            for Pareto_ID in list(reho.results[Scn_ID].keys()):
                if not isinstance(reho.results[Scn_ID][Pareto_ID], dict):
                    dataframes = reho.results[Scn_ID][Pareto_ID].__dict__
                else:
                    dataframes = reho.results[Scn_ID][Pareto_ID]

                if Pareto_ID == 0:
                    result_file_path = 'results/' + str(filename) + '_' + str(Scn_ID) + '.xlsx'
                else:
                    result_file_path = 'results/' + str(filename) + '_' + str(Scn_ID) + str(Pareto_ID) + '.xlsx'

                writer = pd.ExcelWriter(result_file_path)

                for df_name, df in dataframes.items():
                    if df is not None:
                        df = df.fillna(0)  # replace all NaN with zeros
                        if filter:
                            df = df.loc[~(df == 0).all(axis=1)]  # drop all lines with only zeros
                        df.to_excel(writer, sheet_name=df_name)
                        worksheet = writer.sheets[df_name]  # pull worksheet object
                writer.close()
                print('results are saved in ' + result_file_path)
