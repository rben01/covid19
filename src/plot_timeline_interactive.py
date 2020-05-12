# %%
import enum
import functools
import itertools
import re
import subprocess
import uuid
from pathlib import Path
from typing import Callable, List, NewType, Tuple, Union

import bokeh.plotting as bplotting
import cmocean
import geopandas
import numpy as np
import pandas as pd
from bokeh.colors import RGB
from bokeh.embed import autoload_static
from bokeh.io import export_png
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
    Title,
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
from plotting_utils import resize_to_even_dims

GEO_DATA_DIR = Paths.DATA / "Geo"
GEO_FIG_DIR: Path = Paths.FIGURES / "Geo"
PNG_SAVE_ROOT_DIR: Path = GEO_FIG_DIR / "BokehInteractiveStatic"
PNG_SAVE_ROOT_DIR.mkdir(parents=True, exist_ok=True)

Polygon = NewType("Polygon", List[Tuple[float, float]])
MultiPolygon = NewType("MultiPolygon", List[Tuple[Polygon]])
DateString = NewType("DateString", str)
BokehColor = NewType("BokehColor", str)
InfoForAutoload = NewType("InfoForAutoload", Tuple[str, str])

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
        """Get the default CRS (effectively a file-wide constant, except you can't
        define constants in enums b/c they'll be interpreted as cases)

        :return: The default case
        :rtype: WorldCRS
        """
        return WorldCRS.EQUIRECTANGULAR

    def get_axis_info(self) -> dict:
        """Get axis parameters appropriate for this CRS

        CRSes project the world into different coordinate systems (like, some are
        long/lat, some are numbers in the hundreds of thousands). This function maps
        CRSes to appropriate axis kwargs for plotting a choropleth in the given CRS.
        The kwargs are used to construct Bokeh's Range1d, but there isn't a direct 1:1
        correspondence between kwarg keys and Range1d's parameters (so you can use any
        keys you want, but you then have to map them back to Range1d parameters).

        :raises NotImplementedError: If `self` is anything other than EQUIRECTANGULAR
        :return: The arguments to be
        :rtype: dict
        """
        if self is WorldCRS.EQUIRECTANGULAR:
            return {
                "x_range": (-2.125e7, 2.125e7),
                "y_range": (-7e6, 1e7),
                "min_visible_y_range": 1e6,
                "plot_aspect_ratio": 2,
            }

        raise NotImplementedError(
            "Just use WorldCRS.EQUIRECTANGULAR; it's the best EPSG"
        )


def get_longs_lats(geo_df: geopandas.GeoDataFrame) -> geopandas.GeoDataFrame:
    """Given a geopandas.GeoDataFrame, add two columns, long and lat, containing the
    coordinates of the geometry's (multi)polygons in a format appropriate for Bokeh

    :param geo_df: The GeoDataFrame for the region of interest (e.g., the world, the US)
    :type geo_df: geopandas.GeoDataFrame
    :return: The same GeoDataFrame with two additional columns, one with long and one
    with lat. These columns' elements are lists of (multi)polygon vertices.
    :rtype: geopandas.GeoDataFrame
    """

    geo_df = geo_df.copy()

    # geopandas gives us geometry as (Multi)Polygons
    # bokeh expects two lists, lat and long, each of which is a 1-D list of floats with
    # "NaN" used to separate the discontiguous regions of a multi-polygon
    # No that's not a typo, it's really the string "NaN"
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
        shape_info: dict = shapely_mapping(multipoly)
        shape_type: str = shape_info["type"]
        # Another option would be Point, but our geo data doesn't have locations
        # like that
        assert shape_type in ["Polygon", "MultiPolygon"]

        polygons = shape_info["coordinates"]
        if shape_type == "Polygon":
            # Turn Polygon into 1-list of Polygons
            polygons = [polygons]

        polygons: MultiPolygon

        for poly_index, poly_tup in enumerate(polygons):
            # Extract the sole element of the 1-tuple
            poly: Polygon = poly_tup[0]
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
    """Get geometry and long/lat coords for each US state

    :return: GeoDataFrame containing, for each US state: 2-letter state code, geometry
    (boundary), and lists of long/lat coords in bokeh-compatible format
    :rtype: geopandas.GeoDataFrame
    """

    geo_df: geopandas.GeoDataFrame = geopandas.read_file(
        GEO_DATA_DIR / "cb_2017_us_state_20m" / "cb_2017_us_state_20m.shp"
    ).to_crs(
        "EPSG:2163"  # US National Atlas Equal Area (Google it)
    ).rename(
        columns={"STUSPS": REGION_NAME_COL}, errors="raise"
    )

    return get_longs_lats(geo_df)


