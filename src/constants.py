# %%
import enum
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Mapping, NewType, NoReturn, Tuple, Union

import pandas as pd
from IPython.display import display  # noqa F401
from typing_extensions import Literal

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
    """A namespace for Path constants

    Intelligently determines the project's ROOT directory regardless of CWD when
    case_tracker.py is run
    """

    # Try to use source filename to get project dir - this works if running from
    # a command line
    ROOT: Path = Path(sys.argv[0]).parent.parent
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

    ROOT_PARENT: Path = ROOT.parent
    DATA: Path = ROOT / "data"
    DATA_TABLE: Path = DATA / "data_table.csv"
    DOCS: Path = ROOT / "docs"
    FIGURES: Path = DOCS / "figures"
    SOURCE: Path = ROOT_PARENT / "src"


class StrictEnumError(Exception):
    """An Exception corresponding to a violation of the StrictEnum assumptions
    """

    pass


class ABCStrictEnum(enum.Enum):
    """An ABC that enums may inherit from in order to gain strict behavior

    Provides a `verify` classmethod that ensures an arbitrary value is indeed a case of
    the calling enum, and a `raise_for_unhandled_case` instance method that errors when
    an if/elif/else statement forgets to handle the calling case
    """

    @classmethod
    def verify(cls, item, *, allow_select: bool = False):
        """Verify that the passed item is a case of this enum

        If `item is not None`, then raise if `item` is not a case of this enum, else
        return nothing. If `item is None`, then raise iff `not none_ok`.

        :param item: The object to test
        :type item: Any
        :param none_ok: Whether None is permissible (True) or should raise (False). By
        default False.
        :raises StrictEnumError: If `item` is not a case of this enum; if `item` is
        None, raise only if `not none_ok`
        """

        if (item in Select and allow_select) or (item not in Select and item in cls):
            return

        raise StrictEnumError(f"Invalid {cls} case {item}")

    def raise_for_unhandled_case(self) -> NoReturn:
        """Unconditionally raises; used to signal that this case was unhandled in a
        if/elif/else statement. Used as a bandaid solution to the problem of no
        compiler-enforced exhaustive case checking.

        Used as follows:
        ```
        if case is value1:
            pass
        elif case is value2:
            pass
        else: # We did not handle every possible value of `case`
            case.raise_for_unhandled_case()
        ```

        :raises StrictEnumError: Always raises, indicating that this case went unhandled
        :return: Never returns
        :rtype: NoReturn
        """
        raise StrictEnumError(f"Unhandled case {self!r}")


class Columns:
    """A namespace for string constants used as column names
    """

    LATITUDE: Column = "Lat"
    LONGITUDE: Column = "Long"
    CITY: Column = "City"
    COUNTY_NOT_COUNTRY: Column = "County"
    TWO_LETTER_STATE_CODE: Column = "State Code"
    STATE: Column = "State"
    COUNTRY: Column = "Country"
    THREE_LETTER_COUNTRY_CODE: Column = "Country Code"
    LOCATION_NAME: Column = "Location"
    POPULATION: Column = "Population"
    IS_STATE: Column = "Is State"
    URL: Column = "Url"
    DATE: Column = "Date"
    CASE_COUNT: Column = "Cases"
    CASE_TYPE: Column = "Case Type"
    STAGE: Column = "DiseaseStage"
    COUNT_TYPE: Column = "Counting"
    OUTBREAK_START_DATE_COL: Column = "Outbreak start date"
    DAYS_SINCE_OUTBREAK: Column = "Days Since Outbreak"
    SOURCE: Column = "Source"

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

    class XAxis(ABCStrictEnum):
        """An enum whose cases represent columns that may be used for the x-axis

        Maintains a mapping between cases in this enum and the corresponding column name
        in `Columns`. Raises an error when compared to an object that's not an `XAxis`.
        """

        DATE = enum.auto()
        DAYS_SINCE_OUTBREAK = enum.auto()

        def column(self) -> Column:
            """Return the column name for this case

            Provides the mapping of `XAxis` to column names

            :return: The corresponding column name
            :rtype: Column
            """

            if self is self.DATE:
                return Columns.DATE
            elif self is self.DAYS_SINCE_OUTBREAK:
                return Columns.DAYS_SINCE_OUTBREAK
            else:
                self.raise_for_unhandled_case()

        def pprint(self) -> str:
            """Get a string describing self

            Useful for e.g., file/folder names based off this case

            :return: A descriptive string representing this case
            :rtype: str
            """

            if self is self.DATE:
                return "From_fixed_date"
            elif self is self.DAYS_SINCE_OUTBREAK:
                return "From_local_spread_start"
            else:
                self.raise_for_unhandled_case()


