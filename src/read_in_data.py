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
    PARQUET = ".parquet"

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

        df = df[
            [
                Columns.STATE,
                Columns.COUNTRY,
                Columns.DATE,
                Columns.CASE_TYPE,
                Columns.CASE_COUNT,
            ]
        ]

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
            var_name=Columns.CASE_TYPE,
            value_name=Columns.CASE_COUNT,
        )
        df[Columns.CASE_COUNT] = df[Columns.CASE_COUNT].fillna(0).astype(int)

        df[Columns.STATE] = ""
        df[Columns.COUNTRY] = (
            df[Columns.COUNTRY]
            .replace({"U.S.": Locations.USA, "Georgia": "Georgia (country)"})
            .fillna(df[Columns.COUNTRY])
        )

        df = df[
            [
                Columns.STATE,
                Columns.COUNTRY,
                Columns.DATE,
                Columns.CASE_TYPE,
                Columns.CASE_COUNT,
            ]
        ]

        return df

    def _load(self, path: Path) -> pd.DataFrame:
        path = self.path_with_fmt_suffix(path)
        if self == SaveFormats.CSV:
            return pd.read_csv(path, dtype=str, low_memory=False)
        elif self == SaveFormats.PARQUET:
            return pd.read_parquet(path)

    def read(self, *, from_web: bool) -> pd.DataFrame:
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

        world_df = world_df.reset_index().assign(
            **{Columns.STATE: "", Columns.COUNTRY: Locations.WORLD}
        )
        world_minus_china_df = world_minus_china_df.reset_index().assign(
            **{Columns.STATE: "", Columns.COUNTRY: Locations.WORLD_MINUS_CHINA}
        )

        df = pd.concat(
            [states_df, countries_df, world_df, world_minus_china_df],
            axis=0,
            ignore_index=True,
        )

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
        else:
            raise ValueError(f"Unhandled case {self} when writing")
