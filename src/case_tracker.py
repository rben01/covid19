# %%
import enum
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import display  # noqa F401

import read_in_old_data
from constants import (
    CASE_THRESHOLD,
    USA_STATE_CODES,
    CaseTypes,
    Columns,
    Locations,
    Paths,
)
from plotting import (
    plot_cases_by_days_since_first_widespread_locally,
    plot_cases_from_fixed_date,
)

DATA_PATH = Paths.ROOT / "csse_covid_19_data" / "csse_covid_19_time_series"


class DataOrigin(enum.Enum):
    USE_LOCAL_UNCONDITIONALLY = enum.auto()
    USE_LOCAL_IF_EXISTS_ELSE_FETCH_FROM_WEB = enum.auto()
    FETCH_FROM_WEB_UNCONDITIONALLY = enum.auto()

    def should_try_to_use_local(self) -> bool:
        return self in [
            DataOrigin.USE_LOCAL_UNCONDITIONALLY,
            DataOrigin.USE_LOCAL_IF_EXISTS_ELSE_FETCH_FROM_WEB,
        ]


class SaveFormats(enum.Enum):
    CSV = ".csv"
    PARQUET = ".parquet"

    def path_with_fmt_suffix(self, path: Path) -> Path:
        return path.with_suffix(self.value)

    def read(self, path, *, from_web) -> pd.DataFrame:
        if self == SaveFormats.CSV:
            df = pd.read_csv(path, low_memory=False, dtype="string")
            df: pd.DataFrame

            if from_web:
                df = df.rename(
                    columns={
                        "type": Columns.CASE_TYPE,
                        "value": Columns.CASE_COUNT,
                        "country": Columns.THREE_LETTER_COUNTRY_CODE,
                        "state": Columns.TWO_LETTER_STATE_CODE,
                    }
                ).rename(columns=str.title)

                df[Columns.STATE] = df.merge(
                    pd.read_csv(
                        Paths.DATA / "usa_state_abbreviations.csv", dtype="string"
                    ),
                    how="left",
                    left_on=Columns.TWO_LETTER_STATE_CODE,
                    right_on="Abbreviation:",
                )["US State:"]
                df[Columns.STATE] = (
                    df[Columns.STATE]
                    .fillna(df[Columns.TWO_LETTER_STATE_CODE])
                    .astype("string")
                )

                df[Columns.COUNTRY] = df.merge(
                    pd.read_csv(Paths.DATA / "country_codes.csv", dtype="string"),
                    how="left",
                    left_on=Columns.THREE_LETTER_COUNTRY_CODE,
                    right_on="A3 (UN)",
                )["COUNTRY"]
                df[Columns.COUNTRY] = df[Columns.COUNTRY].fillna(
                    df[Columns.THREE_LETTER_COUNTRY_CODE]
                )
                col_order = df.columns.tolist()
                country_col_index = (
                    col_order.index(Columns.THREE_LETTER_COUNTRY_CODE) + 1
                )
                # Place state and country (currently last columns) after country code
                col_order = [
                    *col_order[:country_col_index],
                    Columns.STATE,
                    Columns.COUNTRY,
                    *col_order[country_col_index:-2],
                ]
                df = df.reindex(col_order, axis=1)

                df[Columns.CASE_TYPE] = df[Columns.CASE_TYPE].map(
                    lambda s: s[0].upper() + s[1:]
                )

            df[Columns.DATE] = pd.to_datetime(df[Columns.DATE])
            df[Columns.CASE_COUNT] = df[Columns.CASE_COUNT].fillna("0").astype(float)

            # As much as these should be categorical, for whatever reason groupby on
            # categorical data has absolutely terrible performance
            # Somehow groupby on ordinary strings is much better
            # At some point I'll revisit this and see if the performance is fixed
            for col in [
                Columns.CITY,
                Columns.COUNTY_NOT_COUNTRY,
                Columns.STATE,
                Columns.THREE_LETTER_COUNTRY_CODE,
                Columns.COUNTRY,
                Columns.URL,
                Columns.LATITUDE,
                Columns.LONGITUDE,
                Columns.CASE_TYPE,
            ]:
                pass
                # df[col] = df[col].astype("category")

            return df
        elif self == SaveFormats.PARQUET:
            df = pd.read_parquet(path)
            # parquet seems to store pd.StringType() cols as orindary str
            for col in Columns.string_cols:
                try:
                    df[col] = df[col].astype("string")
                except KeyError:
                    continue
            return df
        else:
            raise ValueError(f"Unhandled case {self} when reading")

    def save(self, df: pd.DataFrame, path: Path):
        if self == SaveFormats.CSV:
            df.to_csv(path, index=False)
        elif self == SaveFormats.PARQUET:
            df.to_parquet(path, index=False, compression="brotli")
        else:
            raise ValueError(f"Unhandled case {self} when writing")


