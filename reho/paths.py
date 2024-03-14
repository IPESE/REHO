import os
from csv import Sniffer
from pathlib import Path
from pandas import read_csv, read_table, read_excel
import sys
from dotenv import load_dotenv

__doc__ = """
*File for managing file paths and configurations.*
"""


load_dotenv()
if "AMPL_PATH" not in os.environ:
    print("AMPL_PATH is not defined. Please include a .env file at the project root (e.g., AMPL_PATH='C:/AMPL')")

path_to_reho = os.path.dirname(__file__)
path_to_data = os.path.join(path_to_reho, 'data')
path_to_model = os.path.join(path_to_reho, 'model')
path_to_plotting = os.path.join(path_to_reho, 'plotting')

# AMPL model
path_to_ampl_model = os.path.join(path_to_model, 'ampl_model')
path_to_units = os.path.join(path_to_ampl_model, 'units')
path_to_district_units = os.path.join(path_to_ampl_model, 'units', 'district_units')
path_to_units_storage = os.path.join(path_to_ampl_model, 'units', 'storage')
path_to_units_h2 = os.path.join(path_to_ampl_model, 'units', 'h2_units')

# data

# elcom
path_to_elcom = os.path.join(path_to_data, 'elcom')

# emissions
path_to_emissions_matrix = os.path.join(path_to_data, 'emissions', 'electricity_matrix_2019_reduced.csv')

# infrastructure
path_to_infrastructure = os.path.join(path_to_data, 'infrastructure')

# QBuildings
path_to_qbuildings = os.path.join(path_to_data, 'QBuildings')

# SIA
path_to_sia = os.path.join(path_to_data, 'SIA')

# skydome
path_to_skydome = os.path.join(path_to_data, 'skydome')
path_to_irradiation = os.path.join(path_to_skydome, 'total_irradiation.csv')

# weather
path_to_weather = os.path.join(path_to_data, 'weather')

# scripts specific paths
path_to_clustering = os.path.join(os.getcwd(), 'data', 'clustering')
path_to_configurations = os.path.join(os.getcwd(), 'configurations')


def path_handler(path_given):
    """To handle the path to csv file, absolute path or not"""

    if os.path.isabs(path_given):
        if os.path.isfile(path_given):
            return path_given
        else:
            raise FileNotFoundError('The absolute path that was given is not a valid file.')
    else:
        if os.path.isfile(os.path.realpath(path_given)):
            return os.path.realpath(path_given)
        else:
            raise FileNotFoundError('The relative path that was given is not a valid file.')


def file_reader(file, index_col=None):
    """To read data files correctly, whether there are csv, txt, dat or excel"""
    file = Path(path_handler(file))
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
        print('It seems there is a problem when reading the file...\n')
        print("%s" % sys.exc_info()[1])