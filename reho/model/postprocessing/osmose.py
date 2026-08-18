import os

import numpy as np
import pandas as pd

__doc__ = """
Aggregates the buildings thermal demands into heat and cold streams, ready to be used in OSMOSE.
"""

# Service: (demand column, inlet temperature, outlet temperature, OSMOSE stream type)
# Temperatures are either a column of df_Buildings_t or a constant value.
services = {
    'SH': ('House_Q_heating', 'Th_return', 'Th_supply', 'cold'),
    'DHW': ('House_Q_DHW', 10.0, 60.0, 'cold'),  # DHW_T_min and DHW_T_max, as defined in units/dhwstorage.mod
    'Cooling': ('House_Q_cooling', 'Tc_return', 'Tc_supply', 'hot')
}


def get_osmose_streams(results, tolerance=10.0, per_building=False, time_resolved=False, filename=None):
    """
    Converts the buildings space heating, domestic hot water, and cooling demands into a list of heat and cold streams.

    For each timestep, a building demand is a thermal stream flowing from its return to its supply temperature.
    Streams are grouped together when they belong to the same service and their inlet and outlet temperatures both lie
    within ``tolerance`` degrees of the same temperature level, i.e. when they have the same temperature interval
    (e.g. 40°C to 20°C) at ``± tolerance``.

    Parameters
    ----------
    results : dict or str
        REHO results, either as a dictionary of dictionaries (``results[Scn_ID][Pareto_ID]``) or as the path to the
        pickle file where they have been saved.
    tolerance : float
        Half-width of the temperature levels, in °C. Temperatures are snapped to the closest multiple of
        2 * `tolerance`, so that everything within ± `tolerance` of a level is grouped as one stream.
    per_building : bool
        If True, the streams are returned per building instead of being aggregated over the district.
    time_resolved : bool
        If True, the load of each stream is returned for every (Period, Time) instead of being aggregated annually.
    filename : str
        If given, path of the csv file where the streams are written.

    Returns
    -------
    pd.DataFrame
        The streams, indexed by *Scn_ID*, *Pareto_ID*, *Stream* (plus *Hub* if `per_building`, and *Period* and *Time*
        if `time_resolved`), with the following columns:

        - *Service*: 'SH' (space heating), 'DHW' (domestic hot water), or 'Cooling' (cooling demand).
        - *Type*: OSMOSE stream type, i.e. 'cold' for a heating demand (it requires a hot utility) and 'hot' for a
          cooling demand (it requires a cold utility).
        - *T_in*, *T_out*: inlet and outlet temperatures of the stream [°C], averaged over the grouped demands.
        - *dT*: temperature difference of the stream [°C], negative for a hot stream.
        - *q_kW*: thermal load of the stream [kW] (the maximum load over the year if not `time_resolved`).
        - *Q_MWh*: yearly energy of the stream [MWh], i.e. the sum over all timesteps of the load times the yearly
          duration of the timestep (not returned if `time_resolved`).
        - *hours*: yearly duration of the stream [h] (not returned if `time_resolved`).

    Notes
    -----
    - The cooling temperatures are only available in ``df_Buildings_t`` for results generated with REHO >= 1.2.1.
      For older results, the nominal temperatures (*Tc_supply_0*, *Tc_return_0*) are used instead.
    - The DHW demand is a stream from *DHW_T_min* to *DHW_T_max*, the tank temperatures hardcoded in
      ``units/dhwstorage.mod``. They are the same for all buildings, so DHW gives a single stream.
    - The extreme periods (dp = 0) are accounted for in the loads but not in the yearly energies and durations.

    Examples
    --------
    >>> get_osmose_streams(reho.results)
    >>> get_osmose_streams('results/2b.pickle', tolerance=5, filename='osmose_streams.csv')
    """

    if isinstance(results, (str, os.PathLike)):
        results = pd.read_pickle(results)

    df_streams = {(Scn_ID, Pareto_ID): _build_streams(results[Scn_ID][Pareto_ID], tolerance, per_building, time_resolved)
                  for Scn_ID in results for Pareto_ID in results[Scn_ID]}
    df_streams = pd.concat(df_streams.values(), keys=df_streams.keys(), names=['Scn_ID', 'Pareto_ID'])

    if filename is not None:
        df_streams.to_csv(filename)

    return df_streams


def _build_streams(df_Results, tolerance, per_building, time_resolved):
    df_Buildings_t = df_Results['df_Buildings_t']
    df_Time = df_Results['df_Time']

    # yearly duration of a timestep [h], null for the extreme periods
    periods = df_Buildings_t.index.get_level_values('Period')
    dt = periods.map(df_Time['dt'])
    hours = periods.map(df_Time['dp']) * dt

    df = pd.concat([_demand_as_stream(df_Results, service, hours, dt) for service in services])
    df = df[df['q_kW'] > 0]

    # snap the temperatures to the closest temperature level to identify the streams
    level = 2 * tolerance
    T_in = (df['T_in'] / level).round() * level
    T_out = (df['T_out'] / level).round() * level
    df['Stream'] = df['Service'] + T_in.map('_{:g}'.format) + T_out.map('_{:g}'.format)

    # temperatures are averaged over the streams, weighted by their load
    df['T_in'] = df['T_in'] * df['w']
    df['T_out'] = df['T_out'] * df['w']

    index = ['Stream', 'Service', 'Type'] + (['Hub'] if per_building else [])
    df = df.groupby(index + ['Period', 'Time'], sort=False).sum()
    if not time_resolved:
        df = pd.concat([df[['q_kW']].groupby(index, sort=False).max(),
                        df.drop(columns='q_kW').groupby(index, sort=False).sum()], axis=1)

    df['T_in'] = df['T_in'] / df['w']
    df['T_out'] = df['T_out'] / df['w']
    df['dT'] = df['T_out'] - df['T_in']
    df['Q_MWh'] = df['Q_kWh'] / 1000

    columns = ['T_in', 'T_out', 'dT', 'q_kW'] + ([] if time_resolved else ['Q_MWh', 'hours'])
    return df.reset_index(['Service', 'Type'])[['Service', 'Type'] + columns].sort_index()


def _demand_as_stream(df_Results, service, hours, dt):
    df_Buildings_t = df_Results['df_Buildings_t']
    demand, T_in, T_out, stream_type = services[service]

    df = pd.DataFrame(index=df_Buildings_t.index)
    df['Service'] = service
    df['Type'] = stream_type
    df['q_kW'] = df_Buildings_t[demand] if demand in df_Buildings_t else 0.0
    for T, source in [('T_in', T_in), ('T_out', T_out)]:
        if not isinstance(source, str):
            df[T] = source
        elif source in df_Buildings_t:
            df[T] = df_Buildings_t[source]
        else:
            # fall back on the nominal temperatures when the profiles are not available (cooling)
            nominal = df_Results['df_Buildings'][source + '_0']
            df[T] = df_Buildings_t.index.get_level_values('Hub').map(nominal)

    df['hours'] = hours
    df['Q_kWh'] = df['q_kW'] * hours
    df['w'] = df['q_kW'] * np.maximum(hours, dt)  # weighting of the temperatures, robust to the extreme periods

    return df
