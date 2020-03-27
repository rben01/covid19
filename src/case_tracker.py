# %%
import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import display  # noqa F401

import read_in_data
from constants import CASE_THRESHOLD, CaseTypes, Columns, Locations
from plotting import (
    plot_cases_by_days_since_first_widespread_locally,
    plot_cases_from_fixed_date,
)


def get_data(*, from_web: bool) -> pd.DataFrame:
    df = read_in_data.SaveFormats.PARQUET.read(from_web=from_web)
    return df


def get_df_with_days_since_n_confirmed_cases(
    df: pd.DataFrame, confirmed_case_threshold: int
) -> pd.DataFrame:
    OUTBREAK_START_DATE_COL = "Outbreak start date"
    outbreak_start_dates = (
        df[
            (df[Columns.CASE_TYPE] == CaseTypes.CONFIRMED)
            & (df[Columns.CASE_COUNT] >= confirmed_case_threshold)
        ]
        .groupby(Columns.id_cols)[Columns.DATE]
        .min()
        .rename(OUTBREAK_START_DATE_COL)
    )
    df = df.merge(outbreak_start_dates, how="left", on=Columns.id_cols)

    df[Columns.DAYS_SINCE_OUTBREAK] = (
        df[Columns.DATE] - df[OUTBREAK_START_DATE_COL]
    ).dt.total_seconds() / 86400

    return df


def clean_up(df: pd.DataFrame) -> pd.DataFrame:
    # Hereafter df is sorted by date, which is helpful as it allows using .iloc[-1]
    # to get current (or most recent known) situation per location
    df = df.sort_values(
        [Columns.LOCATION_NAME, Columns.DATE, Columns.CASE_TYPE], ascending=True
    )

    return df


def get_df(*, refresh_local_data: bool) -> pd.DataFrame:
    df = get_data(from_web=refresh_local_data)
    df = get_df_with_days_since_n_confirmed_cases(
        df, confirmed_case_threshold=CASE_THRESHOLD
    )
    df = clean_up(df)
    return df


def keep_only_n_largest_locations(df: pd.DataFrame, n: int) -> pd.DataFrame:
    def get_n_largest_locations(df: pd.DataFrame, n: int) -> pd.Series:
        return (
            df[df[Columns.CASE_TYPE] == CaseTypes.CONFIRMED]
            .groupby(Columns.id_cols)
            .apply(lambda g: g[Columns.CASE_COUNT].iloc[-1])
            .nlargest(n)
            .rename(CaseTypes.CONFIRMED)
        )

    def keep_only_above_cutoff(df: pd.DataFrame, cutoff: float) -> pd.DataFrame:
        return df.groupby(Columns.id_cols).filter(
            lambda g: (
                g.loc[
                    g[Columns.CASE_TYPE] == CaseTypes.CONFIRMED, Columns.CASE_COUNT
                ].iloc[-1]
                >= cutoff
            )
        )

    n_largest_location_case_counts = get_n_largest_locations(df, n)
    case_count_cutoff = n_largest_location_case_counts.min()
    return keep_only_above_cutoff(df, case_count_cutoff)


def get_world_df(df: pd.DataFrame) -> pd.DataFrame:
    return df[
        df[Columns.LOCATION_NAME].isin(
            [Locations.WORLD, Locations.WORLD_MINUS_CHINA, Locations.CHINA]
        )
    ]


def get_countries_df(df: pd.DataFrame, n: int) -> pd.DataFrame:
    df = df[
        (~df[Columns.IS_STATE])
        & (
            ~df[Columns.LOCATION_NAME].isin(
                [Locations.WORLD, Locations.WORLD_MINUS_CHINA, Locations.CHINA]
            )
        )
    ]
    return keep_only_n_largest_locations(df, n)


def get_usa_states_df(df: pd.DataFrame, n: int) -> pd.DataFrame:
    df = df[(df[Columns.COUNTRY] == Locations.USA) & df[Columns.IS_STATE]]
    return keep_only_n_largest_locations(df, n)


df = get_df(refresh_local_data=True)
display(df)

# %%
plot_cases_from_fixed_date(get_world_df(df))
plot_cases_from_fixed_date(get_countries_df(df, 10))
plot_cases_from_fixed_date(get_usa_states_df(df, 10))

plot_cases_by_days_since_first_widespread_locally(get_world_df(df))
plot_cases_by_days_since_first_widespread_locally(get_countries_df(df, 10))
plot_cases_by_days_since_first_widespread_locally(get_usa_states_df(df, 10))

# days_since_outbreak_df = get_df_with_days_since_local_outbreak(df,)

# %%
plt.show()
