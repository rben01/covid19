import datetime
import time

import requests

from constants import Paths

DATA_PATH = Paths.DATA / "WaPo"

STATES_CURRENT_URL = (
    r"https://www.washingtonpost.com/"
    + r"graphics/2020/world/mapping-spread-new-coronavirus"
    + r"/data/clean/us-states-current.csv"
)

WORLD_HISTORICAL_URL = (
    r"https://www.washingtonpost.com/"
    + r"graphics/2020/world/mapping-spread-new-coronavirus"
    + r"/data/clean/world-daily-historical.csv"
)

HEADERS = {
    "User-Agent": (
        r"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4)"
        + r" AppleWebKit/605.1.15 (KHTML, like Gecko)"
        + r" Version/13.1 Safari/605.1.15"
    )
}


def make_now_str() -> str:
    return datetime.datetime.now(tz=datetime.timezone.utc).isoformat().replace(":", ".")


def request_file_and_save(session: requests.Session, url: str, *, file_basename: str):
    for _ in range(100):
        try:
            r = session.get(url, headers=HEADERS)
            break
        except requests.RequestException:
            time.sleep(5)
            continue

    now_str = make_now_str()
    filename = f"{file_basename}_{now_str}.csv"
    with open(DATA_PATH / filename, "w") as f:
        f.write(r.text)


def main():
    with requests.Session() as s:
        while True:
            request_file_and_save(s, STATES_CURRENT_URL, file_basename="states_current")
            print(
                f"{datetime.datetime.now()}: Got state current file; sleeping for 5 seconds"
            )
            time.sleep(5)
            request_file_and_save(
                s, WORLD_HISTORICAL_URL, file_basename="world_historical"
            )
            print(
                f"{datetime.datetime.now()}: Got world historical file; sleeping for an hour"
            )
            time.sleep(3600)


if __name__ == "__main__":
    main()
