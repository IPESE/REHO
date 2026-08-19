import configparser
import csv
import math
import os.path
import re
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import wkt
from sqlalchemy import create_engine, MetaData, select, and_, func, String, text
from sqlalchemy.exc import SAWarning

from reho.paths import *

__doc__ = """
Handles data for buildings characterization.
"""

df_dome = pd.read_csv(os.path.join(path_to_skydome, 'skydome.csv'))

CRS_QBUILDINGS = 2056  # Swiss coordinate system (CH1903+ / LV95) used in QBuildings


class QBuildingsReader:
    """
    Handles and prepares the data related to buildings.

    There usually come from `QBuildings <https://qbuildings.epfl.ch/>`_ database. However,
    one can use data from a csv, in which case the column names should correspond to the GBuildings one, described in "Processed" tables.

    Parameters
    ----------
    load_facades : bool
        Whether the facades data should be added.
    load_roofs : bool
        Whether the roofs data should be added.
    """

    # Filter layer -> column of the `buildings` table on which it is applied
    LAYER_COLUMNS = {
        'transformers': 'transformer',
        'transformer': 'transformer',
        'transformers_V2': 'id_transformers_V2',
        'geo_girec': 'geo_girec',
        'neighborhoods': 'id_neighborhood',
        'neighborhood': 'id_neighborhood',
        'egid': 'egid',
        'id_building': 'id_building',
    }

    # Filter layer -> table holding the corresponding district boundaries
    DISTRICT_TABLES = {
        'transformers': 'transformers',
        'transformer': 'transformers',
        'transformers_V2': 'transformers_V2',
        'geo_girec': 'geo_girec',
        'neighborhoods': 'neighborhoods',
        'neighborhood': 'neighborhoods',
    }

    # source_heating keyword -> unit(s) implementing it. Several sources can be listed (e.g. "Oil/Electricity").
    HEATING_SOURCE_TO_UNITS = {
        'oil':           ['OIL_Boiler'],
        'gas':           ['NG_Boiler'],
        'wood':          ['WOOD_Stove'],
        'electricity':   ['ElectricalHeater_SH', 'ElectricalHeater_DHW'],
        'district heat': ['DHN_hex'],
    }

    # source_hotwater keyword -> unit(s) implementing it. 'wood' is absent: WOOD_Stove only serves SH.
    HOTWATER_SOURCE_TO_UNITS = {
        'oil':           ['OIL_Boiler'],
        'gas':           ['NG_Boiler'],
        'electricity':   ['ElectricalHeater_DHW'],
        'district heat': ['DHN_hex'],
        'solar':         ['ThermalSolar'],
    }

    # Units that can be a primary heating/DHW system, i.e. that compete with each other.
    PRIMARY_HEATING_UNITS = {unit for units in HEATING_SOURCE_TO_UNITS.values() for unit in units} | {
        'HeatPump_Air', 'HeatPump_Geothermal', 'HeatPump_DHN', 'HeatPump_Lake', 'ThermalSolar',
    }

    # Units whose UnitOfService contains 'DHW'. WOOD_Stove and ElectricalHeater_SH serve SH only.
    DHW_CAPABLE_UNITS = {
        'OIL_Boiler', 'NG_Boiler', 'ElectricalHeater_DHW', 'DHN_hex',
        'HeatPump_Air', 'HeatPump_Geothermal', 'HeatPump_DHN', 'HeatPump_Lake', 'ThermalSolar',
    }

    # Date of the databases predating the [DATE] tag in their table descriptions
    DEFAULT_DB_DATE = '2023'

    def __init__(self, load_facades=False, load_roofs=False, correct_Uh=False):

        self.db = None
        self.tables = None
        self.db_schema = None
        self.db_engine = None
        self.connection = None
        self.data = {}
        self.load_facades = load_facades
        self.load_roofs = load_roofs
        self.correct_Uh = correct_Uh

    def establish_connection(self, db):
        """
        Allows to establish the connection with one of the QBuildings database.

        Parameters
        ----------
        db : str
            Name of the database to which we want to connect

        """
        # Database connection
        file_ini = path_to_qbuildings + "/" + db + ".ini"

        project = configparser.ConfigParser()
        project.read(file_ini)

        # Database
        self.db_schema = "Processed"
        try:
            db_engine_str = 'postgresql+psycopg2://{}:{}@{}:{}/{}'.format(project['database']['username'],
                                                                          project['database']['password'],
                                                                          project['database']['host'],
                                                                          project['database']['port'],
                                                                          project['database']['database'])
            self.db_engine = create_engine(db_engine_str)
            self.connection = self.db_engine.connect()  # test connection
            print('Connected to database')

        except Exception as e:
            print(f'Cannot connect to database engine: {e}')

        if 'database' in project:
            print('\thost: {}\n\tport: {}\n\tdatabase: {}\n\tusername: {}'.format(
                project['database']['host'],
                project['database']['port'],
                project['database']['database'],
                project['database']['username']))

        # input
        warnings.filterwarnings('ignore', category=SAWarning)
        metadata = MetaData()
        metadata.reflect(bind=self.db_engine, schema=self.db_schema)
        self.tables = metadata.tables
        self.db = db

        return

    def read_date_from_description(self, table='buildings'):
        """
        Reads the date tagged as ``[DATE]`` in the description of a table of the database.

        Parameters
        ----------
        table : str
            Name of the table whose description is read.

        Returns
        -------
        str
            The date found, or ``DEFAULT_DB_DATE`` for the databases predating the tag.
        """
        description = None
        if self.connection is not None:
            query = text("SELECT obj_description(CAST(:table AS regclass))")
            try:
                description = self.connection.execute(query, {'table': '"%s".%s' % (self.db_schema, table)}).scalar()
            except Exception as e:
                warnings.warn("Could not read the description of the table '%s': %s" % (table, e))

        match = re.search(r'\[DATE\]\s*:?\s*([\w-]+)', description or '')
        return match.group(1) if match else self.DEFAULT_DB_DATE

    def read_csv(self, buildings_filename='data/buildings.csv', nb_buildings=None, roofs_filename='data/roofs.csv', facades_filename='data/facades.csv'):
        """
        Reads buildings-related data from CSV files and prepare it for the REHO model.

        If not all the buildings from the file should be extracted, one can give a number of buildings.
        The fields from the files are translated to the corresponding ones used in REHO.

        Parameters
        ----------
        buildings_filename : str
            The filename of the CSV file containing buildings data.
        nb_buildings : int, optional
            The number of buildings to consider. If not provided, all buildings in the file are considered.
        roofs_filename : str, optional
            The filename of the CSV file containing roofs data.
        facades_filename : str, optional
            The filename of the CSV file containing facades data.

        Returns
        -------
        dict
            A dictionary containing the prepared data for the REHO model, including buildings, facades, roofs,
            and shadows if roofs and facades are loaded.

        Notes
        -----
        - If ``nb_buildings`` is not provided, all buildings in the 'buildings' data are considered.
        - If ``load_roofs = True``, `roofs_filename` must be provided, else it is not useful. Same goes for the facades.

        Example
        -------
        >>> from reho.model.reho import *
        >>> reader = QBuildingsReader(load_roofs=True)
        >>> qbuildings_data = reader.read_csv("buildings.csv", roofs_filename="roofs.csv", nb_buildings=7)

        >>> qbuildings_data['buildings_data'].keys()
        dict_keys(['Building1', 'Building2', 'Building3'])

        >>> qbuildings_data['buildings_data']['Building1'].keys()
        dict_keys(['id_class', 'ratio', 'status', 'ERA', 'SolarRoofArea', 'area_facade_m2', 'height_m', 'U_h', 'HeatCapacity', 'T_comfort_min_0', 'Th_supply_0', 'Th_return_0', 'Tc_supply_0', 'Tc_return_0', 'x', 'y', 'z', 'geometry', 'transformer', 'id_building', 'egid', 'period', 'n_p', 'energy_heating_signature_kWh_y', 'energy_cooling_signature_kWh_y', 'energy_hotwater_signature_kWh_y', 'energy_el_kWh_y'])
        """
        self.data['buildings'] = file_reader(buildings_filename)
        self.data['buildings'] = translate_buildings_to_REHO(self.data['buildings'])

        if nb_buildings is None:
            nb_buildings = self.data['buildings'].shape[0]
        buildings = self.select_buildings_data(nb_buildings)
        qbuildings = {'buildings_data': buildings}
        if self.load_facades:
            self.data['facades'] = file_reader(path_handler(facades_filename))
            selected_facades = self.select_roofs_or_facades_data(roof=False)
            self.data['facades'] = self.data['facades'][self.data['facades'].index.isin(selected_facades)]
            self.data['facades'] = read_geometry(self.data['facades'])
            self.data['facades'] = translate_facades_to_REHO(self.data['facades'], self.data['buildings'])
            qbuildings['facades_data'] = self.data['facades']
            qbuildings['shadows_data'] = return_shadows_district(qbuildings['buildings_data'], self.data['facades'])

        if self.load_roofs:
            self.data['roofs'] = file_reader(path_handler(roofs_filename))
            selected_roofs = self.select_roofs_or_facades_data(roof=True)
            self.data['roofs'] = self.data['roofs'][self.data['roofs'].index.isin(selected_roofs)]
            self.data['roofs'] = read_geometry(self.data['roofs'])
            self.data['roofs'] = translate_roofs_to_REHO(self.data['roofs'])
            qbuildings['roofs_data'] = self.data['roofs']

        if self.correct_Uh:
            qbuildings["buildings_data"] = get_Uh_corrected(qbuildings["buildings_data"], df_facades=qbuildings["facades_data"])

        qbuildings['data_source'] = buildings_filename
        qbuildings['data_date'] = None
        return qbuildings

    def read_db(self, filters=None, nb_buildings=None, to_csv=False,
                district_boundary=None, district_id=None, egid=None, id_building=None):
        """
        Reads the database and extracts the relevant buildings data.

        The selection is driven by a ``{layer: value}`` dictionary, where each entry restricts the
        buildings to those matching the given layer. The district(s) to which the selected buildings
        belong are retrieved as well, and the fields are translated to the nomenclature used in REHO.

        Parameters
        ----------
        filters : dict
            Selection criteria, given as ``{layer: value}`` and combined with a logical AND. Values
            can be a scalar or a list. The available layers are:

            - ``transformers`` : LV transformer area (default district boundary in QBuildings)
            - ``transformers_V2`` : alternative LV transformer areas
            - ``geo_girec`` : GIREC statistical sectors
            - ``neighborhoods`` : neighborhoods
            - ``egid`` : buildings EGIDs
            - ``id_building`` : QBuildings internal building IDs
            - ``geometry`` : any geometry, given as a file path (.gpkg, .shp, .geojson...), a WKT
              string, a shapely geometry or a (Geo)DataFrame. Buildings intersecting it are selected.

            Not every layer exists in every database (e.g. ``geo_girec`` is specific to Geneva).
        nb_buildings : int
            Number of buildings to select.
        to_csv : bool
            To export the data into csv.
        district_boundary, district_id, egid, id_building
            Deprecated, kept for backward compatibility. Use ``filters`` instead.

        Returns
        -------
        dict
            A dictionary that contains the qbuildings data. The default has only one key ``buildings_data``
            with a dictionary of buildings, with their fields and corresponding values.


        Notes
        -----
        - The use of this function requires the previous creation of a ``QBuildingsReader`` and the use of ``establish_connection('Suisse')``.
        - EGIDs are the postal address unique identifier used in Switzerland. One can find the EGIDs of a given address at the `RegBL <https://www.housing-stat.ch/fr/query/adrtoegid.html>`_.
        - Geometries are expected in EPSG:2056 (LV95); files carrying their own CRS are reprojected.
        - If ``load_roofs = True`` the roofs are returned as well in the dictionary as a DataFrame under the key ``roofs_data``.
        - If ``load_facades = True`` the facades and the shadows are returned as well in the dictionary as a DataFrame under the keys ``roofs_data`` and ``shadows_data``.

        Examples
        --------
        >>> from reho.model.reho import *
        >>> reader = QBuildingsReader(load_roofs=True)
        >>> reader.establish_connection('Suisse')
        >>> qbuildings_data = reader.read_db({'egid': 954117})
        >>> qbuildings_data = reader.read_db({'id_building': [40214, 40215]})
        >>> qbuildings_data = reader.read_db({'transformers': 3658}, nb_buildings=10)
        >>> qbuildings_data = reader.read_db({'neighborhoods': 10302})
        >>> qbuildings_data = reader.read_db({'geometry': 'boundary.gpkg'})
        >>> qbuildings_data = reader.read_db({'geometry': 'MULTIPOLYGON (((2592684 1120074, ...)))'})

        >>> # filters are combined, here the buildings of a transformer that lie in a given perimeter
        >>> qbuildings_data = reader.read_db({'transformers': 3658, 'geometry': 'boundary.gpkg'})

        >>> qbuildings_data['buildings_data']
        {'buildings_data': {'Building1': {'id_class': 'I', 'ratio': '1.0', 'status': "['existing', 'existing', 'existing']", 'ERA': 1396.0, 'SolarRoofArea': 1121.8206745917826, 'area_facade_m2': 848.6771960464813, 'height_m': 9.211343577064236, 'U_h': 0.00152, 'HeatCapacity': 120.29999999999991, 'T_comfort_min_0': 20.0, 'Th_supply_0': 65.0, 'Th_return_0': 50.0, 'Tc_supply_0': 12.0, 'Tc_return_0': 17.0, 'x': 2592703.9673297284, 'y': 1120087.7339999992, 'z': 572.4461527539248, 'geometry': <POLYGON ((2592684.383 1120074.623, 2592683.644 1120075.443, 2592679.083 112...>, 'transformer': 3658, 'id_building': '40214', 'egid': '954117', 'period': '1981-1990', 'n_p': 34.9, 'energy_heating_signature_kWh_y': 111855.52745599969, 'energy_cooling_signature_kWh_y': 0.0, 'energy_hotwater_signature_kWh_y': 4562.903646729638, 'energy_el_kWh_y': 39088.0}}

        >>> qbuildings_data['roofs_data']
            TILT  ...                                           geometry
        0     26  ...  MULTIPOLYGON (((2592819.164 1120187.216, 25928...
        1     25  ...  MULTIPOLYGON (((2592832.585 1120154.503, 25928...
        2     25  ...  MULTIPOLYGON (((2592819.164 1120187.216, 25928...
        3     26  ...  MULTIPOLYGON (((2592824.929 1120157.956, 25928...
        0     19  ...  MULTIPOLYGON (((2592378.668 1120324.589, 25923...
        ..   ...  ...                                                ...
        25     0  ...  MULTIPOLYGON (((2592872.699 1120127.178, 25928...
        26     0  ...  MULTIPOLYGON (((2592917.016 1120132.965, 25929...
        27    28  ...  MULTIPOLYGON (((2592891.248 1120129.691, 25928...
        28    26  ...  MULTIPOLYGON (((2592901.604 1120125.591, 25929...
        29    27  ...  MULTIPOLYGON (((2592887.725 1120119.181, 25928...
        [252 rows x 6 columns]

        """

        # TODO: SQL query to select only roofs and facades of interest

        # geopandas looks for PostGIS's spatial_ref_sys table which may not exist in all deployments;
        # suppress the benign fallback warning since epsg:2056 is always the correct CRS here.
        warnings.filterwarnings("ignore", message="Could not find the spatial reference system table")

        filters = dict(filters) if filters else {}
        # Deprecated arguments are folded into the filters dictionary
        if district_id is not None:
            warnings.warn("district_boundary/district_id are deprecated, use filters={'%s': %r} instead."
                           % (district_boundary or 'transformers', district_id), DeprecationWarning, stacklevel=2)
            filters[district_boundary or 'transformers'] = district_id
        if egid is not None:
            warnings.warn("The egid argument is deprecated, use filters={'egid': %r} instead." % (egid,),
                           DeprecationWarning, stacklevel=2)
            filters['egid'] = egid
        if id_building is not None:
            warnings.warn("The id_building argument is deprecated, use filters={'id_building': %r} instead." % (id_building,),
                           DeprecationWarning, stacklevel=2)
            filters['id_building'] = id_building
        if not filters:
            raise ValueError("No filter given, e.g. {'transformers': 234}, {'egid': 1009515} or {'geometry': 'boundary.gpkg'}.")

        # Whatever the layer the buildings are given on, they are selected first, and the district
        # they belong to is deduced from them afterwards.
        self.select_buildings(filters)
        district_boundary = next((layer for layer in filters if layer in self.DISTRICT_TABLES), 'transformers')
        id_key = self.LAYER_COLUMNS[district_boundary]
        self.select_district_from_buildings(district_boundary)

        if nb_buildings is None:
            nb_buildings = self.data['buildings'].shape[0]
        if to_csv:
            self.data['buildings'].to_csv('buildings.csv', index=False)

        self.data['buildings'] = translate_buildings_to_REHO(self.data['buildings'], district_boundary=id_key)
        # Buildings picked one by one (by EGID or ID) are kept as such, without filtering on their class
        buildings = self.select_buildings_data(nb_buildings, filter_class=not {'egid', 'id_building'}.intersection(filters))
        if to_csv:
            csv_columns = list(buildings[list(buildings.keys())[0]].keys())
            with open('reho_input.csv', 'w') as csvfile:
                writer = csv.DictWriter(csvfile, csv_columns)
                writer.writeheader()
                for building in buildings:
                    writer.writerow(buildings[building])

        qbuildings = {'buildings_data': buildings}

        if self.load_facades:
            self.data['facades'] = gpd.GeoDataFrame()
            for id in self.data['buildings'].id_building:
                sqlQuery = select(self.tables[self.db_schema + '.' + 'facades']) \
                    .where(self.tables[self.db_schema + '.' + 'facades'].columns.id_building == id)
                self.data['facades'] = pd.concat(
                    (self.data['facades'], gpd.read_postgis(sqlQuery,
                                                            con=self.db_engine, geom_col='geometry').fillna(np.nan)))
            if to_csv:
                self.data['facades'].to_csv('facades.csv', index=False)
            self.data['facades'] = translate_facades_to_REHO(self.data['facades'], self.data['buildings'])
            qbuildings['facades_data'] = self.data['facades']
            if len(qbuildings["buildings_data"]) > 1:
                qbuildings['shadows_data'] = return_shadows_district(qbuildings["buildings_data"], self.data['facades'])
        if self.load_roofs:
            self.data['roofs'] = gpd.GeoDataFrame()
            for id in self.data['buildings'].id_building:
                sqlQuery = select(self.tables[self.db_schema + '.' + 'roofs']) \
                    .where(self.tables[self.db_schema + '.' + 'roofs'].columns.id_building == id)
                self.data['roofs'] = pd.concat(
                    (self.data['roofs'], gpd.read_postgis(sqlQuery,
                                                          con=self.db_engine, geom_col='geometry').fillna(np.nan)))
            if to_csv:
                self.data['roofs'].to_csv('roofs.csv', index=False)
            self.data['roofs'] = translate_roofs_to_REHO(self.data['roofs'])
            qbuildings['roofs_data'] = self.data['roofs']

        if self.correct_Uh:
            qbuildings["buildings_data"] = get_Uh_corrected(qbuildings["buildings_data"], df_facades=qbuildings["facades_data"])

        qbuildings['data_source'] = self.db
        qbuildings['data_date'] = self.read_date_from_description()
        return qbuildings

    def get_reference_reho_units(self, buildings_data):
        """
        Returns the units to enforce and exclude to reproduce the existing energy system.

        For each building the DHW provider is resolved with this priority:

        1. ``source_hotwater`` field → matched via ``HOTWATER_SOURCE_TO_UNITS``.
        2. ``source_heating`` unit that also serves DHW (e.g. OIL_Boiler, NG_Boiler).
        3. Fallback: ``ElectricalHeater_DHW`` (e.g. wood-stove buildings with a standalone
           electric boiler for hot water, which is common in Switzerland).

        Parameters
        ----------
        buildings_data : dict
            Dictionary of buildings characteristics, as returned by ``read_db`` or ``read_csv``.

        Returns
        -------
        enforce_units : list of str
            Fully qualified unit names (``Unit_Building``) to enforce.
        exclude_units : list of str
            Fully qualified unit names (``Unit_Building``) to exclude.
        pv_capacities : dict
            Fully qualified PV unit names mapped to existing capacity in kW.

        Notes
        -----
        An enforced unit is only kept if the grid layer it runs on is enabled: an oil-heated
        building needs ``initialize_grids`` to be given the ``Oil`` layer.
        """
        enforce_units = []
        exclude_units = []
        pv_capacities = {}

        for building, data in buildings_data.items():

            source_sh = str(data.get('source_heating', '')).lower()
            matched_sh = set()
            for keyword, units in self.HEATING_SOURCE_TO_UNITS.items():
                if keyword in source_sh:
                    matched_sh.update(units)

            source_hw = str(data.get('source_hotwater', '')).lower()
            matched_hw = set()
            for keyword, units in self.HOTWATER_SOURCE_TO_UNITS.items():
                if keyword in source_hw:
                    matched_hw.update(units)

            if not matched_hw:
                # Priority 2: inherit from source_heating if any of its units serve DHW
                matched_hw = matched_sh & self.DHW_CAPABLE_UNITS

            if not matched_hw and matched_sh:
                # Priority 3: SH units exist but none cover DHW → electric boiler fallback
                matched_hw = {'ElectricalHeater_DHW'}

            matched_all = matched_sh | matched_hw
            if matched_sh:
                enforce_units += [u + '_' + building for u in matched_all]
                exclude_units += [u + '_' + building for u in self.PRIMARY_HEATING_UNITS - matched_all]
            elif matched_hw:
                # Only the DHW system is known: leave the SH choice free
                enforce_units += [u + '_' + building for u in matched_hw]

            pv_kw = data.get('pv_installation_kW', 0)
            pv_kw = 0.0 if pd.isna(pv_kw) else float(pv_kw)
            if pv_kw > 0:
                enforce_units.append('PV_' + building)
                pv_capacities['PV_' + building] = pv_kw
            else:
                exclude_units.append('PV_' + building)

        return enforce_units, exclude_units, pv_capacities

    def select_buildings(self, filters):
        """
        Selects the buildings matching all the given ``{layer: value}`` filters.

        This is the single entry point to the buildings table: selecting the buildings of a district
        is just a filter on the corresponding column, as is selecting them by EGID, by ID or by a
        geometry they intersect. All the criteria are combined into one query.
        """

        table = self.tables[self.db_schema + '.' + 'buildings']
        sqlQuery = select(table).where(and_(*[self._filter_to_sql(table, layer, value) for layer, value in filters.items()]))
        self.data['buildings'] = gpd.read_postgis(sqlQuery, con=self.db_engine, geom_col='geometry').fillna(np.nan)
        # Buildings without EGID cannot be characterized
        self.data['buildings'] = self.data['buildings'][self.data['buildings']['egid'].notnull()]
        if self.data['buildings'].empty:
            raise ValueError("No building found for the filters %s." % filters)

        return self.data['buildings']

    def select_district_from_buildings(self, district_boundary='transformers'):
        """
        Reads the boundaries of the district(s) in which the selected buildings lie.

        The transformers are always read, as they carry the localization of the case study
        (city and canton), used for instance to retrieve the electricity prices.
        """

        boundaries = {'transformers': 'transformer', self.DISTRICT_TABLES[district_boundary]: self.LAYER_COLUMNS[district_boundary]}
        for table_name, id_key in boundaries.items():
            table = self.tables[self.db_schema + '.' + table_name]
            ids = pd.unique(self.data['buildings'][id_key].dropna()).tolist()
            sqlQuery = select(table).where(table.columns.id.in_(ids))
            self.data[table_name] = gpd.read_postgis(sqlQuery, con=self.db_engine, geom_col='geometry').fillna(np.nan)

        return self.data[self.DISTRICT_TABLES[district_boundary]]

    def _filter_to_sql(self, table, layer, value):
        """Translates a single ``{layer: value}`` filter into a SQL condition on the buildings table."""

        if layer == 'geometry':
            geometry = to_shapely(value)
            return func.ST_Intersects(table.columns.geometry, func.ST_GeomFromText(geometry.wkt, CRS_QBUILDINGS))

        if layer not in self.LAYER_COLUMNS:
            raise ValueError("Unknown filter layer '%s'. Available: %s and 'geometry'." % (layer, list(self.LAYER_COLUMNS)))
        if self.LAYER_COLUMNS[layer] not in table.columns:
            raise ValueError("The layer '%s' is not available in the '%s' database." % (layer, self.db))

        column = table.columns[self.LAYER_COLUMNS[layer]]
        values = list(value) if isinstance(value, (list, tuple, set, np.ndarray, pd.Series)) else [value]
        if isinstance(column.type, String):
            values = [str(v) for v in values]  # EGIDs and building IDs are stored as text

        if layer == 'egid':
            # EGIDs can be grouped ('1017073/1017074'): match any element of the group
            return column.op('~')("(^|/)(%s)(/|$)" % '|'.join(re.escape(v) for v in values))
        return column.in_(values)

    def select_buildings_data(self, nb_buildings, filter_class=True):

        nb_select = 0
        selected_buildings = []
        reindex = []
        for i, building in self.data['buildings'].iterrows():
            # Only execute optimization for complete dictionary else skip and count
            if not filter_class or re.search('XIII', building['id_class']) is None:
                selected_buildings.append(building['id_building'])
                nb_select += 1
                reindex.append("Building" + str(nb_select))
            if nb_select >= nb_buildings:
                break
        self.data['buildings'] = self.data['buildings'][
            self.data['buildings']['id_building'].isin(selected_buildings)]
        self.data['buildings'].index = reindex
        if self.db_engine is None:
            self.data['buildings'] = read_geometry(self.data['buildings'])

        return self.data['buildings'].to_dict('index')

    def select_roofs_or_facades_data(self, roof):
        selected_data = []
        for i, building in self.data['buildings'].iterrows():
            if roof:
                selected_data += \
                    self.data['roofs'].index[self.data['roofs']['id_building'] == building['id_building']].to_list()
            else:
                selected_data += \
                    self.data['facades'].index[self.data['facades']['id_building'] == building['id_building']].to_list()

        return selected_data


