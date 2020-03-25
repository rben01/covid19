# %%
import enum
import itertools
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Mapping, Tuple, Set

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import display  # noqa F401
from matplotlib import rcParams
from matplotlib.dates import DateFormatter, DayLocator
from matplotlib.ticker import LogLocator, NullFormatter, ScalarFormatter

from constants import CaseTypes, Columns, Locations, Paths

DATA_PATH = Paths.ROOT / "csse_covid_19_data" / "csse_covid_19_time_series"

rcParams["font.family"] = "Arial"
rcParams["font.size"] = 16

# Contains fields used to do per-series configuration when plotting
class ConfigFields(enum.Enum):
    CASE_TYPE = enum.auto()
    DASH_STYLE = enum.auto()
    INCLUDE = enum.auto()

    # https://docs.python.org/3/library/enum.html#omitting-values
    def __repr__(self):
        return "<%s.%s>" % (self.__class__.__name__, self.name)

    @classmethod
    def validate_fields(cls, fields):
        given_fields = set(fields)
        expected_fields = set(cls)
        given_fields: Set[ConfigFields]
        expected_fields: Set[ConfigFields]

        if given_fields == expected_fields:
            return

        missing_fields = list(expected_fields.difference(given_fields))
        unexpected_fields = list(given_fields.difference(expected_fields))

        err_str_components = []
        if missing_fields:
            err_str_components.append(
                f"missing {len(missing_fields)} expected field(s) {missing_fields}"
            )
        if unexpected_fields:
            err_str_components.append(
                f"{len(unexpected_fields)} unexpected field(s) {unexpected_fields}"
            )
        err_str_components.append(f"given {fields}")
        err_str = "; ".join(err_str_components)
        err_str = err_str[0].upper() + err_str[1:]
        raise ValueError(err_str)


def _plot_helper(
    df: pd.DataFrame,
    *,
    style=None,
    palette=None,
    case_type_config_list: List[Mapping],
    plot_size: Tuple[float],
    filename,
    location_heading=None,
):
    fig, ax = plt.subplots(figsize=plot_size, dpi=400, facecolor="white")
    fig: plt.Figure
    ax: plt.Axes

    start_date = df.loc[
        (df[Columns.CASE_TYPE] == CaseTypes.CONFIRMED) & (df[Columns.CASE_COUNT] > 0),
        Columns.DATE,
    ].iloc[0]

    df = df[df[Columns.DATE] >= start_date]

    current_case_counts = (
        df.groupby(Columns.LOCATION_NAME).apply(
            lambda g: pd.Series(
                {
                    Columns.LOCATION_NAME: g.name,
                    # Get last case count of each case type for each location
                    **g.groupby(Columns.CASE_TYPE)[Columns.CASE_COUNT]
                    # .tail(1).sum() is a hack to get the last value if it exists else 0
                    .apply(lambda h: h.tail(1).sum()).to_dict(),
                }
            )
        )
        # Order locations by decreasing current confirmed case count
        # This is used to keep plot legend in sync with the order of lines on the graph
        # so the location with the most current cases is first in the legend and the
        # least is last
        .sort_values(CaseTypes.CONFIRMED, ascending=False)
    )
    current_case_counts[CaseTypes.MORTALITY] = (
        current_case_counts[CaseTypes.DEATHS] / current_case_counts[CaseTypes.CONFIRMED]
    )

    hue_order = current_case_counts[Columns.LOCATION_NAME]

    # Apply default config and validate resulting dicts
    for config_dict in case_type_config_list:
        config_dict.setdefault(ConfigFields.INCLUDE, True)
        ConfigFields.validate_fields(config_dict)

    config_df = pd.DataFrame.from_records(case_type_config_list)
    config_df = config_df[config_df[ConfigFields.INCLUDE]]

    style = style or "default"
    with plt.style.context(style):
        g = sns.lineplot(
            data=df,
            x=Columns.DATE,
            y=Columns.CASE_COUNT,
            hue=Columns.LOCATION_NAME,
            hue_order=hue_order,
            style=Columns.CASE_TYPE,
            style_order=config_df[ConfigFields.CASE_TYPE].tolist(),
            dashes=config_df[ConfigFields.DASH_STYLE].tolist(),
            palette=None,
        )

        # Configure axes and ticks
        # X axis
        ax.xaxis.set_minor_locator(DayLocator())
        ax.xaxis.set_major_formatter(DateFormatter("%b %-d"))
        for tick in ax.get_xticklabels():
            tick.set_rotation(80)
        # Y axis
        ax.set_ylim(bottom=1)
        ax.set_yscale("log", basey=2, nonposy="mask")
        ax.yaxis.set_major_locator(LogLocator(base=2, numticks=1000))
        ax.yaxis.set_major_formatter(ScalarFormatter())
        ax.yaxis.set_minor_locator(
            # 5-2 = 3 minor ticks between each pair of major ticks
            LogLocator(base=2, subs=np.linspace(0.5, 1, 5)[1:-1], numticks=1000)
        )
        ax.yaxis.set_minor_formatter(NullFormatter())

        # Configure plot design
        now_str = datetime.now(timezone.utc).strftime(r"%b %-d, %Y at %H:%M UTC")
        ax.set_title(f"Last updated {now_str}", loc="right")

        for line in g.lines:
            line.set_linewidth(3)
        ax.grid(b=True, which="both", axis="both")

        # Add case counts of the different categories to the legend (next few blocks)
        legend = plt.legend(loc="best", framealpha=0.9)
        sep_str = " / "
        left_str = " ("
        right_str = ")"

        # Add number format to legend title (the first item in the legend)
        legend_fields = [*config_df[ConfigFields.CASE_TYPE], CaseTypes.MORTALITY]
        fmt_str = sep_str.join(legend_fields)
        if location_heading is None:
            location_heading = Columns.LOCATION_NAME

        next(iter(legend.texts)).set_text(
            f"{location_heading}{left_str}{fmt_str}{right_str}"
        )

        # Add case counts to legend labels (first label is title, so skip it)
        case_count_str_cols = [
            current_case_counts[col].map(r"{:,}".format)
            for col in config_df[ConfigFields.CASE_TYPE]
        ]
        case_count_str_cols.append(
            current_case_counts[CaseTypes.MORTALITY].map(r"{0:.2%}".format)
        )
        labels = (
            current_case_counts[Columns.LOCATION_NAME]
            + left_str
            + case_count_str_cols[0].str.cat(case_count_str_cols[1:], sep=sep_str)
            + right_str
        )
        for text, label in zip(itertools.islice(legend.texts, 1, None), labels):
            text.set_text(label)

        # Save
        fig.savefig(Paths.FIGURES / filename, bbox_inches="tight")