@functools.lru_cache(None)
def get_countries_geo_df() -> geopandas.GeoDataFrame:
    """Get geometry and long/lat coords for world countries

    The country names in the returned GeoDataFrame must match those in the COVID data
    source; if not, they must be remapped here.

    :return: GeoDataFrame containing, for each country: name, geometry (boundary), and
    lists of long/lat coords in bokeh-compatible format
    :rtype: geopandas.GeoDataFrame
    """

    geo_df: geopandas.GeoDataFrame = geopandas.read_file(
        GEO_DATA_DIR / "ne_110m_admin_0_map_units" / "ne_110m_admin_0_map_units.shp"
    ).to_crs(WorldCRS.default().value)

    geo_df = geo_df.rename(columns={"ADMIN": REGION_NAME_COL}, errors="raise")

    # Keys are what's in the geo df, values are what we want to rename them to
    # Values must match the names in the original data source. If you don't like those
    # names, change them there and then come back and change the values here.
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
    subplot_title_prefix: str,
    plot_aspect_ratio: float = None,
    cmap=None,
    n_cbar_buckets: int = None,
    n_buckets_btwn_major_ticks: int = None,
    n_minor_ticks_btwn_major_ticks: int = None,
    per_capita_denominator: int = None,
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
    min_visible_y_range: float,
    should_make_video: bool,
) -> InfoForAutoload:
    """Create the bokeh interactive timeline plot(s)

    This function takes the given DataFrame, which must contain COVID data for locations
    on different dates, and a GeoDataFrame, which contains the long/lat coords for those
    locations, and creates an interactive choropleth of the COVID data over time.

    :param df: The COVID data DataFrame
    :type df: pd.DataFrame
    :param geo_df: The geometry GeoDataFrame for the locations in `df`
    :type geo_df: geopandas.GeoDataFrame
    :param value_col: The column of `df` containing the values to plot in the
    choropleth; should be something like "Case_Counts" or "Case_Diff_From_Prev_Day"
    :type value_col: str
    :param stage: The DiseaseStage to plot, defaults to Select.ALL. If ALL, then all
    stages are plotted and are stacked vertically.
    :type stage: Union[DiseaseStage, Literal[Select.ALL]], optional
    :param count: The Counting to plot, defaults to Select.ALL. If ALL, then all
    count types are plotted and are stacked horizontally.
    :type count: Union[Counting, Literal[Select.ALL]], optional
    :param out_file_basename: The basename of the file to save the interactive plots to
    (there are two components, the JS script and the HTML <div>)
    :type out_file_basename: str
    :param subplot_title_prefix: What the first part of the subplot title should be;
    probably a function of `value_col` (if value_col is "Case_Counts" then this param
    might be "Cases" or "# of Cases")
    :type subplot_title_prefix: str
    :param x_range: The range of the x-axis as (min, max)
    :type x_range: Tuple[float, float]
    :param y_range: The range of the y-axis as (min, max)
    :type y_range: Tuple[float, float]
    :param min_visible_y_range: The minimum height (in axis units) of the y-axis; it
    will not be possible to zoom in farther than this on the choropleth.
    :type min_visible_y_range: float
    :param should_make_video: Optionally run through the timeline day by day, capture
    a screenshot for each day, and then stitch the screenshots into a video. The video
    shows the same info as the interactive plots, but not interactively. This easily
    takes 20x as long as just making the graphs themselves, so use with caution.
    :type should_make_video: bool
    :param transform_df_func: This function expects data in a certain format, and does
    a bunch of preprocessing (expected to be common) before plotting. This gives you a
    chance to do any customization on the postprocessed df before it's plotted. Defaults
    to None, in which case no additional transformation is performed.
    :type transform_df_func: Callable[[pd.DataFrame], pd.DataFrame], optional
    :param plot_aspect_ratio: The aspect ratio of the plot as width/height; if set, the
    aspect ratio will be fixed to this. Defaults to None, in which case the aspect ratio
    is determined from the x_range and y_range arguments
    :type plot_aspect_ratio: float, optional
    :param cmap: The colormap to use as either a matplotlib-compatible colormap or a
    list of hex strings (e.g., ["#ae8f1c", ...]). Defaults to None in which case a
    reasonable default is used.
    :type cmap: Matplotlib-compatible colormap or List[str], optional
    :param n_cbar_buckets: How many colorbar buckets to use. Has little effect if the
    colormap is continuous, but always works in conjunction with
    n_buckets_btwn_major_ticks to determine the number of major ticks. Defaults to 6.
    :type n_cbar_buckets: int, optional
    :param n_buckets_btwn_major_ticks: How many buckets are to lie between colorbar
    major ticks, determining how many major ticks are drawn. Defaults to 1.
    :type n_buckets_btwn_major_ticks: int, optional
    :param n_minor_ticks_btwn_major_ticks: How many minor ticks to draw between colorbar
    major ticks. Defaults to 8 (which means each pair of major ticks has 10 ticks
    total).
    :type n_minor_ticks_btwn_major_ticks: int, optional
    :param per_capita_denominator: When describing per-capita numbers, what to use as
    the denominator (e.g., cases per 100,000 people). If None, it is automatically
    computed per plot to be appropriately scaled for the data.
    :type per_capita_denominator: int, optional
    :raises ValueError: [description]
    :return: The two pieces of info required to make a Bokeh autoloading HTML+JS plot:
    the HTML div to be inserted somewhere in the HTML body, and the JS file that will
    load the plot into that div.
    :rtype: InfoForAutoload
    """

    Counting.verify(count, allow_select=True)
    DiseaseStage.verify(stage, allow_select=True)

    # The date as a string, so that bokeh can use it as a column name
    STRING_DATE_COL = "String_Date_"
    # A column whose sole purpose is to be a (the same) date associated with each
    # location
    FAKE_DATE_COL = "Fake_Date_"
    # The column we'll actually use for the colors; it's computed from value_col
    COLOR_COL = "Color_"

    # Under no circumstances may you change this date format
    # It's not just a pretty date representation; it actually has to match up with the
    # date strings computed in JS
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

    if stage is Select.ALL:
        stage_list = list(DiseaseStage)
    else:
        stage_list = [stage]

    if count is Select.ALL:
        count_list = list(Counting)
    else:
        count_list = [count]

    stage_list: List[DiseaseStage]
    count_list: List[Counting]

    stage_count_list: List[Tuple[DiseaseStage, Counting]] = list(
        itertools.product(stage_list, count_list)
    )

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
    # enums will be replaced by their name (kind of important)
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

    df = geo_df.merge(df, how="inner", on=REGION_NAME_COL)[
        [
            REGION_NAME_COL,
            Columns.DATE,
            STRING_DATE_COL,
            Columns.STAGE,
            Columns.COUNT_TYPE,
            value_col,
        ]
    ]

    dates: List[pd.Timestamp] = [pd.Timestamp(d) for d in df[Columns.DATE].unique()]

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
    # avoid that. (This seems to be one downside of bokeh when compared to plotly)
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

    # All three oclumns are just initial values; they'll change with the date slider
    df[value_col] = df[max_date_str]
    df[FAKE_DATE_COL] = max_date_str
    df[COLOR_COL] = np.where(df[value_col] > 0, df[value_col], "NaN")

    # Technically takes a df but we don't need the index
    bokeh_data_source = ColumnDataSource(
        {k: v.tolist() for k, v in df.to_dict(orient="series").items()}
    )

    filters = [
        [
            GroupFilter(column_name=Columns.STAGE, group=stage.name),
            GroupFilter(column_name=Columns.COUNT_TYPE, group=count.name),
        ]
        for stage, count in stage_count_list
    ]

    figures = []

    for subplot_index, (stage, count) in enumerate(stage_count_list):
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

        # Compute and set axes titles
        if stage is DiseaseStage.CONFIRMED:
            fig_stage_name = "Cases"
        elif stage is DiseaseStage.DEATH:
            fig_stage_name = "Deaths"
        else:
            raise ValueError

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
                HoverTool(
                    tooltips=[
                        ("Date", f"@{{{FAKE_DATE_COL}}}"),
                        ("State", f"@{{{REGION_NAME_COL}}}"),
                        ("Count", f"@{{{value_col}}}{tooltip_fmt}"),
                    ],
                    toggleable=False,
                ),
                PanTool(),
                BoxZoomTool(match_aspect=True),
                ZoomInTool(),
                ZoomOutTool(),
                ResetTool(),
            ],
            active_drag=None,
            aspect_ratio=plot_aspect_ratio,
            output_backend="webgl",
            lod_factor=4,
            lod_interval=400,
            lod_threshold=1000,
            lod_timeout=300,
        )

        p.xgrid.grid_line_color = None
        p.ygrid.grid_line_color = None
        # Finally, add the actual choropleth data we care about
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

        # Add evenly spaced ticks and their labels to the colorbar
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

        p.add_layout(color_bar, "right")
        p.hover.point_policy = "follow_mouse"

        # Bokeh axes (and most other things) are splattable
        p.axis.visible = False

        figures.append(p)

    # Make all figs pan and zoom together by setting their axes equal to each other
    # Also fix the plots' aspect ratios
    figs_iter = iter(np.ravel(figures))
    anchor_fig = next(figs_iter)

    if x_range is not None and y_range is not None:
        data_aspect_ratio = (x_range[1] - x_range[0]) / (y_range[1] - y_range[0])
    else:
        data_aspect_ratio = plot_aspect_ratio

    if x_range is not None:
        anchor_fig.x_range = Range1d(
            *x_range,
            bounds="auto",
            min_interval=min_visible_y_range * data_aspect_ratio,
        )

    if y_range is not None:
        anchor_fig.y_range = Range1d(
            *y_range, bounds="auto", min_interval=min_visible_y_range
        )

    for fig in figs_iter:
        fig.x_range = anchor_fig.x_range
        fig.y_range = anchor_fig.y_range

    # 2x2 grid (for now)
    gp = gridplot(
        figures,
        ncols=len(count_list),
        sizing_mode="scale_both",
        toolbar_location="above",
    )
    plot_layout = [gp]

    # Ok, pause
    # Now we're going into a whole other thing: we're doing all the JS logic behind a
    # date slider that changes which date is shown on the graphs. The structure of the
    # data is one column per date, one row per location, and a few extra columns to
    # store the data the graph will use. When we adjust the date of the slider, we copy
    # the relevant column of the df into the columns the graphs are looking at.
    # That's the easy part; the hard part is handling the "play button" functionality,
    # whereby the user can click one button and the date slider will periodically
    # advance itself. That requires a fair bit of logic to schedule and cancel the
    # timers and make it all feel right.

    # Create unique ID for the JS playback info object for this plot (since it'll be on
    # the webpage with other plots, and their playback info isn't shared)
    _THIS_PLOT_ID = uuid.uuid4().hex

    __TIMER = "'timer'"
    __IS_ACTIVE = "'isActive'"
    __SELECTED_INDEX = "'selectedIndex'"
    __BASE_INTERVAL_MS = "'BASE_INTERVAL'"  # Time (in MS) btwn frames when speed==1
    __TIMER_START_DATE = "'startDate'"
    __TIMER_ELAPSED_TIME_MS = "'elapsedTimeMS'"
    __TIMER_ELAPSED_TIME_PROPORTION = "'elapsedTimeProportion'"
    __SPEEDS_KEY = "'SPEEDS'"
    __PLAYBACK_INFO = f"window._playbackInfo_{_THIS_PLOT_ID}"

    _PBI_TIMER = f"{__PLAYBACK_INFO}[{__TIMER}]"
    _PBI_IS_ACTIVE = f"{__PLAYBACK_INFO}[{__IS_ACTIVE}]"
    _PBI_SELECTED_INDEX = f"{__PLAYBACK_INFO}[{__SELECTED_INDEX}]"
    _PBI_TIMER_START_DATE = f"{__PLAYBACK_INFO}[{__TIMER_START_DATE}]"
    _PBI_TIMER_ELAPSED_TIME_MS = f"{__PLAYBACK_INFO}[{__TIMER_ELAPSED_TIME_MS}]"
    _PBI_TIMER_ELAPSED_TIME_PROPORTION = (
        f"{__PLAYBACK_INFO}[{__TIMER_ELAPSED_TIME_PROPORTION}]"
    )
    _PBI_BASE_INTERVAL = f"{__PLAYBACK_INFO}[{__BASE_INTERVAL_MS}]"
    _PBI_SPEEDS = f"{__PLAYBACK_INFO}[{__SPEEDS_KEY}]"
    _PBI_CURR_INTERVAL_MS = (
        f"{_PBI_BASE_INTERVAL} / {_PBI_SPEEDS}[{_PBI_SELECTED_INDEX}]"
    )

    _SPEED_OPTIONS = [0.25, 0.5, 1.0, 2.0]
    _DEFAULT_SPEED = 1.0
    _DEFAULT_SELECTED_INDEX = _SPEED_OPTIONS.index(_DEFAULT_SPEED)

    _SETUP_WINDOW_PLAYBACK_INFO = f"""
        if (typeof({__PLAYBACK_INFO}) === 'undefined') {{
            {__PLAYBACK_INFO} = {{
                {__TIMER}: null,
                {__IS_ACTIVE}: false,
                {__SELECTED_INDEX}: {_DEFAULT_SELECTED_INDEX},
                {__TIMER_START_DATE}: null,
                {__TIMER_ELAPSED_TIME_MS}: 0,
                {__TIMER_ELAPSED_TIME_PROPORTION}: 0,
                {__BASE_INTERVAL_MS}: 1000,
                {__SPEEDS_KEY}: {_SPEED_OPTIONS}
            }};
        }}

    """

    _DEFFUN_INCR_DATE = f"""
        // See this link for why this works (it's an undocumented feature?)
        // https://discourse.bokeh.org/t/5254
        // Tl;dr we need this to automatically update the hover as the play button plays
        // Without this, the hover tooltip only updates when we jiggle the mouse
        // slightly

        let prev_val = null;
        source.inspect.connect(v => prev_val = v);

        function updateDate() {{
            {_PBI_TIMER_START_DATE} = new Date();
            {_PBI_TIMER_ELAPSED_TIME_MS} = 0
            if (dateSlider.value < maxDate) {{
                dateSlider.value += 86400000;
            }}

            if (dateSlider.value >= maxDate) {{
                console.log(dateSlider.value, maxDate)
                console.log('reached end')
                clearInterval({_PBI_TIMER});
                {_PBI_IS_ACTIVE} = false;
                playPauseButton.active = false;
                playPauseButton.change.emit();
                playPauseButton.label = 'Restart';
            }}

            dateSlider.change.emit();

            // This is pt. 2 of the prev_val/inspect stuff above
            if (prev_val !== null) {{
                source.inspect.emit(prev_val);
            }}
        }}
    """

    _DO_START_TIMER = f"""
        function startLoopTimer() {{
            updateDate();
            if ({_PBI_IS_ACTIVE}) {{
                {_PBI_TIMER} = setInterval(updateDate, {_PBI_CURR_INTERVAL_MS})
            }}

        }}

        {_PBI_TIMER_START_DATE} = new Date();

        // Should never be <0 or >1 but I am being very defensive here
        const proportionRemaining = 1 - (
            {_PBI_TIMER_ELAPSED_TIME_PROPORTION} <= 0
            ? 0
            : {_PBI_TIMER_ELAPSED_TIME_PROPORTION} >= 1
            ? 1
            : {_PBI_TIMER_ELAPSED_TIME_PROPORTION}
        );
        const remainingTimeMS = (
            {_PBI_CURR_INTERVAL_MS} * proportionRemaining
        );
        const initialInterval = (
            {_PBI_TIMER_ELAPSED_TIME_MS} === 0
            ? 0
            : remainingTimeMS
        );

        {_PBI_TIMER} = setTimeout(
            startLoopTimer,
            initialInterval
        );
    """

    _DO_STOP_TIMER = f"""
        const now = new Date();
        {_PBI_TIMER_ELAPSED_TIME_MS} += (
            now.getTime() - {_PBI_TIMER_START_DATE}.getTime()
        );
        {_PBI_TIMER_ELAPSED_TIME_PROPORTION} = (
            {_PBI_TIMER_ELAPSED_TIME_MS} / {_PBI_CURR_INTERVAL_MS}
        );
        clearInterval({_PBI_TIMER});
    """

    update_on_date_change_callback = CustomJS(
        args={"source": bokeh_data_source},
        code=f"""

        {_SETUP_WINDOW_PLAYBACK_INFO}

        const sliderValue = cb_obj.value;
        const sliderDate = new Date(sliderValue)
        // Ugh, actually requiring the date to be YYYY-MM-DD (matching DATE_FMT)
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
    # date (might be off by 1 if not using day over diffs but in practice not an issue)
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
        label="Start playing",
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

                // Hack to get timer to wait after date slider wraps; any positive
                // number works but the smaller the better
                {_PBI_TIMER_ELAPSED_TIME_MS} = 1;
            }}
        }}

        const active = cb_obj.active;
        {_PBI_IS_ACTIVE} = active;

        if (active) {{
            playPauseButton.label = 'Playing – Click/tap to pause'
            {_DO_START_TIMER}
        }} else {{
            playPauseButton.label = 'Paused – Click/tap to play'
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

        // Must stop timer before handling changing the speed, as stopping the timer
        // saves values based on the current (unchaged) speed selection
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

        console.log({__PLAYBACK_INFO})

    """,
    )

    playback_speed_radio = RadioButtonGroup(
        labels=[f"{speed:.2g}x speed" for speed in _SPEED_OPTIONS],
        active=_DEFAULT_SELECTED_INDEX,
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

    # Create the autoloading bokeh plot info (HTML + JS)
    js_path = str(Path(out_file_basename + "_autoload").with_suffix(".js"))
    tag_html_path = str(Path(out_file_basename + "_div_tag").with_suffix(".html"))

    js_code, tag_code = autoload_static(plot_layout, CDN, js_path)
    tag_uuid = re.search(r'id="([^"]+)"', tag_code).group(1)
    tag_code = re.sub(r'src="([^"]+)"', f'src="\\1?uuid={tag_uuid}"', tag_code)

    with open(Paths.DOCS / js_path, "w") as f_js, open(
        Paths.DOCS / tag_html_path, "w"
    ) as f_html:
        f_js.write(js_code)
        f_html.write(tag_code)

    # Create the video by creating stills of the graphs for each date and then stitching
    # the images into a video
    if should_make_video:
        save_dir: Path = PNG_SAVE_ROOT_DIR / out_file_basename
        save_dir.mkdir(parents=True, exist_ok=True)

        STILL_WIDTH = 1500
        STILL_HEIGHT = int(
            np.ceil(STILL_WIDTH / plot_aspect_ratio) * 1.05
        )  # Unclear why *1.05 is necessary
        gp.height = STILL_HEIGHT
        gp.width = STILL_WIDTH
        gp.sizing_mode = "fixed"
        orig_title = anchor_fig.title.text

        for date in dates:
            date_str = date.strftime(DATE_FMT)
            anchor_fig.title = Title(text=f"{orig_title} {date_str}")

            for p in figures:
                p.title = Title(text=p.title.text, text_font_size="20px")

            # Just a reimplementation of the JS code in the date slider's callback
            data = bokeh_data_source.data
            data[value_col] = data[date_str]

            for i, value in enumerate(data[value_col]):
                if value == 0:
                    data[COLOR_COL][i] = "NaN"
                else:
                    data[COLOR_COL][i] = value

                data[FAKE_DATE_COL][i] = date_str

            save_path: Path = (save_dir / date_str).with_suffix(".png")
            export_png(gp, filename=save_path)
            resize_to_even_dims(save_path, pad_bottom=0.08)

            if date == max(dates):
                poster_path: Path = (
                    PNG_SAVE_ROOT_DIR / (out_file_basename + "_poster")
                ).with_suffix(".png")
                poster_path.write_bytes(save_path.read_bytes())

        make_video(save_dir, out_file_basename, 0.9)

    print(f"Did interactive {out_file_basename}")

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
    min_visible_y_range: float,
    should_make_video: bool,
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
        min_visible_y_range=min_visible_y_range,
        should_make_video=should_make_video,
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
    min_visible_y_range: float,
    should_make_video: bool,
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
        per_capita_denominator=100000,
        x_range=x_range,
        y_range=y_range,
        min_visible_y_range=min_visible_y_range,
        should_make_video=should_make_video,
    )