def to_shapely(geometry, crs=CRS_QBUILDINGS):
    """
    Converts a geometry into a single shapely geometry expressed in the QBuildings CRS.

    Parameters
    ----------
    geometry : str, os.PathLike, shapely geometry, GeoDataFrame or GeoSeries
        A path to a geographic file (.gpkg, .shp, .geojson...), a WKT string, an already opened
        (Geo)DataFrame or a shapely geometry.
    crs : int
        The CRS in which the geometry is returned.

    Returns
    -------
    shapely.geometry.base.BaseGeometry
        The union of the given geometries.
    """

    if isinstance(geometry, (str, os.PathLike)) and os.path.exists(geometry):
        geometry = gpd.read_file(geometry)
    elif isinstance(geometry, str):
        geometry = wkt.loads(geometry)

    if isinstance(geometry, (gpd.GeoDataFrame, pd.DataFrame)):
        geometry = geometry['geometry']
    if isinstance(geometry, pd.Series) and not isinstance(geometry, gpd.GeoSeries):
        geometry = gpd.GeoSeries(geometry.apply(lambda g: wkt.loads(g) if isinstance(g, str) else g))
    if isinstance(geometry, gpd.GeoSeries):
        if geometry.crs is not None:
            geometry = geometry.to_crs(crs)
        return geometry.union_all()

    return geometry  # shapely geometry, assumed to be already in the right CRS