def plot_world_and_china(df: pd.DataFrame, *, style=None, start_date=None):
    if start_date is not None:
        df = df[df[Columns.DATE] >= pd.Timestamp(start_date)]

    df = df[
        df[Columns.LOCATION_NAME].isin(
            [Locations.WORLD, Locations.WORLD_MINUS_CHINA, Locations.CHINA]
        )
        & (df[Columns.CASE_TYPE] != CaseTypes.RECOVERED)
    ]

    configs = [
        {ConfigFields.CASE_TYPE: CaseTypes.CONFIRMED, ConfigFields.DASH_STYLE: (1, 0)},
        {ConfigFields.CASE_TYPE: CaseTypes.DEATHS, ConfigFields.DASH_STYLE: (1, 1,)},
    ]

    plot_size = (12, 12)
    savefile_name = "world.png"

    return _plot_helper(
        df,
        style=style,
        case_type_config_list=configs,
        plot_size=plot_size,
        filename=savefile_name,
    )


def plot_regions(
    df: pd.DataFrame, *, style=None, start_date=None, include_recovered=False,
):
    if start_date is not None:
        df = df[df[Columns.DATE] >= pd.Timestamp(start_date)]

    df = df[(include_recovered | (df[Columns.CASE_TYPE] != CaseTypes.RECOVERED))]

    configs = [
        {ConfigFields.CASE_TYPE: CaseTypes.CONFIRMED, ConfigFields.DASH_STYLE: (1, 0)},
        {
            ConfigFields.CASE_TYPE: CaseTypes.RECOVERED,
            ConfigFields.DASH_STYLE: (3, 3, 1, 3),
            ConfigFields.INCLUDE: include_recovered,
        },
        {ConfigFields.CASE_TYPE: CaseTypes.DEATHS, ConfigFields.DASH_STYLE: (1, 1)},
    ]

    plot_size = (12, 12)

    if df[Columns.COUNTRY].iloc[0] == Locations.CHINA:
        savefile_name = "china_provinces.png"
        location_heading = "Province"
    elif df[Columns.IS_STATE].iloc[0]:
        savefile_name = "states.png"
        location_heading = "State"
    else:
        savefile_name = "countries.png"
        location_heading = "Country"

    _plot_helper(
        df,
        style=style,
        case_type_config_list=configs,
        plot_size=plot_size,
        filename=savefile_name,
        location_heading=location_heading,
    )


class DataOrigin(enum.Enum):
    USE_LOCAL_UNCONDITIONALLY = enum.auto()
    USE_LOCAL_IF_EXISTS_ELSE_FETCH_FROM_WEB = enum.auto()
    FETCH_FROM_WEB_UNCONDITIONALLY = enum.auto()

    def should_try_to_use_local(self) -> bool:
        return self in [
            DataOrigin.USE_LOCAL_UNCONDITIONALLY,
            DataOrigin.USE_LOCAL_IF_EXISTS_ELSE_FETCH_FROM_WEB,
        ]


