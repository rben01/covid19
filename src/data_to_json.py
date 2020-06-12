# %%
import json
from pathlib import Path

import pandas as pd

from constants import Columns, Paths
from plot_timeline_interactive import (
    get_usa_states_geo_df,
    get_countries_geo_df,
    REGION_NAME_COL,
    LONG_COL,
    LAT_COL,
)


def nan_to_none(x):
    return None if pd.isna(x) else x


def data_to_json(outfile: Path):
    df: pd.DataFrame = pd.read_csv(Paths.DATA_TABLE)

    usa_df = get_usa_states_geo_df()[[REGION_NAME_COL, LONG_COL, LAT_COL]]
    countries_df = get_countries_geo_df()[[REGION_NAME_COL, LONG_COL, LAT_COL]]

    category_map = {}
    cat_cols = [
        Columns.STATE,
        Columns.COUNTRY,
        Columns.TWO_LETTER_STATE_CODE,
        Columns.DATE,
    ]

    records = {}
    for col in df.columns:
        if col in cat_cols and False:
            col_as_cat = df[col].astype("category")
            category_map[col] = dict(
                zip(col_as_cat.cat.codes, df[col].map(nan_to_none),)
            )
            records[col] = col_as_cat.cat.codes.tolist()
        else:
            records[col.lower().replace(" ", "_").replace("cap.", "capita")] = list(
                map(nan_to_none, df[col].tolist())
            )

    data = {
        "records": records,
        "geo": {
            "usa": usa_df.to_dict(orient="list"),
            "world": countries_df.to_dict(orient="list"),
        },
    }
    if category_map:
        data["categories"] = category_map

    if outfile is not None:
        with outfile.open("w") as f:
            json.dump(data, f)

    return data


data_to_json(outfile=Paths.DATA / "data.json")
None