def __assign_region_name_col(df: pd.DataFrame, region_name_col: str) -> pd.DataFrame:
    """Replace the df-specific region column name with the generic, file-wide constant

    :param df: The DataFrame containing a location column to rename
    :type df: pd.DataFrame
    :param region_name_col: The name of the column to rename
    :type region_name_col: str
    :return: `df` with the column renamed
    :rtype: pd.DataFrame
    """
    return df.rename(columns={region_name_col: REGION_NAME_COL})


def _prepare_usa_states_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df[
        (df[Columns.TWO_LETTER_STATE_CODE].isin(USA_STATE_CODES))
        & (~df[Columns.TWO_LETTER_STATE_CODE].isin(["AK", "HI"]))
    ].copy()

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
        "min_visible_y_range": 8.5e5,
    }


@functools.lru_cache(None)
def _get_countries_kwargs(
    world_crs: Union[WorldCRS, Literal[Select.DEFAULT]] = Select.DEFAULT
) -> dict:
    if world_crs is Select.DEFAULT:
        world_crs = WorldCRS.default()

    world_crs: WorldCRS

    return {
        "out_file_basename": "countries",
        **world_crs.get_axis_info(),
    }


def make_usa_daybyday_total_interactive_timeline(
    states_df: pd.DataFrame,
    *,
    usa_states_geo_df: geopandas.GeoDataFrame = None,
    stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
    count: Union[Counting, Literal[Select.ALL]] = Select.ALL,
    should_make_video: bool,
) -> Tuple:

    states_df = _prepare_usa_states_df(states_df)

    if usa_states_geo_df is None:
        usa_states_geo_df = get_usa_states_geo_df()

    return _make_daybyday_total_interactive_timeline(
        states_df,
        geo_df=usa_states_geo_df,
        stage=stage,
        count=count,
        should_make_video=should_make_video,
        **_get_usa_kwargs(),
    )


