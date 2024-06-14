import calendar

import numpy as np
import pandas as pd

from reho.paths import *

__doc__ = """
Utilities for plotting functions.
"""


# Definition of colors and labels
cm = dict({'ardoise': '#413D3A', 'perle': '#CAC7C7', 'rouge': '#FF0000', 'groseille': '#B51F1F',
           'canard': '#007480', 'leman': '#00A79F', 'salmon': '#FEA993', 'green': '#69B58A', 'yellow': '#FFB100',
           'darkblue': '#1246B5', 'lightblue': '#8bacf4', 'perle_light': '#dad8d8',
           'canard_light': '#4d9ea6', 'leman_light': '#4dc2bc', 'salmon_light': '#fec3b4',
           'groseille_light': "#ff6666", 'darkyellow': '#A57300', 'dark': '#000000',
           'yellow_light': '#FECC93'})

# Colors and labels for units and layers
layout = pd.read_csv(os.path.join(path_to_plotting, 'layout.csv'), index_col='Name').dropna(how='all')


def dict_to_df(results, df):
    t = {(Scn_ID, Pareto_ID): results[Scn_ID][Pareto_ID][df]
         for Scn_ID in results.keys()
         for Pareto_ID in results[Scn_ID].keys()}

    df_merged = pd.concat(t.values(), keys=t.keys(), names=['Scn_ID', 'Pareto_ID'], axis=0)

    return df_merged


def moving_average(data, n):
    return np.convolve(data, np.ones(n), 'valid') / n


def handle_zero_rows(df):
    is_zero_row = (df == 0).all(axis=1)
    return df.loc[~is_zero_row]


def custom_round(value, decimal):
    if decimal == 0:
        rounded_value = int(round(value))
    elif decimal == 1:
        rounded_value = round(value, 1)
    else:
        raise ValueError("decimal argument must be 0 or 1")
    return rounded_value


def merge_handles_labels(ax):
    handles = []
    labels = []
    for axis in ax:
        handle, label = axis.get_legend_handles_labels()
        handles = handles + handle
        labels = labels + label

    handles.reverse()
    labels.reverse()
    by_label = dict(zip(labels, handles))
    return by_label


def monthly_average(results, df_to_extract):
    np_to_extract = np.array([])
    np_month = np.array([])
    ranges = divide_hours_into_months()
    for i in range(1, 366):
        hour = i * 24
        month = len(np_to_extract)
        id_period = results['df_Index'].PeriodOfYear[hour]
        data_id = df_to_extract.xs(id_period)
        np_month = np.concatenate((np_month, data_id))
        if ranges[month][1] == hour:
            np_to_extract = np.append(np_to_extract, np.sum(np_month) / (ranges[month][1] - ranges[month][0]))
            np_month = np.array([])

    return np_to_extract


def divide_hours_into_months():
    num_months = 12

    month_ranges = []
    start_hour = 1
    for month in range(num_months):
        days = calendar.monthrange(2023, month + 1)
        end_hour = start_hour + days[1] * 24 - 1
        month_ranges.append((start_hour, end_hour))
        start_hour = end_hour + 1

    return month_ranges


def prepare_dfs(df_Economics, indexed_on='Scn_ID', neg=False, premium_version=None, additional_data=None, scaling_factor=1):
    """
    This function prepares the dataframes that will be needed for the plot_performance and plot_expenses
    """
    if additional_data is None:
        additional_data = {}
    df_Economics = df_Economics.xs('Network', level='Hub', axis=0)
    df_Economics = df_Economics.groupby(level=indexed_on, sort=False).sum() * scaling_factor
    indexes = df_Economics.index.tolist()

    data_capacities = df_Economics.xs('investment', level='Category', axis=1).transpose()
    data_capacities.index.names = ['Unit']

    if 'isolation' in additional_data:
        data_capacities.loc['Isolation', :] = additional_data['isolation']

    data_capacities = data_capacities.reset_index().merge(layout, left_on="Unit", right_on='Name').set_index("Unit").fillna(0)

    data_resources = df_Economics.xs('operation', level='Category', axis=1).transpose()
    indices = data_resources.index.get_level_values(0)
    new_indices = []
    [new_indices.append(tuple(idx.split("_", 1))) for idx in indices]
    for i, tup in enumerate(new_indices):
        if tup == ('costs', 'Electricity'):
            new_indices[i] = ('costs', 'Electrical_grid')
        elif tup == ('revenues', 'Electricity'):
            new_indices[i] = ('revenues', 'Electrical_grid_feed_in')
    data_resources.index = pd.MultiIndex.from_tuples(new_indices, names=['type', 'Layer'])

    if premium_version is not None:
        data_resources.loc[('avoided', 'solar_premium'), :] = data_resources.loc[('avoided', 'PV_SC')] * (premium_version[0] - premium_version[1]) / \
                                                              premium_version[0]
        data_resources.loc[('revenues', 'solar_value'), :] = data_resources.loc[('revenues', 'Electrical_grid_feed_in')] + data_resources.loc[
            ('avoided', 'PV_SC')] - data_resources.loc[('avoided', 'solar_premium')]
        data_resources = data_resources.drop("PV_SC", level='Layer')
        data_resources = data_resources.drop("Electrical_grid_feed_in", level='Layer')

    data_resources = data_resources.drop("PV", level='Layer')

    if 'mobility' in additional_data:
        data_resources.loc[('costs', 'Gasoline'), :] = additional_data['mobility']

    if 'ict' in additional_data:
        data_resources.loc[('costs', 'Data'), :] = additional_data['ict']
        data_resources.loc[('revenues', 'Data'), :] = 0

    if neg:
        indices = data_resources.index.get_level_values(0)
        neg_indices = indices.str.contains('avoided')
        neg_indices = neg_indices + indices.str.contains('revenues')
        data_resources.loc[neg_indices] = - data_resources.loc[neg_indices]
    data_resources = data_resources.reset_index().merge(layout, left_on='Layer', right_on='Name').set_index(['type', 'Layer'])

    return indexes, data_capacities, data_resources


def remove_building_from_index(df):
    """
    Removes the Building_[123] appended to the name of the units in the index
    """

    def filter_building_str(str):
        str_split = str.split("_")
        if len(str_split) > 2:
            new_idx = "_".join(str.split("_", 2)[:2])
        else:
            new_idx = str_split[0]
        return new_idx

    new_index = []
    index_frame = df.index.to_frame()
    if 'Unit' in index_frame.columns:
        for idx in index_frame['Unit']:
            new_index.append(filter_building_str(idx))
        index_frame['Unit'] = new_index
    if 'Hub' in index_frame.columns:
        for idx in index_frame['Hub']:
            new_index.append(filter_building_str(idx))
        index_frame['Hub'] = new_index

    index_modified = pd.MultiIndex.from_frame(index_frame)

    return df.set_index(index_modified)
