# %%
import enum
import itertools
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Mapping, Set, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import display  # noqa F401
from matplotlib import rcParams
from matplotlib.dates import DateFormatter, DayLocator
from matplotlib.ticker import (
    LogLocator,
    MultipleLocator,
    NullFormatter,
    ScalarFormatter,
)

from constants import CASE_THRESHOLD, CaseTypes, Columns, Locations, Paths

FROM_FIXED_DATE_DESC = "from_fixed_date"
FROM_LOCAL_OUTBREAK_START_DESC = "from_local_spread_start"

PLOTTED_CASE_TYPES = [CaseTypes.CONFIRMED, CaseTypes.DEATHS]
START_DATE = "start_date"

rcParams["font.family"] = "Arial"
rcParams["font.size"] = 16

# Contains fields used to do per-series configuration when plotting
class ConfigFields(enum.Enum):
    CASE_TYPE = enum.auto()
    DASH_STYLE = enum.auto()
    INCLUDE = enum.auto()

    # https://docs.python.org/3/library/enum.html#omitting-values
    # Note that the VSCode interactive window has a bug where text between <> is
    # omitted; if you try to print this and are getting empty output, that might be why
    def __repr__(self):
        return "<%s.%s>" % (self.__class__.__name__, self.name)

    @classmethod
    def validate_fields(cls, fields):
        given_fields = set(fields)
        expected_fields = set(cls)  # Magic; Enum is iterable and produces its cases
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


def get_current_case_counts(df: pd.DataFrame) -> pd.DataFrame:
    current_case_counts = (
        df.groupby(Columns.id_cols)
        .apply(
            lambda g: pd.Series(
                {
                    START_DATE: g.loc[
                        g[Columns.CASE_TYPE] == CaseTypes.CONFIRMED, Columns.DATE
                    ].min(),
                    # Get last case count of each case type for current group
                    # .tail(1).sum() is a trick to get the last value if it exists,
                    # else 0
                    **g.groupby(Columns.CASE_TYPE)[Columns.CASE_COUNT]
                    .apply(lambda h: h.tail(1).sum())
                    .to_dict(),
                },
                index=[
                    START_DATE,
                    CaseTypes.CONFIRMED,
                    CaseTypes.DEATHS,
                    CaseTypes.ACTIVE,
                    CaseTypes.RECOVERED,
                ],
            )
        )
        # Order locations by decreasing current confirmed case count
        # This is used to keep plot legend in sync with the order of lines on the graph
        # so the location with the most current cases is first in the legend and the
        # least is last
        .sort_values(CaseTypes.CONFIRMED, ascending=False)
        .reset_index()
    )

    current_case_counts[CaseTypes.MORTALITY] = (
        current_case_counts[CaseTypes.DEATHS] / current_case_counts[CaseTypes.CONFIRMED]
    )

    return current_case_counts


