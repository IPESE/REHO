import configparser
import os.path
from sqlalchemy import create_engine, MetaData, select
from sqlalchemy.dialects import postgresql
import geopandas as gpd
import re
import csv
from reho.paths import *
import reho.model.preprocessing.skydome as skd
import pandas as pd
import numpy as np
import math


class QBuildingsReader:
    """
    This class is used to handle and prepare the data related to buildings.

    There usually come from `GBuildings <https://ipese-web.epfl.ch/lepour/qbuildings/index.html>`_ database. However,
    one can use data from a csv, in which case the column names should correspond to the GBuildings one, described in
    `Processed GBuildings tables <https://ipese-web.epfl.ch/lepour/qbuildings/GBuildings/description.html#processed>`_.

    Parameters
    ----------
    load_facades : bool
        Whether the facades data should be added.
    load_roofs : bool
        Whether the roofs data should be added.
    """
    def __init__(self, load_facades=False, load_roofs=False):

        self.db = None
        self.tables = None
        self.db_schema = None
        self.db_engine = None
        self.connection = None
        self.data = {}
        self.load_facades = load_facades
        self.load_roofs = load_roofs

    def establish_connection(self, db):
        """
        Allows to establish the connection with one of the QBuildings database.

        Parameters
        ----------
        db : str
            Name of the database to which we want to connect

        Notes
        -----
        - It is highly recommend to pick 'Suisse' as a database as it is the only one maintained at the moment.
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

        except:
            print('Cannot connect to database engine')

        if 'database' in project:
            print('\thost: {}\n\tport: {}\n\tdatabase: {}\n\tusername: {}'.format(
                project['database']['host'],
                project['database']['port'],
                project['database']['database'],
                project['database']['username']))

        # input
        metadata = MetaData(bind=self.db_engine)
        metadata.reflect(schema=self.db_schema)
        self.tables = metadata.tables
        self.db = db

        return

    def read_csv(self, buildings_filename='buildings.csv', nb_buildings=None,
                 roofs_filename='roofs.csv', facades_filename='facades.csv'):
        """
        Read buildings-related data from CSV files and prepare it for the REHO model.

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
        - If `nb_buildings` is not provided, all buildings in the 'buildings' data are considered.
        - If ``load_roofs = True``, `roofs_filename` must be provided, else it is not useful. Same goes for the facades.
        - This function can be used with default files in case one does not want to connect to the database and does
          not need a particular building.
          In that case, do not fill any filename. `buildings.csv`, `roofs.csv` and `facades.csv`
          will be used by default.
          It should be noted that those names are therefore reserved for the default and cannot be used for your own files.

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
        # self.data['buildings'] = add_geometry(self.data['buildings'])
        if nb_buildings is None:
            nb_buildings = self.data['buildings'].shape[0]
        buildings = self.select_buildings_data(nb_buildings, None)
        # buildings = add_geometry(buildings)
        qbuildings = {'buildings_data': buildings}
        if self.load_facades:
            self.data['facades'] = file_reader(path_handler(facades_filename))
            selected_facades = self.select_roofs_or_facades_data(roof=False)
            self.data['facades'] = self.data['facades'][self.data['facades'].index.isin(selected_facades)]
            self.data['facades'] = add_geometry(self.data['facades'])
            self.data['facades'] = translate_facades_to_REHO(self.data['facades'], self.data['buildings'])
            qbuildings['facades_data'] = self.data['facades']
            qbuildings['shadows_data'] = return_shadows_district(qbuildings['buildings_data'], self.data['facades'])

        if self.load_roofs:
            self.data['roofs'] = file_reader(path_handler(roofs_filename))
            selected_roofs = self.select_roofs_or_facades_data(roof=True)
            self.data['roofs'] = self.data['roofs'][self.data['roofs'].index.isin(selected_roofs)]
            self.data['roofs'] = add_geometry(self.data['roofs'])
            self.data['roofs'] = translate_roofs_to_REHO(self.data['roofs'])
            qbuildings['roofs_data'] = self.data['roofs']

        return qbuildings

    def read_db(self, transformer=None, nb_buildings=None, egid=None, to_csv=False, return_location=False):
        """
        Reads the database and extract from it the buildings required, by the LV transformer's ID.

        If not all the buildings from the transformer should be extracted, one can give a number of buildings or if
        the EGIDs are known, pass a list of EGIDs.
        The fields from the database are translated to the corresponding ones used in REHO.

        Parameters
        ----------
        transformer : int
            ID of the transformer on which we want to optimize
        nb_buildings : int
            Number of buildings to select
        egid : list
            To specify a list of buildings to optimize with their EGIDs
        to_csv : bool
            To export the data into csv
        return_location : bool
            To obtain the corresponding meteo cluster

        Returns
        -------
        dict
            A Dictionary that contains the qbuildings data. The default has only one key ``buildings_data``
            with a dictionary of buildings, with their fields and corresponding values.


        Notes
        -----
        - The use of this function requires the previous creation of a ``QBuildingsReader`` and the use of ``establish_connection('Suisse')``.
        - EGIDs are the postal address unique identifier used in Switzerland. One can find the EGIDs of a given address at the `RegBL <https://www.housing-stat.ch/fr/query/adrtoegid.html>`_.
        - If ``load_roofs = True`` the roofs are returned as well in the dictionary as a DataFrame under the key ``roofs_data``.
        - If ``load_facades = True`` the facades and the shadows are returned as well in the dictionary as a DataFrame under the keys ``roofs_data`` and ``shadows_data``.

        Examples
        --------
        >>> from reho.model.reho import *
        >>> reader = QBuildingsReader(load_roofs=True)
        >>> reader.establish_connection('Suisse')
        >>> qbuildings_data = reader.read_db(transformer=3658, egid=[954117])

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

        # TODO: SQL query to select only buildings, roofs and facades of interest

        # Select the right transformer
        sqlQuery = select([self.tables[self.db_schema + '.' + 'transformers']]) \
            .where(self.tables[self.db_schema + '.' + 'transformers'].columns.id == transformer)
        self.data['transformers'] = gpd.read_postgis(sqlQuery.compile(dialect=postgresql.dialect()), con=self.db_engine,
                                                     geom_col='geometry').fillna(np.nan)
        if return_location:
            meteo_cluster = translate_meteo_to_period_cluster(self.data['transformers']['meteo'][0])
        else:
            meteo_cluster = None

        # Select buildings
        sqlQuery = select([self.tables[self.db_schema + '.' + 'buildings']]) \
            .where(self.tables[self.db_schema + '.' + 'buildings'].columns.transformer == transformer)
        self.data['buildings'] = gpd.read_postgis(sqlQuery.compile(dialect=postgresql.dialect()), con=self.db_engine,
                                                  geom_col='geometry').fillna(np.nan)
        mask = (self.data['buildings']['egid'].isnull())
        self.data['buildings'] = self.data['buildings'].loc[~mask, :]

        if nb_buildings is None:
            nb_buildings = self.data['buildings'].shape[0]
        if to_csv:
            self.data['buildings'].to_csv('buildings.csv', index=False)

        self.data['buildings'] = translate_buildings_to_REHO(self.data['buildings'])
        buildings = self.select_buildings_data(nb_buildings, egid)
        if to_csv:
            csv_columns = list(buildings[list(buildings.keys())[0]].keys())
            with open('reho_input.csv', 'w') as csvfile:
                writer = csv.DictWriter(csvfile, csv_columns)
                writer.writeheader()
                for building in buildings:
                    writer.writerow(buildings[building])

        qbuildings = {'buildings_data': buildings}

        if self.load_facades:
            # TODO: Correct the roofs and facades selection with the id filtered by select_buildings_data
            self.data['facades'] = gpd.GeoDataFrame()
            for id in self.data['buildings'].id_building:
                sqlQuery = select([self.tables[self.db_schema + '.' + 'facades']]) \
                    .where(self.tables[self.db_schema + '.' + 'facades'].columns.id_building == id)
                self.data['facades'] = pd.concat(
                    (self.data['facades'], gpd.read_postgis(sqlQuery.compile(dialect=postgresql.dialect()),
                                                            con=self.db_engine, geom_col='geometry').fillna(np.nan)))
            if to_csv:
                self.data['facades'].to_csv('facades.csv', index=False)
            self.data['facades'] = translate_facades_to_REHO(self.data['facades'], self.data['buildings'])
            qbuildings['facades_data'] = self.data['facades']
            qbuildings['shadows_data'] = return_shadows_district(qbuildings["buildings_data"], self.data['facades'])
        if self.load_roofs:
            self.data['roofs'] = gpd.GeoDataFrame()
            for id in self.data['buildings'].id_building:
                sqlQuery = select([self.tables[self.db_schema + '.' + 'roofs']]) \
                    .where(self.tables[self.db_schema + '.' + 'roofs'].columns.id_building == id)
                self.data['roofs'] = pd.concat(
                    (self.data['roofs'], gpd.read_postgis(sqlQuery.compile(dialect=postgresql.dialect()),
                                                          con=self.db_engine, geom_col='geometry').fillna(np.nan)))
            if to_csv:
                self.data['roofs'].to_csv('roofs.csv', index=False)
            self.data['roofs'] = translate_roofs_to_REHO(self.data['roofs'])
            qbuildings['roofs_data'] = self.data['roofs']

        if qbuildings["buildings_data"] == {}:
            raise print("Empty building data")

        return qbuildings

    def select_buildings_data(self, nb_buildings, egid=None):

        if egid is None:
            nb_select = 0
            selected_buildings = []
            reindex = []
            for i, building in self.data['buildings'].iterrows():
                # Only execute optimization for complete dictionary else skip and count
                if re.search('XIII', building['id_class']) is None:
                    selected_buildings.append(building['id_building'])
                    nb_select += 1
                    reindex.append("Building" + str(nb_select))
                if nb_select >= nb_buildings:
                    break
            self.data['buildings'] = self.data['buildings'][
                self.data['buildings']['id_building'].isin(selected_buildings)]
            self.data['buildings'].index = reindex
            if self.db_engine is None:
                self.data['buildings'] = add_geometry(self.data['buildings'])
            buildings_data = self.data['buildings'].to_dict('index')

        else:
            nb_select = 1
            if type(egid) != list:
                egid = [egid]

            buildings_data = gpd.GeoDataFrame()
            for i in egid:
                data_single_bui = self.data['buildings'][self.data['buildings']['egid'] == str(i)]
                data_single_bui.index = ["Building" + str(nb_select)]
                nb_select += 1
                buildings_data = pd.concat([buildings_data, data_single_bui])
            buildings_data = buildings_data.to_dict('index')

        return buildings_data

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


def translate_buildings_to_REHO(df_buildings):
    new_buildings_data = gpd.GeoDataFrame()
    dict_QBuildings_REHO = {

        #################################################
        # Data strictly necessary for a REHO optimization
        #################################################

        # Data for EUD profiles
        'id_class': 'id_class',
        'ratio': 'ratio',
        'status': 'status',

        # Area
        'area_era_m2': 'ERA',
        'area_roof_solar_m2': 'SolarRoofArea',
        'area_facade_m2': 'area_facade_m2',
        'height_m': 'height_m',  # only for use facades

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
        'transformer': 'transformer',

        # Additional information
        'id_building': 'id_building',
        'egid': 'egid',
        'period': 'period',
        'capita_cap': 'n_p',

        # Annual energy
        'energy_heating_signature_kWh_y': 'energy_heating_signature_kWh_y',
        'energy_cooling_signature_kWh_y': 'energy_cooling_signature_kWh_y',
        'energy_hotwater_signature_kWh_y': 'energy_hotwater_signature_kWh_y',
        'energy_el_kWh_y': 'energy_el_kWh_y',
    }

    # TODO: correct heat source dictionary
    dict_translate_heat_source = {
        'Gas': 'gas',
        'Oil': 'oil',
        'Wood (beech)': 'wood',
        'Electricity': 'electricity',
        'Heat pump': 'Heat pump',
        'District heat': 'District heat',
        'Other': 'gas',
        'Other/Oil': 'oil',
        'Electricity/Other': 'electricity',
        'Oil/Gas': 'oil',
        'Oil/Other': 'oil',
        'Electricity/Oil': 'electricity',
        'Heat pump/Electricity': 'Heat pump',
        'Solar collector': 'solar',
        'Solar (thermal)': 'solar',
        'No energy source/Oil': 'oil',
        'No energy source': 'gas',
        'Electricity/No energy source': 'electricity',
        'Oil/No energy source': 'oil',
        'Gas/Solar collector': 'gas',
        'Not determined': 'unknown'
    }

    for key in dict_QBuildings_REHO.keys():
        REHO_index = dict_QBuildings_REHO[key]
        try:
            new_buildings_data[REHO_index] = df_buildings[key]
        except KeyError:
            print('Key %s not in the dictionary' % key)
        except:
            print('Missing key in loaded data %s' % key)

    # for i, building in new_buildings_data.iterrows():
    #     try:
    #         sources_translated = dict_translate_heat_source[building['source_heating']]
    #         sources_translated_w = dict_translate_heat_source[building['source_hotwater']]
    #         building['source_heating'] = sources_translated
    #         building['source_hotwater'] = sources_translated_w
    #     except:
    #         sources = building['source_heating'].split('/')
    #         try:
    #             sources_translated = dict_translate_heat_source[sources[0]]
    #         except KeyError:
    #             print('Source %s not in the dictionary' % sources[0])
    #             sources_translated = 'not documented'
    #         for source in sources[1:]:
    #             try:
    #                 sources_translated += '/' + dict_translate_heat_source[source]
    #             except KeyError:
    #                 print('Source %s not in the dictionary' % source)
    #                 continue
    #         building['source_heating'] = sources_translated
    #         sources_w = building['source_hotwater'].split('/')
    #         try:
    #             sources_translated_w = dict_translate_heat_source[sources_w[0]]
    #         except KeyError:
    #             print('Source %s not in the dictionary' % sources_w[0])
    #             sources_translated_w = 'not documented'
    #         for source_w in sources_w[1:]:
    #             try:
    #                 sources_translated_w += '/' + dict_translate_heat_source[source_w]
    #             except KeyError:
    #                 print('Source %s not in the dictionary' % source_w)
    #         building['source_hotwater'] = sources_translated_w
    #     new_buildings_data.loc[i, :] = building

    df_buildings = new_buildings_data

    return df_buildings


def translate_facades_to_REHO(df_facades, df_buildings):
    new_facades_data = gpd.GeoDataFrame()
    dict_facades = {'azimuth': 'AZIMUTH',
                    'id_facade': 'Facades_ID',
                    'area_facade_solar_m2': 'AREA',
                    'id_building': 'id_building',
                    # 'cx': 'CX',
                    # 'cy': 'CY',
                    'geometry': 'geometry'}

    for key in dict_facades.keys():
        REHO_index = dict_facades[key]
        try:
            new_facades_data[REHO_index] = df_facades[key]
        except KeyError:
            print('Key %s not in the dictionary' % key)
        except:
            print('Missing key in loaded data %s' % key)
    df_facades = new_facades_data
    df_facades['CX'] = df_facades['geometry'].centroid.x
    df_facades['CY'] = df_facades['geometry'].centroid.y
    df_facades['coord_Z0'] = None

    for i, b in df_buildings.iterrows():
        concerned_facades = df_facades[df_facades['id_building'] == b['id_building']]
        if not pd.isna(b['z']):
            df_facades.loc[concerned_facades.index, 'coord_Z0'] = b['z']

    return df_facades


def translate_roofs_to_REHO(df_roofs):
    # TODO: in Luise fct there is azimuth + 180
    new_roofs_data = gpd.GeoDataFrame()
    dict_roofs = {'tilt': 'TILT',
                  'azimuth': 'AZIMUTH',
                  'id_roof': 'ROOF_ID',
                  'area_roof_solar_m2': 'AREA',
                  'id_building': 'id_building',
                  'geometry': 'geometry'}

    for key in dict_roofs.keys():
        REHO_index = dict_roofs[key]
        try:
            new_roofs_data[REHO_index] = df_roofs[key]
        except KeyError:
            print('Key %s not in the dictionary' % key)
        except:
            print('Missing key in loaded data %s' % key)
    df_roofs = new_roofs_data

    return df_roofs


def translate_meteo_to_period_cluster(location):
    dict_meteo = {'Zermatt': 'Disentis',
                  'Geneva': 'Geneva',
                  'Berne': 'Bern-Liebefeld',
                  'CHDF': 'Piotta',
                  'Zurich': 'Zuerich-SMA',
                  'Gruyères': 'Lugano'}  # TODO set real cluster
    return dict_meteo[location]


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

    df_dome = skd.skydome_to_df()

    df_shadow = pd.DataFrame()

    for az in df_dome.azimuth.unique():
        df_angles.loc[:, 'cosa2'] = df_angles.apply(lambda x: skd.f_cos([x['azimuth'], az]), axis=1)
        # df_cosa2 = df_id_building.apply(lambda x: skd.f_cos([x['azimuth'], az]), axis=1)
        df = df_angles.loc[(df_angles['cosa2'] > 0)].copy()
        # filter buildings which are more than 180 degree apart from patch with az
        df.loc[:, 'tanba'] = df.tanb * df.cosa2
        # calculate tan(beta) for all buildings. Assumption: dxy is shortest distance and buildings infinite wide

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
        print('Calculate angles for building: ' + str(id_building))
        df_BUI = pd.DataFrame()
        df_district = {buildings: bui for buildings, bui in buildings.items() if bui['id_building'] != id_building}
        df_district = pd.DataFrame.from_dict(df_district, orient='index')
        df_district = df_district.set_index('id_building')
        # exclude current building to avoid division with zero
        facades_build = facades[facades.id_building == id_building]  # facades of building
        for f in facades_build.index:
            df_c = pd.DataFrame(index=df_district.index)  # df for calculating values for each facades
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
            df_c['azimuth'] = df_c[['dx', 'dy']].apply(skd.f_atan, axis=1)
            df_c['beta'] = df_c[['dz', 'dxy']].apply(skd.f_atan, axis=1)
            df_c = pd.concat([df_c], keys=[f], names=['UID'])
            df_BUI = pd.concat((df_BUI, df_c))

        df_BUI = df_BUI.reset_index()
        df_BUI = df_BUI.rename(columns={'id_building': 'to_id_building'})
        df_BUI['id_building'] = int(id_building)

        df_angles = pd.concat((df_angles, df_BUI))

    df_angles.to_csv('data/angles.csv')

    return df_angles


def return_shadows_district(buildings, facades):
    df_shadows = pd.DataFrame()

    if os.path.exists('data/angles.csv'):
        df_angles = pd.read_csv('data/angles.csv')
    else:
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
    df_shadows.to_csv('data/shadows.csv')

    return df_shadows


def return_shadows_id_building(id_building, df_district):
    id_building = int(id_building)

    if os.path.isfile('data/shadows.csv'):
        df = file_reader('data/shadows.csv', index_col=0)
    else:
        df = df_district
    df = df.xs(id_building)
    df_dome = skd.skydome_to_df()

    df_beta_dome = pd.DataFrame()
    for az in df_dome.azimuth:
        df_beta_dome = pd.concat((df_beta_dome, df.beta[df.azimuth == az]), ignore_index=True)

    df_beta_dome = df_beta_dome.rename(columns={0: 'Limiting_angle_shadow'})

    return df_beta_dome


def add_geometry(df):
    """
    Avoid issues with geometry when read from a csv
    """
    try:
        geom = gpd.GeoSeries.from_wkb(df['geometry'])
    except KeyError:
        print("No geometry in the dataframe")
        return df
    except:
        try:
            geom = gpd.GeoSeries.from_wkt(df['geometry'])
        except TypeError:
            print("Geometry passed is neither of format wkb or wkt so neither from PostGIS, neither from QBuildings\n"
                  "I wonder what you are trying to do here...")
            return df

    return gpd.GeoDataFrame(df, geometry=geom)
