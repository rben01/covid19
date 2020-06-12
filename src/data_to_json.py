# %%
import json
from pathlib import Path
import io

import pandas as pd

from constants import Columns, Paths
from plot_timeline_interactive import (
    get_usa_states_geo_df,
    get_countries_geo_df,
    REGION_NAME_COL,
    LONG_COL,
    LAT_COL,
)

GEO_COL_REMAPPER = {REGION_NAME_COL: "region_name", LONG_COL: "lon", LAT_COL: "lat"}


def nan_to_none(x):
    return None if pd.isna(x) else x


def data_to_json(outfile: Path):
    df: pd.DataFrame = pd.read_csv(Paths.DATA_TABLE)

    is_state = df[Columns.STATE].notna()
    usa_df = df[is_state].drop(columns=Columns.COUNTRY)
    countries_df = df[~is_state].drop(
        columns=[Columns.STATE, Columns.TWO_LETTER_STATE_CODE]
    )

    usa_geo_df = get_usa_states_geo_df()
    countries_geo_df = get_countries_geo_df()

    # category_map = {}
    # cat_cols = [
    #     Columns.STATE,
    #     Columns.COUNTRY,
    #     Columns.TWO_LETTER_STATE_CODE,
    #     Columns.DATE,
    # ]

    data = {"usa": {}, "world": {}}
    for name, df in [("usa", usa_df), ("world", countries_df)]:
        r = data[name]
        if "records" not in r:
            r["records"] = {}

        d = r["records"]

        for col in df.columns:
            # if col in cat_cols and False:
            #     col_as_cat = df[col].astype("category")
            #     category_map[col] = dict(
            #         zip(col_as_cat.cat.codes, df[col].map(nan_to_none),)
            #     )
            #     d[col] = col_as_cat.cat.codes.tolist()
            # else:
            d[col.lower().replace(" ", "_").replace("cap.", "capita")] = list(
                map(nan_to_none, df[col].tolist())
            )

    for name, df in [("usa", usa_geo_df), ("world", countries_geo_df)]:
        r = data[name]
        r["geo"] = df._to_geo()

    # data = {
    #     "records": records,
    #     "geo": {
    #         "usa": usa_geo_df.to_dict(orient="index"),
    #         "world": countries_geo_df.to_dict(orient="index"),
    #     },
    # }
    # if category_map:
    #     data["categories"] = category_map

    if outfile is not None:
        with outfile.open("w") as f:
            json.dump(data, f)

    return data


data_to_json(outfile=Paths.DATA / "data.json")
None