def make_usa_daybyday_diff_interactive_timeline(
    states_df: pd.DataFrame,
    *,
    usa_states_geo_df: geopandas.GeoDataFrame = None,
    stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
    count: Union[Counting, Literal[Select.ALL]] = Select.ALL,
    should_make_video: bool,
) -> InfoForAutoload:

    states_df = _prepare_usa_states_df(states_df)

    if usa_states_geo_df is None:

        usa_states_geo_df = get_usa_states_geo_df()

    return _make_daybyday_diff_interactive_timeline(
        states_df,
        geo_df=usa_states_geo_df,
        stage=stage,
        count=count,
        should_make_video=should_make_video,
        **_get_usa_kwargs(),
    )


def make_countries_daybyday_total_interactive_timeline(
    countries_df: pd.DataFrame,
    *,
    countries_geo_df: geopandas.GeoDataFrame = None,
    stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
    count: Union[Counting, Literal[Select.ALL]] = Select.ALL,
    should_make_video: bool,
) -> InfoForAutoload:

    countries_df = _prepare_countries_df(countries_df)

    if countries_geo_df is None:
        countries_geo_df = get_countries_geo_df()

    return _make_daybyday_total_interactive_timeline(
        countries_df,
        geo_df=countries_geo_df,
        stage=stage,
        count=count,
        should_make_video=should_make_video,
        **_get_countries_kwargs(),
    )


