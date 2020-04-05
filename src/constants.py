# %%
import enum
import itertools
import sys
from functools import lru_cache
from pathlib import Path
from typing import Union

import pandas as pd
from IPython.display import display  # noqa F401

# Includes D.C.; has length 51
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
    # Try to use source filename to get project dir - this works if running from
    # a command line
    ROOT = Path(sys.argv[0]).parent.parent
    # If using interactively in ipython, it might not work
    # Path() will be correct, but sys.argv[0] might be some ipython.py (or similar) file
    if not (ROOT / "src" / "case_tracker.py").exists():
        ROOT = Path().resolve()
        while not (ROOT / "src" / "case_tracker.py").exists():
            if ROOT == ROOT.parent:
                raise FileNotFoundError(
                    f"Could not find a suitable project directory; "
                    + f"current folder is {Path().resolve()}"
                )

            ROOT = ROOT.parent

    ROOT: Path

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
    OUTBREAK_START_DATE_COL = "Outbreak start date"
    DAYS_SINCE_OUTBREAK = "Days Since Outbreak"
    SOURCE = "Source"
    POPULATION = "Population"

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
        SOURCE,
        POPULATION,
    ]

    id_cols = [COUNTRY, STATE, LOCATION_NAME]


class CaseGroup:
    _STAGE = "Stage_"
    _COUNT_TYPE = "Count_Type_"

    class Stage(enum.Enum):
        CONFIRMED = enum.auto()
        DEATH = enum.auto()

        def __str__(self):
            return self.name

    class CountType(enum.Enum):
        ABSOLUTE = enum.auto()
        PER_CAPITA = enum.auto()

        def __str__(self):
            return self.name

    @staticmethod
    def get_case_type(stage: Stage, count_type: CountType) -> str:
        case_type_groups = {
            CaseGroup.Stage.CONFIRMED: {
                CaseGroup.CountType.ABSOLUTE: CaseTypes.CONFIRMED,
                CaseGroup.CountType.PER_CAPITA: CaseTypes.CASES_PER_CAPITA,
            },
            CaseGroup.Stage.DEATH: {
                CaseGroup.CountType.ABSOLUTE: CaseTypes.DEATHS,
                CaseGroup.CountType.PER_CAPITA: CaseTypes.DEATHS_PER_CAPITA,
            },
        }
        return case_type_groups[stage][count_type]


class CaseTypes:
    CONFIRMED = "Cases"
    DEATHS = "Deaths"
    CASES_PER_CAPITA = CONFIRMED + " Per Cap."
    DEATHS_PER_CAPITA = DEATHS + " Per Cap."

    # We can't create this df until the class is defined, so we make it a staticmethod
    # and for effiicency purposes memoize it
    @staticmethod
    @lru_cache(None)
    def _get_case_type_groups_series() -> pd.Series:
        return pd.DataFrame.from_records(
            [
                {
                    CaseGroup._STAGE: stage,
                    CaseGroup._COUNT_TYPE: count_type,
                    "Case_Type": CaseGroup.get_case_type(stage, count_type),
                }
                for (stage, count_type) in itertools.product(
                    CaseGroup.Stage, CaseGroup.CountType,
                )
            ],
            index=[CaseGroup._STAGE, CaseGroup._COUNT_TYPE],
        )["Case_Type"]

    # We call this method a ton, no point in not caching its results
    @classmethod
    @lru_cache(None)
    def get_case_types(
        cls, *, stage: CaseGroup = None, count_type: CaseGroup = None, flatten=True
    ) -> Union[pd.Series, str]:

        stage = stage or slice(None)
        count_type = count_type or slice(None)
        case_types = cls._get_case_type_groups_series().xs(
            (stage, count_type), level=(CaseGroup._STAGE, CaseGroup._COUNT_TYPE), axis=0
        )

        if len(case_types) == 1 and flatten:
            return case_types.iloc[0]

        return case_types

    TESTED = "Tested"
    ACTIVE = "Active"
    RECOVERED = "Recovered"
    MORTALITY = "CFR"
    GROWTH_FACTOR = "GrowthFactor"


class Thresholds:
    CASE_COUNT = 100
    CASES_PER_CAPITA = 1e-5


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
    NEW_YORK = "New York"


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


# display(CaseTypes.get_case_types(stage=CaseGroup.Stage.CONFIRMED))
