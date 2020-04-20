# %%
import itertools
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Union

import matplotlib.pyplot as plt

# import matplotlib
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import display  # noqa F401
from matplotlib.dates import DateFormatter, DayLocator
from matplotlib.legend import Legend
from matplotlib.ticker import (
    LogLocator,
    MultipleLocator,
    NullFormatter,
    StrMethodFormatter,
)
from typing_extensions import Literal

from constants import (
    ABCStrictEnum,
    CaseInfo,
    CaseTypes,
    Columns,
    Counting,
    DiseaseStage,
    InfoField,
    Paths,
    Select,
)
from plotting_utils import (
    ADTL_DAY_INDICES,
    COLOR,
    START_DATE,
    LocationColorMapping,
    form_doubling_time_colname,
    get_color_palette_assignments,
    get_current_case_data,
    get_savefile_path_and_location_heading,
    remove_empty_leading_dates,
)


class EdgeGuide(ABCStrictEnum):
    """An enum whose cases represent which edge of the graph text is to be aligned with
    """

    RIGHT: "EdgeGuide" = "right"
    TOP: "EdgeGuide" = "top"


def _add_doubling_time_lines(
    fig: plt.Figure,
    ax: plt.Axes,
    *,
    stage: DiseaseStage,
    count: Counting,
    x_axis: Columns.XAxis,
):
    """Add doubling time lines to the given plot

    On a log-scale graph, doubling time lines originate from a point near the
    lower-left and show how fast the number of cases (per capita) would grow if it
    doubled every n days.

    :param fig: The figure containing the plots
    :type fig: plt.Figure
    :param ax: The axes object we wish to annotate
    :type ax: plt.Axes
    :param x_axis: The column to be used for the x-axis of the graph. We only add
    doubling time lines for graphs plotted against days since outbreak (and not actual
    days, as doubling time lines don't make sense then because there is no common
    origin to speak of)
    :type x_axis: Columns.XAxis
    :param stage: The disease stage we are plotting
    :type stage: DiseaseStage
    :param count: The count method used
    :type count: Counting
    """

    DiseaseStage.verify(stage)
    Counting.verify(count)
    Columns.XAxis.verify(x_axis)

    # For ease of computation, everything will be in axes coordinate system
    # Variable names beginning with "ac" refer to axis coords and "dc" to data coords
    # {ac,dc}_{x,y}_{min,max} refer to the coordinates of the doubling-time lines
    if x_axis is Columns.XAxis.DAYS_SINCE_OUTBREAK:
        # Create transformation from data coords to axes coords
        # This composes two transforms, data -> fig and (axes -> fig)^(-1)
        dc_to_ac = ax.transData + ax.transAxes.inverted()

        dc_x_lower_lim, dc_x_upper_lim = ax.get_xlim()
        dc_y_lower_lim, dc_y_upper_lim = ax.get_ylim()

        # Adding stuff causes the axis to resize itself, and we have to stop it
        # from doing so (by setting it back to its original size)
        ax.set_xlim(dc_x_lower_lim, dc_x_upper_lim)

        # Also need to add back margin
        dc_y_upper_lim = dc_to_ac.inverted().transform((0, 1.1))[1]
        ax.set_ylim(dc_y_lower_lim, dc_y_upper_lim)

        # Getting min x,y bounds of lines is easy
        dc_x_min = 0
        dc_y_min = CaseInfo.get_info_item_for(
            InfoField.THRESHOLD, stage=stage, count=count
        )

        ac_x_min, ac_y_min = dc_to_ac.transform((dc_x_min, dc_y_min))

        # Getting max x,y bounds is trickier due to needing to use the maximum
        # extent of the graph area
        # Get top right corner of graph in data coords (to avoid the edges of the
        # texts' boxes clipping the axes, we move things in just a hair)
        ac_x_upper_lim = ac_y_upper_lim = 1

        doubling_times = [1, 2, 3, 4, 7, 14]  # days (x-axis units)
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
                dashes=(1, 2),
                linewidth=1,
            )

            # Annotate lines with assocated doubling times

            # Get text to annotate with
            n_weeks, weekday = divmod(dt, 7)
            if weekday == 0:
                annot_text_str = f"{n_weeks} week"
                if n_weeks != 1:
                    annot_text_str += "s"
            else:
                annot_text_str = f"{dt} day"
                if dt != 1:
                    annot_text_str += "s"

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
            PADDING = 0.005
            ac_rot_text_width = (
                (ac_text_width * cos_ac_angle)
                + (ac_text_height * sin_ac_angle)
                + PADDING
            )
            ac_rot_text_height = (
                (ac_text_width * sin_ac_angle)
                + (ac_text_height * cos_ac_angle)
                + PADDING
            )

            # Perpendicular distance from text to corresponding line
            AC_DIST_FROM_LINE = 0.005
            # Get text box origin relative to line upper endpoint
            EdgeGuide.verify(edge)
            if edge is EdgeGuide.RIGHT:
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
                    + (ac_text_origin_x - ac_x_min) * ac_line_slope
                    + AC_DIST_FROM_LINE / cos_ac_angle
                )

            # If text box is in very top right of graph, it may use only the right
            # edge of the graph as a guide and hence clip through the top; if that
            # happens, it's effectively the same situation as using the top edge from
            # the start
            if (
                edge is EdgeGuide.TOP  # Must go first to short-circuit
                or ac_text_origin_y + ac_rot_text_height > ac_y_upper_lim
            ):
                ac_text_origin_y = ac_y_upper_lim - ac_rot_text_height
                ac_text_origin_x = (
                    ac_x_min
                    - AC_DIST_FROM_LINE / sin_ac_angle
                    + (ac_text_origin_y - ac_y_min) / ac_line_slope
                )

            # set_x and set_y work in axis coordinates
            plotted_text.set_x(ac_text_origin_x)
            plotted_text.set_y(ac_text_origin_y)
            plotted_text.set_horizontalalignment("left")
            plotted_text.set_verticalalignment("bottom")
            plotted_text.set_rotation(ac_text_angle_rad * 180 / np.pi)  # takes degrees
            plotted_text.set_rotation_mode("anchor")


