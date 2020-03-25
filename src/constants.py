from pathlib import Path

# Includes D.C.
USA_STATE_CODES = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DC",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
]


class Paths:
    ROOT = Path("..")
    FIGURES = ROOT / "Figures"
    DATA = ROOT / "data"


class Columns:
    LATITUDE = "Lat"
    LONGITUDE = "Long"
    CITY = "City"
    COUNTY_NOT_COUNTRY = "County"
    TWO_LETTER_STATE_CODE = "State Code"
    STATE = "State"
    COUNTRY = "Country"
    THREE_LETTER_COUNTRY_CODE = "Country Code"
    LOCATION_NAME = "Location"
    POPULATION = "Population"
    IS_STATE = "Is State"
    URL = "Url"
    DATE = "Date"
    CASE_COUNT = "Cases"
    CASE_TYPE = "Case Type"

    string_cols = [
        LATITUDE,
        LONGITUDE,
        CITY,
        COUNTY_NOT_COUNTRY,
        TWO_LETTER_STATE_CODE,
        STATE,
        COUNTRY,
        THREE_LETTER_COUNTRY_CODE,
        LOCATION_NAME,
        POPULATION,
        URL,
        CASE_TYPE,
    ]


class CaseTypes:
    CONFIRMED = "Confirmed"
    RECOVERED = "Recovered"
    DEATHS = "Deaths"
    MORTALITY = "Mortality"
    GROWTH_FACTOR = "GrowthFactor"
    TESTED = "Tested"


class Locations:
    WORLD = "World"
    WORLD_MINUS_CHINA = "Non-China"
    CHINA = "China"
    USA = "United States"
    UK = "United Kingdom"
    ITALY = "Italy"
    GERMANY = "Germany"
    SPAIN = "Spain"
    SOUTH_KOREA = "South Korea"
    IRAN = "Iran"
    FRANCE = "France"
