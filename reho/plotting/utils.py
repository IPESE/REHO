import calendar

import numpy as np
import pandas as pd

import os

from reho.model.preprocessing.weather import get_cluster_file_ID  # noqa: F401  (re-exported)
from reho.paths import path_to_plotting

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


def hex_to_rgb(value, transparency=0.5):
    """
    Convert a hexadecimal color into a Plotly ``rgba`` color string.

    Parameters
    ----------
    value : str
        Color in six-digit hexadecimal notation, with or without the leading ``#`` (e.g. ``'#007480'``).
    transparency : float, optional
        Alpha channel, from 0 (transparent) to 1 (opaque). Default is 0.5.

    Returns
    -------
    str
        The color as ``'rgba(r, g, b, transparency)'``.
    """
    value = value.lstrip('#')
    lv = len(value)
    rgb = tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))
    return "rgba" + str(rgb)[:-1] + ", " + str(transparency) + ")"


def dict_to_df(results, df):
    """
    Gather one result DataFrame across every scenario and Pareto point.

    Parameters
    ----------
    results : dict
        REHO results nested as ``results[Scn_ID][Pareto_ID]``, i.e. ``reho.results``.
    df : str
        Name of the DataFrame to gather, e.g. ``'df_Performance'``.

    Returns
    -------
    pandas.DataFrame
        The DataFrames stacked on top of each other, with the index levels ``Scn_ID`` and
        ``Pareto_ID`` prepended to their own index.
    """
    t = {(Scn_ID, Pareto_ID): results[Scn_ID][Pareto_ID][df]
         for Scn_ID in results.keys()
         for Pareto_ID in results[Scn_ID].keys()}

    df_merged = pd.concat(t.values(), keys=t.keys(), names=['Scn_ID', 'Pareto_ID'], axis=0)

    return df_merged


def moving_average(data, n):
    """
    Smooth a profile with a simple moving average.

    Parameters
    ----------
    data : array-like
        One-dimensional values to smooth.
    n : int
        Window length, in number of values.

    Returns
    -------
    numpy.ndarray
        The average over each complete window, hence ``n - 1`` values shorter than ``data``.
    """
    return np.convolve(data, np.ones(n), 'valid') / n


def handle_zero_rows(df):
    """
    Drop the rows of a DataFrame whose values are all zero.

    Parameters
    ----------
    df : pandas.DataFrame
        Data to filter.

    Returns
    -------
    pandas.DataFrame
        ``df`` without its all-zero rows.
    """
    is_zero_row = (df == 0).all(axis=1)
    return df.loc[~is_zero_row]


def custom_round(value, decimal):
    """
    Round a value for display in a plot label.

    Parameters
    ----------
    value : float
        Value to round.
    decimal : int
        Number of decimals to keep: 0 or 1.

    Returns
    -------
    int or float
        ``value`` as an integer when ``decimal`` is 0, rounded to one decimal otherwise.

    Raises
    ------
    ValueError
        If ``decimal`` is neither 0 nor 1.
    """
    if decimal == 0:
        rounded_value = int(round(value))
    elif decimal == 1:
        rounded_value = round(value, 1)
    else:
        raise ValueError("decimal argument must be 0 or 1")
    return rounded_value


def merge_handles_labels(ax):
    """
    Gather the legend entries of several matplotlib axes, to draw a single legend.

    Parameters
    ----------
    ax : iterable of matplotlib.axes.Axes
        Axes whose legend handles and labels are collected.

    Returns
    -------
    dict
        Label -> handle, in the reverse order of appearance. A label shared by several axes is
        kept once, with the handle of the first axes that uses it.

    Examples
    --------
    >>> by_label = merge_handles_labels([ax_left, ax_right])
    >>> fig.legend(by_label.values(), by_label.keys())
    """
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
    """
    Compute the monthly averages of a profile defined on the typical periods.

    Each day of the year is mapped to its typical period through ``results['df_Index']``, the
    values of that period are appended to the current month, and the month is averaged once
    its last hour is reached.

    Parameters
    ----------
    results : dict
        Results of one optimization, i.e. ``reho.results[Scn_ID][Pareto_ID]``.
    df_to_extract : pandas.Series
        Hourly values indexed by ``(Period, Time)``, without the extreme periods.

    Returns
    -------
    numpy.ndarray
        Twelve values, the average hourly value of each month.

    Notes
    -----
    Assumes a 365-day year and typical periods of 24 hours, see :func:`divide_hours_into_months`.
    """
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
    """
    Split the hours of a non-leap year into months.

    Returns
    -------
    list of tuple of int
        Twelve ``(first_hour, last_hour)`` pairs, inclusive and counted from 1:
        ``[(1, 744), (745, 1416), ...]``.
    """
    num_months = 12

    month_ranges = []
    start_hour = 1
    for month in range(num_months):
        days = calendar.monthrange(2023, month + 1)
        end_hour = start_hour + days[1] * 24 - 1
        month_ranges.append((start_hour, end_hour))
        start_hour = end_hour + 1

    return month_ranges


