2019 COVID-19/Coronavirus Tracker
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |total cases| replace:: confirmed cases and deaths

.. contents::

This repository contains graphs of the spread of coronavirus throughout the world and code to create those graphs.

🛠 Setup
#########

Clone this GitHub repo (https://github.com/rben01/covid19)

Create the conda environment using

.. code-block:: bash

	conda env create -f environment.yml

Activate the environment with

.. code-block:: bash

	conda activate covid

Finally, run the graphing script

.. code-block:: bash

	python src/case_tracker.py

The script has a command line interface; check it out with

.. code-block:: bash

	python src/case_tracker.py --help

💾 Data Sources
################

.. _Washington Post world historical data: https://www.washingtonpost.com/graphics/2020/world/mapping-spread-new-coronavirus/data/clean/world-daily-historical.csv

.. _covidtracking.com US states historical data: https://covidtracking.com/api/states/daily.csv

.. _Wikipedia - List of Countries by Population: https://en.wikipedia.org/wiki/List_of_countries_and_dependencies_by_population

.. _Wikipedia - List of US States by Population: https://en.wikipedia.org/wiki/List_of_states_and_territories_of_the_United_States_by_population

* `Washington Post world historical data`_
* `covidtracking.com US states historical data`_
* `Wikipedia - List of Countries by Population`_
* `Wikipedia - List of US States by Population`_

.. tip::
	This source is not currently used, but it seems decent as well: `Corona Data Scraper <https://coronadatascraper.com/#home>`_
