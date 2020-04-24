# %%
import enum
import functools
import itertools
from pathlib import Path
from typing import Callable, List, Tuple, Union

import bokeh.plotting as bplotting
import cmocean
import geopandas
import numpy as np
import pandas as pd
from bokeh.colors import RGB
from bokeh.embed import autoload_static
from bokeh.layouts import column as layout_column
from bokeh.layouts import gridplot
from bokeh.layouts import row as layout_row
from bokeh.models import (
    BoxZoomTool,
    CDSView,
    ColorBar,
    ColumnDataSource,
    CustomJS,
    DateSlider,
    GroupFilter,
    HoverTool,
    LogColorMapper,
    PanTool,
    RadioButtonGroup,
    Range1d,
    ResetTool,
    Toggle,
    ZoomInTool,
    ZoomOutTool,
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
DateString = str
BokehColor = str
InfoForAutoload = Tuple[str, str]

LAT_COL = "Lat_"
LONG_COL = "Long_"
REGION_NAME_COL = "Region_Name_"


class WorldCRS(enum.Enum):
    EQUIRECTANGULAR: "WorldCRS" = "EPSG:4087"
    ECKERT_IV: "WorldCRS" = "ESRI:54012"
    LOXIMUTHAL: "WorldCRS" = "ESRI:54023"

    # If you don't care about faithfully representing data and hate the truth in
    # general, you can use this as a case
    # WEB_MERCATOR: "WorldCRS" = "EPSG:3857"

    @staticmethod
    def default() -> "WorldCRS":
        return WorldCRS.EQUIRECTANGULAR

    def get_axis_info(self) -> dict:
        if self is WorldCRS.EQUIRECTANGULAR:
            return {
                "x_range": (-2.125e7, 2.125e7),
                "y_range": (-7e6, 1e7),
                "min_interval": 1e6,
                "plot_aspect_ratio": 2,
            }

        raise NotImplementedError(
            "Just use WorldCRS.EQUIRECTANGULAR; it's the best EPSG"
        )


def get_longs_lats(geo_df: geopandas.GeoDataFrame) -> geopandas.GeoDataFrame:

    geo_df = geo_df.copy()

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
        # I don't know why they use 1-tuples instead of just tup[0], but they do
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

    return geo_df


@functools.lru_cache(None)
def get_usa_states_geo_df() -> geopandas.GeoDataFrame:
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
    ).rename(
        columns={"STUSPS": REGION_NAME_COL}, errors="raise"
    )

    return get_longs_lats(geo_df)


@functools.lru_cache(None)
def get_countries_geo_df() -> geopandas.GeoDataFrame:

    geo_df: geopandas.GeoDataFrame = geopandas.read_file(
        Paths.DATA
        / "Geo"
        / "ne_110m_admin_0_map_units"
        / "ne_110m_admin_0_map_units.shp"
    ).to_crs(WorldCRS.default().value)

    # display(geo_df)
    # display(geo_df.columns)
    geo_df = geo_df.rename(columns={"ADMIN": REGION_NAME_COL}, errors="raise")

    geo_df[REGION_NAME_COL] = (
        geo_df[REGION_NAME_COL]
        .map(
            {
                "Central African Republic": "Central African Rep.",
                "Democratic Republic of the Congo": "Dem. Rep. Congo",
                "Equatorial Guinea": "Eq. Guinea",
                "eSwatini": "Eswatini",
                "Georgia (Country)": "Georgia (country)",
                "South Sudan": "S. Sudan",
                "United Arab Emirates": "UAE",
                "United Kingdom": "Britain",
                "Western Sahara": "W. Sahara",
                "United States of America": "United States",
            }
        )
        .fillna(geo_df[REGION_NAME_COL])
    )

    return get_longs_lats(geo_df)