def prepare_dfs(df_Economics, indexed_on='Scn_ID', neg=False, include_avoided=False, additional_data=None, scaling_factor=1):
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

    if 'renovation' in additional_data:
        data_capacities.loc['renovation', :] = additional_data['renovation']
    if 'subsidies' in additional_data:
        data_capacities.loc['Subsidies', :] = additional_data['subsidies']

    data_capacities = data_capacities.reset_index().merge(layout, left_on="Unit", right_on='Name').set_index("Unit").fillna(0)

    data_resources = df_Economics.xs('operation', level='Category', axis=1).transpose()
    indices = data_resources.index.get_level_values(0)
    new_indices = []
    [new_indices.append(tuple(idx.split("_", 1))) for idx in indices]

    energy_layers = ['Electricity', 'Heat', 'Oil', 'NaturalGas', 'Gasoline', 'Wood', 'Hydrogen', 'Biomethane', 'Data']

    for i, tup in enumerate(new_indices):
        for energy in energy_layers:
            if tup == ('costs', energy):
                new_indices[i] = ('costs', f'{energy}_import')
                break
            elif tup == ('revenues', energy):
                new_indices[i] = ('revenues', f'{energy}_export')
                break

    data_resources.index = pd.MultiIndex.from_tuples(new_indices, names=['type', 'Layer'])

    if include_avoided is not False:

        data_resources.loc[('costs', 'Electricity_import'), :] = data_resources.loc[('costs', 'Electricity_import'), :] + data_resources.loc[('avoided', 'PV_SC'), :]
        if include_avoided is True:
            pass
        elif 'sc_premium' in include_avoided:
            retail_price = include_avoided['sc_premium'][0]
            feedin_price = include_avoided['sc_premium'][1]

            data_resources.loc[('revenues', 'solar_value'), :] = data_resources.loc[('revenues', 'Electricity_export')] + feedin_price * data_resources.loc[
                ('avoided', 'PV_SC')] / retail_price

            data_resources.loc[('avoided', 'sc_premium'), :] = data_resources.loc[('avoided', 'PV_SC')] * (retail_price - feedin_price) / retail_price

            data_resources = data_resources.drop("PV_SC", level='Layer')
            data_resources = data_resources.drop("Electricity_export", level='Layer')
    else:
        data_resources.loc[('avoided', 'PV_SC'), :] = 0

    data_resources = data_resources.drop("PV", level='Layer')

    if 'mobility' in additional_data:
        data_resources.loc[('costs', 'Gasoline_import'), :] = additional_data['mobility']

    if 'ict' in additional_data:
        data_resources.loc[('costs', 'Data_export'), :] = additional_data['ict']
    if additional_data.get('no_ict_profit', False):
        data_resources.loc[('revenues', 'Data_export'), :] = 0

    if neg:
        indices = data_resources.index.get_level_values(0)
        neg_indices = indices.str.contains('avoided')
        neg_indices = neg_indices + indices.str.contains('revenues')
        data_resources.loc[neg_indices] = - data_resources.loc[neg_indices]
    data_resources = data_resources.reset_index().merge(layout, left_on='Layer', right_on='Name').set_index(['type', 'Layer'])

    return indexes, data_capacities, data_resources


def remove_building_from_index(df):
    """Strip the building suffix from the ``Unit`` and ``Hub`` index levels.

    ``'HeatPump_Air_Building1'`` becomes ``'HeatPump_Air'``, so that the same
    technology installed in several buildings aggregates into one series when
    plotting.

    Parameters
    ----------
    df : pandas.DataFrame
        Frame whose index has a ``Unit`` and/or a ``Hub`` level.

    Returns
    -------
    pandas.DataFrame
        The same frame, re-indexed.

    See also
    --------
    reho.model.postprocessing.KPIs.remove_building_from_index
        Same name, different purpose: it *splits* the building out into its own
        index level rather than discarding it.
    """

    def strip_building(name):
        parts = str(name).split("_")
        # Unit names are '<type>_<variant>_<building>' or '<type>_<building>'.
        return "_".join(parts[:2]) if len(parts) > 2 else parts[0]

    index_frame = df.index.to_frame()
    for level in ("Unit", "Hub"):
        if level in index_frame.columns:
            index_frame[level] = [strip_building(value) for value in index_frame[level]]

    return df.set_index(pd.MultiIndex.from_frame(index_frame))