def get_full_dataset(data_origin: DataOrigin, *, fmt: SaveFormats) -> pd.DataFrame:

    local_data_path = fmt.path_with_fmt_suffix(
        Paths.DATA / "covid_long_data_all_countries_states_counties"
    )
    if data_origin.should_try_to_use_local():
        try:
            df = fmt.read(local_data_path, from_web=False)
        except (FileNotFoundError, IOError):
            if data_origin == DataOrigin.USE_LOCAL_UNCONDITIONALLY:
                raise
            return get_full_dataset(DataOrigin.FETCH_FROM_WEB_UNCONDITIONALLY, fmt=fmt)

    else:
        df = SaveFormats.CSV.read(
            "https://coronadatascraper.com/timeseries-tidy.csv", from_web=True
        )
        fmt.save(df, local_data_path)

    return df


def remove_extraneous_rows(df: pd.DataFrame) -> pd.DataFrame:
    # For some reason USA is listed twice, once under country code 'US' and once
    # under 'USA'. 'US' is garbage data so remove it
    df = df[df[Columns.THREE_LETTER_COUNTRY_CODE] != "US"]

    # Cache isna() calculations
    is_null = {
        col: df[col].isna()
        for col in [Columns.CITY, Columns.COUNTY_NOT_COUNTRY, Columns.STATE]
    }
    df = df[
        (
            # For most countries, only keep country-level data
            (~df[Columns.COUNTRY].isin([Locations.USA, Locations.CHINA]))
            & is_null[Columns.CITY]
            & is_null[Columns.COUNTY_NOT_COUNTRY]
            & is_null[Columns.STATE]
        )
        | (  # For China, keep only province-level data
            # (State and province are the same column)
            (df[Columns.COUNTRY] == Locations.CHINA)
            & (~is_null[Columns.STATE])
        )
        | (
            # For USA, keep only state-level data, excluding territories like Guam
            (df[Columns.COUNTRY] == Locations.USA)
            & is_null[Columns.CITY]
            & is_null[Columns.COUNTY_NOT_COUNTRY]
            & df[Columns.TWO_LETTER_STATE_CODE].isin(USA_STATE_CODES)
        )
    ]

    # We don't need these statistics
    df = df[~df[Columns.CASE_TYPE].isin([CaseTypes.GROWTH_FACTOR, CaseTypes.TESTED])]

    return df


def fill_gaps_with_old_data(df: pd.DataFrame) -> pd.DataFrame:
    old_data = read_in_old_data.get_old_data()
    old_data = old_data[old_data[Columns.DATE] <= pd.Timestamp("2020-03-20")]
    # Ordinarily we'd use Columns.LOCATION_NAME as an identifier column, but it hasn't
    # been assigned yet. Since it's determined by COUNTRY and STATE we can use
    # those instead (and we need at least one of them anyway in case location
    # names aren't unique)
    df = pd.concat(
        [
            df.assign(**{Columns.SOURCE: "new"}),
            old_data.assign(**{Columns.SOURCE: "old"}),
        ],
        axis=0,
        ignore_index=True,
    )
    for col in Columns.string_cols:
        df[col] = df[col].fillna("").astype("string")

    df = df.drop_duplicates(
        [Columns.COUNTRY, Columns.STATE, Columns.DATE, Columns.CASE_TYPE], keep="last",
    )
    return df