def make_countries_daybyday_diff_interactive_timeline(
    countries_df: pd.DataFrame,
    *,
    countries_geo_df: geopandas.GeoDataFrame = None,
    stage: Union[DiseaseStage, Literal[Select.ALL]] = Select.ALL,
    count: Union[Counting, Literal[Select.ALL]] = Select.ALL,
    should_make_video: bool,
) -> InfoForAutoload:

    countries_df = _prepare_countries_df(countries_df)

    if countries_geo_df is None:
        countries_geo_df = get_countries_geo_df()

    return _make_daybyday_diff_interactive_timeline(
        countries_df,
        geo_df=countries_geo_df,
        stage=stage,
        count=count,
        should_make_video=should_make_video,
        **_get_countries_kwargs(),
    )


def make_video(img_dir: Path, out_file_name: str, fps: float):
    """Given a folder containing PNGs, stitch the PNGs into a video

    Uses ffmpeg to take PNGs in the specified folder and create a video out of them,
    which plays at the specific FPS

    :param img_dir: The folder of PNGs
    :type img_dir: Path
    :param out_file_name: Where to save the video
    :type out_file_name: str
    :param fps: The FPS; in the output video, one image will be shown every `fps`
    seconds
    :type fps: float
    """

    img_files = sorted(img_dir.glob("*.png"))

    # Prepare the concat demuxer, which describes how to stitch the images into a video
    concat_demux_lines = []
    # https://trac.ffmpeg.org/wiki/Slideshow
    for f in img_files:
        concat_demux_lines.append(f"file '{f}'")
        concat_demux_lines.append(f"duration {1/fps}")

    # Duplicate last frame 2x so that it's clear when video has ended
    for _ in range(2):
        concat_demux_lines.append(f"file '{img_files[-1]}'")
        concat_demux_lines.append(f"duration {1/fps}")

    concat_demux_lines.append(f"file '{img_files[-1]}'")

    concat_demux_str = "\n".join(concat_demux_lines)

    save_path = (PNG_SAVE_ROOT_DIR / out_file_name).with_suffix(".mp4")

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-protocol_whitelist",
        "file,pipe,crypto",
        "-safe",
        "0",
        "-i",
        "-",  # Read concat demux info from stdin
        "-vsync",
        "vfr",
        "-vcodec",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-tune",
        "stillimage",
        str(save_path),
    ]

    ps = subprocess.run(cmd, input=concat_demux_str, text=True)

    ps.check_returncode()

    print(f"Saved video '{save_path}'")


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
