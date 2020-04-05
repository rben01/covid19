# %%
import enum
import itertools
import sys
from functools import lru_cache
from pathlib import Path
from typing import NoReturn, Optional, Tuple

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

    def col_name(self):
        if self == self.URL:
            return "URL"
        else:
            return self.value.title()


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
        return f"DS.{self.name}"


class Counting(AbstractStrictEnum):
    TOTAL_CASES = enum.auto()
    PER_CAPITA = enum.auto()

    def __str__(self):
        return f"C.{self.name}"


class Constants:
    @staticmethod
    @lru_cache(None)
    def threshold_for(*, stage: DiseaseStage, counting: Counting) -> float:
        THRESHOLDS = {
            (DiseaseStage.CONFIRMED, Counting.TOTAL_CASES): 100,
            (DiseaseStage.CONFIRMED, Counting.PER_CAPITA): 1e-5,
            (DiseaseStage.DEATH, Counting.TOTAL_CASES): 25,
            (DiseaseStage.DEATH, Counting.PER_CAPITA): 1e-5,
        }
        return THRESHOLDS[(stage, counting)]

    @staticmethod
    @lru_cache(None)
    def dash_style_for(*, stage: DiseaseStage) -> Tuple:
        DASH_STYLES = {DiseaseStage.CONFIRMED: (1, 0), DiseaseStage.DEATH: (1, 1)}
        return DASH_STYLES[stage]


class CaseType(enum.Enum):
    # The main ones we use
    CONFIRMED = "Cases"
    DEATHS = "Deaths"
    CONFIRMED_PER_CAPITA = CONFIRMED + " Per Cap."
    DEATHS_PER_CAPITA = DEATHS + " Per Cap."

    # Not used much, but keep them around
    TESTED = "Tested"
    ACTIVE = "Active"
    RECOVERED = "Recovered"
    MORTALITY = "CFR"
    GROWTH_FACTOR = "GrowthFactor"

    # Impart type info
    CONFIRMED: "CaseType"
    DEATHS: "CaseType"
    CONFIRMED_PER_CAPITA: "CaseType"
    DEATHS_PER_CAPITA: "CaseType"
    TESTED: "CaseType"
    ACTIVE: "CaseType"
    RECOVERED: "CaseType"
    MORTALITY: "CaseType"
    GROWTH_FACTOR: "CaseType"

    @classmethod
    @lru_cache(None)
    def from_specifiers(cls, *, stage: DiseaseStage, counting: Counting) -> "CaseType":
        DiseaseStage.verify(stage)
        Counting.verify(counting)

        if stage == DiseaseStage.CONFIRMED:
            if counting == Counting.TOTAL_CASES:
                return cls.CONFIRMED
            elif counting == Counting.PER_CAPITA:
                return cls.CONFIRMED_PER_CAPITA
            else:
                counting.raise_for_unhandled_case()

        elif stage == DiseaseStage.DEATH:
            if counting == Counting.TOTAL_CASES:
                return cls.DEATHS
            elif counting == Counting.PER_CAPITA:
                return cls.DEATHS_PER_CAPITA
            else:
                counting.raise_for_unhandled_case()

        else:
            stage.raise_for_unhandled_case()

    # Return the series that contains the case type mapping defined
    # in from_specifiers
    @classmethod
    @lru_cache(None)
    def _get_case_type_groups_series(cls) -> pd.Series:
        index = pd.MultiIndex.from_product(
            [DiseaseStage, Counting], names=[DiseaseStage.__name__, Counting.__name__]
        )
        values = index.to_frame().apply(
            lambda row: cls.from_specifiers(
                stage=row[DiseaseStage.__name__], counting=row[Counting.__name__]
            ),
            axis=1,
        )
        return pd.Series(values, index=index, name=cls.__name__)

    # Get the Series of case types corresponding to the arguments
    # If both arguments are a single enum case, result is a 1-element Series
    # None arguments are converted to slice(None), i.e., are wildcards
    @classmethod
    @lru_cache(None)
    def get_case_types_for(
        cls,
        *,
        stage: Optional[DiseaseStage] = None,
        counting: Optional[Counting] = None,
    ) -> pd.Series:

        if stage is None:
            stage = slice(None)

        if counting is None:
            counting = slice(None)

        case_types = cls._get_case_type_groups_series().xs(
            (stage, counting), level=(DiseaseStage.__name__, Counting.__name__), axis=0,
        )

        return case_types


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


# display(CaseType.get_case_types(stage=CaseGroup.Stage.CONFIRMED))


# %%