def append_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    groupby_cols = [Columns.DATE, Columns.CASE_TYPE]

    world_case_counts = df.groupby(groupby_cols)[Columns.CASE_COUNT].sum()

    china_case_counts = (
        df[df[Columns.COUNTRY] == Locations.CHINA]
        .groupby(groupby_cols)[Columns.CASE_COUNT]
        .sum()
    )

    usa_case_counts = (
        df[df[Columns.COUNTRY] == Locations.USA]
        .groupby(groupby_cols)[Columns.CASE_COUNT]
        .sum()
    )

    world_minus_china_case_counts = world_case_counts.sub(china_case_counts)
    world_minus_china_case_counts

    dfs = [df]
    for country, case_count_series in {
        Locations.WORLD: world_case_counts,
        Locations.CHINA: china_case_counts,
        Locations.USA: usa_case_counts,
        Locations.WORLD_MINUS_CHINA: world_minus_china_case_counts,
    }.items():
        case_count_df = case_count_series.reset_index()

        # I assume it's a problem with groupby not supporting StringDType indices
        case_count_df[Columns.CASE_TYPE] = case_count_df[Columns.CASE_TYPE].astype(
            "string"
        )

        case_count_df[Columns.COUNTRY] = country
        case_count_df[Columns.COUNTRY] = case_count_df[Columns.COUNTRY].astype("string")

        # case_count_df now has four columns: country, date, case type, count
        for col in [
            Columns.CITY,
            Columns.COUNTY_NOT_COUNTRY,
            Columns.TWO_LETTER_STATE_CODE,
            Columns.STATE,
            Columns.THREE_LETTER_COUNTRY_CODE,
            Columns.URL,
            Columns.POPULATION,
            Columns.LATITUDE,
            Columns.LONGITUDE,
        ]:
            case_count_df[col] = pd.NA
            case_count_df[col] = case_count_df[col].astype("string")
            case_count_df[Columns.SOURCE] = "new"

        dfs.append(case_count_df)

    return pd.concat(dfs, axis=0, sort=False, ignore_index=True)


def assign_location_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[Columns.COUNTRY] = (
        df[Columns.COUNTRY]
        .replace(
            {
                "Iran, Islamic Republic of": Locations.IRAN,
                "Korea, Republic of": Locations.SOUTH_KOREA,
                "Georgia": "Georgia (country)",
                "Viet Nam": "Vietnam",
                "XKX": "Kosovo",
            }
        )
        .astype("string")
    )
    df[Columns.IS_STATE] = df[Columns.STATE].notna() & (
        df[Columns.STATE].str.strip() != ""
    )
    df[Columns.LOCATION_NAME] = df[Columns.STATE].where(
        df[Columns.STATE].notna() & (df[Columns.STATE].str.strip() != ""),
        df[Columns.COUNTRY],
    )
    return df


def get_df_with_days_since_n_confirmed_cases(
    df: pd.DataFrame, confirmed_case_threshold: int
) -> pd.DataFrame:
    OUTBREAK_START_DATE_COL = "Outbreak start date"
    outbreak_start_dates = (
        df[
            (df[Columns.CASE_TYPE] == CaseTypes.CONFIRMED)
            & (df[Columns.CASE_COUNT] >= confirmed_case_threshold)
        ]
        .groupby(Columns.id_cols)[Columns.DATE]
        .min()
        .rename(OUTBREAK_START_DATE_COL)
    )
    df = df.merge(outbreak_start_dates, how="left", on=Columns.id_cols)
    df[Columns.DAYS_SINCE_OUTBREAK] = (
        df[Columns.DATE] - df[OUTBREAK_START_DATE_COL]
    ).dt.days

    return df


