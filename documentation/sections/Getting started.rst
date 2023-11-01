Getting started
+++++++++++++++


Installation
============

Installation
------------



AMPL
~~~~

Running the model in AMPL requires the licences of AMPL and of at least one LP solver.

Plenty of text editors exist which feature AMPL.
We are using Sublime Text (https://www.sublimetext.com/) for syntax highlighting.
To install the ampl package follow the steps:

1. Tools/Install package control
2. Tools/Command palette/package control: Install package -> install ampl
3. Tools/Build system/ampl

Python
~~~~~~

You will need Python3 (https://www.python.org/downloads/), just pick the latest version,
which should already be installed on your VM. As IDE we highly recommend you to use PyCharm (https://www.jetbrains.com/pycharm/).
There is a free professional license for students (click special offers and click for students and teachers).
Please connect using (or creating) your PyCharm account to, it will be a great support for you.


REHO repository
~~~~~~~~~~~~~~~

Select a directory where you would like to have your files,
open the terminal/cmd in this folder and clone the repository (https://github.com/Renewable-Energy-Hub-Optimizer/REHO_model) using the command:

.. code-block:: bash
   :caption: Cloning the REHO repository

   git clone https://github.com/Renewable-Energy-Hub-Optimizer/REHO_model.git

After it finished cloning, you can check if everything works. If everything is up to date, you can continue:

.. code-block:: bash
   :caption: Checking repository status

   cd reho
   git status

Important: As soon as everything is cloned, please check out your own branch (from branch master).
Go back to the terminal where you just have checked your git status and run:

.. code-block:: bash
   :caption: Creating and switching to a new branch

   git checkout -b your_branch_name

First run
~~~~~~~~~

1. Open PyCharm, open a project and browse to the folder of the repository REHO. Do not accept the automatic virtual environment creation. We will install it by our own.
2. Go to File > Settings > Project: REHO to set up your Project Interpreter, click on the gear symbol and choose to add.
3. Add a new virtual environment (venv) and select as base interpreter your python.exe file of your python installation. Confirm with OK.
4. Install required Python packages. Open the Terminal tab (View > Tool Windows > Terminal) and type the command one by one:

.. code-block:: bash
   :caption: Installing Python packages

   pip install -r requirements.txt
   pipwin install -r requirements_win.txt

   # if geopandas failed to install
   pip install geopandas


5. Finally run:

.. code-block:: bash
   :caption: Installing additional package

   pip install "git+https://github.com/building-energy/epw.git"

6. Create a new folder for your future work with REHO. Right click on the folder run in wrapper_amplpy and create a New > Directory. You will use this folder to write and save your first scripts.




Run the model
=============

7. Choose the file 2a_Centralized_TOTEX.py and run the script. If your installation is correct, you should receive the final message “Process finished with exit code 0”. Sometimes, when running the model for the first time, you need to explicitly tell PyCharm to connect to the AMPL server by typing ampl in the PyCharm Terminal tab.


Exercises
=========

.. caution ::
   TO DO