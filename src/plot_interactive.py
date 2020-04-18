# %%
from pathlib import Path
from typing import List, Optional, Tuple, Union

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing_extensions import Literal

from constants import (
    CaseInfo,
    CaseTypes,
    Columns,
    Counting,
    DiseaseStage,
    InfoField,
    Select,
)
from plotting_utils import (
    COLOR,
    LocationColorMapping,
    get_current_case_data,
    get_savefile_path_and_location_heading,
    remove_empty_leading_dates,
)


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
) -> List[go.Figure]:

    DiseaseStage.verify(stage, allow_select=True)
    Counting.verify(count)
    Columns.XAxis.verify(x_axis)

    SORTED_POSITION = "Sorted_Position_"

    figs_and_axes = []

    if plot_size is None:
        plot_size = (10, 12)

    # fig, ax = plt.subplots(figsize=(8, 8), dpi=200, facecolor="white")
    # fig: plt.Figure
    # ax: plt.Axes

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
    # color_mapping = color_mapping.copy()
    # color_mapping = color_mapping[
    #     color_mapping[Columns.LOCATION_NAME].isin(
    #         current_case_counts[Columns.LOCATION_NAME]
    #     )
    # ]
    # color_mapping[SORTED_POSITION] = color_mapping[Columns.LOCATION_NAME].map(
    #     current_case_counts[Columns.LOCATION_NAME].tolist().index
    # )
    # color_mapping = color_mapping.sort_values(SORTED_POSITION)

    config_df = CaseInfo.get_info_items_for(
        InfoField.CASE_TYPE, InfoField.DASH_STYLE, stage=stage, count=count
    )

    dashes = {
        CaseTypes.CONFIRMED: "solid",
        CaseTypes.DEATHS: "dash",
    }
    display(dashes)

    fig = px.line(
        data_frame=df,
        log_y=True,
        x=x_axis.column(),
        y=Columns.CASE_COUNT,
        color=Columns.LOCATION_NAME,
        line_dash=Columns.CASE_TYPE,
        line_dash_map=dashes,
    )

    return fig

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
) -> go.Figure:
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


_plot_helper(
    s,
    stage=Select.ALL,
    count=Counting.TOTAL_CASES,
    x_axis=Columns.XAxis.DATE,
    savefile_path=None,
)
