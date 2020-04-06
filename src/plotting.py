# %%
import itertools
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt

# import matplotlib
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import display  # noqa F401
from matplotlib import rcParams
from matplotlib.dates import DateFormatter, DayLocator
from matplotlib.legend import Legend
from matplotlib.ticker import (
    LogLocator,
    MultipleLocator,
    NullFormatter,
    ScalarFormatter,
)

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

FROM_FIXED_DATE_DESC = "from_fixed_date"
FROM_LOCAL_OUTBREAK_START_DESC = "from_local_spread_start"

START_DATE = "Start_Date_"
DOUBLING_TIME = "Doubling_Time_"
COLOR = "Color_"

# Decides which doubling times are included in addition to the net (from day 1)
# Don't include 0 here; it'll be added automatically (hence "additional")
ADTL_DAY_INDICES = [-20, -10]

rcParams.update({"font.family": "sans-serif", "font.size": 12})


SingleColor = Tuple[float, float, float]
ColorPalette = List[SingleColor]
LocationColorMapping = pd.DataFrame


class EdgeGuide(ABCStrictEnum):
    RIGHT = "right"
    TOP = "top"


def form_doubling_time_colname(day_idx: int) -> Tuple[str, int]:
    return (DOUBLING_TIME, day_idx)


def get_current_case_data(
    df: pd.DataFrame,
    *,
    stage: Optional[DiseaseStage],
    count: Counting,
    x_axis: Columns.XAxis,
) -> pd.DataFrame:

    Columns.XAxis.verify(x_axis)

    # Filter in order to compute doubling time
    df = df[df[Columns.CASE_COUNT] > 0]
    relevant_case_types = CaseInfo.get_info_items_for(
        InfoField.CASE_TYPE, stage=stage, count=count
    ).values

    day_indices = [0, *ADTL_DAY_INDICES]

    def get_group_stats(g: pd.DataFrame) -> pd.Series:
        # Filter to the relevant case type and just the two columns
        relevant_subsection = g.loc[
            g[Columns.CASE_TYPE].isin(relevant_case_types),
            [Columns.DATE, Columns.CASE_COUNT],
        ]

        # Get the doubling times for selected day indices (fed to iloc)
        # Keys are stringified iloc positions (0, k, -j, etc),
        # Values are values at that iloc
        doubling_times = {}
        current_date, current_count = relevant_subsection.iloc[-1]
        for day_idx in day_indices:
            col_name = form_doubling_time_colname(day_idx)
            try:
                then_row = relevant_subsection.iloc[day_idx]
            except IndexError:
                doubling_times[col_name] = np.nan
                continue

            # $ currentCount = initialCount * 2^{_days/doublingTime} $
            then_date = then_row[Columns.DATE]
            then_count = then_row[Columns.CASE_COUNT]

            n_days = (current_date - then_date).total_seconds() / 86400
            count_ratio = current_count / then_count

            doubling_times[col_name] = n_days / np.log2(count_ratio)

        data_dict = {
            START_DATE: g[Columns.DATE].min(),
            **doubling_times,
            # Get last case count of each case type for current group
            # .tail(1).sum() is a trick to get the last value if it exists,
            # else 0 (remember, this is sorted by date)
            **(
                g.groupby(Columns.CASE_TYPE)[Columns.CASE_COUNT]
                .apply(lambda h: h.tail(1).sum())
                .to_dict()
            ),
        }

        return pd.Series(
            data_dict,
            index=[
                START_DATE,
                *doubling_times.keys(),
                *CaseInfo.get_info_items_for(InfoField.CASE_TYPE),
            ],
        )

    if x_axis == Columns.XAxis.DAYS_SINCE_OUTBREAK:
        sort_col = form_doubling_time_colname(0)
        sort_ascending = True
    elif x_axis == Columns.XAxis.DATE:
        sort_col = relevant_case_types.tolist()
        sort_ascending = False
    else:
        x_axis.raise_for_unhandled_case()

    # display(df.columns)
    # display(Columns.location_id_cols)
    # display(df.groupby(Columns.location_id_cols).apply(get_group_stats).columns)
    current_case_counts = (
        df.groupby(Columns.location_id_cols)
        .apply(get_group_stats)
        # Order locations by decreasing current confirmed case count
        # This is used to keep plot legend in sync with the order of lines on the graph
        # so the location with the most current cases is first in the legend and the
        # least is last
        .sort_values(sort_col, ascending=sort_ascending)
        .reset_index()
    )

    confirmed_col, death_col = [
        CaseInfo.get_info_item_for(InfoField.CASE_TYPE, stage=stage, count=count)
        for stage in [DiseaseStage.CONFIRMED, DiseaseStage.DEATH]
    ]
    current_case_counts[CaseTypes.MORTALITY] = (
        current_case_counts[death_col] / current_case_counts[confirmed_col]
    )

    return current_case_counts


