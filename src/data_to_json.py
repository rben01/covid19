# %%
import hashlib
import json
import re
from pathlib import Path

import geopandas
import pandas as pd
from IPython.display import display  # noqa E401

from constants import CaseTypes, Columns, Locations, Paths
from plot_timeline_interactive import GEO_DATA_DIR

CODE = "code"


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

    geo_df = geo_df.rename(columns={"ADMIN": CODE}, errors="raise")

    # Keys are what's in the geo df, values are what we want to rename them to
    # Values must match the names in the original data source. If you don't like those
    # names, change them there and then come back and change the values here.
    geo_df[CODE] = (
        geo_df[CODE]
        .map(
            {
                "Central African Republic": "Central African Rep.",
                "Democratic Republic of the Congo": "Dem. Rep. Congo",
                "Equatorial Guinea": "Eq. Guinea",
                "eSwatini": "Eswatini",
                "Georgia (Country)": "Georgia",
                "Republic of Serbia": "Serbia",
                "United Arab Emirates": "UAE",
                "United Kingdom": "Britain",
                "United Republic of Tanzania": "Tanzania",
                "Western Sahara": "W. Sahara",
                "United States of America": "United States",
            }
        )
        .fillna(geo_df[CODE])
    )
    geo_df = geo_df[geo_df[CODE] != "Antarctica"]

    colonial_power_main_countries = {
        "Britain": "England",
        "France": "France, Metropolitan",
        "Norway": "Norway",
        "Papua New Guinea": "Papua New Guinea",
    }

    is_main_country_idx = geo_df[CODE].map(colonial_power_main_countries).isna() | (
        geo_df["NAME_SORT"] == geo_df[CODE].map(colonial_power_main_countries)
    )

    geo_df[CODE] = geo_df[CODE].where(
        is_main_country_idx, geo_df[CODE].str.cat(geo_df["NAME_SORT"], sep=" - "),
    )
    geo_df["name"] = geo_df[CODE]

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
            CODE,
            "name",
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
    ).rename(columns={"STUSPS": CODE}, errors="raise")

    geo_df = geo_df[
        [
            "STATEFP",
            # "STATENS",
            # "AFFGEOID",
            # "GEOID",
            CODE,
            # "NAME",
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


def save_file_with_digest(filename_stub, data):
    data_str = json.dumps(data)
    hasher = hashlib.sha1()
    hasher.update(data_str.encode())
    digest = hasher.hexdigest()
    digest_pattern = f"[a-fA-F0-9]{{{len(digest)}}}"

    existing_data_file_name = None
    for f in DATA_DIR.iterdir():
        if re.match(filename_stub.format(digest_pattern), f.name):
            existing_data_file_name = f.name
            break

    new_data_file_name = filename_stub.format(digest)
    with (DATA_DIR / new_data_file_name).open("w") as f:
        json.dump(data, f, indent=0)

    with (Paths.DOCS / "html" / "plots.ts").open() as f:
        ts_file_contents = f.read()

    ts_file_contents = re.sub(
        re.escape('d3.json("./data/{}")').replace(
            r"\{\}", filename_stub.format(digest_pattern)
        ),
        f'd3.json("./data/{new_data_file_name}")',
        ts_file_contents,
    )

    with (Paths.DOCS / "html" / "plots.ts").open("w") as f:
        f.write(ts_file_contents)

    if (
        existing_data_file_name is not None
        and existing_data_file_name != new_data_file_name
    ):
        print(
            "Deleting", existing_data_file_name, "replacing with", new_data_file_name,
        )
        (DATA_DIR / existing_data_file_name).unlink()


def data_to_json():
    df: pd.DataFrame = pd.read_csv(Paths.DATA_TABLE)
    for c in df:
        if "per cap." in c.lower():
            df[c] *= 100000

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
                "Georgia (country)": "Georgia",
                "North Macedonia": "Macedonia",
                "S. Sudan": "South Sudan",
            }
        )
        .fillna(countries_df[Columns.COUNTRY])
    )
    countries_df = countries_df.rename(columns={Columns.COUNTRY: "name"})

    countries_geo_df = get_countries_geo_df()

    countries_df[CODE] = countries_df.merge(countries_geo_df, how="left", on="name")[
        CODE
    ].values

    usa_geo_df = get_usa_states_geo_df()
    usa_geo_df["name"] = usa_geo_df.merge(
        usa_df.groupby([CODE, "name"]).first().index.to_frame(index=False),
        how="left",
        on=CODE,
    )["name"]

    data = {}
    for df_name, df in [("usa", usa_df), ("world", countries_df)]:

        data[df_name] = {}

        agg_methods = ["min", "max"]
        agg_stats: pd.DataFrame = df[[Columns.DATE, *CASE_TYPES]].agg(
            agg_methods
        ).rename(columns=jsonify)
        data[df_name]["agg"] = {}
        data[df_name]["agg"]["net"] = agg_stats.to_dict("dict")

        data[df_name]["agg"]["net"][jsonify(Columns.DATE)]["min_nonzero"] = df.loc[
            df[CaseTypes.CONFIRMED] > 0, Columns.DATE
        ].min()

        for ct in CASE_TYPES:
            min_val = df.loc[df[ct] > 0, ct].min()
            if int(min_val) == min_val:
                min_val = int(min_val)

            data[df_name]["agg"]["net"][jsonify(ct)]["min_nonzero"] = min_val

        dodd_diffs = df[CASE_TYPES].diff().fillna(0)
        for ct in CASE_TYPES:
            dodd_diffs.loc[dodd_diffs[ct] < 0, ct] = 0
        data[df_name]["agg"]["dodd"] = (
            dodd_diffs.agg(agg_methods).rename(columns=jsonify).to_dict("dict")
        )

        max_moving_avg_days = 7
        for ct in CASE_TYPES:
            min_nonzero = dodd_diffs.loc[dodd_diffs[ct] > 0, ct].min()
            moving_avg = dodd_diffs.rolling(max_moving_avg_days).mean()
            min_val = moving_avg.loc[
                moving_avg[ct] >= min_nonzero / max_moving_avg_days * 0.9, ct
            ].min()
            if int(min_val) == min_val:
                min_val = int(min_val)

            data[df_name]["agg"]["dodd"][jsonify(ct)]["min_nonzero"] = min_val

        outbreak_cutoffs = {
            "Cases": 100,
            "Cases Per Cap.": 1e-5,
            "Deaths": 25,
            "Deaths Per Cap.": 2.5e-6,
        }

        for k in ["dodd", "net"]:
            data[df_name]["agg"][k]["outbreak_cutoffs"] = {
                jsonify(k): v for k, v in outbreak_cutoffs.items()
            }

        data[df_name]["data"] = {}
        d = data[df_name]["data"]
        for code, g in df.groupby(CODE):
            d[code] = {"net": {}}
            d[code]["outbreak_cutoffs"] = {}
            g = g.copy()

            for col in g.columns:
                if col in [CODE, "name"]:
                    continue

                if col == Columns.DATE:
                    elem = {k: i for i, k in enumerate(g[col].tolist())}
                    d[code][jsonify(col)] = elem
                else:
                    elem = list(map(nan_to_none, g[col].tolist()))
                    outbreak_start_idx = int((g[col] < outbreak_cutoffs[ct]).sum())
                    d[code]["outbreak_cutoffs"][jsonify(col)] = outbreak_start_idx
                    d[code]["net"][jsonify(col)] = elem

    geojson = {"usa": usa_geo_df._to_geo(), "world": countries_geo_df._to_geo()}
    save_file_with_digest("geo_data-{}.json", geojson)

    save_file_with_digest("covid_data-{}.json", data)

    return data


if __name__ == "__main__":
    data_to_json()
