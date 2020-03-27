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

CASE_THRESHOLD = 100


class Paths:
    ROOT = Path("..")
    FIGURES = ROOT / "Figures"
    DATA = ROOT / "data"

    FIGURES: Path
    DATA: Path


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
    DAYS_SINCE_OUTBREAK = "Days Since Outbreak"
    SOURCE = "Source"

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

    id_cols = [COUNTRY, STATE, LOCATION_NAME]


class CaseTypes:
    CONFIRMED = "Cases"
    TESTED = "Tested"
    ACTIVE = "Active"
    RECOVERED = "Recovered"
    DEATHS = "Deaths"
    MORTALITY = "Mortality"
    GROWTH_FACTOR = "GrowthFactor"


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


class Urls:
    WAPO_COUNTRIES_DAILY_HISTORICAL = (
        "https://www.washingtonpost.com/graphics/2020/"
        + "world/mapping-spread-new-coronavirus/"
        + "data/clean/world-daily-historical.csv"
    )
    COVIDTRACKING_STATES_DAILY_HISTORICAL = (
        "https://covidtracking.com/api/states/daily.csv"
    )

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4)"
            + " AppleWebKit/605.1.15 (KHTML, like Gecko)"
            + " Version/13.1 Safari/605.1.15"
        )
    }
