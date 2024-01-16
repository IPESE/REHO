import configparser
from sqlalchemy import create_engine, MetaData, select
from sqlalchemy.dialects import postgresql
import geopandas as gpd
import re
import csv
from reho.paths import *
import reho.model.preprocessing.skydome_input_parser as skd
import pandas as pd
import numpy as np
import math
from csv import Sniffer
from pathlib import Path
from pandas import read_csv, read_table, read_excel
import sys


class QBuildingsReader:

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
        :param db: Name of the database to which we want to connect - Florissant, Sierre, Geneva
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

    def read_csv(self, buildings_filename, nb_buildings=None, roofs_filename=None, facades_filename=None):

        self.data['buildings'] = file_reader(os.path.join(path_to_buildings, buildings_filename))
        self.data['buildings'] = translate_buildings_to_REHO(self.data['buildings'])
        # self.data['buildings'] = add_geometry(self.data['buildings'])
        if nb_buildings is None:
            nb_buildings = self.data['buildings'].shape[0]
        buildings = self.select_buildings_data(nb_buildings, None)
        # buildings = add_geometry(buildings)
        qbuildings = {'buildings_data': buildings}
        if self.load_facades:
            self.data['facades'] = file_reader(os.path.join(path_to_buildings, facades_filename))
            selected_facades = self.select_roofs_or_facades_data(roof=False)
            self.data['facades'] = self.data['facades'][self.data['facades'].index.isin(selected_facades)]
            self.data['facades'] = add_geometry(self.data['facades'])
            self.data['facades'] = translate_facades_to_REHO(self.data['facades'], self.data['buildings'])
            qbuildings['facades_data'] = self.data['facades']
            qbuildings['shadows_data'] = return_shadows_district(self.data['buildings'], self.data['facades'])

        if self.load_roofs:
            self.data['roofs'] = file_reader(os.path.join(path_to_buildings, roofs_filename))
            selected_roofs = self.select_roofs_or_facades_data(roof=True)
            self.data['roofs'] = self.data['roofs'][self.data['roofs'].index.isin(selected_roofs)]
            self.data['roofs'] = add_geometry(self.data['roofs'])
            self.data['roofs'] = translate_roofs_to_REHO(self.data['roofs'])
            qbuildings['roofs_data'] = self.data['roofs']

        return qbuildings

    def read_db(self, transformer=None, nb_buildings=None, egid=None, to_csv=False, to_csv_REHO=False,
                return_location=False):
        """
        :param transformer: ID of the transformer on which we want to optimize
        :param nb_buildings: Number of buildings to select
        :param egid: To specify a list of buildings to optimize with their egid
        :param to_csv: To export the data into csv
        :param to_csv_REHO: To export the data into csv but translated for REHO
        :param return_location: To obtain the corresponding meteo cluster
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
            csv_file = os.path.join(path_to_buildings,
                                    self.db + '_' + str(transformer) + '_' + str(nb_buildings) + '.csv')
            self.data['buildings'].to_csv(csv_file, index=False)

        self.data['buildings'] = translate_buildings_to_REHO(self.data['buildings'])
        # self.district = self.data['buildings']
        buildings = self.select_buildings_data(nb_buildings, egid)
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
            self.data['roofs'] = translate_roofs_to_REHO(self.data['roofs'])
            qbuildings['roofs_data'] = self.data['roofs']

        if to_csv_REHO:
            csv_file = os.path.join(path_to_buildings,
                                    self.db + '_' + str(transformer) + '_' + str(nb_buildings) + '_REHO.csv')
            csv_columns = list(buildings[list(buildings.keys())[0]].keys())
            with open(csv_file, 'w') as csvfile:
                writer = csv.DictWriter(csvfile, csv_columns)
                writer.writeheader()
                for building in buildings:
                    writer.writerow(buildings[building])

        # TODO return meteo_cluster
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

    # filename = os.path.join(path_to_buildings, 'angles.csv')
    # df_angles.to_csv(filename)
    # df_angles.index = int(df_angles.index)
    return df_angles


def return_shadows_district(buildings, facades):
    df_district = pd.DataFrame()
    filename = os.path.join(path_to_buildings, 'angles.csv')
    # if not os.path.exists(filename):
    df_angles = neighbourhood_angles(buildings, facades)
    # else:
    #   df_angles = pd.read_csv(filename)

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
        df_district = pd.concat((df_district, df_id_building))

    df_district["id_building"] = df_district["id_building"].astype(str)
    out_put = os.path.join(path_to_buildings, 'district_shadows.csv')
    df_district.to_csv(out_put)

    return df_district


def return_shadows_id_building(id_building, df_district):
    id_building = int(id_building)
    filepath = os.path.join(path_to_buildings, 'district_shadows.csv')
    if os.path.isfile(filepath):
        df = file_reader(filepath, index_col=0)
    else:
        df = df_district
    df = df.xs(id_building)
    df_dome = skd.skydome_to_df()

    df_beta_dome = pd.DataFrame()
    for az in df_dome.azimuth:
        df_beta_dome = pd.concat((df_beta_dome, df.beta[df.azimuth == az]), ignore_index=True)

    df_beta_dome = df_beta_dome.rename(columns={0: 'Limiting_angle_shadow'})

    return df_beta_dome


def file_reader(file, index_col=None):
    """To read data files correctly, whether there are csv, txt, dat or excel"""
    file = Path(file)
    try:
        if file.suffix == '.csv' or file.suffix == '.dat' or file.suffix == '.txt':
            sniffer = Sniffer()
            with open(file, 'r') as f:
                line = next(f).strip()
                delim = sniffer.sniff(line)
            return read_csv(file, sep=delim.delimiter, index_col=index_col)
        elif file.suffix == '.xlsx':
            return read_excel(file)
        else:
            return read_table(file)
    except:
        print('It seems there is a problem while reading the file...\n')
        print("%s" % sys.exc_info()[1])


def add_geometry(df):
    """
    Avoid issues with geometry when read from a csv
    """
    try:
        geom = gpd.GeoSeries.from_wkb(df['geometry'])
    except TypeError:
        try:
            geom = gpd.GeoSeries.from_wkt(df['geometry'])
        except TypeError:
            print("Geometry passed is neither of format wkb or wkt so neither from PostGIS, neither from QBuildings\n"
                  "I wonder what you are trying to do here...")
            return df
    except KeyError:
        print("No geometry in the dataframe")
        return df
    except:
        print("Incompatible geometry")
        return df

    return gpd.GeoDataFrame(df, geometry=geom)