def translate_buildings_to_REHO(df_buildings, district_boundary="transformers"):
    dict_QBuildings_REHO = {

        #################################################
        # Data strictly necessary for a REHO optimization
        #################################################

        # Data for EUD profiles
        'id_building': 'id_building',
        'egid': 'egid',
        'id_class': 'id_class',
        'class': 'class',
        'ratio': 'ratio',
        'status': 'status',
        'period': 'period',
        'capita_cap': 'n_p',

        # Area
        'area_era_m2': 'ERA',
        'area_roof_solar_m2': 'SolarRoofArea',
        'area_facade_m2': 'area_facade_m2',
        'area_footprint_m2': 'area_footprint_m2',
        'height_m': 'height_m',  # only for use_facades
        'count_floor': 'count_floor',

        # Heating source
        'source_heating': 'source_heating',
        'source_hotwater': 'source_hotwater',

        # Existing PV installation, used to build a 'reference' (as-is) scenario
        'pv_installation_kW': 'pv_installation_kW',

        # Thermal envelope
        'thermal_transmittance_signature_kW_m2_K': 'U_h',
        'thermal_specific_capacity_Wh_m2_K': 'HeatCapacity',

        # Temperature requirements
        'temperature_interior_C': 'T_comfort_min_0',
        'temperature_heating_supply_C': 'Th_supply_0',
        'temperature_heating_return_C': 'Th_return_0',
        'temperature_cooling_supply_C': 'Tc_supply_0',
        'temperature_cooling_return_C': 'Tc_return_0',

        #############################
        # Data not strictly necessary
        #############################

        # Geographic information
        'x': 'x',
        'y': 'y',
        'z': 'z',
        'geometry': 'geometry',
        district_boundary: 'transformer',

        # Annual energy
        'energy_heating_signature_kWh_y': 'energy_heating_signature_kWh_y',
        'energy_cooling_signature_kWh_y': 'energy_cooling_signature_kWh_y',
        'energy_hotwater_signature_kWh_y': 'energy_hotwater_signature_kWh_y',
        'energy_el_kWh_y': 'energy_el_kWh_y',

        # Annual roof and facade irradiance
        'roof_annual_irr_kWh_y': 'roof_annual_irr_kWh_y',
        'facade_annual_irr_kWh_y': 'facade_annual_irr_kWh_y'
    }

    try:
        translated_buildings_data = gpd.GeoDataFrame(geometry=df_buildings['geometry'])
    except TypeError:
        # Convert WKT strings to shapely geometries if needed
        df_buildings['geometry'] = df_buildings['geometry'].apply(lambda x: wkt.loads(x) if isinstance(x, str) else x)
        # Filter out invalid geometries
        df_buildings = df_buildings[df_buildings['geometry'].apply(lambda x: x.is_valid if hasattr(x, 'is_valid') else True)]
        # Create GeoDataFrame
        translated_buildings_data = gpd.GeoDataFrame(geometry=df_buildings['geometry'])

    for key in dict_QBuildings_REHO.keys():
        REHO_index = dict_QBuildings_REHO[key]
        try:
            translated_buildings_data[REHO_index] = df_buildings[key]
        except KeyError:
            print('Key %s not in the dictionary' % key)

    df_buildings = translated_buildings_data

    return df_buildings