def clean_up(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Fill NAs for groupby purposes
    for col in Columns.string_cols:
        df[col] = df[col].fillna("").astype("string")

    # Hereafter df is sorted by date, which is helpful as it allows using .iloc[-1]
    # to get current (or most recent known) situation per location
    df = df.sort_values(
        [Columns.LOCATION_NAME, Columns.DATE, Columns.CASE_TYPE], ascending=True
    )

    return df


def get_df(*, refresh_local_data: bool) -> pd.DataFrame:
    if refresh_local_data:
        origin = DataOrigin.FETCH_FROM_WEB_UNCONDITIONALLY
    else:
        origin = DataOrigin.USE_LOCAL_IF_EXISTS_ELSE_FETCH_FROM_WEB

    df = get_full_dataset(origin, fmt=SaveFormats.PARQUET)
    df = remove_extraneous_rows(df)
    df = fill_gaps_with_old_data(df)
    df = append_aggregates(df)
    df = assign_location_names(df)
    df = get_df_with_days_since_n_confirmed_cases(df, CASE_THRESHOLD)
    df = clean_up(df)
    return df


def keep_only_n_largest_locations(df: pd.DataFrame, n: int) -> pd.DataFrame:
    def get_n_largest_locations(df: pd.DataFrame, n: int) -> pd.Series:
        return (
            df[df[Columns.CASE_TYPE] == CaseTypes.CONFIRMED]
            .groupby(Columns.id_cols)
            .apply(lambda g: g[Columns.CASE_COUNT].iloc[-1])
            .nlargest(n)
            .rename(CaseTypes.CONFIRMED)
        )

    def keep_only_above_cutoff(df: pd.DataFrame, cutoff: float) -> pd.DataFrame:
        return df.groupby(Columns.id_cols).filter(
            lambda g: (
                g.loc[
                    g[Columns.CASE_TYPE] == CaseTypes.CONFIRMED, Columns.CASE_COUNT
                ].iloc[-1]
                >= cutoff
            )
        )

    n_largest_location_case_counts = get_n_largest_locations(df, n)
    case_count_cutoff = n_largest_location_case_counts.min()
    return keep_only_above_cutoff(df, case_count_cutoff)


def get_world_df(df: pd.DataFrame) -> pd.DataFrame:
    return df[
        df[Columns.LOCATION_NAME].isin(
            [Locations.WORLD, Locations.WORLD_MINUS_CHINA, Locations.CHINA]
        )
    ]


def get_countries_df(df: pd.DataFrame, n: int) -> pd.DataFrame:
    df = df[
        (~df[Columns.IS_STATE])
        & (
            ~df[Columns.LOCATION_NAME].isin(
                [Locations.WORLD, Locations.WORLD_MINUS_CHINA, Locations.CHINA]
            )
        )
    ]
    return keep_only_n_largest_locations(df, n)


def get_usa_states_df(df: pd.DataFrame, n: int) -> pd.DataFrame:
    df = df[(df[Columns.COUNTRY] == Locations.USA) & df[Columns.IS_STATE]]
    return keep_only_n_largest_locations(df, n)


def get_chinese_provinces_df(df: pd.DataFrame, n: int) -> pd.DataFrame:
    df = df[(df[Columns.COUNTRY] == Locations.CHINA) & df[Columns.IS_STATE]]
    return keep_only_n_largest_locations(df, n)


df = get_df(refresh_local_data=False)
display(df)

plot_cases_from_fixed_date(get_world_df(df))
plot_cases_from_fixed_date(get_countries_df(df, 10))
plot_cases_from_fixed_date(get_usa_states_df(df, 10))
plot_cases_from_fixed_date(get_chinese_provinces_df(df, 10))

plot_cases_by_days_since_first_widespread_locally(get_countries_df(df, 10))
plot_cases_by_days_since_first_widespread_locally(get_usa_states_df(df, 10))

# days_since_outbreak_df = get_df_with_days_since_local_outbreak(df,)

# %%
plt.show()
