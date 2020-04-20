# %%
import itertools
import subprocess
from pathlib import Path
from typing import List, Union

import cmocean
import geopandas
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import display  # noqa F401
from matplotlib.collections import PatchCollection
from matplotlib.colors import ListedColormap, LogNorm
from matplotlib.ticker import NullLocator
from mpl_toolkits.axes_grid1 import axes_size, make_axes_locatable
from PIL import Image
from typing_extensions import Literal

from constants import USA_STATE_CODES, Columns, Counting, DiseaseStage, Paths, Select

GEO_FIG_DIR: Path = Paths.FIGURES / "Geo"
DOD_DIFF_DIR: Path = GEO_FIG_DIR / "DayOverDayDiffs"
DOD_DIFF_DIR.mkdir(parents=True, exist_ok=True)


def get_geo_df() -> geopandas.GeoDataFrame:
    return geopandas.read_file(
        Paths.DATA / "Geo" / "cb_2018_us_state_5m" / "cb_2018_us_state_5m.shp"
    ).to_crs(
        "EPSG:2163"
    )  # Google this magic string


def _resize_to_even_dims(img_path: Path):
    image: Image = Image.open(img_path)
    width_px, height_px = image.size
    width_px = (width_px // 2) * 2
    height_px = (height_px // 2) * 2
    image = image.resize((width_px, height_px))
    image.save(img_path)


def plot_usa_daybyday_case_diffs(
    states_df: pd.DataFrame,
    *,
    geo_df: geopandas.GeoDataFrame = None,
    stage: Union[DiseaseStage, Literal[Select.ALL]],
    count: Union[Counting, Literal[Select.ALL]],
    dates: List[pd.Timestamp] = None,
) -> pd.DataFrame:

    Counting.verify(count, allow_select=True)
    DiseaseStage.verify(stage, allow_select=True)

    if geo_df is None:
        geo_df = get_geo_df()

    DIFF_COL = "Diff_"
    ASPECT_RATIO = 1 / 20
    PAD_FRAC = 0.5
    N_CBAR_BUCKETS = 9
    N_CBAR_TICKS = N_CBAR_BUCKETS + 1  # N_CBAR_BUCKETS // 2 + 1
    CMAP = ListedColormap(cmocean.cm.matter(np.linspace(0, 1, N_CBAR_BUCKETS)))
    DPI = 300

    ID_COLS = [
        Columns.TWO_LETTER_STATE_CODE,
        Columns.DATE,
        Columns.STAGE,
        Columns.COUNT_TYPE,
    ]

    if count is Select.ALL:
        count_list = list(Counting)
    else:
        count_list = [count]

    if stage is Select.ALL:
        stage_list = list(DiseaseStage)
    else:
        stage_list = [stage]

    count_list: List[Counting]
    stage_list: List[DiseaseStage]

    if dates is None:
        dates: List[pd.Timestamp] = states_df[Columns.DATE].unique()

    dates = sorted(pd.Timestamp(date) for date in dates)

    case_diffs_df = states_df[
        (states_df[Columns.TWO_LETTER_STATE_CODE].isin(USA_STATE_CODES))
        & (~states_df[Columns.TWO_LETTER_STATE_CODE].isin(["AK", "HI"]))
    ].copy()

    state_date_stage_combos = pd.MultiIndex.from_product(
        [
            case_diffs_df[Columns.TWO_LETTER_STATE_CODE].unique(),
            dates,
            [s.name for s in DiseaseStage],
            [c.name for c in Counting],
        ],
        names=ID_COLS,
    )

    case_diffs_df = (
        state_date_stage_combos.to_frame(index=False)
        .merge(case_diffs_df, how="left", on=ID_COLS,)
        .sort_values(ID_COLS)
    )

    case_diffs_df[Columns.CASE_COUNT] = case_diffs_df[Columns.CASE_COUNT].fillna(0)

    case_diffs_df[DIFF_COL] = case_diffs_df.groupby(
        [Columns.TWO_LETTER_STATE_CODE, Columns.STAGE, Columns.COUNT_TYPE]
    )[Columns.CASE_COUNT].diff()

    case_diffs_df = case_diffs_df[case_diffs_df[DIFF_COL].notna()]

    dates = case_diffs_df[Columns.DATE].unique()

    vmins = {
        Counting.TOTAL_CASES: 1,
        Counting.PER_CAPITA: case_diffs_df.loc[
            case_diffs_df[DIFF_COL] > 0, DIFF_COL
        ].min(),
    }
    vmaxs = case_diffs_df.groupby([Columns.STAGE, Columns.COUNT_TYPE])[DIFF_COL].max()

    fig: plt.Figure = plt.figure(facecolor="white")

    # For encoding to mp4, these both have to be even integers
    fig_width_px = len(count_list) * 1800
    fig_height_px = len(stage_list) * 1000 + 200

    img_files: List[Path] = []

    for date in reversed(dates):
        date = pd.Timestamp(date)
        fig.suptitle(date.strftime(r"%b %-d, %Y"))

        for i, (stage, count) in enumerate(
            itertools.product(stage_list, count_list), start=1
        ):
            ax: plt.Axes = fig.add_subplot(len(stage_list), len(count_list), i)

            stage_date_df = case_diffs_df[
                (case_diffs_df[Columns.STAGE] == stage.name)
                & (case_diffs_df[Columns.COUNT_TYPE] == count.name)
                & (case_diffs_df[Columns.DATE] == date)
            ]

            # Should have length 49 (50 + DC - AK - HI)
            stage_geo_df: geopandas.GeoDataFrame = geo_df.merge(
                stage_date_df,
                how="inner",
                left_on="STUSPS",
                right_on=Columns.TWO_LETTER_STATE_CODE,
            )

            stage_geo_df.plot(column=DIFF_COL, ax=ax, legend=False)
            stage_geo_df.boundary.plot(ax=ax, linewidth=0.06, edgecolor="k")

            naive_vmax = vmaxs.loc[(stage.name, count.name)]
            power_of_10 = np.floor(np.log10(naive_vmax))
            cbar_tick_dist = 2 * 10 ** power_of_10

            vmax = np.ceil(naive_vmax / cbar_tick_dist) * cbar_tick_dist

            vmin = vmins[count]

            # https://stackoverflow.com/a/33505522
            divider = make_axes_locatable(ax)
            width = axes_size.AxesY(ax, aspect=ASPECT_RATIO)
            pad = axes_size.Fraction(PAD_FRAC, width)
            cax = divider.append_axes("right", size=width, pad=pad)
            # cmap = plt.get_cmap('cividis', N_CBAR_BUCKETS)  # bucket colors

            # https://stackoverflow.com/a/43807666
            norm = LogNorm(vmin, vmax)
            scm = plt.cm.ScalarMappable(norm=norm, cmap=CMAP)

            cbar = fig.colorbar(scm, cax=cax)
            cbar.minorticks_off()

            # Adapted from https://stackoverflow.com/a/50314773
            bucket_size = (vmax / vmin) ** (1 / N_CBAR_BUCKETS)
            tick_dist = bucket_size
            # ((vmax / vmin) / bucket_size) ** (1 / (N_CBAR_TICKS - 1))

            tick_locs = [
                *(
                    vmin
                    # * (bucket_size ** 0.5)
                    * (tick_dist ** np.arange(0, N_CBAR_TICKS))
                ),
            ]

            cbar.set_ticks(tick_locs)
            if count is Counting.PER_CAPITA:
                fmt_str = "{:.2e}"
            else:
                fmt_str = "{:.5g}"
            cbar.set_ticklabels(
                [fmt_str.format(x) if x != 0 else "0" for x in tick_locs]
            )

            # https://stackoverflow.com/a/23091382
            # "In my case the plot was more complex, to find the correct child I had to
            # do: for PCM in ax.get_children(): if type(PCM) ==
            # matplotlib.image.AxesImage: break"
            for pcm in ax.get_children():
                if type(pcm) == PatchCollection:
                    pcm: plt.cm.ScalarMappable
                    pcm.set_cmap(CMAP)
                    pcm.set_clim(vmin, vmax)
                    pcm.set_norm(norm)
                    break

            ax_stage_name = {
                DiseaseStage.CONFIRMED: "Cases",
                DiseaseStage.DEATH: "Deaths",
            }[stage]
            ax_title_components = ["New Daily", ax_stage_name]
            if count is Counting.PER_CAPITA:
                ax_title_components.append("Per Cap.")

            ax.set_title(" ".join(ax_title_components))

            for spine in [ax.xaxis, ax.yaxis]:
                spine.set_major_locator(NullLocator())
                spine.set_minor_locator(NullLocator())

        save_path = DOD_DIFF_DIR / f"dod_diff_{date.strftime(r'%Y%m%d')}.png"
        fig.set_size_inches(fig_width_px / DPI, fig_height_px / DPI)
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        img_files.append(save_path)

        fig.clf()

        print(f"Saved '{save_path}'")

        # if date < pd.Timestamp("2020-4-16"):
        #     break

    print("Resizing images")
    for img_file in img_files:
        _resize_to_even_dims(img_file)

    return case_diffs_df


def make_video(fps: float):
    img_files = sorted(DOD_DIFF_DIR.glob("*.png"))
    concat_demux_lines = []

    # https://trac.ffmpeg.org/wiki/Slideshow
    for f in img_files:
        concat_demux_lines.append(f"file '{f}'")
        concat_demux_lines.append(f"duration {1/fps}")

    concat_demux_lines.append(f"file '{img_files[-1]}'")

    concat_demux_str = "\n".join(concat_demux_lines)

    save_path = GEO_FIG_DIR / "dod_diffs.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-protocol_whitelist",
        "file,pipe,crypto",
        "-safe",
        "0",
        "-i",
        "-",
        "-vsync",
        "vfr",
        "-vcodec",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(save_path),
    ]

    ps = subprocess.run(cmd, input=concat_demux_str, text=True)

    ps.check_returncode()

    print(f"Saved video '{save_path}'")


if __name__ == "__main__":
    make_video(1.25)
    # from case_tracker import get_df, get_usa_states_df

    # geo_df = get_geo_df()
    # s = get_usa_states_df(get_df(refresh_local_data=False))

    # plot_usa_daybyday_case_diffs(s, geo_df=geo_df, stage=Select.ALL, count=Select.ALL)
