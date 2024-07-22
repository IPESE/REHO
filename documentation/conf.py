# Configuration file for the Sphinx documentation builder.

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import os
import sys
from unittest.mock import MagicMock
sys.path.insert(0, os.path.abspath('../'))

# -- Project information -----------------------------------------------------

project = 'REHO'
copyright = '2021, IPESE, EPFL'
author = 'D. Lepour, J. Loustau, C. Terrier'
release = '1.1.0'


# -- General configuration ---------------------------------------------------

extensions = ['sphinxcontrib.bibtex',
              'sphinx.ext.autodoc',
              'sphinx.ext.napoleon',
              'sphinx.ext.autosummary',
              'sphinx_design',
              'sphinx_copybutton']
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
  "external_links": [{"name": "REHO-fm", "url": "https://ipese-test.epfl.ch/reho-fm/"}],
  "icon_links": [{"name": "IPESE",
                  "url": "https://ipese-web.epfl.ch/ipese-blog/",
                  "icon": "https://github.com/IPESE/REHO/blob/documentation/documentation/images/logos/ipese_square.png?raw=true",
                  "type": "url"}],
  "logo": {"image_light": 'images/logos/logo_reho.png',
           "image_dark": "images/logos/logo_reho_light.png",
           "alt_text": "REHO documentation - Home"},
  "navigation_depth": 6
}
numfig = True  # Add figure numbering
numtab = True  # Add table numbering
add_function_parentheses = False
toc_object_entries_show_parents = 'all'


# ------------ Autodoc ------------------------------------
autodoc_member_order = 'bysource'
autodoc_mock_imports = ['amplpy',
                        'pandas',
                        'openpyxl',
                        'numpy',
                        'scipy',
                        'scikit-learn',
                        'scikit-learn-extra',
                        'sqlalchemy',
                        'psycopg2',
                        'geopandas',
                        'matplotlib',
                        'plotly',
                        'kaleido',
                        'dotenv',
                        'requests',
                        'coloredlogs',
                        'SALib',
                        'qmcpy',
                        'pvlib',
                        'pyproj',
                        'shapely']
sys.modules['scikit-learn'] = MagicMock()
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.metrics'] = MagicMock()
sys.modules['scikit-learn-extra'] = MagicMock()
sys.modules['sklearn_extra'] = MagicMock()
sys.modules['sklearn_extra.cluster'] = MagicMock()
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['sqlalchemy.dialects'] = MagicMock()
sys.modules['sqlalchemy.exc'] = MagicMock()