@enum.unique
class DiseaseStage(ABCStrictEnum):
    """An enum whose cases represent stages of the disease (confirmed, dead)
    """

    CONFIRMED: "DiseaseStage" = enum.auto()
    DEATH: "DiseaseStage" = enum.auto()

    def __str__(self) -> str:
        return f"DS.{self.name}"

    def pprint(self) -> str:
        return self.name.capitalize()

    def to_str(self) -> str:
        return self.pprint()

    def to_percapita_str(self) -> str:
        return " ".join([self.to_str(), "Per Cap."])


@enum.unique
class Counting(ABCStrictEnum):
    """An enum whose cases represent how to count cases of COVID for a given disease
    stage (total cases, per capita) within a given region
    """

    TOTAL_CASES: "Counting" = enum.auto()
    PER_CAPITA: "Counting" = enum.auto()

    def __str__(self) -> str:
        return f"C.{self.name}"

    def pprint(self) -> str:
        return f"{self.name.capitalize()}"


@enum.unique
class Select(ABCStrictEnum):
    """An enum that represents a choice of cases of other enums
    """

    DEFAULT: "Select" = enum.auto()
    ALL: "Select" = enum.auto()


class CaseTypes:
    """A namespace containing string constants that describe the different case types

    There are a number of different case types: confirmd, tested, active, revovered,
    dead, as well as per-capita versions of these. This class collects these cases as
    string constants for use in interpreting data stored in dataframes.
    """

    # The main ones we use
    CONFIRMED: "CaseType" = "Cases"
    DEATHS: "CaseType" = "Deaths"
    CONFIRMED_PER_CAPITA: "CaseType" = "Cases Per Cap."
    DEATHS_PER_CAPITA: "CaseType" = "Deaths Per Cap."

    # Not used much, but keep them around
    TESTED: "CaseType" = "Tested"
    ACTIVE: "CaseType" = "Active"
    RECOVERED: "CaseType" = "Recovered"
    MORTALITY: "CaseType" = "CFR"
    GROWTH_FACTOR: "CaseType" = "GrowthFactor"


@enum.unique
class InfoField(ABCStrictEnum):
    """An enum whose cases represent a piece of information mapped from a combination
    of `DiseaseStage` and `Counting`

    Each (`DiseaseStage`, `Counting`) tuple has an associated set of data: the case
    type, the outbreak threshold, the dash style (for plotting). This enum contains
    cases for specifying a field to fetch from this data set.
    """

    CASE_TYPE: "InfoField" = "CaseType_"
    THRESHOLD: "InfoField" = "Threshold_"
    DASH_STYLE: "InfoField" = "DashStyle_"

    def __str__(self) -> str:
        return f"IF.{self.name}"