def get_Uh_corrected(df_buildings, uh_data=None, df_facades=None):
    """
    Parameters
    ----------
    df_buildings : dict
        The dictionary of building table from QBuilding
    uh_data : dataframe
        Typical U values per building element and construction period.
        Default values are based on SIA 2024 and Energy Performance Gap bei Instandsetzungen, Literaturstudie Schlussbericht, 17. Januar 2022
    df_facades : geodataframe
        Geoataframe of the facades in the case study

    Returns
    -------
    dict
        it returns the dictionary df_buildings with the corrected U values based on uh_data.
        It as well corrects the area of facades if df_facades if given.
        [1] KHOURY, Assessment of Geneva multifamily building stock: main characteristics and regression models for
        energy reference area determination. Geneva : SCCER Future Energy Efficient Buildings & Districts
    """

    if uh_data is None:
        uh_data = pd.read_csv(os.path.join(path_to_infrastructure, 'U_values.csv'), sep=";").set_index("period")

    for i in df_buildings:
        df_h = df_buildings[i]
        periods = df_h["period"].split("/")
        ratios = [float(x) for x in df_h["ratio"].split("/")]
        id_class = df_h["id_class"].split("/")

        if len(periods) < len(ratios):
            periods = periods + [periods[0]] * (len(ratios) - len(periods))
        if len(periods) > len(ratios):
            ratios = ratios + [0] * (len(ratios) - len(periods))

        if df_facades is not None:
            facades = df_facades[df_facades["id_building"] == df_h["id_building"]]
            perimeter = np.sum([line.length for line in facades["geometry"]])
            # df_h["area_facade_m2"] = perimeter * df_h["height_m"]
            footprint_factor = df_h["area_footprint_m2"] / perimeter
        else:
            footprint_factor = df_h["area_footprint_m2"] / df_h['geometry'].length

        b_value_floor = pd.read_csv(os.path.join(path_to_sia, 'b_value_floor.csv'), sep=";").set_index("U_footprint")
        b_value = b_value_floor[min(b_value_floor.columns, key=lambda x: abs(float(x) - footprint_factor))]

        if df_h["ERA"] < 0.7 * (0.93 * df_h["area_footprint_m2"] * df_h['count_floor']):
            # When we have case where the ERA is particularly lower than the footprint (because some spaces do not need to be heated),
            # issues arise from gains and losses

            df_h["area_facade_m2"] = df_h["ERA"] / footprint_factor * df_h['height_m']
            downscaling = df_h["ERA"] / (0.93 * df_h["area_footprint_m2"] * df_h['count_floor'])
            df_h["SolarRoofArea"] = df_h["SolarRoofArea"] * downscaling
            df_h["area_footprint_m2"] = df_h["area_footprint_m2"] * downscaling

        U_h_ins_data = 0
        for j in range(len(periods)):
            glass_fraction = 0.5
            if id_class[j] in ["I", "II"]:
                glass_fraction = 0.3
            thermal_capacity_air = (1200 - 0.14 * 610) / 3600   # Wh/K/m3 SIA 380/1
            air_renewal = 0.7 / 2.5  # 1/h
            volume = df_h['ERA'] * 2.5  # m3
            ventilation = air_renewal * volume * thermal_capacity_air / 1000  # kW/K

            uh_period = uh_data.loc[periods[j]]
            b = b_value.loc[min(b_value.index, key=lambda x: abs(float(x) - uh_period["U_footprint"] * 1000))]
            b_roof = 1
            if df_h['SolarRoofArea'] > df_h["area_footprint_m2"]*1.1:  # non heated space under roof
                b_roof = 0.9

            U_h_ins_data += (df_h['area_facade_m2'] * (1 - glass_fraction) * uh_period["U_facade"] +
                             df_h["area_footprint_m2"] * uh_period["U_footprint"]*b +
                             df_h['area_facade_m2'] * glass_fraction * uh_period["U_window"] +
                             df_h['SolarRoofArea'] * uh_period["U_roof"] * b_roof +
                             ventilation) * ratios[j] / df_h['ERA']
        df_buildings[i]["U_h"] = U_h_ins_data

    return df_buildings


