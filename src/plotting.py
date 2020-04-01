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


class EdgeGuide(enum.Enum):
    RIGHT = "right"
    TOP = "top"


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


def _add_doubling_time_lines(fig: plt.Figure, ax: plt.Axes, *, x_axis_col, count_type):

    # For ease of computation, everything will be in axes coordinate system
    # Variable names beginning with "ac" refer to axis coords and "dc" to data coords
    # {ac,dc}_{min,max}_{x,y} refer to the coordinates of the doubling-time lines
    if x_axis_col == Columns.DAYS_SINCE_OUTBREAK:

        dc_x_lower_lim, dc_x_upper_lim = ax.get_xlim()
        dc_y_lower_lim, dc_y_upper_lim = ax.get_ylim()

        # Create transformation from data coords to axes coords
        # This composes two transforms, data -> fig, and (axes -> fig)^(-1)
        dc_to_ac = ax.transData + ax.transAxes.inverted()

        # Getting min x,y bounds of lines is easy
        dc_x_min = 0
        if count_type == CaseGroup.CountType.ABSOLUTE:
            dc_y_min = Thresholds.CASE_COUNT
        elif count_type == CaseGroup.CountType.PER_CAPITA:
            dc_y_min = Thresholds.CASES_PER_CAPITA
        else:
            raise ValueError(f"{count_type=} not understood")

        ac_x_min, ac_y_min = dc_to_ac.transform((dc_x_min, dc_y_min))

        # Getting max x,y bounds is trickier due to needing to use the maximum
        # extent of the graph area
        # Get top right corner of graph in data coords (to a void the edges of the
        # texts' boxes clipping the axes, we move things in just a hair)
        ac_x_upper_lim = ac_y_upper_lim = 1

        doubling_times = [1, 2, 3, 4, 7]  # days (x-axis units)
        for dt in doubling_times:
            # Simple math: assuming dc_y_max := dc_y_upper_lim, then if
            # dc_y_max = dc_y_min * 2**((dc_x_max-dc_x_min)/dt),
            # then...
            dc_x_max = dc_x_min + dt * np.log2(dc_y_upper_lim / dc_y_min)
            ac_x_max, ac_y_max = dc_to_ac.transform((dc_x_max, dc_y_upper_lim))

            # We try to use ac_y_max=1 by default, and if that leads to too long a line
            # (sticking out through the right side of the graph) then we use ac_x_max=1
            # instead and compute ac_y_max accordingly
            if ac_x_max > ac_x_upper_lim:
                dc_y_max = dc_y_min * 2 ** ((dc_x_upper_lim - dc_x_min) / dt)
                ac_x_max, ac_y_max = dc_to_ac.transform((dc_x_upper_lim, dc_y_max))
                edge = EdgeGuide.RIGHT
            else:
                edge = EdgeGuide.TOP

            # Plot the lines themselves
            ax.plot(
                [ac_x_min, ac_x_max],
                [ac_y_min, ac_y_max],
                transform=ax.transAxes,
                color="0.0",
                alpha=0.7,
                dashes=(3, 2),
                linewidth=1,
            )

            # Annotate lines with assocated doubling times
            if dt == 1:
                annot_text_str = f"{dt} day"
            elif dt == 7:
                annot_text_str = "1 week"
            else:
                annot_text_str = f"{dt} days"

            text_props = {
                "bbox": {
                    "fc": "1.0",
                    "pad": 0,
                    # "edgecolor": "1.0",
                    "alpha": 0.7,
                    "lw": 0,
                }
            }

            # Plot in a temporary location just to get the text box size; we'll move and
            # rotate later
            plotted_text = ax.text(
                0, 0, annot_text_str, text_props, transform=ax.transAxes
            )

            ac_line_slope = (ac_y_max - ac_y_min) / (ac_x_max - ac_x_min)
            ac_text_angle_rad = np.arctan(ac_line_slope)
            sin_ac_angle = np.sin(ac_text_angle_rad)
            cos_ac_angle = np.cos(ac_text_angle_rad)

            # Get the unrotated text box bounds
            ac_text_box = plotted_text.get_window_extent(
                fig.canvas.get_renderer()
            ).transformed(ax.transAxes.inverted())
            ac_text_width = ac_text_box.x1 - ac_text_box.x0
            ac_text_height = ac_text_box.y1 - ac_text_box.y0

            # Compute the width and height of the upright rectangle bounding the rotated
            # text box in axis coordinates
            # Simple geometry (a decent high school math problem)
            # We cheat a bit; to create some padding between the rotated text box and
            # the axes, we can add the padding directly to the width and height of the
            # upright rectangle bounding the rotated text box
            # This works because the origin of the rotated text box is in the lower left
            # corner of the upright bounding rectangle, so anything added to these
            # dimensions gets added to the top and right, pushing it away from the axes
            # and producing the padding we want
            # If we wanted to do this the "right" way we'd *redo* the calculations above
            # but with ac_x_upper_lim = ac_y_upper_lim = 1 - padding
            padding = 0.005
            ac_rot_text_width = (
                (ac_text_width * cos_ac_angle)
                + (ac_text_height * sin_ac_angle)
                + padding
            )
            ac_rot_text_height = (
                (ac_text_width * sin_ac_angle)
                + (ac_text_height * cos_ac_angle)
                + padding
            )

            # Perpendicular distance from text to corresponding line
            ac_dist_from_line = 0.005
            # Get text box origin relative to line upper endpoint
            # If the doubling-time line is y = m*x + b, then the bottom edge of the text
            # box lies on y = m*x + b + ac_vert_dist_from_line
            assert edge in EdgeGuide
            if edge == EdgeGuide.RIGHT:
                # Account for bit of overhang; when slanted, top left corner of the
                # text box extends left of the bottom left corner, which is its origin
                # Subtracting that bit of overhang (height * sin(theta)) gets us the
                # x-origin
                # This only applies to the x coord; the bottom left corner of the text
                # box is also the bottom of the rotated rectangle
                ac_text_origin_x = ac_x_max - (
                    ac_rot_text_width - ac_text_height * sin_ac_angle
                )
                ac_text_origin_y = (
                    ac_y_min
                    + ac_dist_from_line * cos_ac_angle
                    + (ac_text_origin_x - ac_x_min) * ac_line_slope
                )

            # If text box is in very top right of graph, it may use only the right
            # edge of the graph as a guide and hence clip through the top; if that
            # happens, it's effectively the same situation as using the top edge from
            # the start
            if (
                edge == EdgeGuide.TOP  # Must go first to short-circuit
                or ac_text_origin_y + ac_rot_text_height > ac_y_upper_lim
            ):
                ac_text_origin_y = ac_y_upper_lim - ac_rot_text_height
                ac_text_origin_x = (
                    ac_x_min
                    - (ac_dist_from_line / sin_ac_angle)
                    + ((ac_text_origin_y - ac_y_min) / ac_line_slope)
                )

            # set_x and set_y work in axis coordinates
            plotted_text.set_x(ac_text_origin_x)
            plotted_text.set_y(ac_text_origin_y)
            plotted_text.set_horizontalalignment("left")
            plotted_text.set_verticalalignment("bottom")
            plotted_text.set_rotation(ac_text_angle_rad * 180 / np.pi)  # takes degrees
            plotted_text.set_rotation_mode("anchor")

        # Adding stuff causes the axis to resize itself, and we have to stop it
        # from doing so (by setting it back to its original size)
        ax.set_xlim(dc_x_lower_lim, dc_x_upper_lim)
        ax.set_ylim(dc_y_lower_lim, dc_y_upper_lim)


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
        _add_doubling_time_lines(fig, ax, x_axis_col=x_axis_col, count_type=count_type)

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