def __make_daybyday_interactive_timeline(
    df: pd.DataFrame,
    *,
    geo_df: geopandas.GeoDataFrame,
    value_col: str,
    transform_df_func: Callable[[pd.DataFrame], pd.DataFrame] = None,
    stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
    count: Union[Counting, Literal[Select.ALL]] = Select.ALL,
    out_file_basename: str,
    subplot_title_prefix,
    plot_aspect_ratio: float = None,
    cmap=None,
    n_cbar_buckets: int = None,
    n_buckets_btwn_major_ticks: int = None,
    n_minor_ticks_btwn_major_ticks: int = None,
    per_capita_denominator: int = None,
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
    min_interval: float,
) -> InfoForAutoload:

    Counting.verify(count, allow_select=True)
    DiseaseStage.verify(stage, allow_select=True)

    STRING_DATE_COL = "String_Date_"
    FAKE_DATE_COL = "Fake_Date_"
    COLOR_COL = "Color_"

    DATE_FMT = r"%Y-%m-%d"
    ID_COLS = [
        REGION_NAME_COL,
        Columns.DATE,
        Columns.STAGE,
        Columns.COUNT_TYPE,
    ]

    if cmap is None:
        cmap = cmocean.cm.matter

    if n_cbar_buckets is None:
        n_cbar_buckets = 6

    if n_buckets_btwn_major_ticks is None:
        n_buckets_btwn_major_ticks = 1

    if n_minor_ticks_btwn_major_ticks is None:
        n_minor_ticks_btwn_major_ticks = 8

    n_cbar_major_ticks = n_cbar_buckets // n_buckets_btwn_major_ticks + 1

    try:
        color_list = [
            # Convert matplotlib colormap to bokeh (list of hex strings)
            # https://stackoverflow.com/a/49934218
            RGB(*rgb).to_hex()
            for i, rgb in enumerate((255 * cmap(range(256))).astype("int"))
        ]
    except TypeError:
        color_list = cmap

    color_list: List[BokehColor]

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

    df = df.copy()

    # Unadjust dates (see SaveFormats._adjust_dates)
    normalized_dates = df[Columns.DATE].dt.normalize()
    is_at_midnight = df[Columns.DATE] == normalized_dates
    df.loc[is_at_midnight, Columns.DATE] -= pd.Timedelta(days=1)
    df.loc[~is_at_midnight, Columns.DATE] = normalized_dates[~is_at_midnight]

    min_date, max_date = df[Columns.DATE].agg(["min", "max"])
    dates: List[pd.Timestamp] = pd.date_range(start=min_date, end=max_date, freq="D")
    max_date_str = max_date.strftime(DATE_FMT)

    # Get day-by-day case diffs per location, date, stage, count-type

    # Make sure data exists for every date for every state so that the entire country is
    # plotted each day; fill missing data with 0 (missing really *is* as good as 0)
    # enums will be replaced by their name (this is kind of important)
    id_cols_product: pd.MultiIndex = pd.MultiIndex.from_product(
        [
            df[REGION_NAME_COL].unique(),
            dates,
            [s.name for s in DiseaseStage],
            [c.name for c in Counting],
        ],
        names=ID_COLS,
    )

    df = (
        id_cols_product.to_frame(index=False)
        .merge(df, how="left", on=ID_COLS,)
        .sort_values(ID_COLS)
    )

    df[STRING_DATE_COL] = df[Columns.DATE].dt.strftime(DATE_FMT)
    df[Columns.CASE_COUNT] = df[Columns.CASE_COUNT].fillna(0)

    if transform_df_func is not None:
        df = transform_df_func(df)

    df = geo_df.merge(df, how="inner", on=REGION_NAME_COL,)[
        [
            REGION_NAME_COL,
            Columns.DATE,
            STRING_DATE_COL,
            Columns.STAGE,
            Columns.COUNT_TYPE,
            value_col,
        ]
    ]

    dates = df[Columns.DATE].unique()

    values_mins_maxs = (
        df[df[value_col] > 0]
        .groupby([Columns.STAGE, Columns.COUNT_TYPE])[value_col]
        .agg(["min", "max"])
    )

    vmins: pd.Series = values_mins_maxs["min"]
    vmaxs: pd.Series = values_mins_maxs["max"]

    pow10s_series: pd.Series = vmaxs.map(lambda x: int(10 ** (-np.floor(np.log10(x)))))

    # _pow_10s_series_dict = {}
    # for stage in DiseaseStage:
    #     _pow_10s_series_dict.update(
    #         {
    #             (stage.name, Counting.TOTAL_CASES.name): 100000,
    #             (stage.name, Counting.PER_CAPITA.name): 10000,
    #         }
    #     )

    # pow10s_series = pd.Series(_pow_10s_series_dict)

    vmins: dict = vmins.to_dict()
    vmaxs: dict = vmaxs.to_dict()

    for stage in DiseaseStage:
        _value_key = (stage.name, Counting.PER_CAPITA.name)
        if per_capita_denominator is None:
            _max_pow10 = pow10s_series.loc[
                (slice(None), Counting.PER_CAPITA.name)
            ].max()
        else:
            _max_pow10 = per_capita_denominator

        vmins[_value_key] *= _max_pow10
        vmaxs[_value_key] *= _max_pow10
        pow10s_series[_value_key] = _max_pow10

    percap_pow10s: pd.Series = df.apply(
        lambda row: pow10s_series[(row[Columns.STAGE], row[Columns.COUNT_TYPE])],
        axis=1,
    )

    _per_cap_rows = df[Columns.COUNT_TYPE] == Counting.PER_CAPITA.name
    df.loc[_per_cap_rows, value_col] *= percap_pow10s.loc[_per_cap_rows]

    # Ideally we wouldn't have to pivot, and we could do a JIT join of state longs/lats
    # after filtering the data. Unfortunately this is not possible, and a long data
    # format leads to duplication of the very large long/lat lists; pivoting is how we
    # avoid that
    df = (
        df.pivot_table(
            index=[REGION_NAME_COL, Columns.STAGE, Columns.COUNT_TYPE],
            columns=STRING_DATE_COL,
            values=value_col,
            aggfunc="first",
        )
        .reset_index()
        .merge(
            geo_df[[REGION_NAME_COL, LONG_COL, LAT_COL]],
            how="inner",
            on=REGION_NAME_COL,
        )
    )

    df[value_col] = df[max_date_str]
    df[FAKE_DATE_COL] = max_date_str

    df[COLOR_COL] = np.where(df[value_col] > 0, df[value_col], "NaN")

    bokeh_data_source = ColumnDataSource(df)

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

        fig_title_components: List[str] = []
        if subplot_title_prefix is not None:
            fig_title_components.append(subplot_title_prefix)

        fig_title_components.append(fig_stage_name)

        if count is Counting.PER_CAPITA:
            _per_cap_denom = pow10s_series[(stage.name, count.name)]
            fig_title_components.append(f"Per {_per_cap_denom:,d} people")
            formatter = PrintfTickFormatter(format=r"%2.3f")
            label_standoff = 12
            tooltip_fmt = "{0.000}"
        else:
            formatter = NumeralTickFormatter(format="0.0a")
            label_standoff = 10
            tooltip_fmt = "{0}"

        color_mapper = LogColorMapper(
            color_list, low=vmin, high=vmax, nan_color="#f2f2f2",
        )

        fig_title = " ".join(fig_title_components)

        hover_tool = HoverTool(
            tooltips=[
                ("Date", f"@{{{FAKE_DATE_COL}}}"),
                ("State", f"@{{{REGION_NAME_COL}}}"),
                ("Count", f"@{{{value_col}}}{tooltip_fmt}"),
            ],
            toggleable=False,
        )

        if plot_aspect_ratio is None:
            if x_range is None or y_range is None:
                raise ValueError(
                    "Must provide both `x_range` and `y_range`"
                    + " when `plot_aspect_ratio` is None"
                )
            plot_aspect_ratio = (x_range[1] - x_range[0]) / (y_range[1] - y_range[0])

        # Create figure object
        p = bplotting.figure(
            title=fig_title,
            title_location="above",
            tools=[
                hover_tool,
                BoxZoomTool(match_aspect=True),
                PanTool(),
                ZoomInTool(),
                ZoomOutTool(),
                ResetTool(),
            ],
            aspect_ratio=plot_aspect_ratio,
            output_backend="webgl",
            lod_factor=10,
            lod_interval=400,
            lod_threshold=1,
            lod_timeout=300,
        )

        p.xgrid.grid_line_color = None
        p.ygrid.grid_line_color = None
        # Add patch renderer to figure.
        p.patches(
            LONG_COL,
            LAT_COL,
            source=bokeh_data_source,
            view=view,
            fill_color={"field": COLOR_COL, "transform": color_mapper},
            line_color="black",
            line_width=0.25,
            fill_alpha=1,
        )

        # Add evenly spaced ticks and their labels
        # First major, then minor
        # Adapted from https://stackoverflow.com/a/50314773
        bucket_size = (vmax / vmin) ** (1 / n_cbar_buckets)
        tick_dist = bucket_size ** n_buckets_btwn_major_ticks

        # Simple log scale math
        major_tick_locs = (
            vmin
            * (tick_dist ** np.arange(0, n_cbar_major_ticks))
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
                    n_minor_ticks_btwn_major_ticks + 2,
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

    # Make all figs pan and zoom together
    figs_iter = iter(np.ravel(figures))
    anchor_fig = next(figs_iter)

    if x_range is not None and y_range is not None:
        data_aspect_ratio = (x_range[1] - x_range[0]) / (y_range[1] - y_range[0])
    else:
        data_aspect_ratio = plot_aspect_ratio

    if x_range is not None:
        anchor_fig.x_range = Range1d(
            *x_range, bounds="auto", min_interval=min_interval * data_aspect_ratio
        )

    if y_range is not None:
        anchor_fig.y_range = Range1d(*y_range, bounds="auto", min_interval=min_interval)

    for fig in figs_iter:
        fig.x_range = anchor_fig.x_range
        fig.y_range = anchor_fig.y_range

    # 2x2 grid (for now)
    plot_layout = [
        gridplot(
            figures,
            ncols=len(count_list),
            sizing_mode="scale_both",
            toolbar_location="above",
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
        let prev_val = null;
        source.inspect.connect(v => prev_val = v);

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
                playPauseButton.label = 'Restart';
            }}

            dateSlider.change.emit();

            if (prev_val !== null) {{
                source.inspect.emit(prev_val);
            }}
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
            data['{value_col}'] = data[dateStr]

            const valueCol = data['{value_col}'];
            const colorCol = data['{COLOR_COL}'];
            const fakeDateCol = data['{FAKE_DATE_COL}']

            for (var i = 0; i < data['{value_col}'].length; i++) {{
                const value = valueCol[i]
                if (value == 0) {{
                    colorCol[i] = 'NaN';
                }} else {{
                    colorCol[i] = value;
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
            "source": bokeh_data_source,
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
            "source": bokeh_data_source,
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
        }} else {{
            {_PBI_TIMER_ELAPSED_TIME_MS} = 0
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

    js_path = str(Path(out_file_basename + "_autoload").with_suffix(".js"))
    tag_html_path = str(Path(out_file_basename + "_div_tag").with_suffix(".html"))

    js_code, tag_code = autoload_static(plot_layout, CDN, js_path)

    with open(Paths.DOCS / js_path, "w") as s, open(
        Paths.DOCS / tag_html_path, "w"
    ) as d:
        s.write(js_code)
        d.write(tag_code)

    return (js_code, tag_code)


def _make_daybyday_total_interactive_timeline(
    df: pd.DataFrame,
    *,
    geo_df: geopandas.GeoDataFrame,
    stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
    count: Union[Counting, Literal[Select.ALL]] = Select.ALL,
    out_file_basename: str,
    plot_aspect_ratio: float = None,
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
    min_interval: float,
) -> InfoForAutoload:

    return __make_daybyday_interactive_timeline(
        df,
        geo_df=geo_df,
        value_col=Columns.CASE_COUNT,
        stage=stage,
        count=count,
        out_file_basename=f"{out_file_basename}_total_interactive",
        subplot_title_prefix="Total",
        plot_aspect_ratio=plot_aspect_ratio,
        per_capita_denominator=100_000,
        x_range=x_range,
        y_range=y_range,
        min_interval=min_interval,
    )


def _make_daybyday_diff_interactive_timeline(
    df: pd.DataFrame,
    *,
    geo_df: geopandas.GeoDataFrame,
    stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
    count: Union[Counting, Literal[Select.ALL]] = Select.ALL,
    out_file_basename: str,
    plot_aspect_ratio: float = None,
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
    min_interval: float,
) -> InfoForAutoload:

    DIFF_COL = "Diff_"

    def get_case_diffs(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df[DIFF_COL] = df.groupby([REGION_NAME_COL, Columns.STAGE, Columns.COUNT_TYPE])[
            Columns.CASE_COUNT
        ].diff()

        df = df[df[DIFF_COL].notna()]
        return df

    return __make_daybyday_interactive_timeline(
        df,
        geo_df=geo_df,
        value_col=DIFF_COL,
        transform_df_func=get_case_diffs,
        stage=stage,
        count=count,
        out_file_basename=f"{out_file_basename}_diff_interactive",
        subplot_title_prefix="New Daily",
        plot_aspect_ratio=plot_aspect_ratio,
        per_capita_denominator=10000,
        x_range=x_range,
        y_range=y_range,
        min_interval=min_interval,
    )


def __assign_region_name_col(df: pd.DataFrame, region_name_col: str) -> pd.DataFrame:
    return df.rename(columns={region_name_col: REGION_NAME_COL})


def _prepare_usa_states_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()[
        (df[Columns.TWO_LETTER_STATE_CODE].isin(USA_STATE_CODES))
        & (~df[Columns.TWO_LETTER_STATE_CODE].isin(["AK", "HI"]))
    ]

    df = __assign_region_name_col(df, Columns.TWO_LETTER_STATE_CODE)

    return df


def _prepare_countries_df(df: pd.DataFrame) -> pd.DataFrame:
    return __assign_region_name_col(df, Columns.COUNTRY)


@functools.lru_cache(None)
def _get_usa_kwargs() -> dict:
    return {
        "out_file_basename": "usa_states",
        "x_range": (-2.25e6, 2.7e6),
        "y_range": (-2.3e6, 9e5),
        "min_interval": 8.5e5,
    }


@functools.lru_cache(None)
def _get_countries_kwargs() -> dict:
    return {
        "out_file_basename": "countries",
        **WorldCRS.default().get_axis_info(),
    }


def make_usa_daybyday_total_interactive_timeline(
    states_df: pd.DataFrame,
    *,
    usa_states_geo_df: geopandas.GeoDataFrame = None,
    stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
    count: Union[Counting, Literal[Select.ALL]] = Select.ALL,
) -> Tuple:

    states_df = _prepare_usa_states_df(states_df)

    if usa_states_geo_df is None:
        usa_states_geo_df = get_usa_states_geo_df()

    return _make_daybyday_total_interactive_timeline(
        states_df,
        geo_df=usa_states_geo_df,
        stage=stage,
        count=count,
        **_get_usa_kwargs(),
    )


def make_usa_daybyday_diff_interactive_timeline(
    states_df: pd.DataFrame,
    *,
    usa_states_geo_df: geopandas.GeoDataFrame = None,
    stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
    count: Union[Counting, Literal[Select.ALL]] = Select.ALL,
) -> InfoForAutoload:

    states_df = _prepare_usa_states_df(states_df)

    if usa_states_geo_df is None:

        usa_states_geo_df = get_usa_states_geo_df()

    return _make_daybyday_diff_interactive_timeline(
        states_df,
        geo_df=usa_states_geo_df,
        stage=stage,
        count=count,
        **_get_usa_kwargs(),
    )


def make_countries_daybyday_total_interactive_timeline(
    countries_df: pd.DataFrame,
    *,
    countries_geo_df: geopandas.GeoDataFrame = None,
    stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
    count: Union[Counting, Literal[Select.ALL]] = Select.ALL,
) -> InfoForAutoload:

    countries_df = _prepare_countries_df(countries_df)

    if countries_geo_df is None:
        countries_geo_df = get_countries_geo_df()

    return _make_daybyday_total_interactive_timeline(
        countries_df,
        geo_df=countries_geo_df,
        stage=stage,
        count=count,
        **_get_countries_kwargs(),
    )


def make_countries_daybyday_diff_interactive_timeline(
    countries_df: pd.DataFrame,
    *,
    countries_geo_df: geopandas.GeoDataFrame = None,
    stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
    count: Union[Counting, Literal[Select.ALL]] = Select.ALL,
) -> InfoForAutoload:

    countries_df = _prepare_countries_df(countries_df)

    if countries_geo_df is None:
        countries_geo_df = get_countries_geo_df()

    return _make_daybyday_diff_interactive_timeline(
        countries_df,
        geo_df=countries_geo_df,
        stage=stage,
        count=count,
        **_get_countries_kwargs(),
    )


if __name__ == "__main__":
    display(get_countries_geo_df())
    # from case_tracker import get_df, get_usa_states_df

    # usa_df = get_usa_states_df(get_df(refresh_local_data=False))
    # make_usa_daybyday_total_interactive_timeline(
    #     usa_df, stage=Select.ALL, count=Select.ALL
    # )
    # make_usa_daybyday_diff_interactive_timeline(
    #     usa_df, stage=Select.ALL, count=Select.ALL
    # )


# %%