def translate_facades_to_REHO(df_facades, df_buildings):
    dict_facades = {'azimuth': 'AZIMUTH',
                    'id_facade': 'Facades_ID',
                    'area_facade_solar_m2': 'AREA',
                    'id_building': 'id_building',
                    # 'cx': 'CX',
                    # 'cy': 'CY',
                    'geometry': 'geometry'}

    try:
        translated_facades_data = gpd.GeoDataFrame(geometry=df_facades['geometry'])
    except TypeError:
        # Convert WKT strings to shapely geometries if needed
        df_facades['geometry'] = df_facades['geometry'].apply(lambda x: wkt.loads(x) if isinstance(x, str) else x)
        # Filter out invalid geometries
        df_facades = df_facades[df_facades['geometry'].apply(lambda x: x.is_valid if hasattr(x, 'is_valid') else True)]
        # Create GeoDataFrame
        translated_facades_data = gpd.GeoDataFrame(geometry=df_facades['geometry'])

    for key in dict_facades.keys():
        REHO_index = dict_facades[key]
        try:
            translated_facades_data[REHO_index] = df_facades[key]
        except KeyError:
            print('Key %s not in the dictionary' % key)

    df_facades = translated_facades_data
    df_facades['CX'] = df_facades['geometry'].centroid.x
    df_facades['CY'] = df_facades['geometry'].centroid.y
    df_facades['coord_Z0'] = None

    for i, b in df_buildings.iterrows():
        concerned_facades = df_facades[df_facades['id_building'] == b['id_building']]
        if not pd.isna(b['z']):
            df_facades.loc[concerned_facades.index, 'coord_Z0'] = b['z']

    return df_facades


