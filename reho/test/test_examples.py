import os
import requests
from pathlib import Path

BASE_API_URL = "https://api.github.com/repos/IPESE/REHO/contents/scripts/examples"
EXAMPLES_DIR = Path(__file__).parent.parent.parent / "scripts" / "examples"


def download_file(file_url, local_path):
    response = requests.get(file_url)
    if response.status_code == 200:
        with open(local_path, 'wb') as file_out:
            file_out.write(response.content)
        print(f"Downloaded {file_url} to {local_path}")
    else:
        print(f"Failed to download {file_url}: {response.status_code}")


def process_directory(api_url, local_dir):
    response = requests.get(api_url)
    if response.status_code != 200:
        print(f"Failed to fetch directory listing: {response.status_code}")
        return

    items = response.json()
    for item in items:
        item_name = item['name']
        item_path = os.path.join(local_dir, item_name)
        if item['type'] == 'file':
            raw_url = item['download_url']
            download_file(raw_url, item_path)
        elif item['type'] == 'dir':
            os.makedirs(item_path, exist_ok=True)
            process_directory(item['url'], item_path)


def test_download_examples():
    if not EXAMPLES_DIR.exists():
        os.makedirs(EXAMPLES_DIR)
        process_directory(BASE_API_URL, EXAMPLES_DIR)


def execute_script(script_path):
    print(f"Executing {script_path}...")
    os.system(f"python {script_path}")


def test_example_0():
    script_path = Path(EXAMPLES_DIR) / "0_Compact_formulation.py"
    execute_script(script_path)


def test_example_1a():
    script_path = Path(EXAMPLES_DIR) / "1a_Building-scale_totex.py"
    execute_script(script_path)


def test_example_1b():
    script_path = Path(EXAMPLES_DIR) / "1b_Building-scale_Pareto.py"
    execute_script(script_path)


def test_example_2a():
    script_path = Path(EXAMPLES_DIR) / "2a_District-scale_totex.py"
    execute_script(script_path)


def test_example_2b():
    script_path = Path(EXAMPLES_DIR) / "2b_District-scale_Pareto.py"
    execute_script(script_path)


def test_example_3a():
    script_path = Path(EXAMPLES_DIR) / "3a_Read_csv.py"
    execute_script(script_path)


def test_example_3b():
    script_path = Path(EXAMPLES_DIR) / "3b_Custom_infrastructure.py"
    execute_script(script_path)


def test_example_3c():
    script_path = Path(EXAMPLES_DIR) / "3c_HP_T_source.py"
    execute_script(script_path)


def test_example_3d():
    script_path = Path(EXAMPLES_DIR) / "3d_EVs.py"
    execute_script(script_path)


def test_example_3e():
    script_path = Path(EXAMPLES_DIR) / "3e_DHN.py"
    execute_script(script_path)


def test_example_3f():
    script_path = Path(EXAMPLES_DIR) / "3f_Custom_profiles.py"
    execute_script(script_path)


def test_example_3g():
    script_path = Path(EXAMPLES_DIR) / "3g_Stochastic_profiles.py"
    execute_script(script_path)


def test_example_3h():
    script_path = Path(EXAMPLES_DIR) / "3h_Fix_units.py"
    execute_script(script_path)


def test_example_3i():
    script_path = Path(EXAMPLES_DIR) / "3i_Electricity_prices.py"
    execute_script(script_path)


def test_example_4a():
    script_path = Path(EXAMPLES_DIR) / "4a_Progressive_scenarios.py"
    execute_script(script_path)


def test_example_4b():
    script_path = Path(EXAMPLES_DIR) / "4b_Sensitivity_analysis.py"
    execute_script(script_path)


def test_example_5a():
    script_path = Path(EXAMPLES_DIR) / "5a_PV_orientation.py"
    execute_script(script_path)


def test_example_5b():
    script_path = Path(EXAMPLES_DIR) / "5b_PV_facades.py"
    execute_script(script_path)


def test_example_6a():
    script_path = Path(EXAMPLES_DIR) / "6a_Actors_problem.py"
    execute_script(script_path)
