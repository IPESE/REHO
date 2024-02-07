# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
from unittest.mock import MagicMock
sys.path.insert(0, os.path.abspath('../'))

# -- Project information -----------------------------------------------------

project = 'REHO'
copyright = '2021, IPESE, EPFL'
author = 'D. Lepour'

# The full version, including alpha/beta/rc tags
release = '1.0'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ['sphinxcontrib.bibtex',
              'sphinx.ext.autodoc',
              'sphinx.ext.napoleon',
              'sphinx.ext.autosummary',
              'sphinx_design']
# autosummary_generate = True  # Turn on sphinx.ext.autosummary

# -- Bibliography ------------------------------------------------------------
bibtex_bibfiles = ['refs.bib']
bibtex_default_style = 'plain'
bibtex_reference_style = 'super'


# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.

html_theme = 'pydata_sphinx_theme'
html_sidebars = {
  "**": []
}

html_theme_options = {
  'github_url': 'https://github.com/IPESE/REHO',
  'header_links_before_dropdown': 6,
  'navbar_align': 'left',
  # "external_links": [{"name": "IPESE", "url": "https://ipese-web.epfl.ch/ipese-blog/"},],
  "icon_links": [{"name": "IPESE",
                  "url": "https://ipese-web.epfl.ch/ipese-blog/",
                  "icon": "https://github.com/IPESE/REHO/blob/main/documentation/images/ipese-square.png?raw=true",
                  "type": "url"}],
  "logo": {"image_light": 'sections/1_Overview/images/logo_reho.png',
           "image_dark": "images/logo_reho_light.png",
           "alt_text": "REHO documentation - Home"},
  "navigation_depth": 6
}
numfig = True  # Add figure numbering
numtab = True  # Add table numbering
add_function_parentheses = False
toc_object_entries_show_parents = 'all'
# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_extra_path = ['_static']
# html_style = 'css/custom.css'
# def setup(app):
#     app.add_css_file('css/custom.css')

# ------------ Autodoc ------------------------------------
autodoc_mock_imports = ['amplpy',
                        'pandas',
                        'openpyxl',
                        'numpy',
                        'scikit-learn',
                        'scikit-learn-extra',
                        'psycopg2',
                        'requests',
                        'sqlalchemy',
                        'scipy',
                        'matplotlib',
                        'plotly',
                        'geopandas',
                        'urllib3',
                        'dotenv']
sys.modules['scikit-learn'] = MagicMock()
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.metrics'] = MagicMock()
sys.modules['scikit-learn-extra'] = MagicMock()
sys.modules['sklearn_extra'] = MagicMock()
sys.modules['sklearn_extra.cluster'] = MagicMock()
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['sqlalchemy.dialects'] = MagicMock()
sys.modules['shapely'] = MagicMock()
