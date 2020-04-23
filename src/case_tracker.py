# %%
# Imported globally so that `main`'s type annotations work
import argparse

if __name__ == "__main__":
    import sys

    try:
        __this_file = __file__
    except NameError:
        __this_file = None

    # If we're in ipython, sys.argv[0] will be ipykernel.py or something similar, and
    # IN_TERMINAL will be False. When running from a terminal it will be True.
    IN_A_TERMINAL = sys.argv[0] == __this_file

    if IN_A_TERMINAL:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--create-data-table",
            action="store_true",
            help="Save data used in graphs to a file",
        )
        graph_group = parser.add_mutually_exclusive_group()
        graph_group.add_argument(
            "--no-graphs", action="store_true", help="Don't create graphs",
        )
        graph_group.add_argument(
            "--force-graphs",
            action="store_true",
            help="Unconditionally create graphs (even when there's no new data)",
        )

        timeline_group = parser.add_mutually_exclusive_group()
        timeline_group.add_argument(
            "--no-timeline",
            action="store_true",
            help="Don't create the USA timeline video",
        )
        timeline_group.add_argument(
            "--force-timeline",
            action="store_true",
            help=(
                "Unconditionally create the USA timeline "
                + "video (even when there's no new data)"
            ),
        )

        interactive_group = parser.add_mutually_exclusive_group()
        interactive_group.add_argument(
            "--no-interactive",
            action="store_true",
            help="Don't create the interactive USA timeline",
        )
        interactive_group.add_argument(
            "--force-interactive",
            action="store_true",
            help=(
                "Unconditionally create the USA interactive timeline "
                + "(even when there's no new data)"
            ),
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

        # If `--help`, this will exit and we can avoid importing everything below
        args = parser.parse_args()


from typing import Union  # noqa E402

import pandas as pd  # noqa E402
from IPython.display import display  # noqa F401

import read_in_data  # noqa E402
from constants import (  # noqa E402
    CaseInfo,
    CaseTypes,
    Counting,
    Columns,
    DiseaseStage,
    InfoField,
    Locations,
    Paths,
    Select,
)
from typing_extensions import Literal  # noqa E402

DATA_TABLE_PATH = Paths.DATA / "data_table.csv"


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
    df: pd.DataFrame,
    n: int = None,
    count: Union[Counting, Literal[Select.DEFAULT]] = Select.DEFAULT,
    *,
    include_china: bool
) -> pd.DataFrame:
    """Get the top n countries in the world, optionally dropping China from the list

    :param df: Dataframe containing data on all locations
    :type df: pd.DataFrame
    :param n: How many countries to keep. If include_china is False, n-1 countries will
    be kept. If None (default), all countries will be kept.
    :type n: int
    :param include_china: Whether to include China
    :type include_china: bool
    :param count: Which count method to use when sorting, defaults to None (total cases)
    :type count: Counting, optional
    :return: The input dataframe filtered to just three locations: whole world, China,
    and whole world minus China
    :rtype: pd.DataFrame
    """

    Counting.verify(count, allow_select=True)
    if count is Select.DEFAULT:
        count = Counting.TOTAL_CASES

    exclude_locations = set([Locations.WORLD, Locations.WORLD_MINUS_CHINA])
    if not include_china:
        exclude_locations.add(Locations.CHINA)

    df = df[
        (~df[Columns.IS_STATE]) & (~df[Columns.LOCATION_NAME].isin(exclude_locations))
    ]

    if n is None:
        return df

    return keep_only_n_largest_locations(df, n, count)