def translate_roofs_to_REHO(df_roofs):
    dict_roofs = {'tilt': 'TILT',
                  'azimuth': 'AZIMUTH',
                  'id_roof': 'ROOF_ID',
                  'area_roof_solar_m2': 'AREA',
                  'id_building': 'id_building',
                  'geometry': 'geometry'}

    try:
        translated_roofs_data = gpd.GeoDataFrame(geometry=df_roofs['geometry'])
    except TypeError:
        # Convert WKT strings to shapely geometries if needed
        df_roofs['geometry'] = df_roofs['geometry'].apply(lambda x: wkt.loads(x) if isinstance(x, str) else x)
        # Filter out invalid geometries
        df_roofs = df_roofs[df_roofs['geometry'].apply(lambda x: x.is_valid if hasattr(x, 'is_valid') else True)]
        # Create GeoDataFrame
        translated_roofs_data = gpd.GeoDataFrame(geometry=df_roofs['geometry'])

    for key in dict_roofs.keys():
        REHO_index = dict_roofs[key]
        try:
            translated_roofs_data[REHO_index] = df_roofs[key]
        except KeyError:
            print('Key %s not in the dictionary' % key)

    df_roofs = translated_roofs_data

    return df_roofs


def get_roofs(self, buildings):
    selected_roofs = []
    for i, building in buildings.iterrows():
        selected_roofs += \
            self.data['roofs'].index[self.data['roofs']['id_building'] == building['id_building']].to_list()
    self.data['roofs'] = self.data['roofs'][self.data['roofs'].index.isin(selected_roofs)]

    return self.data['roofs']


