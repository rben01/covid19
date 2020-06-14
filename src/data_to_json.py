# %%
import json
from pathlib import Path

import geopandas
import pandas as pd
from IPython.display import display

from constants import Columns, Locations, Paths
from plot_timeline_interactive import (
    GEO_DATA_DIR,
    LAT_COL,
    LONG_COL,
    REGION_NAME_COL,
)

GEO_COL_REMAPPER = {REGION_NAME_COL: "region_name", LONG_COL: "lon", LAT_COL: "lat"}

DATA_DIR: Path = Paths.DOCS / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)


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
    )

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

    return geo_df


def get_usa_states_geo_df() -> geopandas.GeoDataFrame:
    """Get geometry and long/lat coords for each US state

    :return: GeoDataFrame containing, for each US state: 2-letter state code, geometry
    (boundary), and lists of long/lat coords in bokeh-compatible format
    :rtype: geopandas.GeoDataFrame
    """

    geo_df: geopandas.GeoDataFrame = geopandas.read_file(
        GEO_DATA_DIR / "cb_2017_us_state_20m" / "cb_2017_us_state_20m.shp"
    ).rename(columns={"STUSPS": REGION_NAME_COL}, errors="raise")

    return geo_df


def nan_to_none(x):
    return None if pd.isna(x) else x


def data_to_json(outfile: Path):
    df: pd.DataFrame = pd.read_csv(Paths.DATA_TABLE)

    is_state = df[Columns.STATE].notna()
    usa_df = (
        df[is_state]
        .drop(columns=Columns.COUNTRY)
        .rename(
            columns={Columns.TWO_LETTER_STATE_CODE: "codes", Columns.STATE: "names"}
        )
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
    ).rename(columns={"A3 (UN)": "codes", Columns.COUNTRY: "names"})
    countries_df = countries_df[countries_df["codes"].notna()]

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
