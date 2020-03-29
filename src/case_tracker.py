# %%
import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import display  # noqa F401

import read_in_data
from constants import CaseTypes, Columns, Locations, Thresholds, CaseGroup
from plotting import (
    plot_cases_by_days_since_first_widespread_locally,
    plot_cases_from_fixed_date,
)


def get_data(*, from_web: bool) -> pd.DataFrame:
    df = read_in_data.SaveFormats.PARQUET.read(from_web=from_web)
    return df


def _get_df_with_outbreak_start_date_and_days_since(
    df: pd.DataFrame, *, case_type: str, confirmed_case_threshold: int,
) -> pd.DataFrame:
    outbreak_start_dates = (
        df[
            (df[Columns.CASE_TYPE] == case_type)
            & (df[Columns.CASE_COUNT] >= confirmed_case_threshold)
        ]
        .groupby(Columns.id_cols)[Columns.DATE]
        .min()
        .rename(Columns.OUTBREAK_START_DATE_COL)
    )

    df = df.merge(outbreak_start_dates, how="left", on=Columns.id_cols)

    df[Columns.DAYS_SINCE_OUTBREAK] = (
        df[Columns.DATE] - df[Columns.OUTBREAK_START_DATE_COL]
    ).dt.total_seconds() / 86400

    return df


def append_per_capita_data(df: pd.DataFrame) -> pd.DataFrame:
    per_capita_df = df.copy()
    per_capita_df[Columns.CASE_COUNT] /= per_capita_df[Columns.POPULATION]
    per_capita_df[Columns.CASE_TYPE] = (
        per_capita_df[Columns.CASE_TYPE]
        .map(
            {
                CaseTypes.CONFIRMED: CaseTypes.CASES_PER_CAPITA,
                CaseTypes.DEATHS: CaseTypes.DEATHS_PER_CAPITA,
            }
        )
        .fillna(per_capita_df[Columns.CASE_TYPE])
    )

    df = _get_df_with_outbreak_start_date_and_days_since(
        df,
        case_type=CaseTypes.CONFIRMED,
        confirmed_case_threshold=Thresholds.CASE_COUNT,
    )
    per_capita_df = _get_df_with_outbreak_start_date_and_days_since(
        per_capita_df,
        case_type=CaseTypes.CASES_PER_CAPITA,
        confirmed_case_threshold=Thresholds.CASES_PER_CAPITA,
    )

    df = pd.concat([df, per_capita_df], axis=0, ignore_index=True)
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
    # df = df[df[Columns.LOCATION_NAME] == "New York"]
    df = append_per_capita_data(df)
    df = clean_up(df)
    return df


def keep_only_n_largest_locations(
    df: pd.DataFrame, n: int, count_type: CaseGroup.CountType
) -> pd.DataFrame:
    case_type = CaseTypes.get_case_types(
        stage=CaseGroup.Stage.CONFIRMED, count_type=count_type
    )

    def get_n_largest_locations(df: pd.DataFrame) -> pd.Series:
        return (
            df[df[Columns.CASE_TYPE] == case_type]
            .groupby(Columns.id_cols)
            .apply(lambda g: g[Columns.CASE_COUNT].iloc[-1])
            .nlargest(n)
            .rename(CaseTypes.CONFIRMED)
        )

    def keep_only_above_cutoff(df: pd.DataFrame, cutoff: float) -> pd.DataFrame:
        return df.groupby(Columns.id_cols).filter(
            lambda g: (
                g.loc[g[Columns.CASE_TYPE] == case_type, Columns.CASE_COUNT].iloc[-1]
                >= cutoff
            )
        )

    n_largest_location_case_counts = get_n_largest_locations(df)
    case_count_cutoff = n_largest_location_case_counts.min()
    return keep_only_above_cutoff(df, case_count_cutoff)


def get_world_df(df: pd.DataFrame) -> pd.DataFrame:
    return df[
        df[Columns.LOCATION_NAME].isin(
            [Locations.WORLD, Locations.WORLD_MINUS_CHINA, Locations.CHINA]
        )
    ]


def get_countries_df(
    df: pd.DataFrame, n: int, count_type: CaseGroup = None, *, include_china: bool,
) -> pd.DataFrame:
    count_type = count_type or CaseGroup.CountType.ABSOLUTE

    exclude_locations = set([Locations.WORLD, Locations.WORLD_MINUS_CHINA])
    if not include_china:
        exclude_locations.add(Locations.CHINA)

    df = df[
        (~df[Columns.IS_STATE]) & (~df[Columns.LOCATION_NAME].isin(exclude_locations))
    ]
    return keep_only_n_largest_locations(df, n, count_type)


def get_usa_states_df(
    df: pd.DataFrame, n: int, count_type: CaseGroup.CountType = None
) -> pd.DataFrame:
    count_type = count_type or CaseGroup.CountType.ABSOLUTE
    df = df[(df[Columns.COUNTRY] == Locations.USA) & df[Columns.IS_STATE]]
    return keep_only_n_largest_locations(df, n, count_type)


df = get_df(refresh_local_data=True)
# display(df)

for count_type in [*CaseGroup.CountType]:
    world_df = get_world_df(df)
    usa_states_df = get_usa_states_df(df, 10)
    countries_with_china_df = get_countries_df(df, 10, include_china=True)
    countries_wo_china_df = get_countries_df(df, 9, include_china=False)

    plot_cases_from_fixed_date(world_df, count_type=count_type)
    plot_cases_from_fixed_date(
        countries_wo_china_df,
        df_with_china=countries_with_china_df,
        count_type=count_type,
    )
    plot_cases_from_fixed_date(usa_states_df, count_type=count_type)

    plot_cases_by_days_since_first_widespread_locally(
        countries_with_china_df, count_type=count_type
    )
    plot_cases_by_days_since_first_widespread_locally(
        countries_wo_china_df,
        df_with_china=countries_with_china_df,
        count_type=count_type,
    )
    plot_cases_by_days_since_first_widespread_locally(
        usa_states_df, count_type=count_type
    )


# %%
plt.show()
