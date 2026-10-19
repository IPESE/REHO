# Configuration file for the Sphinx documentation builder.

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import os
import sys
import requests
from unittest.mock import MagicMock
sys.path.insert(0, os.path.abspath('../'))

# -- Project information -----------------------------------------------------

try:
    response = requests.get("https://pypi.org/pypi/REHO/json")
    if response.status_code == 200:
        data = response.json()
        latest_version = data["info"]["version"]
    else:
        latest_version = ">1.1.5"
except Exception as e:
    f"error: {str(e)}"

project = 'REHO'
copyright = '2021, IPESE, EPFL'
author = 'D. Lepour, J. Loustau, C. Terrier'
version = latest_version

# -- General configuration ---------------------------------------------------

extensions = ['sphinxcontrib.bibtex',
              'sphinx.ext.autodoc',
              'sphinx.ext.napoleon',
              'sphinx.ext.autosummary',
              'sphinx_design',
              'sphinx_copybutton']
source_suffix = [".rst", ".md"]
exclude_patterns = ['LICENSE']
# autosummary_generate = True  # Turn on sphinx.ext.autosummary

# -- Bibliography ------------------------------------------------------------
bibtex_bibfiles = ['refs.bib']
bibtex_default_style = 'unsrt'
bibtex_reference_style = 'super'

# -- Options for HTML output -------------------------------------------------

html_theme = 'pydata_sphinx_theme'

html_sidebars = {
  "_autosummary": ["sidebar-nav-bs"],
  "sections/*": []
}

html_theme_options = {
  'github_url': 'https://github.com/IPESE/REHO',
  'header_links_before_dropdown': 7,
  'navbar_align': 'left',
  # "external_links": [{"name": "REHO-fm", "url": "https://ipese-test.epfl.ch/reho-fm/"}],
  "icon_links": [{"name": "IPESE",
                  "url": "https://ipese-web.epfl.ch/ipese-blog/",
                  "icon": "https://github.com/IPESE/REHO/blob/main/docs/images/logos/ipese_square.png?raw=true",
                  "type": "url"}],
  "logo": {"image_light": 'images/logos/logo-reho-black.png',
           "image_dark": "images/logos/logo-reho-white.png",
           "alt_text": "REHO documentation - Home"},
  "navigation_depth": 6
}
numfig = True  # Add figure numbering
numtab = True  # Add table numbering
add_function_parentheses = False
toc_object_entries_show_parents = 'all'


# ------------ Autodoc ------------------------------------
autodoc_member_order = 'bysource'

# From REHO requirements.txt
autodoc_mock_imports = [
    "amplpy",
    "ampl_module_base",
    "ampl_module_highs",
    "coloredlogs",
    "geopandas",
    "kaleido",
    "matplotlib",
    "numpy",
    "openpyxl",
    "pandas",
    "plotly",
    "psycopg2",
    "pvlib",
    "pyclustering"
    "pyproj",
    "python-dotenv",
    "pytest",
    "qmcpy",
    "requests",
    "SALib",
    "scipy",
    "setuptools",
    "shapely",
    "sqlalchemy",
    "sympy",
    "urllib3",
]

# Handling specific imports
sys.modules['pyclustering.cluster.kmedoids'] = MagicMock()
sys.modules['pyclustering.utils.metric'] = MagicMock()
sys.modules['pyclustering.utils'] = MagicMock()

sys.modules['dotenv'] = MagicMock()

sys.modules['pyproj'] = MagicMock()