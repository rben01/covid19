from pathlib import Path


class Paths:
    ROOT = Path("..")
    FIGURES = ROOT / "Figures"


class Columns:
    LATITUDE = "Lat"
    LONGITUDE = "Long"
    STATE = "Province/State"
    COUNTRY = "Country/Region"
    LOCATION_NAME = "Location"
    IS_STATE = "Is State"
    DATE = "Date"
    CASE_COUNT = "Cases"
    CASE_TYPE = "Case Type"


class CaseTypes:
    CONFIRMED = "Confirmed"
    RECOVERED = "Recovered"
    DEATHS = "Deaths"
    MORTALITY = "Mortality"


class Locations:
    WORLD = "World"
    WORLD_MINUS_CHINA = "Non-China"
    CHINA = "China"
    USA = "US"
    UK = "United Kingdom"
    ITALY = "Italy"
    GERMANY = "Germany"
    SPAIN = "Spain"
    SOUTH_KOREA = "South Korea"
    IRAN = "Iran"
    FRANCE = "France"
