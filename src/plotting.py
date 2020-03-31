# %%
import enum
import itertools
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Mapping, Set, Tuple

import matplotlib.pyplot as plt

# import matplotlib
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

from constants import CaseGroup, CaseTypes, Columns, Locations, Paths, Thresholds

FROM_FIXED_DATE_DESC = "from_fixed_date"
FROM_LOCAL_OUTBREAK_START_DESC = "from_local_spread_start"

START_DATE = "Start_Date_"
COLOR = "Color_"

rcParams.update({"font.family": "sans-serif", "font.size": 12})


SingleColor = Tuple[float, float, float]
ColorPalette = List[SingleColor]
LocationColorMapping = pd.DataFrame


class Style:
    class Dash:
        PRIMARY = (1, 0)
        SECONDARY = (1, 1)


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


def get_current_case_data(
    df: pd.DataFrame, count_type: CaseGroup.CountType
) -> pd.DataFrame:
    def get_group_stats(g: pd.DataFrame) -> pd.Series:
        data_dict = {
            START_DATE: g[Columns.DATE].min(),
            # Get last case count of each case type for current group
            # .tail(1).sum() is a trick to get the last value if it exists,
            # else 0 (remember, this is sorted by date)
            **g.groupby(Columns.CASE_TYPE)[Columns.CASE_COUNT]
            .apply(lambda h: h.tail(1).sum())
            .to_dict(),
        }

        return pd.Series(data_dict, index=[START_DATE, *CaseTypes.get_case_types()],)

    current_case_counts = (
        df.groupby(Columns.id_cols)
        .apply(get_group_stats)
        # Order locations by decreasing current confirmed case count
        # This is used to keep plot legend in sync with the order of lines on the graph
        # so the location with the most current cases is first in the legend and the
        # least is last
        .sort_values(
            CaseTypes.get_case_types(
                stage=CaseGroup.Stage.CONFIRMED, count_type=count_type
            ),
            ascending=False,
        )
        .reset_index()
    )

    current_case_counts[CaseTypes.MORTALITY] = (
        current_case_counts[
            CaseTypes.get_case_types(stage=CaseGroup.Stage.DEATH, count_type=count_type)
        ]
        / current_case_counts[
            CaseTypes.get_case_types(
                stage=CaseGroup.Stage.CONFIRMED, count_type=count_type
            )
        ]
    )

    return current_case_counts


