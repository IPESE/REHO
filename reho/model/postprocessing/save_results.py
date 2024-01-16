import pandas as pd
import pickle
from reho.paths import *


def save_results(reho, save=('pickle'), filename='results', erase_file=True, filter=True):
    """
    Save the results in the desired format: pickle file or Excel sheet
    """
    try:
        os.makedirs('results')
    except OSError:
        if not os.path.isdir('results'):
            raise

    if 'save_all' in save:
        results = reho  # save the whole reho object
    else:
        results = reho.results  # save only reho results

    result_file_name = str(filename) + '.pickle'
    counter = 0
    while os.path.isfile('results/' + result_file_name) and not erase_file:
        counter += 1
        result_file_name = str(filename) + '_' + str(counter) + '.pickle'

    result_file_path = 'results/' + result_file_name
    f = open(result_file_path, 'wb')
    pickle.dump(results, f)
    f.close()
    print('Results are saved in ' + result_file_path)

    if 'xlsx' in save:

        for Scn_ID in list(results.keys()):
            for Pareto_ID in list(results[Scn_ID].keys()):

                if Pareto_ID == 0:
                    result_file_path = 'results/' + str(filename) + '_' + str(Scn_ID) + '.xlsx'
                else:
                    result_file_path = 'results/' + str(filename) + '_' + str(Scn_ID) + str(Pareto_ID) + '.xlsx'

                writer = pd.ExcelWriter(result_file_path)

                for df_name, df in results[Scn_ID][Pareto_ID].items():
                    if df is not None:
                        df = df.fillna(0)  # replace all NaN with zeros
                        if filter:
                            df = df.loc[~(df == 0).all(axis=1)]  # drop all lines with only zeros
                        df.to_excel(writer, sheet_name=df_name)

                writer.close()
                print('Results are saved in ' + result_file_path)
