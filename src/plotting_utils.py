from pathlib import Path
from typing import List, Tuple, Union

import numpy as np
import pandas as pd
from typing_extensions import Literal

from constants import (
    CaseInfo,
    CaseTypes,
    Columns,
    Counting,
    DiseaseStage,
    InfoField,
    Locations,
    Select,
)

FROM_FIXED_DATE_DESC = "from_fixed_date"
FROM_LOCAL_OUTBREAK_START_DESC = "from_local_spread_start"

START_DATE = "Start_Date_"
DOUBLING_TIME = "Doubling_Time_"
COLOR = "Color_"

# Decides which doubling times are included in addition to the net (from day 1)
# Don't include 0 here; it'll be added automatically (hence "additional")
ADTL_DAY_INDICES = [-20, -10]

SingleColor = Tuple[float, float, float]
ColorPalette = List[SingleColor]
LocationColorMapping = pd.DataFrame


def form_doubling_time_colname(day_idx: int) -> Tuple[str, int]:
    """Create the column label for the given doubling time days-ago number

    :param day_idx: The iloc[] index giving the time interval (in days) over which to
    compute the doubling time
    :type day_idx: int
    :return: The column label
    :rtype: Tuple[str, int]
    """
    return (DOUBLING_TIME, day_idx)


def get_current_case_data(
    df: pd.DataFrame,
    *,
    stage: Union[DiseaseStage, Literal[Select.DEFAULT]],
    count: Counting,
    x_axis: Columns.XAxis,
) -> pd.DataFrame:
    """Get the current case information

    For the given stage (optional), count, and x_axis, return a dataframe containing the
    current case information -- current stage (per capita) count

    :param df: The dataframe containing all case info
    :type df: pd.DataFrame
    :param stage: The stage to keep when getting current data
    :type stage: Optional[DiseaseStage]
    :param count: The count type to keep when getting current data
    :type count: Counting
    :param x_axis: Used to determine which column to sort the current case data by
    :type x_axis: Columns.XAxis
    :return: Dataframe representing the current state of affairs
    :rtype: pd.DataFrame
    """

    DiseaseStage.verify(stage, allow_select=True)
    Counting.verify(count)
    Columns.XAxis.verify(x_axis)

    # Filter in order to compute doubling time
    df = df[df[Columns.CASE_COUNT] > 0]

    if stage is Select.DEFAULT:
        stage = DiseaseStage.CONFIRMED

    relevant_case_type = CaseInfo.get_info_item_for(
        InfoField.CASE_TYPE, stage=stage, count=count
    )

    day_indices = [0, *ADTL_DAY_INDICES]

    def get_group_stats(g: pd.DataFrame) -> pd.Series:
        # Filter to the relevant case type and just the two columns
        doubling_time_group = g.loc[
            g[Columns.CASE_TYPE] == relevant_case_type,
            [Columns.DATE, Columns.CASE_COUNT],
        ]

        # Get the doubling times for selected day indices (fed to iloc)
        # Keys are stringified iloc positions (0, k, -j, etc),
        # Values are values at that iloc
        doubling_times = {}
        current_date, current_count = doubling_time_group.iloc[-1]
        for day_idx in day_indices:
            col_name = form_doubling_time_colname(day_idx)
            try:
                then_row = doubling_time_group.iloc[day_idx]
            except IndexError:
                doubling_times[col_name] = np.nan
                continue

            # $ currentCount = initialCount * 2^{_days/doublingTime} $
            then_date = then_row[Columns.DATE]
            then_count = then_row[Columns.CASE_COUNT]

            n_days = (current_date - then_date).total_seconds() / 86400
            count_ratio = current_count / then_count

            doubling_times[col_name] = n_days / np.log2(count_ratio)

        data_dict = {
            START_DATE: doubling_time_group[Columns.DATE].min(),
            **doubling_times,
            # Get last case count of each case type for current group
            # .tail(1).sum() is a trick to get the last value if it exists,
            # else 0 (remember, this is sorted by date)
            **(
                g.groupby(Columns.CASE_TYPE)[Columns.CASE_COUNT]
                .apply(lambda h: h.tail(1).sum())
                .to_dict()
            ),
        }

        return pd.Series(
            data_dict,
            index=[
                START_DATE,
                *doubling_times.keys(),
                *CaseInfo.get_info_items_for(InfoField.CASE_TYPE),
            ],
        )

    if x_axis is Columns.XAxis.DAYS_SINCE_OUTBREAK:
        sort_col = form_doubling_time_colname(0)
        sort_ascending = True
    elif x_axis is Columns.XAxis.DATE:
        sort_col = relevant_case_type
        sort_ascending = False
    else:
        x_axis.raise_for_unhandled_case()

    current_case_counts = (
        df.groupby(Columns.location_id_cols)
        .apply(get_group_stats)
        # Order locations by decreasing current confirmed case count
        # This is used to keep plot legend in sync with the order of lines on the graph
        # so the location with the most current cases is first in the legend and the
        # least is last
        .sort_values(sort_col, ascending=sort_ascending)
        .reset_index()
    )

    confirmed_col, death_col = [
        CaseInfo.get_info_item_for(InfoField.CASE_TYPE, stage=stage, count=count)
        for stage in [DiseaseStage.CONFIRMED, DiseaseStage.DEATH]
    ]
    current_case_counts[CaseTypes.MORTALITY] = (
        current_case_counts[death_col] / current_case_counts[confirmed_col]
    )

    return current_case_counts


