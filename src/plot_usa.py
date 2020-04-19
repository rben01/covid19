# %%
from typing import List, Union

import geopandas
import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import display  # noqa F401
from shapely.geometry import Polygon
from typing_extensions import Literal
from matplotlib.ticker import NullLocator

from case_tracker import get_df, get_usa_states_df
from constants import (
    CaseInfo,
    Columns,
    Counting,
    DiseaseStage,
    InfoField,
    Paths,
    USA_STATE_CODES,
    Select,
)


def get_geo_df() -> geopandas.GeoDataFrame:
    return geopandas.read_file(
        Paths.DATA / "Geo" / "cb_2018_us_state_5m" / "cb_2018_us_state_5m.shp"
    )


def plot_usa_daybyday_case_diffs(
    states_df: pd.DataFrame,
    *,
    geo_df: geopandas.GeoDataFrame,
    stage: Union[DiseaseStage, Literal[Select.ALL]],
    dates: List[pd.Timestamp] = None
) -> plt.Figure:

    DIFF_COL = "Diff_"

    DiseaseStage.verify(stage, allow_select=True)

    if stage is Select.ALL:
        stage_list = list(DiseaseStage)
    else:
        stage_list = [stage]

    stage_list: List[DiseaseStage]
    del stage

    case_diffs_df = states_df[
        (states_df[Columns.COUNT_TYPE] == Counting.PER_CAPITA.name)
        & (states_df[Columns.TWO_LETTER_STATE_CODE].isin(USA_STATE_CODES))
        & (~states_df[Columns.TWO_LETTER_STATE_CODE].isin(["AK", "HI"]))
    ]
    case_diffs_df[DIFF_COL] = case_diffs_df.groupby([Columns.STATE, Columns.STAGE])[
        Columns.CASE_COUNT
    ].diff()

    if dates is None:
        dates: List[pd.Timestamp] = case_diffs_df.loc[
            case_diffs_df[DIFF_COL].notna(), Columns.DATE
        ].unique()

    vmin = 0
    vmaxs = case_diffs_df.groupby(Columns.STAGE)[DIFF_COL].max()

    for date in dates:

        fig, axs = plt.subplots(nrows=len(stage_list))
        if len(stage_list) == 1:
            axs: List[plt.Axes] = [axs]

        for stage, ax in zip(stage_list, axs):
            ax: plt.Axes

            stage_date_df = case_diffs_df[
                (case_diffs_df[Columns.STAGE] == stage.name)
                & (case_diffs_df[Columns.DATE] == date)
            ]
            stage_geo_df: geopandas.GeoDataFrame = geo_df.merge(
                stage_date_df,
                how="left",
                left_on="STUSPS",
                right_on=Columns.TWO_LETTER_STATE_CODE,
            )
            # stage_geo_df = geopandas.clip(stage_geo_df, stage_geo_df)
            # display(stage_geo_df.columns)
            stage_geo_df.plot(
                column=DIFF_COL, ax=ax, legend=True, vmin=0, vmax=vmaxs[stage.name],
            )

            ax.set_title(stage.to_percapita_str())

            for spine in [ax.xaxis, ax.yaxis]:
                spine.set_major_locator(NullLocator())
                spine.set_minor_locator(NullLocator())

        return


geo_df = get_geo_df()
s = get_usa_states_df(get_df(refresh_local_data=False), 55)


plot_usa_daybyday_case_diffs(s, geo_df=geo_df, stage=Select.ALL)