def get_usa_states_df(
    df: pd.DataFrame,
    n: int = None,
    count: Union[Counting, Literal[Select.DEFAULT]] = Select.DEFAULT,
) -> pd.DataFrame:
    """Get the top n US states from the dataframe

    :param df: Dataframe containing data for all locations
    :type df: pd.DataFrame
    :param n: How many states to keep. If None (default), all states will be kept.
    :type n: int
    :param count: Whether to count by total cases or per capita, by default None,
    defaults to None (total cases)
    :type count: Counting, optional
    :return: The dataframe filtered to the top n US states
    :rtype: pd.DataFrame
    """

    Counting.verify(count, allow_select=True)
    if count is Select.DEFAULT:
        count = Counting.TOTAL_CASES

    df = df[(df[Columns.COUNTRY] == Locations.USA) & df[Columns.IS_STATE]]

    if n is None:
        return df

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

    # Normalize times by labeling all of today's data with its future label, 00:00
    # tomorrow (as that's the timestamp marking the end of the 24-hour data collection
    # period). No need to adjust data not from today; it's already been adjusted and is
    # labeled with the date whose 00:00 marked the end of data collection (i.e., data
    # generated on Mar 20 is labeled Mar 21).
    normalized_dates = df[Columns.DATE].dt.normalize()
    is_at_midnight = df[Columns.DATE] == normalized_dates
    df.loc[~is_at_midnight, Columns.DATE] = normalized_dates[
        ~is_at_midnight
    ] + pd.Timedelta(days=1)
    df[Columns.DATE] = df[Columns.DATE].dt.strftime(r"%Y-%m-%d")

    df = df.drop(
        columns=[
            Columns.IS_STATE,
            Columns.LOCATION_NAME,
            Columns.OUTBREAK_START_DATE_COL,
            Columns.DAYS_SINCE_OUTBREAK,
            Columns.POPULATION,
            Columns.STAGE,
            Columns.COUNT_TYPE,
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

    # save_path = Paths.DATA / "data_table.csv"
    # df.to_csv(save_path, index=False)
    # print(f"Saved data to {save_path.relative_to(Paths.ROOT)}")

    return df


def save_as_data_table(df: pd.DataFrame, dest=None):
    if dest is None:
        dest = DATA_TABLE_PATH

    data_table = create_data_table(df)
    data_table.to_csv(dest, index=False)


def read_data_table(*, as_text=False) -> Union[pd.DataFrame, str, None]:
    try:
        if as_text:
            with open(DATA_TABLE_PATH) as f:
                return f.read()

        return pd.read_csv(DATA_TABLE_PATH)
    except FileNotFoundError:
        return None


def is_new_data(df: pd.DataFrame) -> bool:
    """Check whether the df is materially different from the data we have saved

    When downloading new data, this function checks whether the new data is materially
    different from the existing data. If the "new" data was loaded from disk, this
    function should return False.
    Two dataframes are equal (up to dtypes) iff the CSVs they'd produce are the same.
    This is easier than comparing actual df values because of the way pandas converts
    values when reading from csv (it's hard to 100% round trip data, e.g., is a blank
    cell NaN or an empty string?)
    Also this is probably faster than DataFrame.equals() because no parsing happens.

    :param df: The newly downloaded data
    :type df: pd.DataFrame
    :return: True if the data is different from what's saved on disk, False if it's the
    same
    :rtype: bool
    """
    import io

    with io.StringIO() as s:
        save_as_data_table(df, s)
        new_data = s.getvalue()

    existing_data = read_data_table(as_text=True)

    # for li, (el, nl) in enumerate(
    #     zip(existing_data.splitlines(), new_data.splitlines())
    # ):
    #     if el != nl:
    #         print(li)
    #         print(el)
    #         print(nl)
    #         print()

    return new_data != existing_data


def _do_static_plots(df: pd.DataFrame):
    from plot_line_graphs import plot

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


def _do_timeline(df: pd.DataFrame):
    from plot_timeline import plot_usa_daybyday_case_diffs, make_video

    plot_usa_daybyday_case_diffs(
        get_usa_states_df(df), stage=Select.ALL, count=Select.ALL
    )
    make_video(0.9)


def _do_interactive(df: pd.DataFrame):
    from plot_timeline_interactive import (
        make_usa_daybyday_diff_interactive_timeline,
        make_usa_daybyday_total_interactive_timeline,
        make_countries_daybyday_diff_interactive_timeline,
        make_countries_daybyday_total_interactive_timeline,
    )

    make_usa_daybyday_diff_interactive_timeline(get_usa_states_df(df))
    make_usa_daybyday_total_interactive_timeline(get_usa_states_df(df))

    make_countries_daybyday_diff_interactive_timeline(
        get_countries_df(df, include_china=True)
    )
    make_countries_daybyday_total_interactive_timeline(
        get_countries_df(df, include_china=True)
    )

    print("Created interactive")


def main(namespace: argparse.Namespace = None, **kwargs) -> pd.DataFrame:
    """Run everything, optionally performing tasks based on flags in `namespace`

    Entry point to the rest of the functions. Takes an `argparse.Namespace` that
    contains information on which tasks will be performed and has flags governing those
    tasks' behavior. If `None`, sets reasonable defaults.

    :param namespace: The namespace generated by `argparse`; defaults to None (default
    behavior will be used)
    :type namespace: argparse.Namespace, optional
    :param **kwargs: Key-value pairs used to update the namespace. Useful for ad-hoc
    overriding of namespace values (especially defaults).
    :type **kwargs: dict
    :return: The dataframe used to create the plots
    :rtype: pd.DataFrame
    """

    if namespace is None:
        namespace = argparse.Namespace()
        namespace.refresh = False
        namespace.create_data_table = False
        namespace.no_graphs = False
        namespace.force_graphs = False
        namespace.no_timeline = False
        namespace.force_timeline = False
        namespace.no_interactive = False
        namespace.force_interactive = False

    for k, v in kwargs.items():
        setattr(namespace, k, v)

    df = get_df(refresh_local_data=namespace.refresh)

    if not is_new_data(df):
        print("No new data; old data table is up to date")

        if namespace.force_graphs:
            _do_static_plots(df)

        if namespace.force_timeline:
            _do_timeline(df)

        if namespace.force_interactive:
            _do_interactive(df)
    else:
        print("Got new data")
        if namespace.create_data_table:
            save_as_data_table(df)

        if not namespace.no_graphs:
            _do_static_plots(df)

        if not namespace.no_timeline:
            _do_timeline(df)

        if not namespace.no_interactive:
            _do_interactive(df)

    return df


if __name__ == "__main__" and IN_A_TERMINAL:
    df = main(args)

# A little hack -- an ipython cell that will run in an interactive window but not when
# running this from a terminal
if False:
    pass
    # %%
    df = main(refresh=False)