def _plot_helper(
    df: pd.DataFrame,
    *,
    x_axis_col: str,
    count_type: CaseGroup.CountType,
    style=None,
    color_mapping: LocationColorMapping = None,
    case_type_config_list: List[Mapping],
    plot_size: Tuple[float] = None,
    savefile_path: Path,
    location_heading: str = None,
) -> List[Tuple[plt.Figure, plt.Axes]]:

    SORTED_POSITION = "Sorted_Position_"

    figs_and_axes = []

    if plot_size is None:
        plot_size = (10, 10)

    fig, ax = plt.subplots(figsize=(8, 8), dpi=200, facecolor="white")
    fig: plt.Figure
    ax: plt.Axes

    current_case_counts = get_current_case_data(df, count_type)

    df = df[df[Columns.CASE_TYPE].isin(CaseTypes.get_case_types(count_type=count_type))]

    # Filter and sort color mapping correctly so that colors 1. are assigned to the
    # same locations across graphs (for continuity) and 2. are placed correctly in the
    # legend (for correctness)
    color_mapping = color_mapping.copy()
    color_mapping = color_mapping[
        color_mapping[Columns.LOCATION_NAME].isin(
            current_case_counts[Columns.LOCATION_NAME]
        )
    ]
    color_mapping[SORTED_POSITION] = color_mapping[Columns.LOCATION_NAME].map(
        current_case_counts[Columns.LOCATION_NAME].tolist().index
    )
    color_mapping = color_mapping.sort_values(SORTED_POSITION)

    # Apply default config and validate resulting dicts
    for config_dict in case_type_config_list:
        config_dict.setdefault(ConfigFields.INCLUDE, True)
        ConfigFields.validate_fields(config_dict)

    config_df = pd.DataFrame.from_records(case_type_config_list)
    config_df = config_df[config_df[ConfigFields.INCLUDE]]

    with plt.style.context(style or "default"):
        g = sns.lineplot(
            data=df,
            x=x_axis_col,
            y=Columns.CASE_COUNT,
            hue=Columns.LOCATION_NAME,
            hue_order=color_mapping[Columns.LOCATION_NAME].tolist(),
            style=Columns.CASE_TYPE,
            style_order=config_df[ConfigFields.CASE_TYPE].tolist(),
            dashes=config_df[ConfigFields.DASH_STYLE].tolist(),
            palette=color_mapping[COLOR].tolist(),
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
            ax.set_xlabel(f"Days Since Reaching {Thresholds.CASE_COUNT} Cases")
        else:
            raise ValueError(f"Unexpected {x_axis_col=}")

        # Y axis
        ax.set_ylabel(
            CaseTypes.get_case_types(
                stage=CaseGroup.Stage.CONFIRMED, count_type=count_type
            )
        )
        if count_type == CaseGroup.CountType.ABSOLUTE:
            ax.set_yscale("log", basey=2, nonposy="mask")
            ax.set_ylim(bottom=0.9)
            ax.yaxis.set_major_locator(LogLocator(base=2, numticks=1000))
            ax.yaxis.set_major_formatter(ScalarFormatter())
            ax.yaxis.set_minor_locator(
                # 5 ticks is one full "cycle": n, 1.25n, 1.5n, 1.75n, 2n
                # Hence 5-2 minor ticks between each pair of majors (omit endpoints)
                LogLocator(base=2, subs=np.linspace(0.5, 1, 5)[1:-1], numticks=1000)
            )
            ax.yaxis.set_minor_formatter(NullFormatter())
        elif count_type == CaseGroup.CountType.PER_CAPITA:
            ax.set_yscale("log", basey=10, nonposy="mask")
            # No need to set minor ticks; 8 is the default number, which makes one cycle
            # n, 2n, 3n, ..., 8n, 9n, 10n
        else:
            raise ValueError(f"Unexpected y_axis_col {count_type}")

        # Configure plot design
        now_str = datetime.now(timezone.utc).strftime(r"%b %-d, %Y at %H:%M UTC")
        ax.set_title(f"Last updated {now_str}", loc="right", fontsize="small")

        for line in g.lines:
            line.set_linewidth(2)
        ax.grid(True, which="minor", axis="both", color="0.9")
        ax.grid(True, which="major", axis="both", color="0.75")

        # Add case counts of the different categories to the legend (next few blocks)
        legend = plt.legend(loc="best", framealpha=0.9, fontsize="small")
        sep_str = " / "
        left_str = " ("
        right_str = ")"

        # Add legend format to legend title (the first item in the legend)
        include_mortality = (
            x_axis_col == Columns.DATE and count_type == CaseGroup.CountType.ABSOLUTE
        )
        include_start_date = (not include_mortality) and (
            x_axis_col == Columns.DAYS_SINCE_OUTBREAK
        )
        legend_fields = list(config_df[ConfigFields.CASE_TYPE])

        if include_mortality:
            legend_fields.append(CaseTypes.MORTALITY)

        if include_start_date:
            legend_fields.append("Start Date")

        fmt_str = sep_str.join(legend_fields)

        if location_heading is None:
            location_heading = Columns.LOCATION_NAME

        next(iter(legend.texts)).set_text(
            f"{location_heading}{left_str}{fmt_str}{right_str}"
        )

        # Add (formatted) current data to legend labels
        if count_type == CaseGroup.CountType.ABSOLUTE:
            float_format_func = r"{:,.0f}".format
        else:
            float_format_func = r"{:.2e}".format

        case_count_str_cols = [
            current_case_counts[col].map(float_format_func)
            for col in config_df[ConfigFields.CASE_TYPE]
        ]

        if include_mortality:
            case_count_str_cols.append(
                current_case_counts[CaseTypes.MORTALITY].map(r"{0:.2%}".format)
            )

        if include_start_date:
            case_count_str_cols.append(
                current_case_counts[START_DATE].dt.strftime(r"%b %-d")
            )

        labels = (
            current_case_counts[Columns.LOCATION_NAME]
            + left_str
            + case_count_str_cols[0].str.cat(case_count_str_cols[1:], sep=sep_str)
            + right_str
        )

        #  First label is title, so skip it
        for text, label in zip(itertools.islice(legend.texts, 1, None), labels):
            text.set_text(label)

        # If using this for a date-like x axis, use this (leaving commented code because
        # I foresee myself needing it eventually)
        # x_max = pd.Timestamp(matplotlib.dates.num2epoch(ax.get_xlim()[1]), unit="s")

        # Add doubling time lines
        if x_axis_col == Columns.DAYS_SINCE_OUTBREAK:
            # Getting min x,y bounds of lines is easy
            x_min = 0
            if count_type == CaseGroup.CountType.ABSOLUTE:
                y_min = Thresholds.CASE_COUNT
            else:
                y_min = Thresholds.CASES_PER_CAPITA

            # Getting max x,y bounds is tougher due to needing to use the maximum
            # extent of the graph area
            # We try to use ax_y_max by default, and if that leads to too long a line
            # (sticking out through the right side of the graph) then we use ax_x_max
            # instead
            ax_x_min, ax_x_max = ax.get_xlim()
            ax_y_min, ax_y_max = ax.get_ylim()

            visual_ax_x_bounds = ax_x_max - ax_x_min
            visual_ax_y_bounds = np.log2(ax_y_max / ax_y_min)

            doubling_times = [1, 2, 3, 4]  # days
            for dt in doubling_times:
                # Simple math: if y_max = y_min * 2**((x_max-x_min)/dt), then...
                x_max = x_min + dt * np.log2(ax_y_max / y_min)
                if x_max > ax_x_max:
                    line_extent = 0.91
                    x_max = ax_x_max
                    y_max = y_min * 2 ** ((ax_x_max - x_min) / dt)
                else:
                    line_extent = 0.83
                    y_max = ax_y_max

                ax.plot([x_min, x_max], [y_min, y_max], color="0.3", dashes=(1, 2))

                # Annotate lines with assocated doubling times
                annot_loc = np.array(
                    [
                        x_min + line_extent * (x_max - x_min),
                        # The +0.02 is to add a bit of space between text and line
                        y_min * (y_max / y_min) ** (line_extent + 0.02),
                    ]
                )

                # Rotate plotted text
                visual_dy = (np.log2(y_max) - np.log2(y_min)) / visual_ax_y_bounds
                visual_dx = (x_max - x_min) / visual_ax_x_bounds
                visual_line_slope = visual_dy / visual_dx
                text_angle = np.arctan(visual_line_slope) * 180 / np.pi

                annot_text = f"{dt} " + ("days" if dt > 1 else "day")
                text_props = {
                    "bbox": {"fc": "1.0", "pad": 0, "edgecolor": "1.0", "alpha": 0.5},
                    "ha": "left",
                    "va": "bottom",
                }
                ax.text(
                    *annot_loc,
                    annot_text,
                    text_props,
                    rotation=text_angle,
                    rotation_mode="anchor",
                )

                # Adding text causes the axis to resize itself, and we have to stop it
                #  from doing so
                # (I get it, the axis wants to maintain a margin around things in the
                # plot area, but in this case we don't want that)
                ax.set_xlim(ax_x_min, ax_x_max)
                ax.set_ylim(ax_y_min, ax_y_max)

        # Save
        savefile_path = Paths.FIGURES / savefile_path
        savefile_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(savefile_path, bbox_inches="tight", dpi=300)
        print(f"Saved '{savefile_path.relative_to(Paths.ROOT)}'")

        figs_and_axes.append((fig, ax))

    return figs_and_axes


def remove_empty_leading_dates(
    df: pd.DataFrame, count_type: CaseGroup.CountType
) -> pd.DataFrame:
    start_date = df.loc[
        (
            df[Columns.CASE_TYPE]
            == CaseTypes.get_case_types(
                stage=CaseGroup.Stage.CONFIRMED, count_type=count_type
            )
        )
        & (df[Columns.CASE_COUNT] > 0),
        Columns.DATE,
    ].iloc[0]

    df = df[df[Columns.DATE] >= start_date]
    return df


def get_savefile_path_and_location_heading(
    df: pd.DataFrame, description: str, count_type: CaseGroup.CountType
) -> Tuple[Path, str]:

    if Locations.WORLD in df[Columns.COUNTRY].values:
        savefile_basename = "World"
        location_heading = None
    elif df[Columns.COUNTRY].iloc[0] == Locations.CHINA:
        savefile_basename = "China_provinces"
        location_heading = "Province"
    elif df[Columns.IS_STATE].iloc[0]:
        savefile_basename = "States"
        location_heading = "State"
    elif not df[Columns.IS_STATE].any():
        if (df[Columns.COUNTRY] == Locations.CHINA).any():
            savefile_basename = "Countries_w_china"
        else:
            savefile_basename = "Countries_wo_china"

        location_heading = "Country"
    else:
        raise ValueError("DataFrame contents not understood")

    savefile_path = (
        Path()
        / count_type.name.capitalize()
        / description.capitalize()
        / Path(savefile_basename.lower()).with_suffix(".png")
    )
    return savefile_path, location_heading


def get_color_palette_assignments(
    df: pd.DataFrame, palette: ColorPalette = None
) -> LocationColorMapping:
    current_case_data = get_current_case_data(df, CaseGroup.CountType.ABSOLUTE)
    if palette is None:
        palette = sns.color_palette(n_colors=len(current_case_data))
    else:
        palette = palette[: len(current_case_data)]

    return pd.DataFrame(
        {
            Columns.LOCATION_NAME: current_case_data[Columns.LOCATION_NAME],
            COLOR: palette,
        }
    )


def plot_cases_from_fixed_date(
    df: pd.DataFrame,
    *,
    count_type: CaseGroup.CountType,
    df_with_china: pd.DataFrame = None,  # For keeping consistent color assignments
    style=None,
    start_date=None,
) -> List[Tuple[plt.Figure, plt.Axes]]:

    if start_date is not None:
        df = df[df[Columns.DATE] >= pd.Timestamp(start_date)]

    df = remove_empty_leading_dates(df, count_type)

    configs = [
        {
            ConfigFields.CASE_TYPE: CaseTypes.get_case_types(
                stage=CaseGroup.Stage.CONFIRMED, count_type=count_type
            ),
            ConfigFields.DASH_STYLE: Style.Dash.PRIMARY,
        },
        {
            ConfigFields.CASE_TYPE: CaseTypes.get_case_types(
                stage=CaseGroup.Stage.DEATH, count_type=count_type
            ),
            ConfigFields.DASH_STYLE: Style.Dash.SECONDARY,
        },
    ]

    savefile_path, location_heading = get_savefile_path_and_location_heading(
        df, FROM_FIXED_DATE_DESC, count_type
    )

    if df_with_china is not None:
        color_mapping = get_color_palette_assignments(df_with_china)
    else:
        color_mapping = get_color_palette_assignments(df)

    return _plot_helper(
        df,
        x_axis_col=Columns.DATE,
        count_type=count_type,
        style=style,
        color_mapping=color_mapping,
        case_type_config_list=configs,
        savefile_path=savefile_path,
        location_heading=location_heading,
    )


def plot_cases_by_days_since_first_widespread_locally(
    df: pd.DataFrame,
    *,
    count_type: CaseGroup.CountType,
    df_with_china: pd.DataFrame = None,  # For keeping consistent color assignments
    style=None,
) -> List[Tuple[plt.Figure, plt.Axes]]:
    configs = [
        {
            ConfigFields.CASE_TYPE: CaseTypes.get_case_types(
                stage=CaseGroup.Stage.CONFIRMED, count_type=count_type
            ),
            ConfigFields.DASH_STYLE: Style.Dash.PRIMARY,
        },
        {
            ConfigFields.CASE_TYPE: CaseTypes.get_case_types(
                stage=CaseGroup.Stage.DEATH, count_type=count_type
            ),
            ConfigFields.DASH_STYLE: Style.Dash.SECONDARY,
        },
    ]

    savefile_path, location_heading = get_savefile_path_and_location_heading(
        df, FROM_LOCAL_OUTBREAK_START_DESC, count_type
    )

    df = df[df[Columns.DAYS_SINCE_OUTBREAK] >= -1]

    if df_with_china is not None:
        color_mapping = get_color_palette_assignments(df_with_china)
    else:
        color_mapping = get_color_palette_assignments(df)

    return _plot_helper(
        df,
        x_axis_col=Columns.DAYS_SINCE_OUTBREAK,
        count_type=count_type,
        style=style,
        color_mapping=color_mapping,
        case_type_config_list=configs,
        savefile_path=savefile_path,
        location_heading=location_heading,
    )
