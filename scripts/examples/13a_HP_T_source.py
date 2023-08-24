from model.reho import *
from pathlib import Path
from model.preprocessing.QBuildings import *
from model.postprocessing.postcompute_decentralized_districts import *
from model.preprocessing.QBuildings import QBuildingsReader
from model.preprocessing.data_generation import *

current_folder = Path(__file__).resolve().parent
folder = current_folder / 'results'

from model.reho import *
from pathlib import Path
from model.preprocessing.QBuildings import *
from model.postprocessing.postcompute_decentralized_districts import *
from model.preprocessing.QBuildings import QBuildingsReader
import pickle

current_folder = Path(__file__).resolve().parent
folder = current_folder / 'results'


def build_district(grids, scenario, transfo_id, nb_buildings):

    # connect to Suisse database
    reader = QBuildingsReader()
    reader.establish_connection('Suisse')
    qbuildings_data = reader.read_db(transfo_id, nb_buildings=nb_buildings)
    units = infrastructure.initialize_units(scenario, grids=grids, district_units=True)

    # replace nan in buildings data
    for bui in qbuildings_data["buildings_data"]:
        qbuildings_data["buildings_data"][bui]["id_class"] = qbuildings_data["buildings_data"][bui]["id_class"].replace("nan", "II")

        if math.isnan(qbuildings_data["buildings_data"][bui]["U_h"]):
            qbuildings_data["buildings_data"][bui]["U_h"] = 0.00181

        if math.isnan(qbuildings_data["buildings_data"][bui]["HeatCapacity"]):
            qbuildings_data["buildings_data"][bui]["HeatCapacity"] = 120

        if math.isnan(qbuildings_data["buildings_data"][bui]["T_comfort_min_0"]):
            qbuildings_data["buildings_data"][bui]["T_comfort_min_0"] = 20

    return qbuildings_data, units


def execute_DW_with_increasing_BUI():

    transfo = 10889
    nb_buildings = 4

    # Define scenario
    Scenario = {'Objective': 'TOTEX', 'EMOO': {}, 'specific': [], "name": "multi_districts"}
    Scenario["exclude_units"] = ["ThermalSolar"]
    Scenario["enforce_units"] = []

    Method = {"decomposed": False, "decentralized": True}

    grids = infrastructure.initialize_grids({'Electricity': {"Cost_demand_cst": 0.08, "Cost_supply_cst": 0.20},
                                        'NaturalGas': {"Cost_demand_cst": 0.06, "Cost_supply_cst": 0.20}})

    # select district data
    buildings_data, units = build_district(grids, Scenario, transfo, nb_buildings)

    # select weather data
    cluster = {'Location': 'Geneva', 'Attributes': ['I', 'T'], 'Periods': 10, 'PeriodDuration': 24}

    # specify the temperature of the DHN
    parameters = {"T_source": np.repeat({"Geothermal": 17.0}, nb_buildings)}

    # run opti
    reho_model = reho(buildings_data, units=units, grids=grids, cluster=cluster, method=Method, scenario=Scenario, parameters=parameters)
    reho_model.single_optimization()

    # get results
    reho_model.remove_all_ampl_lib()

    SR.save_results(reho_model, save=['xlsx', 'pickle'], filename='13a')
    return



if __name__ == '__main__':
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)
    execute_DW_with_increasing_BUI()