def _plot_helper(
    df: pd.DataFrame,
    *,
    x_axis_col: str,
    style=None,
    palette=None,
    case_type_config_list: List[Mapping],
    plot_size: Tuple[float] = None,
    savefile_name: Union[Path, str],
    location_heading: str = None,
):
    df = df[df[Columns.CASE_TYPE].isin(PLOTTED_CASE_TYPES)]

    if plot_size is None:
        plot_size = (12, 12)
    fig, ax = plt.subplots(figsize=plot_size, dpi=100, facecolor="white")
    fig: plt.Figure
    ax: plt.Axes

    current_case_counts = get_current_case_counts(df)
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
            x=x_axis_col,
            y=Columns.CASE_COUNT,
            hue=Columns.LOCATION_NAME,
            hue_order=hue_order,
            style=Columns.CASE_TYPE,
            style_order=config_df[ConfigFields.CASE_TYPE].tolist(),
            dashes=config_df[ConfigFields.DASH_STYLE].tolist(),
            palette=palette,
        )

        # Configure axes and ticks
        # X axis
        if x_axis_col == Columns.DATE:  # Update this if other date columns appear
            ax.xaxis.set_major_formatter(DateFormatter(r"%b %-d"))
            ax.xaxis.set_minor_locator(DayLocator())
            for tick in ax.get_xticklabels():
                tick.set_rotation(80)
        elif x_axis_col == Columns.DAYS_SINCE_OUTBREAK:
            ax.xaxis.set_major_locator(MultipleLocator(5))
            ax.xaxis.set_minor_locator(MultipleLocator(1))
            ax.set_xlabel(f"Days Since Reaching {CASE_THRESHOLD} Cases")

        # Y axis
        ax.set_yscale("log", basey=2, nonposy="mask")
        ax.set_ylim(bottom=1)
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
        ax.grid(True, which="minor", axis="both", color="0.9")
        ax.grid(True, which="major", axis="both", color="0.75")

        # Add case counts of the different categories to the legend (next few blocks)
        legend = plt.legend(loc="best", framealpha=0.9)
        sep_str = " / "
        left_str = " ("
        right_str = ")"

        # Add number format to legend title (the first item in the legend)
        legend_fields = list(config_df[ConfigFields.CASE_TYPE])
        if x_axis_col == Columns.DATE:
            legend_fields.append(CaseTypes.MORTALITY)
        elif x_axis_col == Columns.DAYS_SINCE_OUTBREAK:
            legend_fields.append("Start Date")

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
        if x_axis_col == Columns.DATE:
            case_count_str_cols.append(
                current_case_counts[CaseTypes.MORTALITY].map(r"{0:.2%}".format)
            )
        elif x_axis_col == Columns.DAYS_SINCE_OUTBREAK:
            case_count_str_cols.append(
                current_case_counts[START_DATE].dt.strftime(r"%b %-d")
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
        fig.savefig(Paths.FIGURES / savefile_name, bbox_inches="tight")


def remove_empty_leading_dates(df: pd.DataFrame) -> pd.DataFrame:
    start_date = df.loc[
        (df[Columns.CASE_TYPE] == CaseTypes.CONFIRMED) & (df[Columns.CASE_COUNT] > 0),
        Columns.DATE,
    ].iloc[0]

    df = df[df[Columns.DATE] >= start_date]
    return df


def get_savefile_name_and_location_heading(
    df: pd.DataFrame, description: str
) -> Tuple[str, str]:

    if Locations.WORLD in df[Columns.COUNTRY].values:
        savefile_basename = "world"
        location_heading = None
    elif df[Columns.COUNTRY].iloc[0] == Locations.CHINA:
        savefile_basename = "china_provinces"
        location_heading = "Province"
    elif df[Columns.IS_STATE].iloc[0]:
        savefile_basename = "states"
        location_heading = "State"
    elif (~df[Columns.IS_STATE]).all():
        if (df[Columns.COUNTRY] == Locations.CHINA).any():
            savefile_basename = "countries_w_china"
        else:
            savefile_basename = "countries_wo_china"

        location_heading = "Country"
    else:
        raise ValueError("DataFrame contents not understood")

    savefile_name = f"{savefile_basename}_{description}.png"
    return savefile_name, location_heading


def get_palette_for_df_excluding_china(
    df: pd.DataFrame,
) -> List[Tuple[float, float, float]]:
    # We'll need to find China in the current case counts, then remove its position
    # from the default color palette
    current_case_counts = get_current_case_counts(df)
    china_pos = current_case_counts[Columns.COUNTRY].tolist().index(Locations.CHINA)

    palette = sns.color_palette()
    palette = [*palette[:china_pos], *palette[china_pos + 1 :]]
    return palette


def plot_cases_from_fixed_date(
    df: pd.DataFrame,
    *,
    df_with_china: pd.DataFrame = None,
    style=None,
    start_date=None,
):
    if start_date is not None:
        df = df[df[Columns.DATE] >= pd.Timestamp(start_date)]

    df = remove_empty_leading_dates(df)

    configs = [
        {ConfigFields.CASE_TYPE: CaseTypes.CONFIRMED, ConfigFields.DASH_STYLE: (1, 0)},
        {ConfigFields.CASE_TYPE: CaseTypes.DEATHS, ConfigFields.DASH_STYLE: (1, 1)},
    ]

    savefile_name, location_heading = get_savefile_name_and_location_heading(
        df, FROM_FIXED_DATE_DESC
    )

    if df_with_china is None:
        palette = None
    else:
        palette = get_palette_for_df_excluding_china(df_with_china)

    _plot_helper(
        df,
        x_axis_col=Columns.DATE,
        style=style,
        case_type_config_list=configs,
        savefile_name=savefile_name,
        location_heading=location_heading,
        palette=palette,
    )


def plot_cases_by_days_since_first_widespread_locally(
    df: pd.DataFrame, *, df_with_china: pd.DataFrame = None, style=None
):
    configs = [
        {ConfigFields.CASE_TYPE: CaseTypes.CONFIRMED, ConfigFields.DASH_STYLE: (1, 0)},
        {ConfigFields.CASE_TYPE: CaseTypes.DEATHS, ConfigFields.DASH_STYLE: (1, 1)},
    ]

    savefile_name, location_heading = get_savefile_name_and_location_heading(
        df, FROM_LOCAL_OUTBREAK_START_DESC
    )

    df = df[df[Columns.DAYS_SINCE_OUTBREAK] >= -1]

    if df_with_china is None:
        palette = None
    else:
        palette = get_palette_for_df_excluding_china(df_with_china)

    _plot_helper(
        df,
        x_axis_col=Columns.DAYS_SINCE_OUTBREAK,
        style=style,
        case_type_config_list=configs,
        savefile_name=savefile_name,
        location_heading=location_heading,
        palette=palette,
    )