def get_facades(self, buildings):
    selected_facades = []
    for i, building in buildings.iterrows():
        selected_facades += \
            self.data['facades'].index[self.data['facades']['id_building'] == building['id_building']].to_list()
    self.data['facades'] = self.data['facades'][self.data['facades'].index.isin(selected_facades)]

    return self.data['facades']


def calculate_id_building_shadows(df_angles, id_building):
    df_angles['to_id_building'] = pd.to_numeric(df_angles['to_id_building'])
    df_angles = df_angles.set_index('to_id_building')
    df_angles = df_angles.xs(id_building)

    df_shadow = pd.DataFrame()

    for az in df_dome.azimuth.unique():
        df_angles['cosa2'] = np.cos(np.radians(df_angles['azimuth'] - az))
        df = df_angles.loc[(df_angles['cosa2'] > 0)].copy()
        # filter buildings which are more than 180 degree apart from patch with az
        df.loc[:, 'tanba'] = df.tanb * df.cosa2
        # calculate tan(beta) for all buildings. Assumption: dxy is the shortest distance and buildings infinite wide

        max_tanba = df['tanba'].max()  # get max obscurance tan(beta, alpha)
        max_b = math.degrees(math.atan(max_tanba))  # get angle

        if math.isnan(max_b):  # if no shadow, set everything to 0
            id_building = 0
            max_b = 0
            max_tanba = 0
        else:
            id_building = df[df.tanba == df['tanba'].max()].index[0]  # get the id_building which causes the obscurance

        df = pd.DataFrame([[max_tanba, max_b, az, id_building]], columns=['tanb', 'beta', 'azimuth', 'id_building'])
        df_shadow = pd.concat((df_shadow, df))

    return df_shadow


