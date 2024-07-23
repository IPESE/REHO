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
    version='1.1.0',
    entry_points={
        'console_scripts': [
            'reho-run-test = reho.tests.test_scripts:test_run',
            'reho-plot-test = reho.tests.test_scripts:test_plot',
            'reho-examples-test = reho.tests.test_scripts:test_examples',
        ],
    },
    packages=find_packages(),
    include_package_data=True,
    install_requires=['amplpy>=0.12.0,<0.13.0',
                      'ampl_module_base',
                      'ampl_module_highs',
                      'pandas>=1.5.3,<2.0.0',
                      'openpyxl>=3.1.2,<4.0.0',
                      'numpy>=1.23.4,<2.0.0',
                      'scipy>=1.9.2,<2.0.0',
                      'scikit-learn>=1.2.2,<2.0.0',
                      'scikit-learn-extra>=0.3.0',
                      'sqlalchemy>=1.4.42,<2.0.0',
                      'psycopg2>=2.9.4,<3.0.0 ; platform_system != "Windows"',
                      'psycopg2-binary>=2.9.9,<3.0.0 ; platform_system == "Windows"',
                      'geopandas>=0.12.2,<1.0.0',
                      'matplotlib>=3.6.1,<4.0.0',
                      'plotly>=5.10,<6.0.0',
                      'kaleido>=0.2.1,<1.0.0',
                      'python-dotenv>=1.0',
                      'requests>=2.0.0,<3.0.0',
                      'coloredlogs>=15.0.1',
                      'SALib>=1.4.8',
                      'qmcpy>=1.4.5',
                      'pvlib==0.10.*',
                      'pytest>=8.3.0',
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
