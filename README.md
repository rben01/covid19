<!-- markdownlint-disable MD010 MD007 -->

# 2019 COVID-19/Coronavirus Tracker

This repository contains graphs of the spread of coronavirus throughout the world and code to create those graphs.

## :card_index_dividers: Contents

- [2019 COVID-19/Coronavirus Tracker](#2019-COVID-19Coronavirus-Tracker)
  - [:card_index_dividers: Contents](#card_index_dividers-Contents)
  - [:hammer_and_wrench: Setup](#hammer_and_wrench-Setup)
  - [:floppy_disk: Data sources](#floppy_disk-Data-sources)
    - [Raw data table](#Raw-data-table)
  - [:notebook: Notes](#notebook-Notes)
  - [:chart_with_upwards_trend: Graphs](#chart_with_upwards_trend-Graphs)
    - [Absolute case counts (not adjusted for region population)](#Absolute-case-counts-not-adjusted-for-region-population)
      - [Number of confirmed cases N days after first day of at least 100 confirmed cases in region](#Number-of-confirmed-cases-N-days-after-first-day-of-at-least-100-confirmed-cases-in-region)
        - [Top 10 countries, including China: confirmed cases after first day of 100 confirmed cases](#Top-10-countries-including-China-confirmed-cases-after-first-day-of-100-confirmed-cases)
        - [Top 10 countries, excluding China (nine countries total): confirmed cases after first day of 100 confirmed cases](#Top-10-countries-excluding-China-nine-countries-total-confirmed-cases-after-first-day-of-100-confirmed-cases)
        - [Top 10 US states: confirmed cases after first day of 100 confirmed cases](#Top-10-US-states-confirmed-cases-after-first-day-of-100-confirmed-cases)
      - [Number of confirmed cases over time](#Number-of-confirmed-cases-over-time)
        - [China and rest of world: confirmed cases over time (Jan 22 - present)](#China-and-rest-of-world-confirmed-cases-over-time-Jan-22---present)
        - [Top 10 countries, excluding China: confirmed cases over time (Jan 24 - present)](#Top-10-countries-excluding-China-confirmed-cases-over-time-Jan-24---present)
        - [Top 10 US states: confirmed cases over time (Mar 10 - present)](#Top-10-US-states-confirmed-cases-over-time-Mar-10---present)
    - [Per-capita case counts](#Per-capita-case-counts)
      - [Number of confirmed cases N days after first day of at least 10^-5 cases per capita (1 case per 100,000 people) in region](#Number-of-confirmed-cases-N-days-after-first-day-of-at-least-10-5-cases-per-capita-1-case-per-100000-people-in-region)
        - [Top 10 countries, including China: confirmed cases per capita after first day of 10^-5 cases per capita](#Top-10-countries-including-China-confirmed-cases-per-capita-after-first-day-of-10-5-cases-per-capita)
        - [Top 10 countries, excluding China (nine countries total): confirmed cases per capita after first day of 10^-5 cases per capita](#Top-10-countries-excluding-China-nine-countries-total-confirmed-cases-per-capita-after-first-day-of-10-5-cases-per-capita)
        - [Top 10 US states: confirmed cases per capita after first day of 10^-5 cases per capita](#Top-10-US-states-confirmed-cases-per-capita-after-first-day-of-10-5-cases-per-capita)
      - [Cases per capita over time](#Cases-per-capita-over-time)
        - [China and rest of world: confirmed cases per capita over time (Jan 22 - present)](#China-and-rest-of-world-confirmed-cases-per-capita-over-time-Jan-22---present)
        - [Top 10 countries, excluding China (nine countries total): confirmed cases per capita over time (Jan 24 - present)](#Top-10-countries-excluding-China-nine-countries-total-confirmed-cases-per-capita-over-time-Jan-24---present)
        - [Top 10 US states: confirmed cases per capita over time (Mar 10 - present)](#Top-10-US-states-confirmed-cases-per-capita-over-time-Mar-10---present)

## :hammer_and_wrench: Setup

Clone this GitHub repo: [https://github.com/rben01/covid19](https://github.com/rben01/covid19)

To create these graphs, create the conda environment using

```bash
conda env create -f environment.yml
```

Activate the environment with

```bash
conda activate covid
```

Finally, run the graphing script

```bash
python src/case_tracker.py
```

## :floppy_disk: Data sources

- [Washington Post world historical data](https://www.washingtonpost.com/graphics/2020/world/mapping-spread-new-coronavirus/data/clean/world-daily-historical.csv)
- [covidtracking.com US states historical data](https://covidtracking.com/api/states/daily.csv)
- [Wikipedia - List of Countries by Population](https://en.wikipedia.org/wiki/List_of_countries_and_dependencies_by_population)
- [Wikipedia - List of US States by Population](https://en.wikipedia.org/wiki/List_of_states_and_territories_of_the_United_States_by_population)

### Raw data table

The data used to create these graphs is available [here](data/data_table.csv).

## :notebook: Notes

- :calendar: In all graphs below, the start date was the earliest date for which there was data available and for which any of the plotted locations had confirmed cases.

- :keycap_ten: In each graph, the "top 10" refers to top 10 by number of cases, even for the graphs of cases per capita. Graphs' legends are, however, sorted according to the relevant measurement (number of cases or cases per capita).
For example, in a graph of countries and their cases per capita, the first country in the legend will have the most cases per capita of all countries included in that graph, but not necessarily the most cases per capita of any country in the world (the country with the most cases per capita in the world — San Marino at the time of writing — would have to be in the top 10 by number of cases to make it onto the graph, which it's obviously not given its population of 33k).

- :arrows_counterclockwise: The data sources used will change frequently due to changing quality and up-to-dateness, which may affect data for past dates (it shouldn't, but it might).

- :memo: Mortality notes

  - Mortality = deaths / confirmed.
  - This is an underestimate of the true mortality rate within a region; how low of an estimate it is depends on how quickly the rate of new confirmed cases relative to existing confirmed cases (the slopes of the lines in the below log-scaled plots) is increasing. If the infection rate increases rapidly, the computed mortality rate will be a gross underestimate, as new infections won't yet have had time to become fatal. If it's been flat for a while, then the computed mortality rate should approach the true mortality rate, as cases will all be resolved (either fatally or not). Of course, the true mortality rate can itself change over time as treatment quality goes up (e.g.,  more resources per capita allocated to response) or down (e.g.,  hospitals become overburdened).

  - The nature of log-scale graphs is that the mortality rate can be observed from the vertical distance between the **Confirmed Cases** and **Deaths** lines for a given country — the larger the distance, the lower the mortality rate. (The computed mortality rate is roughly (1/2)^distance; again this will be an underestimate.)

## :chart_with_upwards_trend: Graphs

### Absolute case counts (not adjusted for region population)

#### Number of confirmed cases N days after first day of at least 100 confirmed cases in region

##### Top 10 countries, including China: confirmed cases after first day of 100 confirmed cases

![Top 10 countries, including China: confirmed cases after first day of 100 confirmed cases](Figures/Absolute/From_local_spread_start/countries_w_china.png)

##### Top 10 countries, excluding China (nine countries total): confirmed cases after first day of 100 confirmed cases

![Top 10 countries, excluding China (nine countries total): confirmed cases after first day of 100 confirmed cases](Figures/Absolute/From_local_spread_start/countries_wo_china.png)

##### Top 10 US states: confirmed cases after first day of 100 confirmed cases

![Top 10 US states: confirmed cases after first day of 100 confirmed cases](Figures/Absolute/From_local_spread_start/states.png)

#### Number of confirmed cases over time

##### China and rest of world: confirmed cases over time (Jan 22 - present)

![China and rest of world: confirmed cases over time (Jan 22 - present)](Figures/Absolute/From_fixed_date/world.png)

##### Top 10 countries, excluding China: confirmed cases over time (Jan 24 - present)

![Top 10 countries, excluding China: confirmed cases over time (Jan 24 - present)](Figures/Absolute/From_fixed_date/countries_wo_china.png)

##### Top 10 US states: confirmed cases over time (Mar 10 - present)

![Top 10 US states: confirmed cases over time (Mar 10 - present)](Figures/Absolute/From_fixed_date/states.png)

### Per-capita case counts

#### Number of confirmed cases N days after first day of at least 10^-5 cases per capita (1 case per 100,000 people) in region

##### Top 10 countries, including China: confirmed cases per capita after first day of 10^-5 cases per capita

![Top 10 countries, including China: confirmed cases per capita after first day of 10^-5 cases per capita](Figures/Per_capita/From_local_spread_start/countries_w_china.png)

##### Top 10 countries, excluding China (nine countries total): confirmed cases per capita after first day of 10^-5 cases per capita

![Top 10 countries, excluding China (nine countries total): confirmed cases per capita after first day of 10^-5 cases per capita](Figures/Per_capita/From_local_spread_start/countries_wo_china.png)

##### Top 10 US states: confirmed cases per capita after first day of 10^-5 cases per capita

![Top 10 US states: confirmed cases per capita after first day of 10^-5 cases per capita](Figures/Per_capita/From_local_spread_start/states.png)

#### Cases per capita over time

##### China and rest of world: confirmed cases per capita over time (Jan 22 - present)

![China and rest of world: confirmed cases per capita over time (Jan 22 - present)](Figures/Per_capita/From_fixed_date/world.png)

##### Top 10 countries, excluding China (nine countries total): confirmed cases per capita over time (Jan 24 - present)

![Top 10 countries, excluding China (nine countries total): confirmed cases per capita over time (Jan 24 - present)](Figures/Per_capita/From_fixed_date/countries_wo_china.png)

##### Top 10 US states: confirmed cases per capita over time (Mar 10 - present)

![Top 10 US states: confirmed cases per capita over time (Mar 10 - present)](Figures/Per_capita/From_fixed_date/states.png)
