<p align="center">
  <img
    src="https://raw.githubusercontent.com/IPESE/REHO/v1.2.1/docs/images/logos/logo-reho-black.png"
    width="300"
    alt="REHO logo"
  />
</p>

[![DOI](https://joss.theoj.org/papers/10.21105/joss.06734/status.svg)](https://doi.org/10.21105/joss.06734)
[![Documentation Status](https://readthedocs.org/projects/reho/badge/?version=main)](https://reho.readthedocs.io/)

[![PyPI](https://img.shields.io/pypi/v/REHO.svg)](https://pypi.org/project/REHO/)[![Python Version](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://pypi.org/project/REHO/)

[![License](https://img.shields.io/badge/license-Apache%202-blue)](https://www.apache.org/licenses/LICENSE-2.0)


Renewable Energy Hub Optimizer (REHO) is a decision support tool for sustainable urban energy system planning.
REHO simultaneously addresses the optimal design and operation of capacities, catering to multi-objective considerations
across economic, environmental, and efficiency criteria.

Key features:
* MILP Framework
* Multi-Objective Optimization
* Multi-Scale Capabilities
* Multi-Service Consideration
* Multi-Energy Integration
* Open-Source and Open-Data

For more information about the model foundations and features, please refer to the [REHO documentation](https://reho.readthedocs.io/en/main/).

## Authors
REHO is developed by EPFL (Switzerland), within the Industrial Process and Energy Systems Engineering (IPESE) group.

Dorsan Lepour <dorsan.lepour@epfl.ch>  
Cédric Terrier <cedric.terrier@epfl.ch>  
Joseph Loustau

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/IPESE/REHO/blob/main/docs/images/logos/ipese-logo-white.svg?raw=true">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/IPESE/REHO/blob/main/docs/images/logos/ipese-logo-black.svg?raw=true">
  <img width="300"  alt="Shows the IPESE logo, white one in dark color mode and black one in light color mode.">
</picture>

## Licence
Copyright (C) <2021-2026> <Ecole Polytechnique Fédérale de Lausanne (EPFL), Switzerland>

Licensed under the Apache License, (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Description and complete License: see LICENSE file.

## Installation

REHO is available as a [PyPI package](https://pypi.org/project/REHO/) and can be installed via pip with:
```
pip install --extra-index-url https://pypi.ampl.com REHO
```

Full code can be accessed from the [REHO GitHub repository](https://github.com/IPESE/REHO) and cloned with:
```
git clone https://github.com/IPESE/REHO.git
```

Please refer to the "[Getting started](https://reho.readthedocs.io/en/main/sections/getting_started.html)" section of the documentation for step-by-step guidelines.

## A first run

```python
from reho import REHO, QBuildingsReader, initialize_grids, initialize_units

reader = QBuildingsReader()
reader.establish_connection('Geneva')
qbuildings_data = reader.read_db({'transformers': 234}, nb_buildings=2)

cluster = {'Location': 'Geneva', 'Attributes': ['T', 'I', 'W'], 'Periods': 10, 'PeriodDuration': 24}
scenario = {'Objective': 'TOTEX', 'name': 'totex'}

grids = initialize_grids()
units = initialize_units(scenario, grids)

reho = REHO(qbuildings_data=qbuildings_data, units=units, grids=grids,
            cluster=cluster, scenario=scenario, method={'building-scale': True})
reho.single_optimization()
reho.save_results(format=['xlsx', 'pickle'], filename='my_run')
```

The [examples](https://github.com/IPESE/REHO/tree/main/scripts/examples) cover the
other features: district-scale decomposition, Pareto fronts, district heating,
electric mobility, renovation, seasonal storage and the multi-actor formulation.

## Documentation

| Page | Content |
|---|---|
| [Overview](https://reho.readthedocs.io/en/main/sections/overview.html) | What REHO is and what it can do |
| [Releases](https://reho.readthedocs.io/en/main/sections/releases.html) | How to cite, license, and the works using REHO |
| [Model](https://reho.readthedocs.io/en/main/sections/model/index.html) | The mathematical formulation, at the building, district and actors scales |
| [Data reference](https://reho.readthedocs.io/en/main/sections/data/index.html) | Inputs, every reference data file, and outputs, every result DataFrame: columns, units, provenance |
| [Package structure](https://reho.readthedocs.io/en/main/sections/package_structure.html) | Layout of the package, and the API reference of every module, class and function |
| [Developer guide](https://reho.readthedocs.io/en/main/sections/developer_guide.html) | Conventions, how to extend, test and document REHO, and how to contribute |
| [Getting started](https://reho.readthedocs.io/en/main/sections/getting_started.html) | Installation, AMPL license, and a first optimization |
| [Examples](https://reho.readthedocs.io/en/main/sections/examples.html) | One runnable script per feature |

## Suggestions and contributions

All suggestions or implementation must be tracked with dedicated issues and reported in the project repository.

Refer to the "[Contributing](https://reho.readthedocs.io/en/main/sections/developer_guide.html#contributing)" section of the developer guide for further guidance.

### Running the tests

```bash
pytest reho/test -m "not slow"        # offline: no AMPL license, solver or database needed
REHO_RUN_EXAMPLES=1 pytest reho/test  # full: runs every example script
```
