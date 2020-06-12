# %%
import json
from pathlib import Path

import pandas as pd

from constants import Columns, Paths, Locations
from plot_timeline_interactive import (
    get_usa_states_geo_df,
    get_countries_geo_df,
    REGION_NAME_COL,
    LONG_COL,
    LAT_COL,
)

GEO_COL_REMAPPER = {REGION_NAME_COL: "region_name", LONG_COL: "lon", LAT_COL: "lat"}

DATA_DIR: Path = Paths.DOCS / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)


def nan_to_none(x):
    return None if pd.isna(x) else x


def data_to_json(outfile: Path):
    df: pd.DataFrame = pd.read_csv(Paths.DATA_TABLE)

    is_state = df[Columns.STATE].notna()
    usa_df = (
        df[is_state]
        .drop(columns=Columns.COUNTRY)
        .rename(columns={Columns.TWO_LETTER_STATE_CODE: "code", Columns.STATE: "name"})
    )
    countries_df = df[
        (~is_state)
        & (~df[Columns.COUNTRY].isin([Locations.WORLD, Locations.WORLD_MINUS_CHINA]))
    ].drop(columns=[Columns.STATE, Columns.TWO_LETTER_STATE_CODE])
    countries_df[Columns.COUNTRY] = (
        countries_df[Columns.COUNTRY]
        .map(
            {
                "Bosnia": "Bosnia and Herzegovina",
                "Britain": "United Kingdom",
                "Central African Rep.": "Central African Republic",
                "Czechia": "Czech Republic",
                "Eswatini": "Swaziland",
                "Georgia (country)": "Georgia",
                "S. Sudan": "South Sudan",
                "The Bahamas": "Bahamas",
                "W. Sahara": "Western Sahara",
            }
        )
        .fillna(countries_df[Columns.COUNTRY])
    )

    country_codes_df = pd.read_csv(Paths.DATA / "country_codes.csv").sort_values(
        "COUNTRY"
    )
    country_codes_df["COUNTRY"] = (
        country_codes_df["COUNTRY"]
        .map(
            {
                "Brunei Darussalam": "Brunei",
                "Democratic Republic of the Congo": "Dem. Rep. Congo",
                "Equatorial Guinea": "Eq. Guinea",
                "Holy See (Vatican City State)": "Holy See",
                "Iran, Islamic Republic of": "Iran",
                "Cote d'Ivoire": "Ivory Coast",
                "Lao People's Democratic Republic": "Laos",
                "Moldova, Republic of": "Moldova",
                "Macedonia, the Former Yugoslav Republic of": "North Macedonia",
                "Russian Federation": "Russia",
                "Korea, Republic of": "South Korea",
                "Syrian Arab Republic": "Syria",
                "United Republic of Tanzania": "Tanzania",
                "United Arab Emirates": "UAE",
                "Viet Nam": "Vietnam",
            }
        )
        .fillna(country_codes_df["COUNTRY"])
    )
    countries_df = countries_df.merge(
        country_codes_df, how="left", left_on=Columns.COUNTRY, right_on="COUNTRY",
    ).rename(columns={"A3 (UN)": "code", Columns.COUNTRY: "name"})
    countries_df = countries_df[countries_df["code"].notna()]

    usa_geo_df = get_usa_states_geo_df()
    countries_geo_df = get_countries_geo_df()

    # category_map = {}
    # cat_cols = [
    #     Columns.STATE,
    #     Columns.COUNTRY,
    #     Columns.TWO_LETTER_STATE_CODE,
    #     Columns.DATE,
    # ]

    data = {}
    for name, df in [("usa", usa_df), ("world", countries_df)]:
        if name not in data:
            data[name] = {}

        # data[name] = df.to_dict('records')

        d = data[name]

        for col in df.columns:
            d[col.lower().replace(" ", "_").replace("cap.", "capita")] = list(
                map(nan_to_none, df[col].tolist())
            )

    for name, df in [("usa", usa_geo_df), ("world", countries_geo_df)]:
        with (DATA_DIR / f"geo_{name}.json").open("w") as f:
            f.write(df.to_json())

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


data_to_json(outfile=DATA_DIR / "covid_data.json")
None