def get_full_dataset(data_origin: DataOrigin) -> pd.DataFrame:
    local_df_path = Paths.DATA / "covid_long_data_all_countries_states_counties.csv"
    if data_origin.should_try_to_use_local():
        try:
            return pd.read_csv(local_df_path, low_memory=False, dtype=str,)
        except FileNotFoundError:
            if data_origin == DataOrigin.USE_LOCAL_UNCONDITIONALLY:
                raise
            return get_full_dataset(DataOrigin.FETCH_FROM_WEB_UNCONDITIONALLY)

    df = pd.read_csv(
        "https://coronadatascraper.com/timeseries-tidy.csv", low_memory=False, dtype=str
    )
    df.to_csv(local_df_path, index=False)
    return df


get_full_dataset(DataOrigin.USE_LOCAL_IF_EXISTS_ELSE_FETCH_FROM_WEB)

# %%


def get_country_cases_df(filepath: Path, *, case_type: str):
    case_type = case_type.title()

    df = pd.read_csv(filepath, dtype=str)
    df: pd.DataFrame
    df = df.melt(
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

    world_df = (
        df.drop(columns=[Columns.LATITUDE, Columns.LONGITUDE])
        .groupby([Columns.DATE, Columns.CASE_TYPE])[Columns.CASE_COUNT]
        .sum()
    )

    china_df = (
        df[df[Columns.COUNTRY] == Locations.CHINA]
        .drop(columns=[Columns.LATITUDE, Columns.LONGITUDE])
        .groupby([Columns.DATE, Columns.CASE_TYPE])[Columns.CASE_COUNT]
        .sum()
    )

    world_minus_china_df = world_df.sub(china_df)

    world_df = world_df.reset_index()
    china_df = china_df.reset_index()
    world_minus_china_df = world_minus_china_df.reset_index()

    world_df[Columns.COUNTRY] = Locations.WORLD
    china_df[Columns.COUNTRY] = Locations.CHINA
    world_minus_china_df[Columns.COUNTRY] = Locations.WORLD_MINUS_CHINA

    df = pd.concat([df, world_df, china_df, world_minus_china_df], axis=0)

    return df


def join_dfs() -> pd.DataFrame:
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

    df = pd.concat(dfs, axis=0)

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

    # Minor cleanup
    df[Columns.COUNTRY] = df[Columns.COUNTRY].replace(
        "Korea, South", Locations.SOUTH_KOREA
    )
    df.loc[
        df[Columns.COUNTRY] == "Georgia", Columns.COUNTRY
    ] = "Georgia (country)"  # not the state

    df[Columns.IS_STATE] = df[Columns.STATE].notna() & (
        df[Columns.STATE] != df[Columns.COUNTRY]
    )
    # Use state as location name for states, else use country name
    df[Columns.LOCATION_NAME] = df[Columns.STATE].fillna(df[Columns.COUNTRY])

    # Hereafter df is sorted by date, which is helpful as it allows using .iloc[-1]
    # to get current (or most recent known) situation per location
    df = df.sort_values([Columns.LOCATION_NAME, Columns.DATE])
    return df


def keep_only_n_largest_locations(df, n):
    def get_n_largest_locations(df, n):
        return (
            df[df[Columns.CASE_TYPE] == CaseTypes.CONFIRMED]
            .groupby(Columns.LOCATION_NAME)
            .apply(lambda g: g[Columns.CASE_COUNT].iloc[-1])
            .nlargest(n)
            .rename(CaseTypes.CONFIRMED)
        )

    def keep_only_above_cutoff(df, cutoff):
        return df.groupby(Columns.LOCATION_NAME).filter(
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


def get_countries_df(df, n):
    df = df[
        (~df[Columns.IS_STATE])
        & (
            ~df[Columns.LOCATION_NAME].isin(
                [Locations.WORLD, Locations.WORLD_MINUS_CHINA, Locations.CHINA]
            )
        )
    ]
    return keep_only_n_largest_locations(df, n)


def get_states_df(df, n):
    df = df[(df[Columns.COUNTRY] == Locations.USA) & df[Columns.IS_STATE]]
    return keep_only_n_largest_locations(df, n)


def get_chinese_provinces_df(df, n):
    df = df[(df[Columns.COUNTRY] == Locations.CHINA) & df[Columns.IS_STATE]]
    return keep_only_n_largest_locations(df, n)


df = join_dfs()

plot_world_and_china(df)
plot_regions(get_countries_df(df, 10))
plot_regions(get_states_df(df, 10))
plot_regions(get_chinese_provinces_df(df, 10))

plt.show()
