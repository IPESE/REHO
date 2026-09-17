# Configuration file for the Sphinx documentation builder.

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import datetime
import os
import sys

sys.path.insert(0, os.path.abspath('..'))

# -- Project information -----------------------------------------------------


def _latest_released_version(fallback=">1.1.5"):
    """Version shown in the documentation, read from PyPI when it is reachable."""
    try:
        import requests

        response = requests.get("https://pypi.org/pypi/REHO/json", timeout=10)
        response.raise_for_status()
        return response.json()["info"]["version"]
    except Exception:
        # Read the Docs builds must not fail because PyPI is unreachable.
        return fallback


project = 'REHO'
copyright = '2021-%s, IPESE, EPFL' % datetime.date.today().year
author = 'D. Lepour, J. Loustau, C. Terrier'
version = _latest_released_version()
release = version

# -- General configuration ---------------------------------------------------

extensions = ['sphinxcontrib.bibtex',
              'sphinx.ext.autodoc',
              'sphinx.ext.napoleon',
              'sphinx.ext.autosummary',
              'sphinx_design',
              'sphinx_copybutton',
              'myst_parser',
              'sphinx.ext.mathjax']
source_suffix = [".rst", ".md"]
myst_enable_extensions = [
    "amsmath",
    "colon_fence",
    "dollarmath",
    "html_admonition",
    "substitution",
]
myst_dmath_double_inline = True
myst_substitutions = {
    "version": version,
    "release": version,
    "today": datetime.date.today().strftime("%B %d, %Y"),
}
# Virtual environments and build outputs live inside docs/; without excluding them
# Sphinx picks up the README and LICENSE files of every installed dependency.
exclude_patterns = [
    'LICENSE',
    '_build',
    '.venvdocs',
    'venvdocs',
    '**/.venv*',
    'Thumbs.db',
    '.DS_Store',
]

# Generate one API page per module under sections/_autosummary/, from
# _templates/autosummary/module.rst: the default template would only show the
# first line of each docstring.
templates_path = ['_templates']
autosummary_generate = True

# -- Bibliography ------------------------------------------------------------
bibtex_bibfiles = ['refs.bib']
bibtex_default_style = 'unsrt'
bibtex_reference_style = 'super'

# -- Options for HTML output -------------------------------------------------

html_theme = 'pydata_sphinx_theme'

html_static_path = ["_static"]
html_js_files = ["custom.js"]
html_css_files = ["custom.css"]

html_sidebars = {
  "_autosummary": ["sidebar-nav-bs"],
  "sections/model/index": [],
  "sections/model/*": ["sidebar-nav-bs"],
  "sections/data/index": [],
  "sections/data/*": ["sidebar-nav-bs"],
  "sections/*": []
}

# ------------ Generated tables ---------------------------
# The option tables are generated from reho.model.options so that the
# documentation cannot drift away from the defaults the code actually applies.


def _write_generated_tables(app=None):
    """Write docs/data/methods.csv and docs/data/dw_params.csv from the code."""
    import csv

    sys.path.insert(0, os.path.abspath('..'))
    try:
        from reho.model.options import (
            DEFAULT_DW_PARAMS,
            DEFAULT_METHODS,
            DW_PARAMS_DESCRIPTIONS,
            METHOD_DESCRIPTIONS,
        )
    except Exception:  # pragma: no cover - the tables committed in the repo are used instead
        return

    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)

    with open(os.path.join(data_dir, 'methods.csv'), 'w', newline='') as handle:
        writer = csv.writer(handle, delimiter=';')
        writer.writerow(['Method name', 'Description', 'Default value'])
        for name, default in DEFAULT_METHODS.items():
            writer.writerow(['*%s*' % name, METHOD_DESCRIPTIONS[name], '``%r``' % (default,)])

    with open(os.path.join(data_dir, 'dw_params.csv'), 'w', newline='') as handle:
        writer = csv.writer(handle, delimiter=';')
        writer.writerow(['Parameter', 'Description', 'Default value'])
        for name, description in DW_PARAMS_DESCRIPTIONS.items():
            default = DEFAULT_DW_PARAMS.get(name)
            writer.writerow(['*%s*' % name, description, '``%r``' % (default,) if default is not None else 'derived'])


def _remove_stale_api_pages(app=None):
    """Delete the generated API pages of modules that are gone from the reference.

    autosummary writes one page per module into sections/_autosummary/ but never deletes
    any: once a module is removed, or left out like the test-suite, the page an earlier
    build wrote fails to import and is in no toctree, which breaks ``sphinx-build -W``.
    """
    pages = os.path.join(os.path.dirname(__file__), 'sections', '_autosummary')
    if not os.path.isdir(pages):
        return
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    for page in os.listdir(pages):
        module, extension = os.path.splitext(page)
        if extension != '.rst':
            continue
        path = os.path.join(root, *module.split('.'))
        exists = os.path.isfile(path + '.py') or os.path.isfile(os.path.join(path, '__init__.py'))
        if not exists or module == 'reho.test' or module.startswith('reho.test.'):
            os.remove(os.path.join(pages, page))


def setup(app):
    # Before autosummary (priority 500) generates the pages, so that it recreates any it still needs
    app.connect('builder-inited', _remove_stale_api_pages, priority=400)
    app.connect('builder-inited', _write_generated_tables)

html_theme_options = {
  'github_url': 'https://github.com/IPESE/REHO',
  'header_links_before_dropdown': 7,
  'navbar_align': 'left',
  "external_links": [{"name": "REHO-fm", "url": "https://reho.epfl.ch/"}],
  "icon_links": [{"name": "IPESE",
                  "url": "https://ipese-web.epfl.ch/ipese-blog/",
                  "icon": "https://github.com/IPESE/REHO/blob/main/docs/images/logos/ipese_square.png?raw=true",
                  "type": "url"}],
  "logo": {"image_light": 'images/logos/logo-reho-black.png',
           "image_dark": "images/logos/logo-reho-white.png",
           "alt_text": "REHO documentation - Home"},
  "navigation_depth": 6
}
numfig = False  # No automatic figure numbering
numtab = False  # No automatic table numbering
add_function_parentheses = False
# Each module has its own API page, so its name need not be repeated in every
# signature and "On this page" entry (``file_reader``, ``REHO.single_optimization``).
add_module_names = False
toc_object_entries_show_parents = 'domain'


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
    "pyclustering",
    "pyclustering.cluster.kmedoids",
    "pyclustering.utils",
    "pyclustering.utils.metric",
    "pyproj",
    "dotenv",
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

# ------------ Napoleon (NumPy-style docstrings) ----------
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_rtype = False

# ------------ Cross-references ---------------------------
# `autodoc_mock_imports` replaces third-party modules by stubs, so their types
# cannot be resolved; do not warn about them.
nitpicky = False