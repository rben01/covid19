# %%
import enum
import io
from pathlib import Path

import pandas as pd
import requests
from IPython.display import display  # noqa F401

from constants import (
    USA_STATE_CODES,
    CaseInfo,
    CaseTypes,
    Columns,
    Counting,
    DiseaseStage,
    InfoField,
    Locations,
    Paths,
    Urls,
)

COUNTRY_DATA = Paths.DATA / "WaPo"
DATA_COLS = [
    Columns.STATE,
    Columns.COUNTRY,
    Columns.TWO_LETTER_STATE_CODE,
    Columns.DATE,
    Columns.CASE_TYPE,
    Columns.CASE_COUNT,
    Columns.POPULATION,
    Columns.IS_STATE,
    Columns.LOCATION_NAME,
    Columns.STAGE,
    Columns.COUNT_TYPE,
    Columns.OUTBREAK_START_DATE_COL,
    Columns.DAYS_SINCE_OUTBREAK,
]


class SaveFormats(enum.Enum):
    CSV: "SaveFormats" = ".csv"

    # Parquet currently broken (pyarrow bug?), don't know why but csv is fine
    # PARQUET = ".parquet"

    @staticmethod
    def _adjust_dates(date_col: pd.Series) -> pd.Series:
        """Adjust dates to take into account minor timekeeping details

        When we get data, data labeled with <date> represents events from 00:00 to 23:59
        of that date. For the last date on which we have data, we will have less than
        24 hours of data, which will skew the scale of the graph at its right edge.
        Therefore we adjust dates slightly so that what is graphed correctly represents
        the situation. Events are labeled by the time *ending* their 24-hour data
        collection period. Data labeled Mar 20 (i.e., collected during 00:00-23:59 on
        Mar 20) is labeled Mar 21, and data labeled <today> has the current time
        added to it, representing the time period 00:00-<current time> of <today>.

        :param date_col: The column of dates to adjust
        :type date_col: pd.Series
        :return: The dates adjusted as described above
        :rtype: pd.Series
        """
        date_col = date_col.copy()
        is_todays_date = date_col.dt.strftime(r"%Y%m%d") == pd.Timestamp.now().strftime(
            r"%Y%m%d"
        )
        date_col.loc[is_todays_date] = pd.Timestamp.now()
        date_col.loc[~is_todays_date] += pd.Timedelta(days=1)
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

        return df

    @staticmethod
    def append_percapita_stage_count(df: pd.DataFrame) -> pd.DataFrame:
        """Add rows for per-capita data to the given dataframe

        For each row in the input dataframe (assumed to not yet contain per-capita
        data), divide the numbers by locations' populations and add the per-capita data
        to the bottom of the dataframe

        :param df: The input dataframe
        :type df: pd.DataFrame
        :return: The input dataframe with per-capita data appended to the bottom
        :rtype: pd.DataFrame
        """

        total_cases_df = df.copy()
        per_capita_df = df.copy()

        total_cases_df[Columns.STAGE] = per_capita_df[Columns.STAGE] = df[
            Columns.CASE_TYPE
        ].map(
            {
                CaseTypes.CONFIRMED: DiseaseStage.CONFIRMED.name,
                CaseTypes.DEATHS: DiseaseStage.DEATH.name,
            }
        )

        per_capita_df[Columns.CASE_TYPE] = (
            per_capita_df[Columns.CASE_TYPE]
            .map(
                {
                    CaseTypes.CONFIRMED: CaseTypes.CONFIRMED_PER_CAPITA,
                    CaseTypes.DEATHS: CaseTypes.DEATHS_PER_CAPITA,
                }
            )
            .fillna(per_capita_df[Columns.CASE_TYPE])
        )

        per_capita_df[Columns.CASE_COUNT] /= per_capita_df[Columns.POPULATION]

        total_cases_df[Columns.COUNT_TYPE] = Counting.TOTAL_CASES.name
        per_capita_df[Columns.COUNT_TYPE] = Counting.PER_CAPITA.name

        return pd.concat(
            [total_cases_df, per_capita_df], axis=0, ignore_index=True, copy=True
        )

    @staticmethod
    def get_df_with_outbreak_start_date_and_days_since(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Append outbreak start date and days since outbreak columns to the given dataframe

        The start of an outbreak is defined to be the date at which the relevant
        statistic (number of cases, deaths per capita, etc) crosses a predefined
        threshold. This start date is computed once for each statistic for each
        location.

        :param df: The input dataframe containing locations and case counts on specific
        dates
        :type df: pd.DataFrame
        :return: The dataframe with outbreak start date and days since outbreak columns
        added
        :rtype: pd.DataFrame
        """

        outbreak_thresholds = CaseInfo.get_info_items_for(
            InfoField.THRESHOLD, InfoField.CASE_TYPE
        )

        # Add threshold column to df
        df = df.merge(
            outbreak_thresholds,
            how="left",
            left_on=Columns.CASE_TYPE,
            right_on=InfoField.CASE_TYPE,
        )

        outbreak_id_cols = [*Columns.location_id_cols, Columns.CASE_TYPE]
        outbreak_start_dates = (
            # Filter df for days where case count was at least threshold for given case
            # type
            df[(df[Columns.CASE_COUNT] >= df[InfoField.THRESHOLD])]
            # Get min date for each region
            .groupby(outbreak_id_cols)[Columns.DATE]
            .min()
            .rename(Columns.OUTBREAK_START_DATE_COL)
        )

        df = df.merge(outbreak_start_dates, how="left", on=outbreak_id_cols).drop(
            columns=[InfoField.THRESHOLD, InfoField.CASE_TYPE]
        )

        # For each row, get n days since outbreak started
        df[Columns.DAYS_SINCE_OUTBREAK] = (
            df[Columns.DATE] - df[Columns.OUTBREAK_START_DATE_COL]
        ).dt.total_seconds() / 86400

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

        df = self.append_percapita_stage_count(df)

        df[Columns.IS_STATE] = df[Columns.STATE] != ""
        df[Columns.LOCATION_NAME] = df[Columns.STATE].where(
            df[Columns.IS_STATE], df[Columns.COUNTRY]
        )

        df = self.get_df_with_outbreak_start_date_and_days_since(df)

        df[Columns.TWO_LETTER_STATE_CODE] = df[Columns.TWO_LETTER_STATE_CODE].fillna("")

        df = df[DATA_COLS]

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


if __name__ == "__main__":
    xx = SaveFormats.CSV.read(from_web=False)
