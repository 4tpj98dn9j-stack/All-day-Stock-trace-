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

Nasdaq Composite and VIX are deliberately NOT sourced from FRED here --
they're already shown (with same-day Yahoo Finance data) in the dashboard's
"나스닥 시황" section, so pulling them again from FRED would just duplicate
that with a one-day-stale number.
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
    {"id": "DGS10", "name": "10년물 국채금리", "prefix": "", "unit": "%"},
    {"id": "FEDFUNDS", "name": "연방기금금리", "prefix": "", "unit": "%"},
    # CPIAUCSL is a raw index level (~310-320), not very readable on its own,
    # so this is shown as a year-over-year % change (the usual "CPI" headline
    # number) instead of the level.
    {"id": "CPIAUCSL", "name": "CPI(전년동월비)", "prefix": "", "unit": "%", "transform": "yoy"},
    # FRED has no series scoped purely to "Standing Repo Facility" usage.
    # RPONTSYD (the Fed's aggregate overnight repo purchases under Temporary
    # Open Market Operations) is the closest available proxy: since the SRF
    # was established in 2021, this total is effectively driven by SRF
    # take-up.
    {"id": "RPONTSYD", "name": "SRF(상시 레포) 잔액", "prefix": "$", "unit": "B"},
    # WALCL is in millions of USD; scaled down to trillions for readability.
    {"id": "WALCL", "name": "Fed 대차대조표 총자산", "prefix": "$", "unit": "T", "scale": 1e-6},
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
        "limit": max(count * 2, 10),
    }
    response = requests.get(FRED_API_URL, params=params, timeout=10)
    response.raise_for_status()
    observations = response.json().get("observations", [])
    valid = [o for o in observations if o.get("value") not in (None, ".")]
    return valid[:count]


def build_series_entry(meta, api_key):
    """Fetch and format one series, either as a level (value + change) or,
    for transform="yoy", as a year-over-year percent change computed from
    12 (and 13, for the prior period's YoY) months of observations back.
    """
    base = {"name": meta["name"], "prefix": meta.get("prefix", ""), "unit": meta.get("unit", "")}
    transform = meta.get("transform", "level")

    if transform == "yoy":
        try:
            observations = fetch_latest_observations(meta["id"], api_key, count=14)
        except Exception:
            observations = []

        if len(observations) < 13:
            return {**base, "error": "no data"}

        yoy = (float(observations[0]["value"]) / float(observations[12]["value"]) - 1) * 100
        change = None
        if len(observations) >= 14:
            prev_yoy = (float(observations[1]["value"]) / float(observations[13]["value"]) - 1) * 100
            change = round(yoy - prev_yoy, 4)

        return {
            **base,
            "date": observations[0]["date"],
            "value": round(yoy, 4),
            "prev_value": None,
            "change": change,
        }

    try:
        observations = fetch_latest_observations(meta["id"], api_key, count=2)
    except Exception:
        observations = []

    if not observations:
        return {**base, "error": "no data"}

    scale = meta.get("scale", 1)
    latest = observations[0]
    value = round(float(latest["value"]) * scale, 4)
    prev_value = round(float(observations[1]["value"]) * scale, 4) if len(observations) > 1 else None
    change = round(value - prev_value, 4) if prev_value is not None else None

    return {**base, "date": latest["date"], "value": value, "prev_value": prev_value, "change": change}


def build_macro_data(api_key):
    series_data = {meta["id"]: build_series_entry(meta, api_key) for meta in MACRO_SERIES}
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
