# %%
import enum
import itertools
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Mapping, Set, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import display  # noqa F401
from matplotlib import rcParams
from matplotlib.dates import DateFormatter, DayLocator
from matplotlib.ticker import LogLocator, NullFormatter, ScalarFormatter

from constants import USA_STATE_CODES, CaseTypes, Columns, Locations, Paths

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


class SaveFormats(enum.Enum):
    CSV = ".csv"
    PARQUET = ".parquet"

    def path_with_fmt_suffix(self, path: Path) -> Path:
        return path.with_suffix(self.value)

    def read(self, path, *, from_web) -> pd.DataFrame:
        if self == SaveFormats.CSV:
            df = pd.read_csv(path, low_memory=False, dtype="string")
            df: pd.DataFrame

            if from_web:
                df = df.rename(
                    columns={
                        "type": Columns.CASE_TYPE,
                        "value": Columns.CASE_COUNT,
                        "country": Columns.THREE_LETTER_COUNTRY_CODE,
                        "state": Columns.TWO_LETTER_STATE_CODE,
                    }
                ).rename(columns=str.title)

                df[Columns.STATE] = df.merge(
                    pd.read_csv(
                        Paths.DATA / "usa_state_abbreviations.csv", dtype="string"
                    ),
                    how="left",
                    left_on=Columns.TWO_LETTER_STATE_CODE,
                    right_on="Abbreviation:",
                )["US State:"]
                df[Columns.STATE] = df[Columns.STATE].fillna(
                    df[Columns.TWO_LETTER_STATE_CODE]
                )

                df[Columns.COUNTRY] = df.merge(
                    pd.read_csv(Paths.DATA / "country_codes.csv", dtype="string"),
                    how="left",
                    left_on=Columns.THREE_LETTER_COUNTRY_CODE,
                    right_on="A3 (UN)",
                )["COUNTRY"]
                df[Columns.COUNTRY] = df[Columns.COUNTRY].fillna(
                    df[Columns.THREE_LETTER_COUNTRY_CODE]
                )
                col_order = df.columns.tolist()
                country_col_index = (
                    col_order.index(Columns.THREE_LETTER_COUNTRY_CODE) + 1
                )
                # Place state and country (currently last columns) after country code
                col_order = [
                    *col_order[:country_col_index],
                    Columns.STATE,
                    Columns.COUNTRY,
                    *col_order[country_col_index:-2],
                ]
                df = df.reindex(col_order, axis=1)

                df[Columns.CASE_TYPE] = df[Columns.CASE_TYPE].map(
                    lambda s: s[0].upper() + s[1:]
                )

            df[Columns.DATE] = pd.to_datetime(df[Columns.DATE])
            df[Columns.CASE_COUNT] = df[Columns.CASE_COUNT].fillna("0").astype(float)

            # As much as these should be categorical, for whatever reason groupby on
            # categorical data has absolutely terrible performance
            # Somehow groupby on ordinary strings is much better
            # At some point I'll revisit this and see if the performance is fixed
            for col in [
                Columns.CITY,
                Columns.COUNTY_NOT_COUNTRY,
                Columns.STATE,
                Columns.THREE_LETTER_COUNTRY_CODE,
                Columns.COUNTRY,
                Columns.URL,
                Columns.LATITUDE,
                Columns.LONGITUDE,
                Columns.CASE_TYPE,
            ]:
                pass
                # df[col] = df[col].astype("category")

            return df
        elif self == SaveFormats.PARQUET:
            df = pd.read_parquet(path)
            # parquet seems to store pd.StringType() cols as orindary str
            for col in Columns.string_cols:
                try:
                    df[col] = df[col].astype("string")
                except KeyError:
                    continue
            return df
        else:
            raise ValueError(f"Unhandled case {self} when reading")

    def save(self, df: pd.DataFrame, path: Path):
        if self == SaveFormats.CSV:
            df.to_csv(path, index=False)
        elif self == SaveFormats.PARQUET:
            df.to_parquet(path, index=False, compression="brotli")
        else:
            raise ValueError(f"Unhandled case {self} when writing")


def get_full_dataset(data_origin: DataOrigin, *, fmt: SaveFormats) -> pd.DataFrame:

    local_data_path = fmt.path_with_fmt_suffix(
        Paths.DATA / "covid_long_data_all_countries_states_counties"
    )
    if data_origin.should_try_to_use_local():
        try:
            df = fmt.read(local_data_path, from_web=False)
        except (FileNotFoundError, IOError):
            if data_origin == DataOrigin.USE_LOCAL_UNCONDITIONALLY:
                raise
            return get_full_dataset(DataOrigin.FETCH_FROM_WEB_UNCONDITIONALLY, fmt=fmt)

    else:
        df = SaveFormats.CSV.read(
            "https://coronadatascraper.com/timeseries-tidy.csv", from_web=True
        )
        fmt.save(df, local_data_path)

    return df


