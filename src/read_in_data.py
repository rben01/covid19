# %%
import enum
import io
from pathlib import Path

import pandas as pd
import requests
from IPython.display import display  # noqa F401

from constants import (
    USA_STATE_CODES,
    CaseTypes,
    Columns,
    Locations,
    Paths,
    Urls,
)

COUNTRY_DATA = Paths.DATA / "WaPo"
DATA_COLS = [
    Columns.STATE,
    Columns.COUNTRY,
    Columns.DATE,
    Columns.CASE_TYPE,
    Columns.CASE_COUNT,
    Columns.POPULATION,
]


# Not currently used
class DataOrigin(enum.Enum):
    USE_LOCAL_UNCONDITIONALLY = enum.auto()
    USE_LOCAL_IF_EXISTS_ELSE_FETCH_FROM_WEB = enum.auto()
    FETCH_FROM_WEB_UNCONDITIONALLY = enum.auto()

    def should_try_to_use_local(self) -> bool:
        return self in [
            DataOrigin.USE_LOCAL_UNCONDITIONALLY,
            DataOrigin.USE_LOCAL_IF_EXISTS_ELSE_FETCH_FROM_WEB,
        ]


class SaveFormats(enum.Enum):
    CSV = ".csv"

    # Parquet currently broken (pyarrow bug?), don't know why but csv is fine
    # PARQUET = ".parquet"

    @staticmethod
    def _adjust_dates(date_col: pd.Series) -> pd.Series:
        date_col = date_col.copy()
        is_todays_date = date_col.dt.strftime(r"%Y%m%d") == pd.Timestamp.now().strftime(
            r"%Y%m%d"
        )
        date_col.loc[is_todays_date] = pd.Timestamp.now() - pd.Timedelta("1 day")
        return date_col

    def path_with_fmt_suffix(self, path: Path) -> Path:
        return path.with_suffix(self.value)

    def _read_states_daily(self, *, from_web: bool) -> pd.DataFrame:
        local_data_path = Paths.DATA / "covid_states_daily"

        if from_web:
            df = pd.read_csv(
                Urls.COVIDTRACKING_STATES_DAILY_HISTORICAL, dtype=str, low_memory=False,
            )
            self.save(df, local_data_path)
        else:
            df = self._load(local_data_path)

        df: pd.DataFrame
        df = df.rename(
            columns={
                "date": Columns.DATE,
                "state": Columns.TWO_LETTER_STATE_CODE,
                "positive": CaseTypes.CONFIRMED,
                "death": CaseTypes.DEATHS,
            }
        )
        for col in [Columns.DATE, "dateChecked"]:
            df[col] = pd.to_datetime(df[col])

        df[Columns.DATE] = self._adjust_dates(df[Columns.DATE])
        df = df.melt(
            id_vars=[Columns.DATE, Columns.TWO_LETTER_STATE_CODE, "dateChecked"],
            value_vars=[
                CaseTypes.CONFIRMED,
                CaseTypes.DEATHS,
                # "negative",
                # "pending",
                # "hospitalized",
                # "total",
                # "totalTestResults",
                # "deathIncrease",
                # "hospitalizedIncrease",
                # "negativeIncrease",
                # "positiveIncrease",
                # "totalTestResultsIncrease",
            ],
            var_name=Columns.CASE_TYPE,
            value_name=Columns.CASE_COUNT,
        )

        df[Columns.CASE_COUNT] = df[Columns.CASE_COUNT].fillna(0).astype(int)

        df[Columns.STATE] = df.merge(
            pd.read_csv(Paths.DATA / "usa_state_abbreviations.csv", dtype="string"),
            how="left",
            left_on=Columns.TWO_LETTER_STATE_CODE,
            right_on="Abbreviation:",
        )["US State:"]
        df[Columns.STATE] = (
            df[Columns.STATE].fillna(df[Columns.TWO_LETTER_STATE_CODE]).astype("string")
        )

        df = df[df[Columns.TWO_LETTER_STATE_CODE].isin(USA_STATE_CODES)]
        df[Columns.COUNTRY] = Locations.USA

        population_series = df.merge(
            pd.read_csv(Paths.DATA / "usa_and_state_populations.csv", dtype="string"),
            how="left",
            left_on=Columns.TWO_LETTER_STATE_CODE,
            right_on="Abbreviation:",
        )["Population"]
        df[Columns.POPULATION] = pd.array(
            population_series.map(int, na_action="ignore")
            # .values needed to handle index alignment issues when assigning
            .values,
            dtype="Int64",
        )

        df = df[DATA_COLS]

        return df

    def _read_countries_daily(self, *, from_web: bool) -> pd.DataFrame:
        local_data_path = Paths.DATA / "covid_countries_daily"
        if from_web:
            # WaPo delays requests if they don't have a human-like user agent
            r = requests.get(Urls.WAPO_COUNTRIES_DAILY_HISTORICAL, headers=Urls.HEADERS)
            df = pd.read_csv(io.StringIO(r.text), dtype=str, low_memory=False)
            self.save(df, local_data_path)
        else:
            df = self._load(local_data_path)

        df: pd.DataFrame
        df = df.rename(
            columns={
                "country": Columns.COUNTRY,
                "date": Columns.DATE,
                "confirmed": CaseTypes.CONFIRMED,
                "deaths": CaseTypes.DEATHS,
            }
        )
        for col in [Columns.DATE]:
            df[col] = pd.to_datetime(df[col])

        df[Columns.DATE] = self._adjust_dates(df[Columns.DATE])

        df = df.melt(
            id_vars=[
                Columns.COUNTRY,
                "countryGeo",
                Columns.DATE,
                "dateInProgress",
                "updated",
            ],
            value_vars=[CaseTypes.CONFIRMED, CaseTypes.DEATHS],
            var_name=Columns.CASE_TYPE,
            value_name=Columns.CASE_COUNT,
        )
        df[Columns.CASE_COUNT] = df[Columns.CASE_COUNT].fillna(0).astype(int)

        df[Columns.STATE] = ""  # NA preferred except it doesn't play nice with groupby
        df[Columns.COUNTRY] = (
            df[Columns.COUNTRY]
            .map({"U.S.": Locations.USA, "Georgia": "Georgia (country)"})
            .fillna(df[Columns.COUNTRY])
        )

        population_series = df.merge(
            pd.read_csv(Paths.DATA / "country_populations.csv", dtype="string"),
            how="left",
            left_on=Columns.COUNTRY,
            right_on="Country (or dependent territory)",
        )["Population"]
        df[Columns.POPULATION] = pd.array(
            population_series.map(int, na_action="ignore").values, dtype="Int64",
        )

        df = df[DATA_COLS]

        return df

    def _load(self, path: Path) -> pd.DataFrame:
        path = self.path_with_fmt_suffix(path)
        if self == SaveFormats.CSV:
            return pd.read_csv(path, dtype=str, low_memory=False)
        elif self == SaveFormats.PARQUET:
            return pd.read_parquet(path)

    def read(self, *, from_web: bool) -> pd.DataFrame:
        if from_web:
            print("Pulling data from web")
        else:
            print("Using locally cached data")

        states_df = self._read_states_daily(from_web=from_web)
        countries_df = self._read_countries_daily(from_web=from_web)

        # We don't really need to groupby state; just don't want to drop the column
        world_df = countries_df.groupby([Columns.DATE, Columns.CASE_TYPE])[
            Columns.CASE_COUNT
        ].sum()
        china_df = (
            countries_df[countries_df[Columns.COUNTRY] == Locations.CHINA]
            .groupby([Columns.DATE, Columns.CASE_TYPE])[Columns.CASE_COUNT]
            .sum()
        )

        world_minus_china_df = world_df - china_df

        countries_pop_df = pd.read_csv(
            Paths.DATA / "country_populations.csv", dtype=str
        )
        world_pop = int(
            countries_pop_df.loc[
                countries_pop_df["Country (or dependent territory)"] == "World",
                "Population",
            ].iloc[0]
        )
        china_pop = int(
            countries_pop_df.loc[
                countries_pop_df["Country (or dependent territory)"] == "China",
                "Population",
            ].iloc[0]
        )

        world_df = world_df.reset_index().assign(
            **{
                Columns.STATE: "",
                Columns.COUNTRY: Locations.WORLD,
                Columns.POPULATION: world_pop,
            }
        )
        world_minus_china_df = world_minus_china_df.reset_index().assign(
            **{
                Columns.STATE: "",
                Columns.COUNTRY: Locations.WORLD_MINUS_CHINA,
                Columns.POPULATION: world_pop - china_pop,
            }
        )

        df = pd.concat(
            [states_df, countries_df, world_df, world_minus_china_df],
            axis=0,
            ignore_index=True,
        )
        df[Columns.POPULATION] = pd.array(df[Columns.POPULATION], dtype="Int64")

        df[Columns.IS_STATE] = df[Columns.STATE] != ""
        df[Columns.LOCATION_NAME] = df[Columns.STATE].where(
            df[Columns.IS_STATE], df[Columns.COUNTRY]
        )

        return df

    def save(self, df: pd.DataFrame, path: Path):
        path = self.path_with_fmt_suffix(path)
        if self == SaveFormats.CSV:
            df.to_csv(path, index=False)
        elif self == SaveFormats.PARQUET:
            df.to_parquet(path, index=False, compression="brotli")
            # Seems silly but I want a human-readable file around at all times
            df.to_csv(path, index=False)
        else:
            raise ValueError(f"Unhandled case {self} when writing")
