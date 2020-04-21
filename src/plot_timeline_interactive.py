# %%
import functools
import itertools
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Union

import bokeh.plotting as bplotting
import cmocean
import geopandas
import numpy as np
import pandas as pd
from bokeh.colors import RGB
from bokeh.io import output_file, output_notebook, show
from bokeh.layouts import gridplot
from bokeh.models import (
    BooleanFilter,
    CDSView,
    ColorBar,
    ColumnDataSource,
    GroupFilter,
    LogColorMapper,
)
from IPython.display import display  # noqa F401
from shapely.geometry import mapping as shapely_mapping
from typing_extensions import Literal

from constants import USA_STATE_CODES, Columns, Counting, DiseaseStage, Paths, Select
from plotting_utils import format_float

GEO_FIG_DIR: Path = Paths.FIGURES / "Geo"
DOD_DIFF_DIR: Path = GEO_FIG_DIR / "DayOverDayDiffs"
DOD_DIFF_DIR.mkdir(parents=True, exist_ok=True)

Polygon = List[Tuple[float, float]]
MultiPolygon = List[Tuple[Polygon]]

LAT_COL = "lat"
LONG_COL = "long"


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


def plot_usa_daybyday_case_diffs(
    states_df: pd.DataFrame,
    *,
    geo_df: geopandas.GeoDataFrame = None,
    stage: Union[DiseaseStage, Literal[Select.ALL]],
    count: Union[Counting, Literal[Select.ALL]],
    dates: List[pd.Timestamp] = None,
) -> pd.DataFrame:

    from case_tracker import get_df, get_usa_states_df

    states_df = get_usa_states_df(get_df(refresh_local_data=False), None)

    Counting.verify(count, allow_select=True)
    DiseaseStage.verify(stage, allow_select=True)

    FAKE_DATE_COL = "Fake_Date_"
    DIFF_COL = "Diff_"
    ASPECT_RATIO = 1 / 20
    PAD_FRAC = 0.5
    N_CBAR_BUCKETS = 6  # only used when bucketing colormap into discrete regions
    N_BUCKETS_BTWN_MAJOR_TICKS = 1
    N_MINOR_TICKS_BTWN_MAJOR_TICKS = 8  # major_1, minor_1, ..., minor_n, major_2
    N_CBAR_MAJOR_TICKS = N_CBAR_BUCKETS // N_BUCKETS_BTWN_MAJOR_TICKS + 1
    CMAP = cmocean.cm.matter
    # CMAP = ListedColormap(cmocean.cm.matter(np.linspace(0, 1, N_CBAR_BUCKETS)))
    DPI = 300
    NOW_STR = datetime.now(timezone.utc).strftime(r"%b %-d, %Y at %H:%M UTC")

    ID_COLS = [
        Columns.TWO_LETTER_STATE_CODE,
        Columns.DATE,
        Columns.STAGE,
        Columns.COUNT_TYPE,
    ]

    if geo_df is None:
        geo_df = get_geo_df()

    save_fig_kwargs = {"dpi": "figure", "bbox_inches": "tight", "facecolor": "w"}

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

    if dates is None:
        dates: List[pd.Timestamp] = states_df[Columns.DATE].unique()

    dates = sorted(pd.Timestamp(date) for date in dates)

    max_date = max(dates)

    # Get day-by-day case diffs per location, date, stage, count-type
    case_diffs_df = states_df[
        (states_df[Columns.TWO_LETTER_STATE_CODE].isin(USA_STATE_CODES))
        & (~states_df[Columns.TWO_LETTER_STATE_CODE].isin(["AK", "HI"]))
    ].copy()

    # Make sure data exists for every date for every state so that the entire country is
    # plotted each day; fill missing data with 0 (missing really *is* as good as 0)
    state_date_stage_combos = pd.MultiIndex.from_product(
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

    case_diffs_df[Columns.CASE_COUNT] = case_diffs_df[Columns.CASE_COUNT].fillna(0)

    case_diffs_df[DIFF_COL] = case_diffs_df.groupby(
        [Columns.TWO_LETTER_STATE_CODE, Columns.STAGE, Columns.COUNT_TYPE]
    )[Columns.CASE_COUNT].diff()

    case_diffs_df = case_diffs_df[case_diffs_df[DIFF_COL].notna()]

    full_data_df: geopandas.GeoDataFrame = geo_df.merge(
        case_diffs_df, how="inner", on=Columns.TWO_LETTER_STATE_CODE,
    )

    selected_data_df: pd.DataFrame = full_data_df[
        [
            Columns.TWO_LETTER_STATE_CODE,
            Columns.DATE,
            Columns.STAGE,
            Columns.COUNT_TYPE,
            DIFF_COL,
        ]
    ]

    selected_data_df[Columns.DATE] = selected_data_df[Columns.DATE].dt.strftime(
        r"%Y-%m-%d"
    )

    # Ideally we wouldn't have to pivot, and we could do a JIT join of state longs/lats
    # after filtering the data. Unfortunately this is not possible, and a long data
    # format leads to duplication of the very large long/lat lists; pivoting is how we
    # avoid that
    selected_data_df = selected_data_df.pivot_table(
        index=[Columns.TWO_LETTER_STATE_CODE, Columns.STAGE, Columns.COUNT_TYPE],
        columns=Columns.DATE,
        values=DIFF_COL,
        aggfunc="first",
    ).reset_index()

    selected_data_df = selected_data_df.merge(
        geo_df[[Columns.TWO_LETTER_STATE_CODE, LONG_COL, LAT_COL]],
        how="inner",
        on=Columns.TWO_LETTER_STATE_CODE,
    )

    selected_data_df[DIFF_COL] = selected_data_df[max_date.strftime(r"%Y-%m-%d")]
    selected_data_df[FAKE_DATE_COL] = max_date.strftime(r"%b %-d, %Y")

    display(selected_data_df)

    bokeh_data_source = ColumnDataSource(selected_data_df)

    filters = [
        [
            GroupFilter(column_name=Columns.STAGE, group=stage.name),
            GroupFilter(column_name=Columns.COUNT_TYPE, group=count.name),
        ]
        for stage, count in itertools.product(stage_list, count_list)
    ]

    dates = case_diffs_df[Columns.DATE].unique()

    vmins = {
        Counting.TOTAL_CASES: 1,
        Counting.PER_CAPITA: case_diffs_df.loc[
            case_diffs_df[DIFF_COL] > 0, DIFF_COL
        ].min(),
    }
    vmaxs = case_diffs_df.groupby([Columns.STAGE, Columns.COUNT_TYPE])[DIFF_COL].max()

    # Don't put too much stock in these, we tweak them later to make sure they're even
    fig_width_px = len(count_list) * 1800
    fig_height_px = len(stage_list) * 1000 + 200

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

        # this_df = full_data_df[
        #     (full_data_df[Columns.DATE] == date)
        #     & (full_data_df[Columns.STAGE] == stage.name)
        #     & (full_data_df[Columns.COUNT_TYPE] == count.name)
        # ]

        vmin = vmins[count]
        vmax = vmaxs.loc[(stage.name, count.name)]
        # Input GeoJSON source that contains features for plotting.
        # geosource = GeoJSONDataSource(geojson=json.dumps(stage_geo_df.to_json()))

        color_mapper = LogColorMapper(
            [
                # Convert matplotlib colormap to bokeh (list of hex strings)
                # https://stackoverflow.com/a/49934218
                RGB(*tuple(rgb)).to_hex()
                for rgb in (255 * CMAP(range(256))).astype("int")
            ],
            low=vmin,
            high=vmax,
        )
        # Define custom tick labels for color bar.
        # Create color bar.
        color_bar = ColorBar(
            color_mapper=color_mapper,
            label_standoff=8,
            border_line_color=None,
            location=(0, 0),
            orientation="vertical",
        )
        # Set axes titles
        fig_stage_name: str = {
            DiseaseStage.CONFIRMED: "Cases",
            DiseaseStage.DEATH: "Deaths",
        }[stage]
        fig_title_components: List[str] = ["New Daily", fig_stage_name]
        if count is Counting.PER_CAPITA:
            fig_title_components.append("Per Capita")

        fig_title = " ".join(fig_title_components)

        # Create figure object.
        p = bplotting.figure(
            title=fig_title,
            toolbar_location=None,
            tooltips=[
                ("State", f"@{{{Columns.TWO_LETTER_STATE_CODE}}}"),
                ("Date", f"@{{{FAKE_DATE_COL}}}"),
                ("Count", f"@{{{DIFF_COL}}}"),
            ],
        )
        p.xgrid.grid_line_color = None
        p.ygrid.grid_line_color = None
        # Add patch renderer to figure.
        p.patches(
            LONG_COL,
            LAT_COL,
            source=bokeh_data_source,
            view=view,
            fill_color={"field": DIFF_COL, "transform": color_mapper},
            line_color="black",
            line_width=0.25,
            fill_alpha=1,
        )
        # Specify figure layout.
        p.add_layout(color_bar, "right")
        # Display figure inline in Jupyter Notebook.
        p.hover.point_policy = "follow_mouse"

        figures.append(p)

    grid = gridplot(figures, ncols=len(count_list), sizing_mode="stretch_both")
    show(grid)


if __name__ == "__main__":
    df = plot_usa_daybyday_case_diffs(None, stage=Select.ALL, count=Select.ALL)