def _add_doubling_time_lines(
    fig: plt.Figure,
    ax: plt.Axes,
    *,
    x_axis: Columns.XAxis,
    stage: DiseaseStage,
    count: Counting,
):
    Columns.XAxis.verify(x_axis)

    # For ease of computation, everything will be in axes coordinate system
    # Variable names beginning with "ac" refer to axis coords and "dc" to data coords
    # {ac,dc}_{min,max}_{x,y} refer to the coordinates of the doubling-time lines
    if x_axis == Columns.XAxis.DAYS_SINCE_OUTBREAK:

        dc_x_lower_lim, dc_x_upper_lim = ax.get_xlim()
        dc_y_lower_lim, dc_y_upper_lim = ax.get_ylim()

        # Create transformation from data coords to axes coords
        # This composes two transforms, data -> fig, and (axes -> fig)^(-1)
        dc_to_ac = ax.transData + ax.transAxes.inverted()

        # Getting min x,y bounds of lines is easy
        dc_x_min = 0
        dc_y_min = CaseInfo.get_info_item_for(
            InfoField.THRESHOLD, stage=stage, count=count
        )

        ac_x_min, ac_y_min = dc_to_ac.transform((dc_x_min, dc_y_min))

        # Getting max x,y bounds is trickier due to needing to use the maximum
        # extent of the graph area
        # Get top right corner of graph in data coords (to a void the edges of the
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
                dashes=(3, 2),
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
            EdgeGuide.verify(edge)
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
                    + ac_dist_from_line / cos_ac_angle
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
                    - ac_dist_from_line / sin_ac_angle
                    + (ac_text_origin_y - ac_y_min) / ac_line_slope
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


