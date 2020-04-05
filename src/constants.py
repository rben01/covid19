# %%
import enum
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, List, NewType, NoReturn, Optional, Union

import pandas as pd
from IPython.display import display  # noqa F401

Atom = NewType("Atom", Any)
Column = NewType("Column", str)
CaseType = NewType("CaseType", str)

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

    LATITUDE: Column
    LONGITUDE: Column
    CITY: Column
    COUNTY_NOT_COUNTRY: Column
    TWO_LETTER_STATE_CODE: Column
    STATE: Column
    COUNTRY: Column
    THREE_LETTER_COUNTRY_CODE: Column
    LOCATION_NAME: Column
    POPULATION: Column
    IS_STATE: Column
    URL: Column
    DATE: Column
    CASE_COUNT: Column
    CASE_TYPE: Column
    OUTBREAK_START_DATE_COL: Column
    DAYS_SINCE_OUTBREAK: Column
    SOURCE: Column

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

    location_id_cols = [COUNTRY, STATE, LOCATION_NAME]


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


class CaseTypes:
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


class InfoField(AbstractStrictEnum):
    CASE_TYPE = "CaseType_"
    THRESHOLD = "Threshold_"
    DASH_STYLE = "DashStyle_"

    def __str__(self):
        return f"IF.{self.name}"


class CaseInfo:
    _CASE_TYPES = {
        (DiseaseStage.CONFIRMED, Counting.TOTAL_CASES): CaseType.CONFIRMED,
        (DiseaseStage.CONFIRMED, Counting.PER_CAPITA,): CaseType.CONFIRMED_PER_CAPITA,
        (DiseaseStage.DEATH, Counting.TOTAL_CASES): CaseType.DEATHS,
        (DiseaseStage.DEATH, Counting.PER_CAPITA): CaseType.DEATHS_PER_CAPITA,
    }
    _THRESHOLDS = {
        (DiseaseStage.CONFIRMED, Counting.TOTAL_CASES): 100,
        (DiseaseStage.CONFIRMED, Counting.PER_CAPITA): 1e-5,
        (DiseaseStage.DEATH, Counting.TOTAL_CASES): 25,
        (DiseaseStage.DEATH, Counting.PER_CAPITA): 1e-6,
    }
    _DASH_STYLES = {DiseaseStage.CONFIRMED: (1, 0), DiseaseStage.DEATH: (1, 1)}

    @classmethod
    def get_info_item_for(
        cls, field: InfoField, *, stage: DiseaseStage, counting: Counting
    ) -> Atom:
        InfoField.verify(field)
        DiseaseStage.verify(stage)
        Counting.verify(counting)

        if field == InfoField.CASE_TYPE:
            return cls._CASE_TYPES[(stage, counting)]
        elif field == InfoField.DASH_STYLE:
            return cls._DASH_STYLES[stage]
        elif field == InfoField.THRESHOLD:
            return cls._THRESHOLDS[(stage, counting)]
        else:
            field.raise_for_unhandled_case()

    @classmethod
    @lru_cache
    # Return df multi-indexed by (Stage, Counting), columns are InfoField
    def _get_case_type_groups_df(cls) -> pd.DataFrame:
        multiindex_dict = {t.__name__: t for t in [DiseaseStage, Counting]}
        index = pd.MultiIndex.from_product(
            multiindex_dict.values(), names=multiindex_dict.keys()
        )
        values = (
            index.to_frame()
            .apply(
                lambda row: {
                    field: cls.get_info_item_for(
                        stage=row[DiseaseStage.__name__],
                        counting=row[Counting.__name__],
                        field=field,
                    )
                    for field in InfoField
                },
                axis=1,
            )
            .tolist()
        )

        return pd.DataFrame.from_records(values, index=index)

    @classmethod
    @lru_cache(None)
    def get_info_items_for(
        cls,
        *fields: List[InfoField],
        stage: Optional[DiseaseStage] = None,
        counting: Optional[Counting] = None,
        squeeze=True,
    ) -> Union[pd.Series, pd.DataFrame]:

        if not fields:
            fields = slice(None)
        else:
            fields = list(fields)
            for field in fields:
                InfoField.verify(field)

        if stage is None:
            stage = slice(None)
        else:
            DiseaseStage.verify(stage)

        if counting is None:
            counting = slice(None)
        else:
            Counting.verify(counting)

        info_df = cls._get_case_type_groups_df().xs(
            (stage, counting), level=(DiseaseStage.__name__, Counting.__name__), axis=0,
        )[fields]

        if squeeze and len(fields) == 1:
            info_df = info_df.iloc[:, 0]

        return info_df


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