def remove_extraneous_rows(df: pd.DataFrame) -> pd.DataFrame:
    # For some reason USA is listed twice, once under country code 'US' and once
    # under 'USA'. 'US' is garbage data so remove it
    df = df[df[Columns.THREE_LETTER_COUNTRY_CODE] != "US"]

    # Cache isna() calculations
    is_null = {
        col: df[col].isna()
        for col in [Columns.CITY, Columns.COUNTY_NOT_COUNTRY, Columns.STATE]
    }
    df = df[
        (
            # For most countries, only keep country-level data
            (~df[Columns.COUNTRY].isin([Locations.USA, Locations.CHINA]))
            & is_null[Columns.CITY]
            & is_null[Columns.COUNTY_NOT_COUNTRY]
            & is_null[Columns.STATE]
        )
        | (  # For China, keep only province-level data
            # (State and province are the same column)
            (df[Columns.COUNTRY] == Locations.CHINA)
            & (~is_null[Columns.STATE])
        )
        | (
            # For USA, keep only state-level data, excluding territories like Guam
            (df[Columns.COUNTRY] == Locations.USA)
            & is_null[Columns.CITY]
            & is_null[Columns.COUNTY_NOT_COUNTRY]
            & df[Columns.TWO_LETTER_STATE_CODE].isin(USA_STATE_CODES)
        )
    ]

    # We don't need these statistics
    df = df[~df[Columns.CASE_TYPE].isin([CaseTypes.GROWTH_FACTOR, CaseTypes.TESTED])]

    return df


def append_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    groupby_cols = [Columns.DATE, Columns.CASE_TYPE]

    world_case_counts = df.groupby(groupby_cols)[Columns.CASE_COUNT].sum()

    china_case_counts = (
        df[df[Columns.COUNTRY] == Locations.CHINA]
        .groupby(groupby_cols)[Columns.CASE_COUNT]
        .sum()
    )

    usa_case_counts = (
        df[df[Columns.COUNTRY] == Locations.USA]
        .groupby(groupby_cols)[Columns.CASE_COUNT]
        .sum()
    )

    world_minus_china_case_counts = world_case_counts.sub(china_case_counts)
    world_minus_china_case_counts

    dfs = [df]
    for country, case_count_series in {
        Locations.WORLD: world_case_counts,
        Locations.CHINA: china_case_counts,
        Locations.USA: usa_case_counts,
        Locations.WORLD_MINUS_CHINA: world_minus_china_case_counts,
    }.items():
        case_count_df = case_count_series.reset_index()

        # I assume it's a problem with groupby not supporting StringDType indices
        case_count_df[Columns.CASE_TYPE] = case_count_df[Columns.CASE_TYPE].astype(
            "string"
        )

        case_count_df[Columns.COUNTRY] = country
        case_count_df[Columns.COUNTRY] = case_count_df[Columns.COUNTRY].astype("string")

        # case_count_df now has four columns: country, date, case type, count
        for col in [
            Columns.CITY,
            Columns.COUNTY_NOT_COUNTRY,
            Columns.TWO_LETTER_STATE_CODE,
            Columns.STATE,
            Columns.THREE_LETTER_COUNTRY_CODE,
            Columns.URL,
            Columns.POPULATION,
            Columns.LATITUDE,
            Columns.LONGITUDE,
        ]:
            case_count_df[col] = pd.NA
            case_count_df[col] = case_count_df[col].astype("string")

        dfs.append(case_count_df)

    return pd.concat(dfs, axis=0, sort=False)


def assign_location_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[Columns.COUNTRY] = (
        df[Columns.COUNTRY]
        .replace(
            {
                "Iran, Islamic Republic of": Locations.IRAN,
                "Korea, Republic of": Locations.SOUTH_KOREA,
                "Georgia": "Georgia (country)",
                "Viet Nam": "Vietnam",
                "XKX": "Kosovo",
            }
        )
        .astype("string")
    )
    df[Columns.IS_STATE] = df[Columns.STATE].notna()
    df[Columns.LOCATION_NAME] = df[Columns.STATE].fillna(df[Columns.COUNTRY])
    return df


def clean_up(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Fill NAs for groupby purposes
    for col in Columns.string_cols:
        df[col] = df[col].fillna("")

    # Hereafter df is sorted by date, which is helpful as it allows using .iloc[-1]
    # to get current (or most recent known) situation per location
    df = df.sort_values(
        [Columns.LOCATION_NAME, Columns.DATE, Columns.CASE_TYPE], ascending=True
    )

    return df


def get_df() -> pd.DataFrame:
    df = get_full_dataset(
        DataOrigin.USE_LOCAL_IF_EXISTS_ELSE_FETCH_FROM_WEB, fmt=SaveFormats.PARQUET
    )
    df = remove_extraneous_rows(df)
    df = append_aggregates(df)
    df = assign_location_names(df)
    df = clean_up(df)
    return df


def convert_to_days_since_outbreak(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    pass


def keep_only_n_largest_locations(df: pd.DataFrame, n: int) -> pd.DataFrame:
    def get_n_largest_locations(df: pd.DataFrame, n: int) -> pd.Series:
        return (
            df[df[Columns.CASE_TYPE] == CaseTypes.CONFIRMED]
            .groupby([Columns.LOCATION_NAME, Columns.COUNTRY, Columns.STATE])
            .apply(lambda g: g[Columns.CASE_COUNT].iloc[-1])
            .nlargest(n)
            .rename(CaseTypes.CONFIRMED)
        )

    def keep_only_above_cutoff(df: pd.DataFrame, cutoff: float) -> pd.DataFrame:
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


def get_chinese_provinces_df(df: pd.DataFrame, n: int) -> pd.DataFrame:
    df = df[(df[Columns.COUNTRY] == Locations.CHINA) & df[Columns.IS_STATE]]
    return keep_only_n_largest_locations(df, n)


df = get_df()

plot_world_and_china(df)
plot_regions(get_countries_df(df, 10))
plot_regions(get_usa_states_df(df, 10))
plot_regions(get_chinese_provinces_df(df, 10))

plt.show()


# %%