def neighbourhood_angles(buildings, facades):
    df_angles = pd.DataFrame()

    for b in buildings:
        id_building = buildings[b]['id_building']
        df_BUI = pd.DataFrame()
        df_district = {buildings: bui for buildings, bui in buildings.items() if bui['id_building'] != id_building}
        df_district = pd.DataFrame.from_dict(df_district, orient='index')
        df_district = df_district.set_index('id_building')

        df_nan = df_district[df_district.height_m.isna()]
        heights_nan = df_nan["ERA"] / df_nan["area_footprint_m2"] / 0.93 * 2.5
        df_district.loc[heights_nan.index, "height_m"] = heights_nan

        # exclude current building to avoid division with zero
        facades_build = facades[facades.id_building == id_building]  # facades of building
        for f in facades_build.index:
            df_c = pd.DataFrame(index=df_district.index)  # df for calculating values for each facade
            df_c['dx'] = df_district.x.values - facades_build.loc[f]['CX']
            df_c['dy'] = df_district.y.values - facades_build.loc[f]['CY']
            df_c['dxy'] = (df_c.dx * df_c.dx + df_c.dy * df_c.dy) ** 0.5
            heights = df_district.height_m.values
            if facades_build.loc[f]['coord_Z0'] is None:
                print('Missing value coord_Z0, not possible to use_facades')
                continue
            df_c['dz'] = df_district.z.values + heights - facades_build.loc[f]['coord_Z0']
            # facades.loc[f]['HEIGHT_Z'] + facades.loc[f]['HEIGHT'] #take foot of facades/ HEIGHT_Z is upperbound
            df_c['tanb'] = df_c.dz / df_c.dxy
            df_c['cosa'] = df_c.dy / df_c.dxy
            df_c['azimuth'] = np.degrees(np.arctan2(df_c['dx'], df_c['dy'])) % 360
            df_c['azimuth'] = df_c['azimuth'].round().astype(int)
            df_c['beta'] = np.degrees(np.arctan2(df_c['dz'], df_c['dxy'])) % 360
            df_c['beta'] = df_c['beta'].round().astype(int)
            df_c = pd.concat([df_c], keys=[f], names=['UID'])
            df_BUI = pd.concat((df_BUI, df_c))

        df_BUI = df_BUI.reset_index()
        df_BUI = df_BUI.rename(columns={'id_building': 'to_id_building'})
        df_BUI['id_building'] = int(id_building)
        df_angles = pd.concat((df_angles, df_BUI))

    return df_angles


def return_shadows_district(buildings, facades):
    df_shadows = pd.DataFrame()
    df_angles = neighbourhood_angles(buildings, facades)

    for b in buildings:
        id_building = int(buildings[b]['id_building'])
        if id_building in df_angles['id_building'].values:  # check if angle calculation for id_building exists
            df_id_building = calculate_id_building_shadows(df_angles, id_building)
            idx = np.repeat(id_building, len(df_id_building))
            df_id_building = df_id_building.set_index(idx)
        else:
            print('NO DATA AVAILABLE FOR id_building ' + str(id_building))
            df_id_building = pd.DataFrame(index=[id_building],
                                          columns=['tanb', 'beta', 'azimuth', 'id_building'])  # pass NaN instead
        df_shadows = pd.concat((df_shadows, df_id_building))

    df_shadows["id_building"] = df_shadows["id_building"].astype(str)
    return df_shadows


def return_shadows_id_building(id_building, df):
    id_building = int(id_building)
    df = df.xs(id_building)

    df_beta_dome = pd.DataFrame()
    for az in df_dome.azimuth:
        df_beta_dome = pd.concat((df_beta_dome, df.beta[df.azimuth == az]), ignore_index=True)

    df_beta_dome = df_beta_dome.rename(columns={0: 'Limiting_angle_shadow', 'beta': 'Limiting_angle_shadow'})

    return df_beta_dome


def read_geometry(df):
    """
    Avoid issues with geometry when reading data from a csv
    """
    if 'geometry' not in df.columns:
        print("No geometry specified in the dataframe.")
        return df
    else:
        if isinstance(df["geometry"], gpd.geoseries.GeoSeries):
            return df
        else:
            try:
                geometry = gpd.GeoSeries.from_wkt(df['geometry'])
                return gpd.GeoDataFrame(df, geometry=geometry)
            except TypeError:
                print("Geometry passed is neither of format wkb or wkt so neither from PostGIS, neither from QBuildings.")
                return df