def _format_legend(
    *,
    ax: plt.Axes,
    x_axis: Columns.XAxis,
    count: Counting,
    location_heading: str,
    current_case_counts: pd.DataFrame,
) -> Legend:
    """Format the legend correctly so that relevant info is shown in the legends' rows

    In addition to just displaying which location maps to a given line color, and which
    case type to a given line style, we also display some current data in the legend
    (e.g., this location currently has this many cases).

    :param ax: The axis to add the legend to
    :type ax: plt.Axes
    :param x_axis: The x axis column we're plotting against
    :type x_axis: Columns.XAxis
    :param count: Which count we're using
    :type count: Counting
    :param location_heading: The name we'll use for the location heading ("Country",
    "State", etc.)
    :type location_heading: str
    :param current_case_counts: Dataframe with current case counts; used to add data
    to the legend
    :type current_case_counts: pd.DataFrame
    :return: The added legend
    :rtype: Legend
    """

    Counting.verify(count)
    Columns.XAxis.verify(x_axis)

    include_confirmed = x_axis is Columns.XAxis.DATE
    include_deaths = x_axis is Columns.XAxis.DATE
    include_doubling_time = x_axis is Columns.XAxis.DAYS_SINCE_OUTBREAK
    include_mortality = x_axis is Columns.XAxis.DATE and count is Counting.TOTAL_CASES
    include_start_date = (not include_mortality) and (
        x_axis is Columns.XAxis.DAYS_SINCE_OUTBREAK
    )

    # Add (formatted) current data to legend labels

    # Fields labels, comprising the first row of the legend
    legend_fields: List[str] = []
    case_count_str_cols: List[pd.Series] = []

    if include_confirmed:
        this_case_type = CaseInfo.get_info_item_for(
            InfoField.CASE_TYPE, stage=DiseaseStage.CONFIRMED, count=count
        )
        legend_fields.append(this_case_type)

        if count is Counting.TOTAL_CASES:
            float_format_func = r"{:,.0f}".format
        else:
            float_format_func = r"{:.2e}".format

        case_count_str_cols.append(
            current_case_counts[this_case_type].map(float_format_func)
        )

    if include_deaths:
        this_case_type = CaseInfo.get_info_item_for(
            InfoField.CASE_TYPE, stage=DiseaseStage.DEATH, count=count
        )
        legend_fields.append(this_case_type)
        case_count_str_cols.append(
            current_case_counts[this_case_type].map(float_format_func)
        )

    if include_start_date:
        legend_fields.append("Start Date")
        case_count_str_cols.append(
            current_case_counts[START_DATE].dt.strftime(r"%b %-d")
        )

    if include_doubling_time:
        for day_idx in [0, *ADTL_DAY_INDICES]:
            if day_idx == 0:
                legend_fields.append("Net DT")
            elif day_idx < 0:
                legend_fields.append(f"{-day_idx}d DT")
            else:
                legend_fields.append(f"From day {day_idx}")

            case_count_str_cols.append(
                current_case_counts[form_doubling_time_colname(day_idx)].map(
                    lambda x: "NA" if pd.isna(x) else r"{:.3g}d".format(x)
                )
            )

    if include_mortality:
        legend_fields.append(CaseTypes.MORTALITY)
        case_count_str_cols.append(
            current_case_counts[CaseTypes.MORTALITY].map(r"{0:.2%}".format)
        )

    # Add case counts of the different categories to the legend (next few blocks)
    legend = ax.legend(loc="best", framealpha=0.9, fontsize="small")
    sep_str = " / "
    left_str = " ("
    right_str = ")"

    fmt_str = sep_str.join(legend_fields)

    if location_heading is None:
        location_heading = Columns.LOCATION_NAME

    next(iter(legend.texts)).set_text(
        f"{location_heading}{left_str}{fmt_str}{right_str}"
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

    return legend


def _plot_helper(
    df: pd.DataFrame,
    *,
    stage: Union[DiseaseStage, Literal[Select.ALL]],
    count: Counting,
    x_axis: Columns.XAxis,
    style: Optional[str] = None,
    color_mapping: LocationColorMapping = None,
    plot_size: Tuple[float] = None,
    savefile_path: Path,
    location_heading: str = None,
) -> List[Tuple[plt.Figure, plt.Axes]]:
    """Do all the logic required to turn the arguments given into the correct plot

    :param df: The dataframe whose data will be plotted
    :type df: pd.DataFrame
    :param x_axis: The x axis column the data will be plotted against
    :type x_axis: Columns.XAxis
    :param stage: The disease stage (one half of the y-value) that will be plotted;
    :type stage: Union[DiseaseStage, Literal[Select.ALL]]
    :param count: The counting method (the other half of the y-value) that will be
    plotted
    :type count: Counting
    :param savefile_path: Where to save the resulting figure
    :type savefile_path: Path
    :param style: The matplotlib plotting style to use, defaults to None
    :type style: Optional[str], optional
    :param color_mapping: The seaborn color mapping to use, defaults to None
    :type color_mapping: LocationColorMapping, optional
    :param plot_size: The (width inches, height inches) plot size, defaults to None
    :type plot_size: Tuple[float], optional
    :param location_heading: What locations are to be called ("Country", "State",
    etc.); the default of None is equivalent to "Location"
    :type location_heading: str, optional
    :return: A list of figures and axes created
    :rtype: List[Tuple[plt.Figure, plt.Axes]]
    """

    DiseaseStage.verify(stage, allow_select=True)
    Counting.verify(count)
    Columns.XAxis.verify(x_axis)

    SORTED_POSITION = "Sorted_Position_"

    figs_and_axes = []

    if plot_size is None:
        plot_size = (10, 12)

    fig, ax = plt.subplots(figsize=(8, 8), dpi=200, facecolor="white")
    fig: plt.Figure
    ax: plt.Axes

    if stage is Select.ALL:
        current_case_counts = get_current_case_data(
            df, stage=Select.DEFAULT, count=count, x_axis=x_axis
        )
    else:
        current_case_counts = get_current_case_data(
            df, stage=stage, count=count, x_axis=x_axis
        )

    df = df[
        df[Columns.CASE_TYPE].isin(
            CaseInfo.get_info_items_for(
                InfoField.CASE_TYPE, stage=stage, count=count
            ).values
        )
    ]

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

    config_df = CaseInfo.get_info_items_for(
        InfoField.CASE_TYPE, InfoField.DASH_STYLE, stage=stage, count=count
    )

    with plt.style.context(style or "default"):
        g = sns.lineplot(
            data=df,
            x=x_axis.column(),
            y=Columns.CASE_COUNT,
            hue=Columns.LOCATION_NAME,
            hue_order=color_mapping[Columns.LOCATION_NAME].tolist(),
            style=Columns.CASE_TYPE,
            style_order=config_df[InfoField.CASE_TYPE].tolist(),
            dashes=config_df[InfoField.DASH_STYLE].tolist(),
            palette=color_mapping[COLOR].tolist(),
        )

        default_stage = stage
        if stage is Select.ALL:
            default_stage = DiseaseStage.CONFIRMED

        # Configure axes and ticks
        # X axis (and y axis bottom limit, which is kind of x-axis related)
        if x_axis is Columns.XAxis.DATE:
            ax.xaxis.set_major_formatter(DateFormatter(r"%b %-d"))
            ax.xaxis.set_minor_locator(DayLocator())
            for tick in ax.get_xticklabels():
                tick.set_rotation(80)

        elif x_axis is Columns.XAxis.DAYS_SINCE_OUTBREAK:
            ax.xaxis.set_major_locator(MultipleLocator(5))
            ax.xaxis.set_minor_locator(MultipleLocator(1))

            _threshold, _axis_name = CaseInfo.get_info_items_for(
                InfoField.THRESHOLD,
                InfoField.CASE_TYPE,
                stage=default_stage,
                count=count,
                squeeze_rows=True,
            ).values
            ax.set_xlabel(f"Days Since Reaching {_threshold:.3g} {_axis_name}")

            if stage is not Select.ALL:  # i.e. if only one DiseaseStage plotted
                ax.set_ylim(bottom=_threshold / 4)

        else:
            x_axis.raise_for_unhandled_case()

        # Y axis
        ax.set_ylabel(
            CaseInfo.get_info_item_for(
                InfoField.CASE_TYPE, stage=default_stage, count=count
            )
        )
        if count is Counting.TOTAL_CASES:
            ax.set_yscale("log", basey=2, nonposy="mask")
            ax.yaxis.set_major_locator(LogLocator(base=2, numticks=1000))
            # ax.yaxis.set_major_formatter(ScalarFormatter())
            ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
            ax.yaxis.set_minor_locator(
                # 5 ticks is one full "cycle": n, 1.25n, 1.5n, 1.75n, 2n
                # Hence 5-2 minor ticks between each pair of majors (omit endpoints)
                LogLocator(base=2, subs=np.linspace(0.5, 1, 5)[1:-1], numticks=1000)
            )
            ax.yaxis.set_minor_formatter(NullFormatter())
        elif count is Counting.PER_CAPITA:
            ax.set_yscale("log", basey=10, nonposy="mask")
            # No need to set minor ticks; 8 is the default number, which makes one cycle
            # n, 2n, 3n, ..., 8n, 9n, 10n
        else:
            count.raise_for_unhandled_case()

        # Configure plot design
        now_str = datetime.now(timezone.utc).strftime(r"%b %-d, %Y at %H:%M UTC")
        ax.set_title(f"Last updated {now_str}", loc="right", fontsize="small")

        for line in g.lines:
            line.set_linewidth(2)
        ax.grid(True, which="minor", axis="both", color="0.9")
        ax.grid(True, which="major", axis="both", color="0.75")

        _format_legend(
            ax=ax,
            x_axis=x_axis,
            count=count,
            location_heading=location_heading,
            current_case_counts=current_case_counts,
        )

        # If using this for a date-like x axis, use this (leaving commented code because
        # I foresee myself needing it eventually)
        # x_max = pd.Timestamp(matplotlib.dates.num2epoch(ax.get_xlim()[1]), unit="s")

        # Add doubling time lines
        _add_doubling_time_lines(
            fig, ax, x_axis=x_axis, stage=default_stage, count=count
        )

        # Save
        savefile_path = Paths.FIGURES / savefile_path
        savefile_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(savefile_path, bbox_inches="tight", dpi=300)
        print(f"Saved '{savefile_path.relative_to(Paths.ROOT)}'")

        figs_and_axes.append((fig, ax))

    return figs_and_axes


def plot(
    df: pd.DataFrame,
    *,
    start_date=None,
    stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
    count: Counting,
    x_axis: Columns.XAxis,
    df_with_china: pd.DataFrame = None,
    style=None,
) -> List[Tuple[plt.Figure, plt.Axes]]:
    """Entry point for plotting

    This function does some basic setup, computing some data necessary for plotting from
    the passed arguments, before passing along all the necessary data to
    _plot_helper, which does the actual plotting work

    :param df: The data to plot
    :type df: pd.DataFrame
    :param x_axis: The x axis column to plot against
    :type x_axis: Columns.XAxis
    :param start_date: A date with which to filter the data; only data after this date
    will be plotted, defaults to None (all data will be plotted)
    :type start_date: [type], optional
    :param stage: The disease stage to plot, defaults to Select.ALL
    :type stage: Union[DiseaseStage, Literal[Select.ALL]], optional
    :param count: The count type to plot
    :type count: Counting
    :param df_with_china: A dataframe to serve as a reference point for creating the
    color mapping; this keeps colors in sync whether or not China is included in the
    plot. Defaults to None, in which case `df` is used to create the color mapping.
    :type df_with_china: pd.DataFrame, optional
    :param style: The matplotlib style to plot with, defaults to None (default style)
    :type style: [type], optional
    :return: A list of plotted objects (Figure, Axes)
    :rtype: List[Tuple[plt.Figure, plt.Axes]]
    """

    DiseaseStage.verify(stage, allow_select=True)
    Counting.verify(count)
    Columns.XAxis.verify(x_axis)

    if x_axis is Columns.XAxis.DATE:
        if start_date is not None:
            df = df[df[Columns.DATE] >= pd.Timestamp(start_date)]

        df = remove_empty_leading_dates(df, count)
    elif x_axis is Columns.XAxis.DAYS_SINCE_OUTBREAK:
        df = df[df[Columns.DAYS_SINCE_OUTBREAK] >= -1]
    else:
        x_axis.raise_for_unhandled_case()

    savefile_path, location_heading = get_savefile_path_and_location_heading(
        df, x_axis=x_axis, stage=stage, count=count
    )

    if df_with_china is not None:
        color_mapping = get_color_palette_assignments(df_with_china)
    else:
        color_mapping = get_color_palette_assignments(df)

    return _plot_helper(
        df,
        x_axis=x_axis,
        stage=stage,
        count=count,
        style=style,
        color_mapping=color_mapping,
        savefile_path=savefile_path,
        location_heading=location_heading,
    )
