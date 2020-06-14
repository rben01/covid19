# %%
import json
from pathlib import Path

import geopandas
import pandas as pd
from IPython.display import display  # noqa E401

from constants import Columns, CaseTypes, Locations, Paths
from plot_timeline_interactive import GEO_DATA_DIR

REGION_NAME_COL = "code"


DATA_DIR: Path = Paths.DOCS / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)

CASE_TYPES = [
    CaseTypes.CONFIRMED,
    CaseTypes.CONFIRMED_PER_CAPITA,
    CaseTypes.DEATHS,
    CaseTypes.DEATHS_PER_CAPITA,
]


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
                "United Republic of Tanzania": "Tanzania",
                "Western Sahara": "W. Sahara",
                "United States of America": "United States",
            }
        )
        .fillna(geo_df[REGION_NAME_COL])
    )

    geo_df = geo_df[
        [
            "featurecla",
            "scalerank",
            "LABELRANK",
            # "SOVEREIGNT",
            # "SOV_A3",
            # "ADM0_DIF",
            "LEVEL",
            # "TYPE",
            REGION_NAME_COL,
            # "ADM0_A3",
            # "GEOU_DIF",
            # "GEOUNIT",
            # "GU_A3",
            # "SU_DIF",
            # "SUBUNIT",
            # "SU_A3",
            # "BRK_DIFF",
            # "NAME",
            # "NAME_LONG",
            # "BRK_A3",
            # "BRK_NAME",
            # "BRK_GROUP",
            "ABBREV",
            # "POSTAL",
            # "FORMAL_EN",
            # "FORMAL_FR",
            # "NAME_CIAWF",
            # "NOTE_ADM0",
            # "NOTE_BRK",
            "NAME_SORT",
            # "NAME_ALT",
            # "MAPCOLOR7",
            # "MAPCOLOR8",
            # "MAPCOLOR9",
            # "MAPCOLOR13",
            # "POP_EST",
            # "POP_RANK",
            # "GDP_MD_EST",
            # "POP_YEAR",
            # "LASTCENSUS",
            # "GDP_YEAR",
            "ECONOMY",
            "INCOME_GRP",
            # "WIKIPEDIA",
            # "FIPS_10_",
            # "ISO_A2",
            # "ISO_A3",
            # "ISO_A3_EH",
            # "ISO_N3",
            # "UN_A3",
            # "WB_A2",
            # "WB_A3",
            # "WOE_ID",
            # "WOE_ID_EH",
            # "WOE_NOTE",
            # "ADM0_A3_IS",
            # "ADM0_A3_US",
            # "ADM0_A3_UN",
            # "ADM0_A3_WB",
            "CONTINENT",
            "REGION_UN",
            "SUBREGION",
            "REGION_WB",
            # "NAME_LEN",
            # "LONG_LEN",
            # "ABBREV_LEN",
            # "TINY",
            # "HOMEPART",
            # "MIN_ZOOM",
            # "MIN_LABEL",
            # "MAX_LABEL",
            # "NE_ID",
            # "WIKIDATAID",
            # "NAME_AR",
            # "NAME_BN",
            # "NAME_DE",
            # "NAME_EN",
            # "NAME_ES",
            # "NAME_FR",
            # "NAME_EL",
            # "NAME_HI",
            # "NAME_HU",
            # "NAME_ID",
            # "NAME_IT",
            # "NAME_JA",
            # "NAME_KO",
            # "NAME_NL",
            # "NAME_PL",
            # "NAME_PT",
            # "NAME_RU",
            # "NAME_SV",
            # "NAME_TR",
            # "NAME_VI",
            # "NAME_ZH",
            "geometry",
        ]
    ]

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

    geo_df = geo_df[
        [
            "STATEFP",
            # "STATENS",
            # "AFFGEOID",
            # "GEOID",
            REGION_NAME_COL,
            "NAME",
            "LSAD",
            # "ALAND",
            # "AWATER",
            "geometry",
        ]
    ]

    return geo_df


def nan_to_none(x):
    return None if pd.isna(x) else x


def jsonify(s):
    return s.lower().replace(" ", "_").replace("cap.", "capita")


def data_to_json(outfile: Path):
    df: pd.DataFrame = pd.read_csv(Paths.DATA_TABLE)

    is_state = df[Columns.STATE].notna()
    usa_df = (
        df[is_state]
        .drop(columns=Columns.COUNTRY)
        .rename(columns={Columns.STATE: "name", Columns.TWO_LETTER_STATE_CODE: "code"})
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
    countries_df = countries_df.rename(columns={Columns.COUNTRY: "name"})
    countries_df["code"] = countries_df["name"]

    usa_geo_df = get_usa_states_geo_df()
    countries_geo_df = get_countries_geo_df()

    data = {}
    for df_name, df in [("usa", usa_df), ("world", countries_df)]:

        data[df_name] = {}

        agg_methods = ["min", "max"]
        agg_stats: pd.DataFrame = df[[Columns.DATE, *CASE_TYPES]].agg(
            agg_methods
        ).rename(columns=jsonify)
        data[df_name]["agg"] = agg_stats.to_dict("dict")

        data[df_name]["agg"][jsonify(Columns.DATE)]["min_nonzero"] = df.loc[
            df[CaseTypes.CONFIRMED] > 0, Columns.DATE
        ].min()

        for ct in CASE_TYPES:
            min_val = df.loc[df[ct] > 0, ct].min()
            if int(min_val) == min_val:
                min_val = int(min_val)

            data[df_name]["agg"][jsonify(ct)]["min_nonzero"] = min_val

        data[df_name]["data"] = {}
        d = data[df_name]["data"]
        for code, group in df.groupby("code"):
            d[code] = {}
            g = group.copy()

            for col in g.columns:
                if col == "code":
                    continue

                if col == "name":
                    d[code][col] = g["name"].iloc[0]
                    continue

                d[code][jsonify(col)] = list(map(nan_to_none, g[col].tolist()))
    with (DATA_DIR / "geo_data.json").open("w") as f:
        geojson = {"usa": usa_geo_df._to_geo(), "world": countries_geo_df._to_geo()}
        json.dump(geojson, f, indent=0)
    # for df_name, df in [("usa", usa_geo_df), ("world", countries_geo_df)]:
    #     with (DATA_DIR / f"geo_{df_name}.json").open("w") as f:
    #         f.write(df.to_json(indent=0))

    if outfile is not None:
        with outfile.open("w") as f:
            json.dump(data, f, indent=0)

    return data


data_to_json(outfile=DATA_DIR / "covid_data.json")
None
