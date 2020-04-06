# %%
import argparse

import pandas as pd
from IPython.display import display  # noqa F401

import read_in_data
from constants import (
    ABCStrictEnum,
    CaseInfo,
    CaseTypes,
    Columns,
    Counting,
    DiseaseStage,
    InfoField,
    Locations,
    Paths,
)
from plotting import plot


def _get_data(*, from_web: bool) -> pd.DataFrame:
    df = read_in_data.SaveFormats.CSV.read(from_web=from_web)
    return df


def _get_df_with_outbreak_start_date_and_days_since(df: pd.DataFrame) -> pd.DataFrame:

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
        # Filter df for days where case count was at least threshold for given case type
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


def append_per_capita_data(df: pd.DataFrame) -> pd.DataFrame:
    per_capita_df = df.copy()
    per_capita_df[Columns.CASE_COUNT] /= per_capita_df[Columns.POPULATION]
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

    df = _get_df_with_outbreak_start_date_and_days_since(df)
    per_capita_df = _get_df_with_outbreak_start_date_and_days_since(per_capita_df)

    df = pd.concat([df, per_capita_df], axis=0, ignore_index=True)

    return df


def clean_up(df: pd.DataFrame) -> pd.DataFrame:
    # Hereafter df is sorted by date, which is helpful as it allows using .iloc[-1]
    # to get current (or most recent known) situation per location
    # (Otherwise we'd have to groupby agg -> min date, and then filter)
    df = df.sort_values(
        [Columns.LOCATION_NAME, Columns.DATE, Columns.CASE_TYPE], ascending=True
    )

    return df


def get_df(*, refresh_local_data: bool) -> pd.DataFrame:
    df = _get_data(from_web=refresh_local_data)
    df = append_per_capita_data(df)
    df = clean_up(df)
    return df


def keep_only_n_largest_locations(
    df: pd.DataFrame, n: int, count: Counting
) -> pd.DataFrame:
    case_type = CaseInfo.get_info_item_for(
        InfoField.CASE_TYPE, stage=DiseaseStage.CONFIRMED, count=count
    )

    def get_n_largest_locations(df: pd.DataFrame) -> pd.Series:
        return (
            df[df[Columns.CASE_TYPE] == case_type]
            .groupby(Columns.location_id_cols)
            .apply(lambda g: g[Columns.CASE_COUNT].iloc[-1])
            .nlargest(n)
            .rename(CaseTypes.CONFIRMED)
        )

    def keep_only_above_cutoff(df: pd.DataFrame, cutoff: float) -> pd.DataFrame:
        return df.groupby(Columns.location_id_cols).filter(
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
    df: pd.DataFrame, n: int, count: Counting = None, *, include_china: bool,
) -> pd.DataFrame:

    if count is None:
        count = Counting.TOTAL_CASES

    exclude_locations = set([Locations.WORLD, Locations.WORLD_MINUS_CHINA])
    if not include_china:
        exclude_locations.add(Locations.CHINA)

    df = df[
        (~df[Columns.IS_STATE]) & (~df[Columns.LOCATION_NAME].isin(exclude_locations))
    ]
    return keep_only_n_largest_locations(df, n, count)


def get_usa_states_df(df: pd.DataFrame, n: int, count: Counting = None) -> pd.DataFrame:

    if count is None:
        count = Counting.TOTAL_CASES

    df = df[(df[Columns.COUNTRY] == Locations.USA) & df[Columns.IS_STATE]]
    return keep_only_n_largest_locations(df, n, count)


