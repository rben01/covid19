# %%
import itertools
from pathlib import Path
from typing import List, NewType, Tuple, Union

import bokeh.plotting as bplotting
import cmocean
import geopandas
import numpy as np
import pandas as pd
from bokeh.colors import RGB
from bokeh.embed import autoload_static
from bokeh.io import output_file
from bokeh.layouts import column as layout_column
from bokeh.layouts import gridplot
from bokeh.layouts import row as layout_row
from bokeh.models import (
    CDSView,
    ColorBar,
    ColumnDataSource,
    CustomJS,
    DateSlider,
    GroupFilter,
    HoverTool,
    LogColorMapper,
    RadioButtonGroup,
    SaveTool,
    Toggle,
)
from bokeh.models.formatters import NumeralTickFormatter, PrintfTickFormatter
from bokeh.models.tickers import FixedTicker
from bokeh.resources import CDN
from IPython.display import display  # noqa F401
from shapely.geometry import mapping as shapely_mapping
from typing_extensions import Literal

from constants import USA_STATE_CODES, Columns, Counting, DiseaseStage, Paths, Select

GEO_FIG_DIR: Path = Paths.FIGURES / "Geo"
DOD_DIFF_DIR: Path = GEO_FIG_DIR / "DayOverDayDiffs"
DOD_DIFF_DIR.mkdir(parents=True, exist_ok=True)

Polygon = List[Tuple[float, float]]
MultiPolygon = List[Tuple[Polygon]]
DateString = NewType("DateString", str)

LAT_COL = "Lat_"
LONG_COL = "Long_"


def get_geo_df() -> geopandas.GeoDataFrame:
    """Get geometry and lat/lon coords for each US state

    Bokeh's polygon plotting requires polygon vertices to be 1-D lists of floats with
    nan separating the connected regions; here we take the geopandas geometry and
    convert it into the desired lat/lon coords

    :return: GeoDataFrame containing, for each US state: 2-letter state code, geometry
    (boundary), and lists of lat/lon coords in bokeh-compatible format
    :rtype: geopandas.GeoDataFrame
    """

    geo_df: geopandas.GeoDataFrame = geopandas.read_file(
        Paths.DATA / "Geo" / "cb_2017_us_state_20m" / "cb_2017_us_state_20m.shp"
    ).to_crs(
        "EPSG:2163"  # US National Atlas Equal Area (Google it)
    )

    # geopandas gives us geometry as (Multi)Polygons
    # bokeh expects two lists, lat and long, each of which is a 1-D list of floats with
    # nan used to separate the discontiguous regions of a multi-polygon
    # We do this conversion here
    # Contrary to the usual English pairing "latitude/longitude", we always have long
    # precede lat here, as long is the x and lat is the y (and in this sense the
    # usual English specification is backwards)
    longs = []
    lats = []
    for multipoly in geo_df.geometry:
        multipoly_vertex_longs = []
        multipoly_vertex_lats = []
        # Shapely Polygons are mapped as 1-tuples containing a list of (x,y) 2-tuples
        # representing the vertices
        # MultiPolygons are lists thereof
        shape_info = shapely_mapping(multipoly)
        shape_type = shape_info["type"]
        assert shape_type in ["Polygon", "MultiPolygon"]

        polygons = shape_info["coordinates"]
        if shape_type == "Polygon":
            # Turn Polygon into 1-list of Polygons
            polygons = [polygons]

        polygons: MultiPolygon

        for poly_index, poly_tup in enumerate(polygons):
            poly_tup: Tuple[Polygon]

            # Extract the sole element of the 1-tuple
            poly = poly_tup[0]
            polygon_vertex_longs, polygon_vertex_lats = zip(*poly)

            multipoly_vertex_longs.extend(polygon_vertex_longs)
            multipoly_vertex_lats.extend(polygon_vertex_lats)

            # Add the nan dividers (but not after the last polygon)
            if poly_index < len(polygons) - 1:
                multipoly_vertex_longs.append("NaN")
                multipoly_vertex_lats.append("NaN")

        longs.append(multipoly_vertex_longs)
        lats.append(multipoly_vertex_lats)

    geo_df[LONG_COL] = longs
    geo_df[LAT_COL] = lats

    geo_df = geo_df.rename(columns={"STUSPS": Columns.TWO_LETTER_STATE_CODE})

    return geo_df


