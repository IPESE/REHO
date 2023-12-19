import os
import platform
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# if "AMPL_PATH" not in os.environ:
#     if platform.system() == 'Darwin':
#         os.environ["AMPL_PATH"] = "/Users/lepour/Applications/ampl"
#     else:
#         os.environ["AMPL_PATH"] = "C:/AMPL"


path_to_reho = os.path.dirname(__file__)
path_to_data = os.path.join(path_to_reho, 'data')
path_to_model = os.path.join(path_to_reho, 'model')
path_to_scripts = os.path.join(path_to_reho, '../scripts')
path_to_plotting = os.path.join(path_to_reho, 'plotting')

# AMPL model
path_to_ampl_model = os.path.join(path_to_model, 'ampl_model')
path_to_units = os.path.join(path_to_ampl_model, 'units')
path_to_district_units = os.path.join(path_to_ampl_model, 'units', 'district_units')
path_to_units_storage = os.path.join(path_to_ampl_model, 'units', 'storage')
path_to_units_h2 = os.path.join(path_to_ampl_model, 'units', 'h2_units')

# actors solutions
path_to_actors_results = os.path.join(path_to_scripts, 'actors', 'results')
path_to_configuration = os.path.join(path_to_actors_results, "configurations")

###### Data

# buildings
path_to_buildings = os.path.join(path_to_data, 'buildings')

# electricity
path_to_electricity = os.path.join(path_to_data, 'electricity')

# emissions
path_to_emissions = os.path.join(path_to_data, 'emissions')
path_to_emissions_matrix = os.path.join(path_to_emissions, 'electricity_matrix_2019_reduced.csv')

# parameters
path_to_parameters = os.path.join(path_to_data, 'parameters')

# QBuildings
path_to_qbuildings = os.path.join(path_to_data, 'QBuildings')

# SIA
path_to_sia = os.path.join(path_to_data, 'SIA')

# skydome
path_to_skydome = os.path.join(path_to_data, 'skydome')
typical_irradiation_csv = os.path.join(path_to_skydome, 'typical_irradiation.csv')
total_irradiation_csv = os.path.join(path_to_skydome, 'total_irradiation_time.csv')

# weather
path_to_clustering_results = os.path.join(path_to_data, 'weather', 'clustering_results')
path_to_weather = os.path.join(path_to_data, 'weather')