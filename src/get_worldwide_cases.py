import re
from pathlib import Path
from typing import Mapping

import pandas as pd
from bs4 import BeautifulSoup, Tag

from constants import CASE_COUNT_COL, CASE_TYPE_COL, DATE_COL, ROOT_PATH


def get_worldwide_case_count() -> pd.DataFrame:
    def is_wwcc_bubble(tag: Tag):
        return tag.name == "circle" and tag.has_attr("aria-label")

    with (ROOT_PATH / "Novel coronavirus (COVID-19) situation.html").open() as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    worldwide_case_count_chart = soup.find_all(is_wwcc_bubble)

    data = {DATE_COL: [], CASE_COUNT_COL: [], CASE_TYPE_COL: []}
    for tag in worldwide_case_count_chart:
        label = tag.get("aria-label")
        date, count = re.match(r"^(.*)\s+(\S+)$", label).groups()
        date = pd.Timestamp(date)
        count = int(re.sub(r"\D", "", count))

        data[DATE_COL].append(date)
        data[CASE_COUNT_COL].append(count)
        data[CASE_TYPE_COL].append("Confirmed")

    df = pd.DataFrame(data)
    df = df.sort_values(DATE_COL)
    return df


if __name__ == "__main__":
    print(get_worldwide_case_count())
