import os
from csv import Sniffer
from pathlib import Path
from pandas import read_csv, read_table, read_excel, set_option
import sys
from dotenv import load_dotenv, find_dotenv

__doc__ = """
File for managing file paths and configurations.
"""

set_option('display.expand_frame_repr', False)

path_to_reho = os.path.dirname(__file__)
path_to_data = os.path.join(path_to_reho, 'data')
path_to_model = os.path.join(path_to_reho, 'model')
path_to_plotting = os.path.join(path_to_reho, 'plotting')

# Load environment variables
package_dotenv = find_dotenv(os.path.join(path_to_reho, '.env'))  # Find the .env file in project root or REHO package installation directory
current_dir_dotenv = find_dotenv(os.path.join(os.getcwd(), '.env'))  # Find the .env file in the current working directory (where script is run)

if package_dotenv:
    load_dotenv(dotenv_path=package_dotenv)
    print(f"Loaded .env from package root: {package_dotenv}")
elif current_dir_dotenv:
    load_dotenv(dotenv_path=current_dir_dotenv, override=True)
    print(f"Loaded .env from current working directory: {current_dir_dotenv}")
else:
    print("No .env file found, using system environment variables.")

# AMPL model
path_to_ampl_model = os.path.join(path_to_model, 'ampl_model')
path_to_units = os.path.join(path_to_ampl_model, 'units')
path_to_district_units = os.path.join(path_to_ampl_model, 'units', 'district_units')
path_to_units_storage = os.path.join(path_to_ampl_model, 'units', 'storage')
path_to_units_h2 = os.path.join(path_to_ampl_model, 'units', 'h2_units')

# data
path_to_elcom = os.path.join(path_to_data, 'elcom')

path_to_emissions = os.path.join(path_to_data, 'emissions', 'electricity_matrix_2019_reduced.csv')

path_to_infrastructure = os.path.join(path_to_data, 'infrastructure')

path_to_qbuildings = os.path.join(path_to_data, 'QBuildings')

path_to_sia = os.path.join(path_to_data, 'SIA')
path_to_sia_equivalence = os.path.join(path_to_sia, 'sia2024_rooms_sia380_1.csv')
path_to_sia_norms = os.path.join(path_to_sia, 'sia2024_data.xlsx')

path_to_skydome = os.path.join(path_to_data, 'skydome')
path_to_irradiation = os.path.join(path_to_skydome, 'total_irradiation.csv')
path_to_areas = os.path.join(path_to_skydome, 'skyPatchesAreas.txt')  # area of patches
path_to_cenpts = os.path.join(path_to_skydome, 'skyPatchesCenPts.txt')  # location of centre points

# scripts specific paths
path_to_clustering = os.path.join(os.getcwd(), 'data', 'clustering')
path_to_configurations = os.path.join(os.getcwd(), 'results', 'configurations')


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
        if file.suffix in ['.csv', '.dat', '.txt']:
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
