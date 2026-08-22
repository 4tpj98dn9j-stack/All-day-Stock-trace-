"""Fetch macro economic indicators from the FRED (St. Louis Fed) API and save them as JSON.

Usage:
    export FRED_API_KEY=...   # or set it in a local .env file
    python fetch_macro_data.py
    # writes data/macro.json

Intended to run once per day via .github/workflows/macro-data.yml, using the
FRED_API_KEY GitHub Actions secret. The deployed Flask app only reads the
committed data/macro.json file -- it never calls FRED directly (this
project's dev/CI sandboxes block outbound access to most external APIs;
GitHub-hosted runners don't have that restriction).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
OUTPUT_PATH = Path("data/macro.json")

MACRO_SERIES = [
    {"id": "DGS10", "name": "10년물 국채금리", "unit": "%"},
    {"id": "NASDAQCOM", "name": "나스닥종합지수(FRED)", "unit": ""},
    {"id": "VIXCLS", "name": "VIX 종가", "unit": ""},
    {"id": "FEDFUNDS", "name": "연방기금금리", "unit": "%"},
]


def fetch_latest_observations(series_id, api_key, count=2):
    """Return up to `count` most recent non-missing observations, newest first.

    FRED marks missing values (e.g. weekends/holidays for daily series) with
    "." instead of omitting the row, so we over-fetch and filter.
    """
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 10,
    }
    response = requests.get(FRED_API_URL, params=params, timeout=10)
    response.raise_for_status()
    observations = response.json().get("observations", [])
    valid = [o for o in observations if o.get("value") not in (None, ".")]
    return valid[:count]


def build_macro_data(api_key):
    series_data = {}
    for meta in MACRO_SERIES:
        try:
            observations = fetch_latest_observations(meta["id"], api_key)
        except Exception:
            observations = []

        if not observations:
            series_data[meta["id"]] = {"name": meta["name"], "unit": meta["unit"], "error": "no data"}
            continue

        latest = observations[0]
        value = float(latest["value"])
        prev_value = float(observations[1]["value"]) if len(observations) > 1 else None
        change = round(value - prev_value, 4) if prev_value is not None else None

        series_data[meta["id"]] = {
            "name": meta["name"],
            "unit": meta["unit"],
            "date": latest["date"],
            "value": value,
            "prev_value": prev_value,
            "change": change,
        }

    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "series": series_data,
    }


def main():
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise SystemExit("FRED_API_KEY environment variable is required (see README)")

    data = build_macro_data(api_key)

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved macro data to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
