# %%
import argparse

import pandas as pd
from IPython.display import display  # noqa F401

import read_in_data
from constants import (
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
    """Get country- and state-level daily data]

    :param from_web: Whether to refresh data by pulling from the web, or just use
    locally cached
    :type from_web: bool
    :return: The data
    :rtype: pd.DataFrame
    """

    df = read_in_data.SaveFormats.CSV.read(from_web=from_web)
    return df


def get_df_with_outbreak_start_date_and_days_since(df: pd.DataFrame) -> pd.DataFrame:
    """Append outbreak start date and days since outbreak columns to the given dataframe

    The start of an outbreak is defined to be the date at which the relevant statistic
    (number of cases, deaths per capita, etc) crosses a predefined threshold. This
    start date is computed once for each statistic for each location.

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
    """Add rows for per-capita data to the given dataframe

    For each row in the input dataframe (assumed to not yet contain per-capita data),
    divide the numbers by locations' populations and add the per-capita data to the
    bottom of the dataframe

    :param df: The input dataframe
    :type df: pd.DataFrame
    :return: The input dataframe with per-capita data appended to the bottom
    :rtype: pd.DataFrame
    """

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

    df = pd.concat([df, per_capita_df], axis=0, ignore_index=True)

    return df


def clean_up(df: pd.DataFrame) -> pd.DataFrame:
    """Perform any remaining cleaning up of the dataframe

    Currently, only sorts the dataframe (which is important as it allows us to assume
    that the earliest data is at iloc[0] and the latest at iloc[-1])

    :param df: The input dataframe
    :type df: pd.DataFrame
    :return: The cleaned up dataframe
    :rtype: pd.DataFrame
    """

    # Hereafter df is sorted by date, which is helpful as it allows using .iloc[-1]
    # to get current (or most recent known) situation per location
    # (Otherwise we'd have to groupby agg -> min date, and then filter)
    df = df.sort_values(
        [Columns.LOCATION_NAME, Columns.DATE, Columns.CASE_TYPE], ascending=True
    )

    return df


def get_df(*, refresh_local_data: bool) -> pd.DataFrame:
    """Get the dataframe to be used in plotting

    Reads in data from the original sources, then augments it with additional
    statistics to be used in plotting. Data is sorted ascending by date so that for any
    subset of the data, the earliest date is at iloc[0] and the latest at iloc[-1].

    :param refresh_local_data: Whether to refresh local data by fetching from the web,
    or just use locally cached data without refreshing
    :type refresh_local_data: bool
    :return: The dataframe to be used in plotting
    :rtype: pd.DataFrame
    """

    df = _get_data(from_web=refresh_local_data)
    df = append_per_capita_data(df)
    df = get_df_with_outbreak_start_date_and_days_since(df)
    df = clean_up(df)
    return df


def keep_only_n_largest_locations(
    df: pd.DataFrame, n: int, count: Counting
) -> pd.DataFrame:
    """Keep only the n largest locations when considering the current confirmed cases
    measured by `count` (total or per capita)

    Given a dataframe, remove all but the n largest locations, using today's value of
    confirmed cases (total or per capita, depending on `count)

    :param df: The input dataframe
    :type df: pd.DataFrame
    :param n: How many locations to keep
    :type n: int
    :param count: Whether to order locations by confirmed cases or confirmed cases per
    capita
    :type count: Counting
    :return: The dataframe filtered to just the top n locations
    :rtype: pd.DataFrame
    """

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
    """Get aggregate data for the world, China, and all countries other than China

    :param df: The input dataframe, containing data for all locations
    :type df: pd.DataFrame
    :return: A dataframe containing data for just three locations: the world, China, and
        everywhere else
    :rtype: pd.DataFrame
    """

    return df[
        df[Columns.LOCATION_NAME].isin(
            [Locations.WORLD, Locations.WORLD_MINUS_CHINA, Locations.CHINA]
        )
    ]


def get_countries_df(
    df: pd.DataFrame, n: int, count: Counting = None, *, include_china: bool
) -> pd.DataFrame:
    """Get the top n countries in the world, optionally dropping China from the list

    :param df: Dataframe containing data on all locations
    :type df: pd.DataFrame
    :param n: How many countries to keep. If include_china is False, n-1 countries will
    be kept
    :type n: int
    :param include_china: Whether to include China
    :type include_china: bool
    :param count: Which count method to use when sorting, defaults to None (total cases)
    :type count: Counting, optional
    :return: The input dataframe filtered to just three locations: whole world, China,
    and whole world minus China
    :rtype: pd.DataFrame
    """

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
    """Get the top n US states from the dataframe

    :param df: Dataframe containing data for all locations
    :type df: pd.DataFrame
    :param n: How many states to keep
    :type n: int
    :param count: Whether to count by total cases or per capita, by default None,
    defaults to None (total cases)
    :type count: Counting, optional
    :return: The dataframe filtered to the top n US states
    :rtype: pd.DataFrame
    """

    if count is None:
        count = Counting.TOTAL_CASES

    df = df[(df[Columns.COUNTRY] == Locations.USA) & df[Columns.IS_STATE]]
    return keep_only_n_largest_locations(df, n, count)


def create_data_table(df: pd.DataFrame) -> pd.DataFrame:
    """Creates a data table containing all of the input dataframe's data in a format
    appropriate for sharing with others

    Return the data in the input dataframe, dropping some columns only used internally
    and pivoting to a wide format w.r.t. case types

    :param df: Dataframe containing all locations' data in long format
    :type df: pd.DataFrame
    :return: Dataframe containing all locations' data in wide format, with some
    auxiliary columns dropped
    :rtype: pd.DataFrame
    """

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


def main(namespace: argparse.Namespace = None) -> pd.DataFrame:
    """Run everything, optionally performing tasks based on flags in `namespace`

    Entry point to the rest of the functions. Takes an `argparse.Namespace` that
    contains information on which tasks will be performed and has flags governing those
    tasks' behavior. If `None`, sets reasonable defaults.

    :param namespace: The namespace generated by `argparse`; defaults to None (default
    behavior will be used)
    :type namespace: argparse.Namespace, optional
    :return: The dataframe used to create the plots
    :rtype: pd.DataFrame
    """

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