def get_savefile_path_and_location_heading(
    df: pd.DataFrame,
    *,
    stage: Union[DiseaseStage, Literal[Select.ALL]],
    count: Counting,
    x_axis: Columns.XAxis,
) -> Tuple[Path, str]:
    """Given arguments used to create a plot, return the save path and the location
    heading for that plot

    :param df: The dataframe to be plotted
    :type df: pd.DataFrame
    :param x_axis: The x axis column to be plotted against
    :type x_axis: Columns.XAxis
    :param stage: The disease stage(s) to be plotted
    :type stage: Union[DiseaseStage, Literal[Select.ALL]]
    :param count: The count type to be plotted
    :type count: Counting
    :raises ValueError: Certain know dataframes are explicitly handled; if a dataframe
    containing data that we don't know how to handle is passed, raise a ValueError
    :return: A (Path, str) tuple containing the save path and location heading,
    respectively
    :rtype: Tuple[Path, str]
    """

    DiseaseStage.verify(stage, allow_select=True)
    Counting.verify(count)
    Columns.XAxis.verify(x_axis)

    if Locations.WORLD in df[Columns.COUNTRY].values:
        savefile_basename = "World"
        location_heading = None
    elif df[Columns.COUNTRY].iloc[0] == Locations.CHINA:
        savefile_basename = "China_provinces"
        location_heading = "Province"
    elif df[Columns.IS_STATE].iloc[0]:
        savefile_basename = "States"
        location_heading = "State"
    elif not df[Columns.IS_STATE].any():
        if (df[Columns.COUNTRY] == Locations.CHINA).any():
            savefile_basename = "Countries_w_china"
        else:
            savefile_basename = "Countries_wo_china"

        location_heading = "Country"
    else:
        raise ValueError("DataFrame contents not understood")

    if stage is Select.ALL:
        stage_name = "All"
    else:
        stage_name = stage.pprint()

    savefile_path = (
        Path()
        / count.pprint()
        / x_axis.pprint()
        / f"Stage_{stage_name}"
        / Path(savefile_basename.lower()).with_suffix(".png")
    )
    return savefile_path, location_heading


def remove_empty_leading_dates(df: pd.DataFrame, count: Counting) -> pd.DataFrame:
    """Removes rows prior to the existence of nonzero data

    :param df: The dataframe to alter
    :type df: pd.DataFrame
    :param count: The count method to use when looking for 0-rows
    :type count: Counting
    :return: The filtered dataframe
    :rtype: pd.DataFrame
    """

    Counting.verify(count)

    start_date = df.loc[
        (
            df[Columns.CASE_TYPE]
            == CaseInfo.get_info_item_for(
                InfoField.CASE_TYPE, stage=DiseaseStage.CONFIRMED, count=count
            )
        )
        & (df[Columns.CASE_COUNT] > 0),
        Columns.DATE,
    ].iloc[0]

    df = df[df[Columns.DATE] >= start_date]
    return df
