# All rights reserved. ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland,
# IPESE Laboratory, Copyright 2021
# This work can be distributed under the Apache Software License.
# See the LICENSE file for more details.

from setuptools import setup, find_packages


def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


setup(

    name='REHO',
    version='1.1.2',
    entry_points={
        'console_scripts': [
            'reho-test-import = reho.test.test_import:test_import_reho_modules',
            'reho-test-run = reho.test.test_run:test_run',
            'reho-test-plot = reho.test.test_plot:all_plots',
            'reho-download-examples = reho.test.test_examples:test_download_examples',
        ],
    },
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "amplpy",
        "ampl_module_base",
        "ampl_module_highs",
        "coloredlogs",
        "geopandas<1.0.0",
        "kaleido",
        "matplotlib",
        "numpy",
        "openpyxl",
        "pandas<2.0.0",
        "plotly",
        "psycopg2<3.0.0 ; platform_system != 'Windows'",
        "psycopg2-binary<3.0.0 ; platform_system == 'Windows'",
        "pvlib",
        "pyclustering",
        "pyproj",
        "python-dotenv",
        "pytest",
        "qmcpy",
        "requests",
        "SALib",
        "scipy",
        "setuptools",
        "shapely",
        "sqlalchemy<2.0.0",
        "urllib3",
    ],

    package_data={
        '': ['*.csv', '*.xlsx', '*.dat', '*.txt' '*.mod', '*.ini'],
    },
    author='Dorsan Lepour',
    author_email='dorsan.lepour@epfl.ch',
    maintainer="IT team of IPESE Laboratory from EPFL",
    maintainer_email="joao.ferreiradasilva@epfl.ch",
    description='Renewable Energy Hub Optimizer (REHO) - A Comprehensive Decision Support Tool for Sustainable Energy System Planning',
    long_description=read_file('README.md'),
    long_description_content_type='text/markdown',
    url='https://github.com/IPESE/REHO',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.10',
    ],
    keywords='MILP, decision support, sustainable energy systems, district optimization',
    project_urls={
        'Documentation': 'https://reho.readthedocs.io/en/main/',
        'Repository': 'https://github.com/IPESE/REHO',
        'Download': 'https://pypi.org/project/REHO',
    },
)
