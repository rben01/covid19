# %%
import enum
import itertools
import sys
from functools import lru_cache
from pathlib import Path
from typing import NoReturn, Tuple

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


class Columns(enum.Enum):
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

    @classmethod
    @lru_cache(None)
    def location_id_cols(cls):
        return [cls.COUNTRY, cls.STATE, cls.LOCATION_NAME]


class StrictEnumError(Exception):
    pass


class AbstractStrictEnum(enum.Enum):
    @classmethod
    def verify(cls, item):
        if item not in cls:
            raise StrictEnumError(f"Invalid {cls} case {item}")

    def raise_for_unhandled_case(self) -> NoReturn:
        raise StrictEnumError(f"Unhandled case {self!r}")


class DiseaseStage(AbstractStrictEnum):
    CONFIRMED = enum.auto()
    DEATH = enum.auto()

    def __str__(self):
        return self.name


class CountType(AbstractStrictEnum):
    ABSOLUTE = enum.auto()
    PER_CAPITA = enum.auto()

    def __str__(self):
        return self.name


class Constants:
    @staticmethod
    @lru_cache(None)
    def threshold_for(*, stage: DiseaseStage, count_type: CountType) -> float:
        THRESHOLDS = {
            (DiseaseStage.CONFIRMED, CountType.ABSOLUTE): 100,
            (DiseaseStage.CONFIRMED, CountType.PER_CAPITA): 1e-5,
            (DiseaseStage.DEATH, CountType.ABSOLUTE): 25,
            (DiseaseStage.DEATH, CountType.PER_CAPITA): 1e-5,
        }
        return THRESHOLDS[(stage, count_type)]

    @staticmethod
    @lru_cache(None)
    def dash_style_for(*, stage: DiseaseStage) -> Tuple:
        DASH_STYLES = {DiseaseStage.CONFIRMED: (1, 0), DiseaseStage.DEATH: (1, 1)}
        return DASH_STYLES[stage]


class CaseTypes(enum.Enum):
    # The main ones we use
    CONFIRMED = "Cases"
    DEATHS = "Deaths"
    CASES_PER_CAPITA = CONFIRMED + " Per Cap."
    DEATHS_PER_CAPITA = DEATHS + " Per Cap."

    # Not used much, but keep them around
    TESTED = "Tested"
    ACTIVE = "Active"
    RECOVERED = "Recovered"
    MORTALITY = "CFR"
    GROWTH_FACTOR = "GrowthFactor"

    # Impart type info
    CONFIRMED: "CaseTypes"
    DEATHS: "CaseTypes"
    CASES_PER_CAPITA: "CaseTypes"
    DEATHS_PER_CAPITA: "CaseTypes"
    TESTED: "CaseTypes"
    ACTIVE: "CaseTypes"
    RECOVERED: "CaseTypes"
    MORTALITY: "CaseTypes"
    GROWTH_FACTOR: "CaseTypes"

    @classmethod
    @lru_cache(None)
    def from_specifiers(
        cls, *, stage: DiseaseStage, count_type: CountType
    ) -> "CaseTypes":
        CASE_TYPE_MAP = {
            (DiseaseStage.CONFIRMED, CountType.ABSOLUTE): cls.CONFIRMED,
            (DiseaseStage.CONFIRMED, CountType.PER_CAPITA): cls.CASES_PER_CAPITA,
            (DiseaseStage.DEATH, CountType.ABSOLUTE): cls.DEATHS,
            (DiseaseStage.DEATH, CountType.PER_CAPITA): cls.DEATHS_PER_CAPITA,
        }
        return CASE_TYPE_MAP[(stage, count_type)]

    # We can't create this df until the class is defined, so we make it a staticmethod
    # and for effiicency purposes memoize it
    @classmethod
    @lru_cache(None)
    def _get_case_type_groups_series(cls) -> pd.Series:
        return pd.DataFrame.from_records(
            [
                {
                    DiseaseStage.__name__: stage,
                    CountType.__name__: count_type,
                    "Case_Type": cls.from_specifiers(
                        stage=stage, count_type=count_type
                    ),
                }
                for (stage, count_type) in itertools.product(DiseaseStage, CountType)
            ],
            index=[DiseaseStage.__name__, CountType.__name__],
        )["Case_Type"]

    # We call this method a ton, no point in not caching its results
    @classmethod
    @lru_cache(None)
    def get_case_types_for(
        cls, *, stage: DiseaseStage = None, count_type: CountType = None
    ) -> pd.Series:

        stage = stage or slice(None)
        count_type = count_type or slice(None)
        case_types = cls._get_case_type_groups_series().xs(
            (stage, count_type),
            level=(DiseaseStage.__name__, CountType.__name__),
            axis=0,
        )

        return case_types

    @classmethod
    @lru_cache(None)
    def get_unique_case_type_for(
        cls, *, stage: DiseaseStage, count_type: CountType
    ) -> str:

        case_types = cls.get_case_types_for(stage=stage, count_type=count_type)
        if len(case_types) != 1:
            raise ValueError(
                f"Expected just one case type; got {case_types} "
                + f"for {stage=}, {count_type=}"
            )

        return case_types.iloc[0]


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
