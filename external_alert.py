import csv
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from urllib import request
from urllib.error import URLError

import zoneinfo

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s %(asctime)s]: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
logger = logging.getLogger(__name__)


MACKEREL_API_KEY = os.getenv("MACKEREL_API_KEY")
if not MACKEREL_API_KEY:
    logger.error("MACKEREL_API_KEY is not set")
    exit(1)

BASE_URL = "https://api.mackerelio.com"
CACHE_DIR = "cache"


def get_monitors():
    url = f"{BASE_URL}/api/v0/monitors"
    headers = {"X-Api-Key": MACKEREL_API_KEY}
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req) as response:
            monitors = json.loads(response.read())["monitors"]
        return monitors
    except URLError as e:
        logger.error(f"Error fetching monitors: {e}")
        return []


def get_cache_filename(from_time, to_time):
    hash_input = f"{from_time.isoformat()}_{to_time.isoformat()}"
    hash_value = hashlib.md5(hash_input.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"alerts_{hash_value}.json")


def get_alerts(from_time, to_time):
    cache_file = get_cache_filename(from_time, to_time)

    if os.path.exists(cache_file):
        logger.info(f"Using cached data from {cache_file}")
        with open(cache_file, "r") as f:
            return json.load(f)

    url = f"{BASE_URL}/api/v0/alerts"
    headers = {"X-Api-Key": MACKEREL_API_KEY}
    PAGE_SIZE = 100
    params = {
        "withClosed": "true",
        "from": int(from_time.timestamp()),
        "to": int(to_time.timestamp()),
        "limit": PAGE_SIZE,
    }

    page = 1
    all_alerts = []
    while True:
        full_url = f"{url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
        req = request.Request(full_url, headers=headers)
        try:
            with request.urlopen(req) as response:
                data = json.loads(response.read())
            all_alerts.extend(data["alerts"])
            logger.info(f"[page {page:5}] fetched {len(data['alerts'])} alerts")
            if (
                "nextId" not in data
                or data["alerts"][-1]["openedAt"] < from_time.timestamp()
            ):
                break
            params["nextId"] = data["nextId"]
            page += 1
        except URLError as e:
            logger.error(f"Error fetching alerts: {e}")
            break

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(all_alerts, f)

    return all_alerts


def unix_to_jst(timestamp):
    utc_time = datetime.fromtimestamp(int(timestamp), tz=zoneinfo.ZoneInfo("UTC"))
    jst_time = utc_time.astimezone(zoneinfo.ZoneInfo("Asia/Tokyo"))
    return jst_time.strftime("%Y-%m-%d %H:%M:%S %Z")


def aggregate_alerts(external_alerts, monitors):
    result = []
    for alert in external_alerts:
        monitor = next((m for m in monitors if m["id"] == alert["monitorId"]), {})
        result.append(
            {
                "id": alert["id"],
                "url": monitor.get("url", ""),
                "service": monitor.get("service", ""),
                "openedAt": alert["openedAt"],
                "closedAt": alert["closedAt"],
                "duration": int(alert["closedAt"]) - int(alert["openedAt"])
                if alert["closedAt"]
                else None,
                "openedAt_jst": unix_to_jst(alert["openedAt"]),
                "closedAt_jst": unix_to_jst(alert["closedAt"])
                if alert["closedAt"]
                else "",
            }
        )
    result.sort(key=lambda x: x["openedAt"])
    return result


def save_csv(result):
    if not os.path.exists("output"):
        os.makedirs("output")

    with open("output/external_alerts.csv", "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "url",
                "service",
                "openedAt",
                "closedAt",
                "duration",
                "openedAt_jst",
                "closedAt_jst",
            ],
        )
        writer.writeheader()
        writer.writerows(result)


def main():
    # 取得範囲: [前月の1日,前月の末日)
    today = datetime.now(zoneinfo.ZoneInfo("Asia/Tokyo"))
    first_day_of_this_month = today.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    last_month_end = first_day_of_this_month - timedelta(seconds=1)
    last_month_start = last_month_end.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    logger.info(f"period: {last_month_start} to {last_month_end}")

    logger.info("fetch monitors")
    monitors = get_monitors()

    logger.info("fetch alerts")
    alerts = get_alerts(last_month_start, last_month_end)

    external_alerts = [alert for alert in alerts if alert["type"] == "external"]

    result = aggregate_alerts(external_alerts, monitors)
    logger.info(f"Total alerts: {len(result)}")

    save_csv(result)
    logger.info("CSV file has been written to output/slo.csv")


if __name__ == "__main__":
    main()
