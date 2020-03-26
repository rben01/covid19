# ***
# WARNING: The code style in this file will seem awful. It is. This used to get the
# old data format, and since it worked and the old data won't be seeing any further
# updates, I am changing as little as possible and just taking the data this file
# produces and concatenating it with the new, good data to fill the gaps in the new data
# ***
from pathlib import Path
from typing import List

import pandas as pd
from IPython.display import display  # noqa F401

from constants import CaseTypes, Columns, Locations, Paths

DATA_PATH = Paths.ROOT / "csse_covid_19_data" / "csse_covid_19_time_series"


def get_country_cases_df(filepath: Path, *, case_type: str):
    case_type = case_type.title()

    df = pd.read_csv(filepath, dtype=str)
    df: pd.DataFrame

    df = df.rename(
        columns={"Province/State": Columns.STATE, "Country/Region": Columns.COUNTRY}
    ).melt(
        id_vars=[Columns.STATE, Columns.COUNTRY, Columns.LATITUDE, Columns.LONGITUDE],
        var_name=Columns.DATE,
        value_name=Columns.CASE_COUNT,
    )
    df[Columns.DATE] = pd.to_datetime(df[Columns.DATE])
    df[Columns.CASE_TYPE] = case_type
    df[Columns.CASE_COUNT] = (
        df[Columns.CASE_COUNT].str.replace(",", "").fillna(0).astype(int)
    )

    return df


def get_world_cases_df(filepath: Path, *, case_type: str):
    df = get_country_cases_df(filepath, case_type=case_type)
    return df


def get_old_data() -> pd.DataFrame:
    dfs = []
    dfs: List[pd.DataFrame]

    # Use this for US states only
    for csv in DATA_PATH.glob("time_series_19*.csv"):
        case_type = csv.stem.replace("time_series_19-covid-", "")
        df = get_country_cases_df(csv, case_type=case_type)
        df = df[
            df[Columns.COUNTRY].isin([Locations.USA])
            & (df[Columns.STATE].notna())
            & (df[Columns.STATE] != df[Columns.COUNTRY])
        ]
        dfs.append(df)

    # Use this for countries (including Chinese provinces)
    for csv in DATA_PATH.glob("time_series_covid19_*_global.csv"):
        case_type = csv.stem.replace("time_series_covid19_", "").replace("_global", "")
        df = get_world_cases_df(csv, case_type=case_type)
        dfs.append(df)

    df = pd.concat(dfs, axis=0, ignore_index=True)

    # Remove cities in US (eg "New York, NY")
    df = df[~df[Columns.STATE].str.contains(",").fillna(False)]

    # For countries other than the US and China don't include their
    # states/discontiguous regions
    # E.g., Gibraltar, Isle of Man, French Polynesia, etc
    # Do keep US states and Chinese provinces
    df = df[
        df[Columns.COUNTRY].isin([Locations.USA, Locations.CHINA])
        | (df[Columns.STATE] == df[Columns.COUNTRY])  # France is like this, idk why
        | df[Columns.STATE].isna()
    ]

    # Convert to new case type names
    df[Columns.CASE_TYPE] = (
        df[Columns.CASE_TYPE]
        .replace(
            {
                "Confirmed": CaseTypes.CONFIRMED,
                "Deaths": CaseTypes.DEATHS,
                "Recovered": CaseTypes.RECOVERED,
            }
        )
        .astype("string")
    )

    # Minor cleanup
    df[Columns.COUNTRY] = (
        df[Columns.COUNTRY]
        .map(
            {
                "US": Locations.USA,
                "Korea, South": Locations.SOUTH_KOREA,
                "Georgia": "Georgia (country)",
            }
        )
        .fillna(df[Columns.COUNTRY])
    )

    df[Columns.IS_STATE] = df[Columns.STATE].notna() & (
        df[Columns.STATE] != df[Columns.COUNTRY]
    )
    # Use state as location name for states, else use country name
    # df[Columns.LOCATION_NAME] = df[Columns.STATE].fillna(df[Columns.COUNTRY])

    # Hereafter df is sorted by date, which is helpful as it allows using .iloc[-1]
    # to get current (or most recent known) situation per location
    # df = df.sort_values([Columns.LOCATION_NAME, Columns.DATE])

    for col in Columns.string_cols:
        if col not in df.columns:
            df[col] = pd.NA

        df[col] = df[col].astype("string")

    return df
