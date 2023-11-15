# All rights reserved. ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland,
# IPESE Laboratory, Copyright 2023
# This work can be distributed under the CC BY-NC-SA 4.0 License.
# See the LICENSE file for more details.

from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='REHO',
    version='1.0',
    packages=find_packages(),  # Automatically discover and include all packages
    install_requires=requirements,
    package_data={
          '': ['*.csv', '*.xlsx', '*.dat', '*.txt'],
      },
    author='Dorsan Lepour',
    author_email='dorsan.lepour@epfl.ch',
    maintainer="IT team of IPESE Laboratory from EPFL",
    maintainer_email="joao.ferreiradasilva@epfl.ch",
    description='Renewable Energy Hub Optimizer (REHO) - A Comprehensive Decision Support Tool for Sustainable Energy System Planning',
    long_description="README.md",
    url='https://github.com/Renewable-Energy-Hub-Optimizer/REHO',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: Apache LICENSE-2.0',
        'Programming Language :: Python :: 3.10',
    ],
    keywords='MILP, decision support, sustainable energy systems, district optimization',
    project_urls={
        'Source': 'https://reho.readthedocs.io/en/main/',
    },
)