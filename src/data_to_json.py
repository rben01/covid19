# %%
import json
from pathlib import Path

import pandas as pd

from constants import Columns, Paths


def nan_to_none(x):
    return None if pd.isna(x) else x


def data_to_json(outfile: Path):
    df: pd.DataFrame = pd.read_csv(Paths.DATA_TABLE)

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
            records[col] = list(map(nan_to_none, df[col].tolist()))

    data = {"categories": category_map, "records": records}
    if outfile is not None:
        with outfile.open("w") as f:
            json.dump(data, f)

    return data


data_to_json(outfile=Paths.DATA / "data.json")
None