class CaseInfo:
    """A namespace for convenience methods to return information related to cases

    Each (`DiseaseStage`, `Counting`) tuple has an associated set of data. This class
    contains methods for slicing that data set (`DiseaseStage` x `Counting` x
    `InfoField`) in order to retrieve values for any cross-section thereof
    """

    _CASE_TYPES = {
        (DiseaseStage.CONFIRMED, Counting.TOTAL_CASES): CaseTypes.CONFIRMED,
        (DiseaseStage.CONFIRMED, Counting.PER_CAPITA,): CaseTypes.CONFIRMED_PER_CAPITA,
        (DiseaseStage.DEATH, Counting.TOTAL_CASES): CaseTypes.DEATHS,
        (DiseaseStage.DEATH, Counting.PER_CAPITA): CaseTypes.DEATHS_PER_CAPITA,
    }
    _THRESHOLDS = {
        (DiseaseStage.CONFIRMED, Counting.TOTAL_CASES): 100,
        (DiseaseStage.CONFIRMED, Counting.PER_CAPITA): 1e-5,
        (DiseaseStage.DEATH, Counting.TOTAL_CASES): 25,
        (DiseaseStage.DEATH, Counting.PER_CAPITA): 1e-6,
    }
    _DASH_STYLES = {DiseaseStage.CONFIRMED: (1, 0), DiseaseStage.DEATH: (2, 1)}

    _CASE_TYPES: Mapping[Tuple[DiseaseStage, Counting], CaseType]
    _THRESHOLDS: Mapping[Tuple[DiseaseStage, Counting], float]
    _DASH_STYLES: Mapping[DiseaseStage, Tuple]

    @classmethod
    def get_info_item_for(
        cls, field: InfoField, *, stage: DiseaseStage, count: Counting
    ) -> Atom:
        """Get the single piece of information corresponding to the arguments

        A tuple (`field`, `stage`, `count`), such as (`DASH_STYLE`, `CONFIRMED`,
        `TOTAL_CASES`), uniquely identifies a piece of information to return (in this
        case, the dash style to be used when plotting total confirmed cases). This
        function returns that information.

        :param field: The field to return for the given `stage`+`count` combination
        :type field: InfoField
        :param stage: The disease stage to return information for
        :type stage: DiseaseStage
        :param count: The count method to return information for
        :type count: Counting
        :return: The single piece of information corresponding to the passed arguments
        :rtype: Atom
        """

        InfoField.verify(field)
        DiseaseStage.verify(stage)
        Counting.verify(count)

        if field is InfoField.CASE_TYPE:
            return cls._CASE_TYPES[(stage, count)]
        elif field is InfoField.DASH_STYLE:
            return cls._DASH_STYLES[stage]
        elif field is InfoField.THRESHOLD:
            return cls._THRESHOLDS[(stage, count)]
        else:
            field.raise_for_unhandled_case()

    @classmethod
    @lru_cache(None)
    # Return df multi-indexed by (Stage, Counting), columns are InfoField
    def _get_case_type_groups_df(cls) -> pd.DataFrame:
        """Get the dataframe containing all (field, stage, count) information

        Returns a dataframe whose index is the product of `DiseaseStage` and `Counting`,
        whose columns are `InfoField` cases, and whose values are the corresponding
        values; `df.loc[(stage, count), field] == get_info_item_for(field, stage,
        count)`. This is effectively a class constant, so we memoize its result.

        :return: [description]
        :rtype: pd.DataFrame
        """

        enums = [DiseaseStage, Counting]
        enum_names = [e.__name__ for e in enums]
        index = pd.MultiIndex.from_product(enums, names=enum_names)
        values = (
            index.to_frame()
            .apply(
                lambda row: {
                    field: cls.get_info_item_for(
                        stage=row[DiseaseStage.__name__],
                        count=row[Counting.__name__],
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
        stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
        count: Union[Counting, Literal[Select.ALL]] = Select.ALL,
        squeeze_rows=False,
        squeeze_cols=True,
    ) -> Union[Atom, pd.Series, pd.DataFrame]:
        """Retrieve the slice of information corresponding to the passed arguments

        Underlying this is a dataframe containing information corresponding to all
        (`field`, `stage`, `count`) tuples. This function takes a variable number of
        fields, a single stage (or None), and a single count (or None), and produces
        the slice of the data corresponding to them. If multiple fields are given,
        multiple columns will be returned.

        :param *fields: The fields whose information is to be returned
        :type *fields: InfoField...
        :param stage: The `DiseaseStage` to return information for.
        Defaults to Select.ALL (return info for all `DiseaseStage` cases).
        :type stage: Union[DiseaseStage, Literal[Select.ALL]], optional
        :param count: The `Counting` to return information for. Defaults to Select.ALL
        (return info for all `Counting` cases).
        :type count: Union[Counting, Literal[Select.ALL]], optional
        :param squeeze_rows: By default False. If True, and the result has a single row,
        return the result as a Series instead of a DataFrame. Has no effect if the
        result has >1 row. If the resulting series has length 1 and `squeeze_cols`, then
        return just the one element of the series.
        :type squeeze_rows: bool, optional
        :param squeeze_cols: By default True. If True, and the result has a single
        column, return the result as a Series instead of a DataFrame. Has no effect
        if the result has >1 column. If the resulting series has length 1 and
        `squeeze_rows`, then return just the one element of the series.
        :type squeeze_cols: bool, optional
        :return: The slice of the data corresponding to the arguments. The `squeeze_*`
        parameters attempt to squeeze the resulting dataframe into a smaller-dimensional
        object. `squeeze_rows` and `squeeze_cols` attempt to squeeze a single row and a
        single column, respectively, into a Series. If both are True, and the result has
        one element (i.e., there is one row and one column) then the element itself
        will be returned.
        If not squeezed, the data is returned as a DataFrame.
        :rtype: Union[Atom, pd.Series, pd.DataFrame]
        """

        if not fields:
            fields = slice(None)
        else:
            fields = list(fields)
            for field in fields:
                InfoField.verify(field)

        DiseaseStage.verify(stage, allow_select=True)
        if stage is Select.ALL:
            stage = slice(None)

        Counting.verify(count, allow_select=True)
        if count is Select.ALL:
            count = slice(None)

        info_df = cls._get_case_type_groups_df().xs(
            (stage, count), level=(DiseaseStage.__name__, Counting.__name__), axis=0,
        )[fields]

        # Col squeezing must come first, as after squeezing rows there might not be an
        # axis 1 (but there'll always be an axis 0)
        if squeeze_cols and len(fields) == 1:
            info_df = info_df.iloc(axis=1)[0]

        if squeeze_rows and len(info_df) == 1:
            info_df = info_df.iloc(axis=0)[0]

        return info_df


class Locations:
    """Namespace for string constants of commonly used location names
    """

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
    """Namespace for string constants of commonly used URLs
    """

    WAPO_COUNTRIES_DAILY_HISTORICAL = (
        "https://inv-covid-data-prod.elections.aws.wapo.pub/world-daily-historical/"
        + "world-daily-historical-combined.csv"
    )
    COVIDTRACKING_STATES_DAILY_HISTORICAL = (
        "https://covidtracking.com/api/v1/states/daily.csv"
    )

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4)"
            + " AppleWebKit/605.1.15 (KHTML, like Gecko)"
            + " Version/13.1 Safari/605.1.15"
        )
    }
