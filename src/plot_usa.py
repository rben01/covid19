# %%
import io
import itertools
import json
from typing import NewType

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.graph_objs as go
from IPython.display import display
from plotly.offline import plot
from plotly.subplots import make_subplots

from case_tracker import get_df, get_usa_states_df
from constants import CaseInfo, Columns, Counting, DiseaseStage, InfoField, Paths

GeoJSON = NewType("GeoJson", dict)


def get_geojson() -> GeoJSON:
    with open(Paths.DATA / "usa_states_geo.json") as f:
        return json.load(f)


# This method pretty much taken wholesale from here:
# https://plotly.com/python/map-subplots-and-small-multiples/
def plot_usa_states_over_time(states_df, geojson: GeoJSON = None) -> go.Figure:

    # Don't change this -- see below
    # https://stackoverflow.com/q/49106957
    def get_geo_id(i: int) -> str:
        if i == 0:
            return "geo"
        return f"geo{i+1}"

    if geojson is None:
        geojson = get_geojson()

    # fig = make_subplots(rows=2, cols=2, specs=[[{"type": "chloropleth"}] * 2] * 2)

    X = "x"
    Y = "y"

    layout = {}
    data = []

    for i, (stage, count) in enumerate(itertools.product(DiseaseStage, Counting)):

        geo_id = get_geo_id(i)

        row, col = divmod(i, 2)
        # Plotly developers: take a good hard look at yourselves in the mirror. What
        # could have possible led you to 1-index your subplot layouts???????????????????

        trace_df = states_df[
            states_df[Columns.CASE_TYPE]
            == CaseInfo.get_info_item_for(InfoField.CASE_TYPE, stage=stage, count=count)
        ]

        latest = (
            trace_df.groupby(
                [Columns.STATE, Columns.STAGE, Columns.COUNT_TYPE], as_index=False
            )
            .apply(lambda g: g.sort_values(Columns.DATE).tail(1))
            .reset_index(drop=True)[
                [
                    Columns.LOCATION_NAME,
                    Columns.DATE,
                    Columns.CASE_COUNT,
                    Columns.STAGE,
                    Columns.COUNT_TYPE,
                    Columns.STATE,
                    Columns.TWO_LETTER_STATE_CODE,
                ]
            ]
        )

        data.append(
            {
                "type": "choropleth",
                "locations": latest[Columns.TWO_LETTER_STATE_CODE],
                "z": latest[Columns.CASE_COUNT],
                "locationmode": "USA-states",
                "geo": geo_id,
            }
        )

        layout[geo_id] = {
            "scope": "usa",
            "showland": True,
            "landcolor": "rgb(229, 229, 229)",
            "showcountries": False,
            "showsubunits": True,
            "domain": {X: [], Y: []},
        }

    N_ROWS = len(DiseaseStage)
    N_COLS = len(Counting)

    i = 0
    for r in reversed(range(N_ROWS)):  # r == y
        for c in range(N_COLS):  # c == x
            geo_id = get_geo_id(i)
            layout[geo_id]["domain"][X] = [
                float(c) / float(N_COLS),
                float(c + 1) / float(N_COLS),
            ]
            layout[geo_id]["domain"][Y] = [
                float(r) / float(N_ROWS),
                float(r + 1) / float(N_ROWS),
            ]

            i += 1

    choromap = go.Figure(data=data, layout=layout)

    return choromap


geojson = get_geojson()
s = get_usa_states_df(get_df(refresh_local_data=False), 55)

fig = plot_usa_states_over_time(s, geojson)
# fig.write_html(str(Paths.ROOT / "docs" / "fig.html"))
plot(fig)
