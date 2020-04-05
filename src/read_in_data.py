# %%
import enum
import io
from pathlib import Path

import pandas as pd
import requests
from IPython.display import display  # noqa F401

from constants import (
    USA_STATE_CODES,
    CaseType,
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


class SaveFormats(enum.Enum):
    CSV = ".csv"
    CSV: "SaveFormats"

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

    def _print_if_new_data(self, df: pd.DataFrame, data_path: Path, message: str):
        # Inform user that new data exists
        try:
            orig_df = self._load(data_path)
        except FileNotFoundError:
            orig_df = None

        if not df.equals(orig_df):
            print(message)

    def _read_states_daily(self, *, from_web: bool) -> pd.DataFrame:
        local_data_path = Paths.DATA / "covid_states_daily"

        if from_web:
            df = pd.read_csv(
                Urls.COVIDTRACKING_STATES_DAILY_HISTORICAL, dtype=str, low_memory=False,
            )
            self._print_if_new_data(df, local_data_path, "Got new US states data")

            self.save(df, local_data_path)
        else:
            df = self._load(local_data_path)

        df: pd.DataFrame
        df = df.rename(
            columns={
                "date": Columns.DATE,
                "state": Columns.TWO_LETTER_STATE_CODE,
                "positive": CaseType.CONFIRMED,
                "death": CaseType.DEATHS,
            }
        )
        for col in [Columns.DATE, "dateChecked"]:
            df[col] = pd.to_datetime(df[col])

        df[Columns.DATE] = self._adjust_dates(df[Columns.DATE])

        df = df.melt(
            id_vars=[Columns.DATE, Columns.TWO_LETTER_STATE_CODE, "dateChecked"],
            value_vars=[
                CaseType.CONFIRMED,
                CaseType.DEATHS,
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
            self._print_if_new_data(df, local_data_path, "Got new countries data")
            self.save(df, local_data_path)
        else:
            df = self._load(local_data_path)

        df: pd.DataFrame
        df = df.rename(
            columns={
                "country": Columns.COUNTRY,
                "date": Columns.DATE,
                "confirmed": CaseType.CONFIRMED,
                "deaths": CaseType.DEATHS,
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
            value_vars=[CaseType.CONFIRMED, CaseType.DEATHS],
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
            try:
                return pd.read_parquet(path)
            except IOError as e:  # pyarrow raises IOError on file not found...
                raise FileNotFoundError(str(e))

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

        world_df = world_df.reset_index()
        for col, value in {
            Columns.STATE: "",
            Columns.COUNTRY: Locations.WORLD,
            Columns.POPULATION: world_pop,
        }.items():
            world_df[col] = value

        world_minus_china_df = world_minus_china_df.reset_index()
        for col, value in {
            Columns.STATE: "",
            Columns.COUNTRY: Locations.WORLD_MINUS_CHINA,
            Columns.POPULATION: world_pop - china_pop,
        }.items():
            world_minus_china_df[col] = value

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


SaveFormats.CSV.read(from_web=False)