def _format_legend(
    *,
    ax: plt.Axes,
    x_axis: Columns.XAxis,
    count,
    location_heading: str,
    current_case_counts: pd.DataFrame,
) -> Legend:

    Columns.XAxis.verify(x_axis)

    include_confirmed = x_axis == Columns.XAxis.DATE
    include_deaths = x_axis == Columns.XAxis.DATE
    include_doubling_time = x_axis == Columns.XAxis.DAYS_SINCE_OUTBREAK
    include_mortality = x_axis == Columns.XAxis.DATE and count == Counting.TOTAL_CASES
    include_start_date = (not include_mortality) and (
        x_axis == Columns.XAxis.DAYS_SINCE_OUTBREAK
    )

    # Add (formatted) current data to legend labels

    # Fields labels, comprising the first row of the legend
    legend_fields = []
    case_count_str_cols = []

    legend_fields: List[str]
    case_count_str_cols: List[pd.Series]

    if include_confirmed:
        this_case_type = CaseInfo.get_info_item_for(
            InfoField.CASE_TYPE, stage=DiseaseStage.CONFIRMED, count=count
        )
        legend_fields.append(this_case_type)

        if count == Counting.TOTAL_CASES:
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
    x_axis: Columns.XAxis,
    stage: DiseaseStage,
    count: Counting,
    style: Optional[str] = None,
    color_mapping: LocationColorMapping = None,
    plot_size: Tuple[float] = None,
    savefile_path: Path,
    location_heading: str = None,
) -> List[Tuple[plt.Figure, plt.Axes]]:

    Columns.XAxis.verify(x_axis)

    SORTED_POSITION = "Sorted_Position_"

    figs_and_axes = []

    if plot_size is None:
        plot_size = (10, 10)

    fig, ax = plt.subplots(figsize=(8, 8), dpi=200, facecolor="white")
    fig: plt.Figure
    ax: plt.Axes

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
        if default_stage is None:
            default_stage = DiseaseStage.CONFIRMED

        # Configure axes and ticks
        # X axis
        if x_axis == Columns.XAxis.DATE:
            ax.xaxis.set_major_formatter(DateFormatter(r"%b %-d"))
            ax.xaxis.set_minor_locator(DayLocator())
            for tick in ax.get_xticklabels():
                tick.set_rotation(80)

        elif x_axis == Columns.XAxis.DAYS_SINCE_OUTBREAK:
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

        else:
            x_axis.raise_for_unhandled_case()

        # Y axis
        ax.set_ylabel(
            CaseInfo.get_info_item_for(
                InfoField.CASE_TYPE, stage=default_stage, count=count
            )
        )
        if count == Counting.TOTAL_CASES:
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
        elif count == Counting.PER_CAPITA:
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


def remove_empty_leading_dates(df: pd.DataFrame, count: Counting) -> pd.DataFrame:
    start_date = df.loc[
        (
            df[Columns.CASE_TYPE]
            == CaseInfo.get_info_item_for(
                InfoField.CASE_TYPE, stage=DiseaseStage.CONFIRMED, count=count
            )
        )
        & (df[Columns.CASE_COUNT] > 0),
        Columns.DATE,
    ].iloc[0]

    df = df[df[Columns.DATE] >= start_date]
    return df


def get_savefile_path_and_location_heading(
    df: pd.DataFrame, description: str, *, stage: DiseaseStage, count: Counting,
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

    if stage is None:
        stage_name = "All"
    else:
        stage_name = stage.pprint()

    savefile_path = (
        Path()
        / count.pprint()
        / description.capitalize()
        / f"Stage {stage_name}"
        / Path(savefile_basename.lower()).with_suffix(".png")
    )
    return savefile_path, location_heading


def get_color_palette_assignments(
    df: pd.DataFrame, palette: ColorPalette = None
) -> LocationColorMapping:
    current_case_data = get_current_case_data(
        df,
        stage=DiseaseStage.CONFIRMED,
        count=Counting.TOTAL_CASES,
        x_axis=Columns.XAxis.DATE,
    )
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


def plot(
    df: pd.DataFrame,
    *,
    x_axis: Columns.XAxis,
    start_date=None,
    stage: DiseaseStage = None,
    count: Counting,
    df_with_china: pd.DataFrame = None,
    style=None,
) -> List[Tuple[plt.Figure, plt.Axes]]:

    Columns.XAxis.verify(x_axis)

    if x_axis == Columns.XAxis.DATE:
        if start_date is not None:
            df = df[df[Columns.DATE] >= pd.Timestamp(start_date)]

        df = remove_empty_leading_dates(df, count)
        description = FROM_FIXED_DATE_DESC
    elif x_axis == Columns.XAxis.DAYS_SINCE_OUTBREAK:
        df = df[df[Columns.DAYS_SINCE_OUTBREAK] >= -1]
        description = FROM_LOCAL_OUTBREAK_START_DESC
    else:
        x_axis.raise_for_unhandled_case()

    savefile_path, location_heading = get_savefile_path_and_location_heading(
        df, description, stage=stage, count=count
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