def make_usa_daybyday_interactive_timeline(
    states_df: pd.DataFrame,
    *,
    geo_df: geopandas.GeoDataFrame = None,
    stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
    count: Union[Counting, Literal[Select.ALL]] = Select.ALL,
) -> pd.DataFrame:

    Counting.verify(count, allow_select=True)
    DiseaseStage.verify(stage, allow_select=True)

    output_file("timeline.html", mode="cdn")

    STRING_DATE_COL = "String_Date_"
    FAKE_DATE_COL = "Fake_Date_"
    DIFF_COL = "Diff_"
    DIFF_COLOR_COL = "Diff_Color_"

    N_CBAR_BUCKETS = 6  # only used when bucketing colormap into discrete regions
    N_BUCKETS_BTWN_MAJOR_TICKS = 1
    N_MINOR_TICKS_BTWN_MAJOR_TICKS = 8  # major_1, minor_1, ..., minor_n, major_2
    N_CBAR_MAJOR_TICKS = N_CBAR_BUCKETS // N_BUCKETS_BTWN_MAJOR_TICKS + 1
    CMAP = cmocean.cm.matter
    # CMAP = ListedColormap(cmocean.cm.matter(np.linspace(0, 1, N_CBAR_BUCKETS)))
    # NOW_STR = datetime.now(timezone.utc).strftime(r"%b %-d, %Y at %H:%M UTC")
    DATE_FMT = r"%Y-%m-%d"

    ID_COLS = [
        Columns.TWO_LETTER_STATE_CODE,
        Columns.DATE,
        Columns.STAGE,
        Columns.COUNT_TYPE,
    ]

    if geo_df is None:
        geo_df = get_geo_df()

    if count is Select.ALL:
        count_list = list(Counting)
    else:
        count_list = [count]

    if stage is Select.ALL:
        stage_list = list(DiseaseStage)
    else:
        stage_list = [stage]

    count_list: List[Counting]
    stage_list: List[DiseaseStage]

    # Unadjust dates (see SaveFormats._adjust_dates)
    states_df = states_df.copy()
    normalized_dates = states_df[Columns.DATE].dt.normalize()
    is_at_midnight = states_df[Columns.DATE] == normalized_dates
    states_df.loc[is_at_midnight, Columns.DATE] -= pd.Timedelta(days=1)
    states_df.loc[~is_at_midnight, Columns.DATE] = normalized_dates[~is_at_midnight]

    min_date, max_date = states_df[Columns.DATE].agg(["min", "max"])
    dates: List[pd.Timestamp] = pd.date_range(start=min_date, end=max_date, freq="D")
    max_date_str = max_date.strftime(DATE_FMT)

    # Get day-by-day case diffs per location, date, stage, count-type
    case_diffs_df = states_df[
        (states_df[Columns.TWO_LETTER_STATE_CODE].isin(USA_STATE_CODES))
        & (~states_df[Columns.TWO_LETTER_STATE_CODE].isin(["AK", "HI"]))
    ].copy()

    # Make sure data exists for every date for every state so that the entire country is
    # plotted each day; fill missing data with 0 (missing really *is* as good as 0)
    state_date_stage_combos: pd.MultiIndex = pd.MultiIndex.from_product(
        [
            case_diffs_df[Columns.TWO_LETTER_STATE_CODE].unique(),
            dates,
            [s.name for s in DiseaseStage],
            [c.name for c in Counting],
        ],
        names=ID_COLS,
    )

    case_diffs_df = (
        state_date_stage_combos.to_frame(index=False)
        .merge(case_diffs_df, how="left", on=ID_COLS,)
        .sort_values(ID_COLS)
    )

    case_diffs_df[STRING_DATE_COL] = case_diffs_df[Columns.DATE].dt.strftime(DATE_FMT)

    case_diffs_df[Columns.CASE_COUNT] = case_diffs_df[Columns.CASE_COUNT].fillna(0)

    case_diffs_df[DIFF_COL] = case_diffs_df.groupby(
        [Columns.TWO_LETTER_STATE_CODE, Columns.STAGE, Columns.COUNT_TYPE]
    )[Columns.CASE_COUNT].diff()

    case_diffs_df = case_diffs_df[case_diffs_df[DIFF_COL].notna()]

    # case_diffs_df.loc[case_diffs_df[DIFF_COL] == 0, DIFF_COL] = "NaN"

    selected_data_df: pd.DataFrame = geo_df.merge(
        case_diffs_df, how="inner", on=Columns.TWO_LETTER_STATE_CODE,
    )[
        [
            Columns.TWO_LETTER_STATE_CODE,
            Columns.DATE,
            STRING_DATE_COL,
            Columns.STAGE,
            Columns.COUNT_TYPE,
            DIFF_COL,
        ]
    ]

    dates = case_diffs_df[Columns.DATE].unique()
    del case_diffs_df

    values_mins_maxs = (
        selected_data_df[selected_data_df[DIFF_COL] > 0]
        .groupby([Columns.STAGE, Columns.COUNT_TYPE])[DIFF_COL]
        .agg(["min", "max"])
    )

    vmins: pd.Series = values_mins_maxs["min"]
    vmaxs: pd.Series = values_mins_maxs["max"]

    pow10s_series: pd.Series = vmaxs.map(lambda x: int(10 ** (-np.floor(np.log10(x)))))

    vmins: dict = vmins.to_dict()
    vmaxs: dict = vmaxs.to_dict()

    for stage in DiseaseStage:
        _value_key = (stage.name, Counting.PER_CAPITA.name)
        _max_pow10 = pow10s_series.loc[(slice(None), Counting.PER_CAPITA.name)].max()
        vmins[_value_key] *= _max_pow10
        vmaxs[_value_key] *= _max_pow10
        pow10s_series[_value_key] = _max_pow10

    percap_pow10s: pd.Series = selected_data_df.apply(
        lambda row: pow10s_series[(row[Columns.STAGE], row[Columns.COUNT_TYPE])],
        axis=1,
    )

    _per_cap_rows = selected_data_df[Columns.COUNT_TYPE] == Counting.PER_CAPITA.name

    selected_data_df.loc[_per_cap_rows, DIFF_COL] *= percap_pow10s.loc[_per_cap_rows]

    # selected_data_df[Columns.DATE] = selected_data_df[Columns.DATE].dt.strftime(
    #     r"%Y-%m-%d"
    # )

    # Ideally we wouldn't have to pivot, and we could do a JIT join of state longs/lats
    # after filtering the data. Unfortunately this is not possible, and a long data
    # format leads to duplication of the very large long/lat lists; pivoting is how we
    # avoid that
    selected_data_df = selected_data_df.pivot_table(
        index=[Columns.TWO_LETTER_STATE_CODE, Columns.STAGE, Columns.COUNT_TYPE],
        columns=STRING_DATE_COL,
        values=DIFF_COL,
        aggfunc="first",
    ).reset_index()

    selected_data_df = selected_data_df.merge(
        geo_df[[Columns.TWO_LETTER_STATE_CODE, LONG_COL, LAT_COL]],
        how="inner",
        on=Columns.TWO_LETTER_STATE_CODE,
    )

    selected_data_df[DIFF_COL] = selected_data_df[max_date_str]
    selected_data_df[FAKE_DATE_COL] = max_date_str

    selected_data_df[DIFF_COLOR_COL] = np.where(
        selected_data_df[DIFF_COL] > 0, selected_data_df[DIFF_COL], "NaN"
    )

    bokeh_data_source = ColumnDataSource(selected_data_df)

    filters = [
        [
            GroupFilter(column_name=Columns.STAGE, group=stage.name),
            GroupFilter(column_name=Columns.COUNT_TYPE, group=count.name),
        ]
        for stage, count in itertools.product(stage_list, count_list)
    ]

    # Data is associated with the right endpoint of the data collection period,
    # e.g., data collected *on* March 20 is labeled March 21 -- this is done so that
    # data collected today (on the day the code is run) has a meaningful date
    # associated with it (today's current time)
    # Anyway, here we undo that and display data on the date it was collected
    # in order to show a meaningful title on the graph

    figures = []

    for subplot_index, (stage, count) in enumerate(
        itertools.product(stage_list, count_list)
    ):
        # fig = bplotting.figure()
        # ax: plt.Axes = fig.add_subplot(
        #     len(stage_list), len(count_list), subplot_index
        # )

        # # Add timestamp to top right axis
        # if subplot_index == 2:
        #     ax.text(
        #         1.25,  # Coords are arbitrary magic numbers
        #         1.23,
        #         f"Last updated {NOW_STR}",
        #         horizontalalignment="right",
        #         fontsize="small",
        #         transform=ax.transAxes,
        #     )

        view = CDSView(source=bokeh_data_source, filters=filters[subplot_index])

        vmin = vmins[(stage.name, count.name)]
        vmax = vmaxs[(stage.name, count.name)]

        # Set axes titles
        fig_stage_name: str = {
            DiseaseStage.CONFIRMED: "Cases",
            DiseaseStage.DEATH: "Deaths",
        }[stage]
        fig_title_components: List[str] = ["New Daily", fig_stage_name]

        if count is Counting.PER_CAPITA:
            formatter = PrintfTickFormatter(
                format=r"%2.3f"
            )  # BasicTickFormatter()  # NumeralTickFormatter(format="0.00[00]")
            # NumeralTickFormatter(format="0.0")
            label_standoff = 12
            _per_cap_denom = pow10s_series[(stage.name, count.name)]
            fig_title_components.append(f"Per {_per_cap_denom:,d} people")
        else:
            formatter = NumeralTickFormatter(format="0.0a")
            label_standoff = 8

        color_mapper = LogColorMapper(
            [
                # Convert matplotlib colormap to bokeh (list of hex strings)
                # https://stackoverflow.com/a/49934218
                RGB(*rgb).to_hex()
                for i, rgb in enumerate((255 * CMAP(range(256))).astype("int"))
            ],
            low=vmin,
            high=vmax,
            nan_color="#f2f2f2",
        )

        fig_title = " ".join(fig_title_components)

        hover_tool = HoverTool(
            tooltips=[
                ("Date", f"@{{{FAKE_DATE_COL}}}"),
                ("State", f"@{{{Columns.TWO_LETTER_STATE_CODE}}}"),
                ("Count", f"@{{{DIFF_COL}}}"),
            ],
            toggleable=False,
        )

        # Create figure object.
        p = bplotting.figure(
            title=fig_title,
            title_location="above",
            tools=[SaveTool(), hover_tool],
            toolbar_location=None,
            aspect_ratio=1.5,
            output_backend="webgl",
            lod_factor=100,
            lod_interval=1000,
            lod_threshold=1,
            lod_timeout=500,
        )

        p.xgrid.grid_line_color = None
        p.ygrid.grid_line_color = None
        # Add patch renderer to figure.
        p.patches(
            LONG_COL,
            LAT_COL,
            source=bokeh_data_source,
            view=view,
            fill_color={"field": DIFF_COLOR_COL, "transform": color_mapper},
            line_color="black",
            line_width=0.25,
            fill_alpha=1,
        )

        # Add evenly spaced ticks and their labels
        # First major, then minor
        # Adapted from https://stackoverflow.com/a/50314773
        bucket_size = (vmax / vmin) ** (1 / N_CBAR_BUCKETS)
        tick_dist = bucket_size ** N_BUCKETS_BTWN_MAJOR_TICKS

        # Simple log scale math
        major_tick_locs = (
            vmin
            * (tick_dist ** np.arange(0, N_CBAR_MAJOR_TICKS))
            # * (bucket_size ** 0.5) # Use this if centering ticks on buckets
        )
        # Get minor locs by linearly interpolating between major ticks
        minor_tick_locs = []
        for major_tick_index, this_major_tick in enumerate(major_tick_locs[:-1]):
            next_major_tick = major_tick_locs[major_tick_index + 1]

            # Get minor ticks as numbers in range [this_major_tick, next_major_tick]
            # and exclude the major ticks themselves (once we've used them to
            # compute the minor tick locs)
            minor_tick_locs.extend(
                np.linspace(
                    this_major_tick,
                    next_major_tick,
                    N_MINOR_TICKS_BTWN_MAJOR_TICKS + 2,
                )[1:-1]
            )

        # Define custom tick labels for color bar.
        # Create color bar.
        color_bar = ColorBar(
            color_mapper=color_mapper,
            ticker=FixedTicker(ticks=major_tick_locs, minor_ticks=minor_tick_locs),
            formatter=formatter,
            label_standoff=label_standoff,
            major_tick_out=0,
            major_tick_in=13,
            major_tick_line_color="white",
            major_tick_line_width=1,
            minor_tick_out=0,
            minor_tick_in=5,
            minor_tick_line_color="white",
            minor_tick_line_width=1,
            location=(0, 0),
            border_line_color=None,
            bar_line_color=None,
            orientation="vertical",
        )

        # Specify figure layout.
        p.add_layout(color_bar, "right")

        # Display figure inline in Jupyter Notebook.
        p.hover.point_policy = "follow_mouse"

        # Bokeh axes (and most other things) are splattable
        p.axis.visible = False

        figures.append(p)

    # 2x2 grid (for now)
    plot_layout = [
        gridplot(
            figures,
            ncols=len(count_list),
            sizing_mode="scale_both",
            toolbar_location=None,
        )
    ]

    # for i, g in enumerate(plot_layout):
    #     plot_layout[i] = layout_row(g, sizing_mode="scale_both")

    _TIMER_KEY = "'timer'"
    _IS_ACTIVE_KEY = "'isActive'"
    _SELECTED_INDEX_KEY = "'selectedIndex'"
    _BASE_INTERVAL_KEY = "'BASE_INTERVAL'"
    _TIMER_START_DATE = "'startDate'"
    _TIMER_ELAPSED_TIME_MS = "'elapsedTime'"
    _SPEEDS_KEY = "'SPEEDS'"
    _PLAYBACK_INFO = "playbackInfo"

    _PBI_TIMER = f"{_PLAYBACK_INFO}[{_TIMER_KEY}]"
    _PBI_IS_ACTIVE = f"{_PLAYBACK_INFO}[{_IS_ACTIVE_KEY}]"
    _PBI_SELECTED_INDEX = f"{_PLAYBACK_INFO}[{_SELECTED_INDEX_KEY}]"
    _PBI_TIMER_START_DATE = f"{_PLAYBACK_INFO}[{_TIMER_START_DATE}]"
    _PBI_TIMER_ELAPSED_TIME_MS = f"{_PLAYBACK_INFO}[{_TIMER_ELAPSED_TIME_MS}]"
    _PBI_BASE_INTERVAL = f"{_PLAYBACK_INFO}[{_BASE_INTERVAL_KEY}]"
    _PBI_SPEEDS = f"{_PLAYBACK_INFO}[{_SPEEDS_KEY}]"
    _PBI_CURR_INTERVAL = f"{_PBI_BASE_INTERVAL} / {_PBI_SPEEDS}[{_PBI_SELECTED_INDEX}]"

    _SETUP_WINDOW_PLAYBACK_INFO = f"""
        if (typeof(window._playbackInfo) === 'undefined') {{
            window._playbackInfo = {{
                {_TIMER_KEY}: null,
                {_IS_ACTIVE_KEY}: false,
                {_SELECTED_INDEX_KEY}: 1,
                {_TIMER_START_DATE}: null,
                {_TIMER_ELAPSED_TIME_MS}: 0,
                {_BASE_INTERVAL_KEY}: 1000,
                {_SPEEDS_KEY}: [0.5, 1.0, 2.0]
            }};
        }}

        var {_PLAYBACK_INFO} = window._playbackInfo
    """

    _DEFFUN_INCR_DATE = f"""
        function updateDate() {{
            {_PBI_TIMER_START_DATE} = new Date();
            {_PBI_TIMER_ELAPSED_TIME_MS} = 0
            if (dateSlider.value < maxDate) {{
                dateSlider.value += 86400000;
            }}

            if (dateSlider.value >= maxDate) {{
                console.log('reached end')
                clearInterval({_PBI_TIMER});
                {_PBI_IS_ACTIVE} = false;
                playPauseButton.active = false;
                playPauseButton.change.emit();
            }}

            dateSlider.change.emit();
        }}
    """

    _DO_START_TIMER = f"""
        {_PBI_TIMER_START_DATE} = new Date();

        const initialInterval = (
            {_PBI_TIMER_ELAPSED_TIME_MS} === 0 ?
            0 :
            Math.max({_PBI_CURR_INTERVAL} - {_PBI_TIMER_ELAPSED_TIME_MS}, 0)
        );


        {_PBI_TIMER} = setTimeout(
            startLoopTimer,
            initialInterval
        );

        function startLoopTimer() {{
            updateDate();
            if ({_PBI_IS_ACTIVE}) {{
                {_PBI_TIMER} = setInterval(updateDate, {_PBI_CURR_INTERVAL})
            }}
        }}
    """

    _DO_STOP_TIMER = f"""
        const now = new Date();
        {_PBI_TIMER_ELAPSED_TIME_MS} += (
            now.getTime() - {_PBI_TIMER_START_DATE}.getTime()
        );
        clearInterval({_PBI_TIMER});
    """

    update_on_date_change_callback = CustomJS(
        args={"source": bokeh_data_source},
        code=f"""

        {_SETUP_WINDOW_PLAYBACK_INFO}

        const sliderValue = cb_obj.value;
        const sliderDate = new Date(sliderValue)
        // Ugh, actually requiring the date to be YYYY-MM-DD
        const dateStr = sliderDate.toISOString().split('T')[0]

        const data = source.data;

        {_PBI_TIMER_ELAPSED_TIME_MS} = 0

        if (typeof(data[dateStr]) !== 'undefined') {{
            data['{DIFF_COL}'] = data[dateStr]

            const diffCol = data['{DIFF_COL}'];
            const diffColorCol = data['{DIFF_COLOR_COL}'];
            const fakeDateCol = data['{FAKE_DATE_COL}']

            for (var i = 0; i < data['{DIFF_COL}'].length; i++) {{
                const diff = diffCol[i]
                if (diff == 0) {{
                    diffColorCol[i] = 'NaN';
                }} else {{
                    diffColorCol[i] = diff;
                }}

                fakeDateCol[i] = dateStr;
            }}

            source.change.emit();

        }}

        """,
    )

    # Taking day-over-day diffs means the min slider day is one more than the min data
    # date
    min_slider_date = min_date + pd.Timedelta(days=1)
    date_slider = DateSlider(
        start=min_slider_date,
        end=max_date,
        value=max_date,
        step=1,
        sizing_mode="stretch_width",
        width_policy="fit",
    )
    date_slider.js_on_change("value", update_on_date_change_callback)

    play_pause_button = Toggle(
        label="Play/pause (paused)",
        button_type="success",
        active=False,
        sizing_mode="stretch_width",
    )

    animate_playback_callback = CustomJS(
        args={
            "dateSlider": date_slider,
            "playPauseButton": play_pause_button,
            "maxDate": max_date,
            "minDate": min_slider_date,
        },
        code=f"""

        {_SETUP_WINDOW_PLAYBACK_INFO}
        {_DEFFUN_INCR_DATE}

        if (dateSlider.value >= maxDate) {{
            if (playPauseButton.active) {{
                dateSlider.value = minDate;
                dateSlider.change.emit();

                // Hack to get timer to wait after date slider wraps; any nonzero number
                // works but the smaller the better
                {_PBI_TIMER_ELAPSED_TIME_MS} = 1;
            }}
        }}

        const active = cb_obj.active;
        {_PBI_IS_ACTIVE} = active;

        if (active) {{
            playPauseButton.label = 'Play/pause (playing)'
            {_DO_START_TIMER}
        }} else {{
            playPauseButton.label = 'Play/pause (paused)'
            {_DO_STOP_TIMER}
        }}

        """,
    )

    play_pause_button.js_on_click(animate_playback_callback)

    change_playback_speed_callback = CustomJS(
        args={
            "dateSlider": date_slider,
            "playPauseButton": play_pause_button,
            "maxDate": max_date,
        },
        code=f"""

        {_SETUP_WINDOW_PLAYBACK_INFO}
        {_DEFFUN_INCR_DATE}

        if ({_PBI_TIMER} !== null) {{
            {_DO_STOP_TIMER}
        }}

        const selectedIndex = cb_obj.active;
        {_PBI_SELECTED_INDEX} = selectedIndex;

        if ({_PBI_IS_ACTIVE}) {{
            {_DO_START_TIMER}
        }}

        console.log({_PLAYBACK_INFO})

    """,
    )

    playback_speed_radio = RadioButtonGroup(
        labels=["0.5x speed", "1x speed", "2x speed"],
        active=1,
        sizing_mode="stretch_width",
    )
    playback_speed_radio.js_on_click(change_playback_speed_callback)

    plot_layout.append(
        layout_column(
            [
                date_slider,
                layout_row(
                    [play_pause_button, playback_speed_radio], height_policy="min",
                ),
            ],
            width_policy="fit",
            height_policy="min",
        )
    )
    plot_layout = layout_column(plot_layout, sizing_mode="scale_both")

    # grid = gridplot(figures, ncols=len(count_list), sizing_mode="stretch_both")

    # show(grid)

    js_path = "load_bokeh.js"
    js_code, tag_code = autoload_static(plot_layout, CDN, js_path)

    with open(Paths.DOCS / js_path, "w") as s, open(
        Paths.DOCS / "usa_states_interactive_div.html", "w"
    ) as d:
        s.write(js_code)
        d.write(tag_code)

    return (js_code, tag_code)


if __name__ == "__main__":
    df = make_usa_daybyday_interactive_timeline(
        None, stage=Select.ALL, count=Select.ALL
    )