def create_data_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[Columns.DATE] = df[Columns.DATE].dt.strftime(r"%Y-%m-%d")

    df = df.drop(
        columns=[
            Columns.IS_STATE,
            Columns.LOCATION_NAME,
            Columns.OUTBREAK_START_DATE_COL,
            Columns.DAYS_SINCE_OUTBREAK,
            Columns.POPULATION,
        ]
    )

    df = (
        df.pivot_table(
            index=[
                c
                for c in df.columns
                if c not in [Columns.CASE_TYPE, Columns.CASE_COUNT]
            ],
            columns=Columns.CASE_TYPE,
            values=Columns.CASE_COUNT,
            aggfunc="first",
        )
        .reset_index()
        .sort_values([Columns.COUNTRY, Columns.STATE, Columns.DATE])
    )

    for col in CaseInfo.get_info_items_for(
        InfoField.CASE_TYPE, count=Counting.TOTAL_CASES
    ):
        df[col] = pd.to_numeric(df[col], downcast="integer")

    for col in CaseInfo.get_info_items_for(
        InfoField.CASE_TYPE, count=Counting.PER_CAPITA
    ):
        df[col] = df[col].map("{:e}".format)

    save_path = Paths.DATA / "data_table.csv"
    df.to_csv(save_path, index=False)
    print(f"Saved data to {save_path.relative_to(Paths.ROOT)}")

    return df


def main(namespace: argparse.Namespace = None):
    if namespace is None:
        namespace = argparse.Namespace()
        namespace.refresh = False
        namespace.create_data_table = False
        namespace.no_graphs = False

    df = get_df(refresh_local_data=namespace.refresh)

    if namespace.create_data_table:
        create_data_table(df)

    if namespace.no_graphs:
        return

    world_df = get_world_df(df)
    usa_states_df = get_usa_states_df(df, 10)
    countries_with_china_df = get_countries_df(df, 10, include_china=True)
    countries_wo_china_df = get_countries_df(df, 9, include_china=False)

    # Make absolute count graphs
    plot(world_df, x_axis=Columns.XAxis.DATE, count=Counting.TOTAL_CASES)
    plot(
        countries_wo_china_df,
        df_with_china=countries_with_china_df,
        x_axis=Columns.XAxis.DATE,
        count=Counting.TOTAL_CASES,
    )
    plot(usa_states_df, x_axis=Columns.XAxis.DATE, count=Counting.TOTAL_CASES)

    plot(
        countries_wo_china_df,
        df_with_china=countries_with_china_df,
        x_axis=Columns.XAxis.DAYS_SINCE_OUTBREAK,
        stage=DiseaseStage.CONFIRMED,
        count=Counting.TOTAL_CASES,
    )
    plot(
        countries_wo_china_df,
        df_with_china=countries_with_china_df,
        x_axis=Columns.XAxis.DAYS_SINCE_OUTBREAK,
        stage=DiseaseStage.DEATH,
        count=Counting.TOTAL_CASES,
    )

    plot(
        usa_states_df,
        x_axis=Columns.XAxis.DAYS_SINCE_OUTBREAK,
        stage=DiseaseStage.CONFIRMED,
        count=Counting.TOTAL_CASES,
    )
    plot(
        usa_states_df,
        x_axis=Columns.XAxis.DAYS_SINCE_OUTBREAK,
        stage=DiseaseStage.DEATH,
        count=Counting.TOTAL_CASES,
    )

    # Make per capita graphs
    plot(
        countries_wo_china_df,
        df_with_china=countries_with_china_df,
        x_axis=Columns.XAxis.DATE,
        count=Counting.PER_CAPITA,
    )
    plot(
        usa_states_df, x_axis=Columns.XAxis.DATE, count=Counting.PER_CAPITA,
    )

    return df


# A little hack -- an ipython cell that will run in an interactive window but not when
# running this from a terminal
if False:
    pass
    # %%
    df = main()

# %% Don't run this cell if using ipython
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--create-data-table",
        action="store_true",
        help="Save data used in graphs to a file",
    )
    parser.add_argument(
        "--no-graphs", action="store_true", help="Don't create graphs",
    )
    data_group = parser.add_mutually_exclusive_group()
    data_group.add_argument(
        "--use-web-data",
        action="store_true",
        dest="refresh",
        help="Pull data from web sources",
    )
    data_group.add_argument(
        "--use-local-data",
        action="store_false",
        dest="refresh",
        help="Use locally cached data",
    )

    args = parser.parse_args()
    df = main(args)
