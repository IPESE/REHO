import pandas as pd

from reho.model.reho import *
from reho.plotting.plotting import *

import datetime


if __name__ == '__main__':

    pickle_files = ["results/standalone_2dchargers13_1516_3658.pickle","results/standalone_2dchargers13_1516_3112.pickle"]
    # pickle_files = ['results/standalone_iter3_277.pickle','results/standalone_iter3_3658.pickle','results/standalone_iter3_3112.pickle']
    pickle_files = ['results/6iter_14_1640_277.pickle', 'results/6iter_14_1640_3658.pickle',
                     'results/6iter_14_1640_3112.pickle']
    # pickle_files = [ 'results/6iter_14_1347_3658.pickle',
    #                  'results/6iter_14_1347_3112.pickle']

    labels = range(len(pickle_files))
    labels = [277,3658,3112]
    # labels = [ 3658, 3112]

    if len(pickle_files) == 1:
        with open(pickle_files[0], 'rb') as handle:
            results = pickle.load(handle)
    else:
        for file,label in zip(pickle_files,labels):
            with open(file, 'rb') as handle:
                vars()[f"results{label}"] = pickle.load(handle)

    # from plotting library
    rehos_dict = dict()
    for label in labels:
        rehos_dict[label] = vars()[f"results{label}"]

    fig = plot_EVexternalloadandprice(rehos_dict,scenario = 'totex')
    fig.write_html('plots\plot.html')
    fig.show()


    print(results)