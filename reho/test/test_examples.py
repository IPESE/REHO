"""End-to-end tests: run every example script and assert that it succeeds.

The example scripts under ``scripts/examples/`` are REHO's tutorial *and* its
integration test-suite. They are run in a subprocess so that a failure — a
non-zero exit code — fails the test, and so that one example crashing does not
take the whole session with it.

Most of them need an AMPL license, a solver and network access to the QBuildings
database; they are therefore marked ``slow`` and skipped unless the environment
variable ``REHO_RUN_EXAMPLES`` is set:

.. code-block:: bash

    REHO_RUN_EXAMPLES=1 pytest reho/test/test_examples.py -k example_1a
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import requests

BASE_API_URL = "https://api.github.com/repos/IPESE/REHO/contents/scripts/examples"
EXAMPLES_DIR = Path(__file__).parent.parent.parent / "scripts" / "examples"

#: Examples in run order. The list is the single source of truth: adding an
#: example here is enough for it to be downloaded, run and reported on.
EXAMPLES = [
    "0_Compact_formulation.py",
    "1a_Building-scale_totex.py",
    "1b_Building-scale_Pareto.py",
    "2a_District-scale_totex.py",
    "2b_District-scale_Pareto.py",
    "3a_Read_csv.py",
    "3b_Custom_infrastructure.py",
    "3c_HP_T_source.py",
    "3d_EVs.py",
    "3e_DHN.py",
    "3f_Custom_profiles.py",
    "3g_Stochastic_profiles.py",
    "3h_Fix_units.py",
    "3i_Electricity_prices.py",
    "3j_Transformer_capacity.py",
    "3k_Renovation.py",
    "3l_Datacenter.py",
    "4a_Progressive_scenarios.py",
    "4b_Sensitivity_analysis.py",
    "5a_PV_orientation.py",
    "5b_PV_facades.py",
    "6a_Mobility_sector.py",
    "6b_Mobility_externaldistricts.py",
    "7a_rSOC_IP.py",
    "7b_rSOC_H2_export.py",
    "7c_district_IP.py",
    "8a_Actors_problem.py",
    "8b_Actors_problem_rent_increase.py",
]

#: Timeout of a single example, in seconds. A Pareto front over a district is the
#: slowest of them.
EXAMPLE_TIMEOUT = 3600

run_examples = pytest.mark.skipif(
    not os.environ.get("REHO_RUN_EXAMPLES"),
    reason="Set REHO_RUN_EXAMPLES=1 to run the examples (needs an AMPL license, a solver and database access).",
)


def download_file(file_url, local_path):
    """Download one file of the examples directory from GitHub."""
    response = requests.get(file_url, timeout=60)
    response.raise_for_status()
    with open(local_path, "wb") as file_out:
        file_out.write(response.content)


def process_directory(api_url, local_dir):
    """Recursively download a directory of the REHO repository from the GitHub API."""
    response = requests.get(api_url, timeout=60)
    response.raise_for_status()

    for item in response.json():
        item_path = os.path.join(local_dir, item["name"])
        if item["type"] == "file":
            download_file(item["download_url"], item_path)
        elif item["type"] == "dir":
            os.makedirs(item_path, exist_ok=True)
            process_directory(item["url"], item_path)


def test_download_examples():
    """Fetch the example scripts, for users who installed REHO from PyPI.

    Exposed as the ``reho-download-examples`` console script.
    """
    if EXAMPLES_DIR.exists():
        return
    os.makedirs(EXAMPLES_DIR)
    process_directory(BASE_API_URL, EXAMPLES_DIR)


def execute_script(script_path):
    """Run one example and raise if it fails.

    Parameters
    ----------
    script_path : str or pathlib.Path
        Path of the script. It is run from its own directory, because the
        examples read their inputs from ``./data`` and write to ``./results``.

    Raises
    ------
    AssertionError
        If the script exits with a non-zero status, with its stderr attached.
    """
    script_path = Path(script_path)
    result = subprocess.run(
        [sys.executable, script_path.name],
        cwd=script_path.parent,
        capture_output=True,
        text=True,
        timeout=EXAMPLE_TIMEOUT,
    )
    assert result.returncode == 0, (
        f"{script_path.name} failed with exit code {result.returncode}\n"
        f"--- stdout (tail) ---\n{result.stdout[-3000:]}\n"
        f"--- stderr (tail) ---\n{result.stderr[-3000:]}"
    )


def test_examples_are_all_listed():
    """Every script in the examples directory must appear in :data:`EXAMPLES`.

    Guards against an example being added to the repository but never run by CI.
    """
    if not EXAMPLES_DIR.exists():
        pytest.skip("The examples directory is not available in this installation.")

    on_disk = {p.name for p in EXAMPLES_DIR.glob("*.py")}
    missing = sorted(on_disk - set(EXAMPLES))
    assert not missing, f"These examples are not listed in test_examples.EXAMPLES: {missing}"


@run_examples
@pytest.mark.slow
@pytest.mark.parametrize("example", EXAMPLES)
def test_example(example):
    """Run one example script and assert it completes successfully."""
    script_path = EXAMPLES_DIR / example
    if not script_path.exists():
        pytest.skip(f"{example} is not available in this installation.")
    execute_script(script_path)
