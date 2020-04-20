2019 COVID-19/Coronavirus Tracker
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |total cases| replace:: confirmed cases and deaths

.. contents::
  :backlinks: none

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

`Corona Data Scraper <https://coronadatascraper.com/#home>`_ is not currently used, but it seems decent as well:

Raw Data Table
$$$$$$$$$$$$$$$$

The data used to create these graphs is available `here <data/data_table.csv>`_.

📓 Notes
###################
- 📅 In all graphs below, the start date was the earliest date for which there was data available and for which any of the plotted locations had confirmed cases.

- | ⏳ Some graphs are annotated with benchmark lines showing the rate of new cases (possibly per capita) for a particular doubling time (or "DT" for short). Lines annotated "n days" show how the number of coronavirus cases would increase within a region if it doubled every n days. Comparing the slope of a region's growth line to the slopes of these benchmark lines gives an indication of that region's doubling time. These graphs' legends also list the doubling times over different periods of time (e.g., "20d DT" means the average doubling time of a region over the past 20 days").
  | To find the daily percent increase for any doubling time T, simply compute 2\ :sup:`1/T`. Below is a list of doubling times and corresponding per-day percent increases.

  - 1 day: +100% daily
  - 2 days: +41% daily
  - 3 days: +26% daily
  - 4 days: +19% daily
  - 5 days: +15% daily
  - 6 days: +12% daily
  - 1 week: + 10% daily

- | 🔟 In each graph, the "top 10" refers to top 10 by number of cases, even for the graphs of cases per capita. Graphs' legends are, however, sorted according to the relevant measurement (number of cases, cases per capita, or doubling time thereof).
  | For example, in a graph of countries and their cases per capita, the first country in the legend will have the most cases per capita of all countries included in that graph, but not necessarily the most cases per capita of any country in the world (the country with the most cases per capita in the world — San Marino at the time of writing — would have to be in the top 10 by number of cases to make it onto the graph, which it's obviously not given its population of 33k).

- 🔄 The data sources used may change due to changing quality and up-to-dateness, which may affect data for past dates (it shouldn't, but it might).

- 📝 Case Fatality Rate (CFR) notes

  - CFR = Case fatality rate = deaths / confirmed.
  - This is an underestimate of the true CFR within a region; how low of an estimate it is depends on how quickly the rate of new confirmed cases relative to existing confirmed cases (the slopes of the lines in the below log-scaled plots) is increasing. If the infection rate increases rapidly, the computed CFR will be a gross underestimate, as new infections won't yet have had time to become fatal. If it's been flat for a while, then the computed CFR should approach the true CFR, as cases will all be resolved (either fatally or not). Of course, the true CFR within a region can itself change over time as treatment quality goes up (e.g., more resources per capita allocated to response) or down (e.g., hospitals become overburdened).

  - The nature of log-scale graphs is that the CFR can be observed from the vertical distance between the **Confirmed Cases** and **Deaths** lines for a given country — the larger the distance, the lower the CFR. (The computed CFR is roughly 1/2\ :sup:`distance`; again this will be an underestimate.)

📈 Graphs
################

🌍 World, China, and Rest of World
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

.. figure:: ./Figures/Total_cases/From_fixed_date/Stage_All/world.png

  World, China, and Rest of World - Case count over time

  :alt: World, China, and Rest of World - Case count over time



### :world_map: Top Ten Countries, Excluding China

#### Countries - Cases and deaths over time

![Countries - Case count over time](./Figures/Total_cases/From_fixed_date/Stage_All/countries_wo_china.png)

#### Countries - Cases and deaths per capita over time

![Countries - Case count over time](./Figures/Per_capita/From_fixed_date/Stage_All/countries_wo_china.png)

#### Countries - Cases since hitting 100 cases

![Countries - Case count since hitting 100 cases](./Figures/Total_cases/From_local_spread_start/Stage_Confirmed/countries_wo_china.png)

#### Countries - Deaths since hitting 25 deaths

![Countries - Case count since hitting 100 cases](./Figures/Total_cases/From_local_spread_start/Stage_Death/countries_wo_china.png)

### :us: Top Ten USA States

#### USA States - Cases and deaths over time

![Countries - Case count over time](./Figures/Total_cases/From_fixed_date/Stage_All/states.png)

#### USA States - Cases and deaths per capita over time

![Countries - Case count over time](./Figures/Per_capita/From_fixed_date/Stage_All/states.png)

#### USA States - Cases since hitting 100 cases

![Countries - Case count since hitting 100 cases](./Figures/Total_cases/From_local_spread_start/Stage_Confirmed/states.png)

#### USA States - Deaths since hitting 25 deaths

![Countries - Case count since hitting 100 cases](./Figures/Total_cases/From_local_spread_start/Stage_Death/states.png)
