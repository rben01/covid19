2019 COVID-19/Coronavirus Tracker
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |total cases| replace:: confirmed cases and deaths

.. contents::
	:backlinks: entry

.. sectnum::
	:suffix: .

This repository contains graphs of the spread of coronavirus throughout the world and code to create those graphs.

.. _setup:

🛠 Setup
#########


Clone this GitHub repo (https://github.com/rben01/covid19)

Create the conda environment using

.. code:: bash

	conda env create -f environment.yml

Activate the environment with

.. code:: bash

	conda activate covid

Finally, run the graphing script

.. code:: bash

	python src/case_tracker.py

The script has a command line interface; check it out with

.. code:: bash

	python src/case_tracker.py --help
