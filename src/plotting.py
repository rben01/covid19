import enum
import itertools
from datetime import datetime, timezone
from typing import List, Mapping, Set, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import display  # noqa F401
from matplotlib import rcParams
from matplotlib.dates import DateFormatter, DayLocator
from matplotlib.ticker import LogLocator, NullFormatter, ScalarFormatter

from constants import CaseTypes, Columns, Locations, Paths

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
                    # .tail(1).sum() is a trick to get the last value if it exists,
                    # else 0
                    **(
                        g.groupby(Columns.CASE_TYPE)[Columns.CASE_COUNT]
                        .apply(lambda h: h.tail(1).sum())
                        .to_dict()
                    ),
                },
                index=[
                    Columns.LOCATION_NAME,
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
