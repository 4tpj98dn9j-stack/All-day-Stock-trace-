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

# Chart-history depth by observation frequency, chosen so every series'
# click-to-chart covers roughly the same multi-year span rather than the
# same point count (a daily series and a monthly series need very
# different counts to each show ~5 years of history).
DAILY_HISTORY = 500  # ~2 years of business days
WEEKLY_HISTORY = 260  # ~5 years of weekly points
MONTHLY_HISTORY = 60  # 5 years of monthly points

MACRO_SERIES = [
    # 금리 / 커브
    {"id": "DGS10", "name": "10년물 국채금리", "prefix": "", "unit": "%", "history_count": DAILY_HISTORY},
    {"id": "DGS2", "name": "2년물 국채금리", "prefix": "", "unit": "%", "history_count": DAILY_HISTORY},
    {"id": "DGS3MO", "name": "3개월물 국채금리", "prefix": "", "unit": "%", "history_count": DAILY_HISTORY},
    # Spreads FRED computes directly; can go negative (yield-curve inversion).
    {"id": "T10Y2Y", "name": "장단기 스프레드(10Y-2Y)", "prefix": "", "unit": "%", "history_count": DAILY_HISTORY},
    {"id": "T10Y3M", "name": "장단기 스프레드(10Y-3M)", "prefix": "", "unit": "%", "history_count": DAILY_HISTORY},
    {"id": "DFII10", "name": "10년 실질금리(TIPS)", "prefix": "", "unit": "%", "history_count": DAILY_HISTORY},
    {"id": "SOFR", "name": "SOFR(익일물 담보금리)", "prefix": "", "unit": "%", "history_count": DAILY_HISTORY},
    {"id": "DFF", "name": "연방기금 실효금리(일별)", "prefix": "", "unit": "%", "history_count": DAILY_HISTORY},
    {"id": "FEDFUNDS", "name": "연방기금금리", "prefix": "", "unit": "%", "history_count": MONTHLY_HISTORY},
    # CPIAUCSL is a raw index level (~310-320), not very readable on its own,
    # so this is shown as a year-over-year % change (the usual "CPI" headline
    # number) instead of the level.
    {"id": "CPIAUCSL", "name": "CPI(전년동월비)", "prefix": "", "unit": "%", "transform": "yoy", "history_count": MONTHLY_HISTORY},

    # 유동성
    # WALCL is in millions of USD; scaled down to trillions for readability.
    {"id": "WALCL", "name": "Fed 대차대조표 총자산", "prefix": "$", "unit": "T", "scale": 1e-6, "history_count": WEEKLY_HISTORY},
    {"id": "RRPONTSYD", "name": "역레포(ON RRP) 잔고", "prefix": "$", "unit": "B", "history_count": DAILY_HISTORY},
    # WRESBAL is in millions of USD (like WALCL); scaled to trillions for readability.
    {"id": "WRESBAL", "name": "은행 지준 잔고", "prefix": "$", "unit": "T", "scale": 1e-6, "history_count": WEEKLY_HISTORY},
    # M2SL is in billions of USD; scaled to trillions for readability.
    {"id": "M2SL", "name": "통화량(M2)", "prefix": "$", "unit": "T", "scale": 1e-3, "history_count": MONTHLY_HISTORY},
    # FRED has no series scoped purely to "Standing Repo Facility" usage.
    # RPONTSYD (the Fed's aggregate overnight repo purchases under Temporary
    # Open Market Operations) is the closest available proxy: since the SRF
    # was established in 2021, this total is effectively driven by SRF
    # take-up.
    {"id": "RPONTSYD", "name": "SRF(상시 레포) 잔액", "prefix": "$", "unit": "B", "history_count": DAILY_HISTORY},

    # 신용 / 리스크
    {"id": "BAMLH0A0HYM2", "name": "하이일드 스프레드", "prefix": "", "unit": "%", "history_count": DAILY_HISTORY},
    {"id": "BAA10Y", "name": "회사채-국채 스프레드(Baa)", "prefix": "", "unit": "%", "history_count": DAILY_HISTORY},
    {"id": "NFCI", "name": "시카고연은 금융여건지수", "prefix": "", "unit": "", "history_count": WEEKLY_HISTORY},
    {"id": "STLFSI4", "name": "세인트루이스연은 금융스트레스지수", "prefix": "", "unit": "", "history_count": WEEKLY_HISTORY},

    # 인플레이션 기대
    {"id": "T5YIE", "name": "5년 기대인플레이션(BEI)", "prefix": "", "unit": "%", "history_count": DAILY_HISTORY},
    {"id": "T10YIE", "name": "10년 기대인플레이션(BEI)", "prefix": "", "unit": "%", "history_count": DAILY_HISTORY},
    {"id": "T5YIFR", "name": "5y5y forward 기대인플레이션", "prefix": "", "unit": "%", "history_count": DAILY_HISTORY},

    # 달러
    {"id": "DTWEXBGS", "name": "무역가중 달러지수(Broad)", "prefix": "", "unit": "", "history_count": DAILY_HISTORY},

    # 실물경제
    # PAYEMS is a cumulative employment level (~161,000 thousand persons),
    # not very readable on its own -- shown as the month-over-month change
    # (e.g. "+180K"), the usual "nonfarm payrolls" headline number.
    {"id": "PAYEMS", "name": "비농업고용 증감(전월비)", "prefix": "", "unit": "K", "transform": "mom_diff", "history_count": MONTHLY_HISTORY},
    {"id": "UNRATE", "name": "실업률", "prefix": "", "unit": "%", "history_count": MONTHLY_HISTORY},
    # ICSA is in raw persons; scaled to thousands to match how it's usually quoted.
    {"id": "ICSA", "name": "신규 실업수당 청구건수", "prefix": "", "unit": "K", "scale": 1e-3, "history_count": WEEKLY_HISTORY},
    {"id": "INDPRO", "name": "산업생산(전년동월비)", "prefix": "", "unit": "%", "transform": "yoy", "history_count": MONTHLY_HISTORY},
    {"id": "UMCSENT", "name": "미시간대 소비자심리지수", "prefix": "", "unit": "", "history_count": MONTHLY_HISTORY},
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
    """Fetch and format one series. Supported transforms:

    - "level" (default): raw value + change vs. the previous observation.
    - "yoy": year-over-year percent change, computed from 12 (and 13, for
      the prior period's YoY) months of observations back. For series whose
      raw level isn't very readable on its own (e.g. a CPI index of ~310).
    - "mom_diff": month-over-month difference between consecutive
      observations (e.g. nonfarm payrolls' "+180K jobs"), for series whose
      raw level is a cumulative stock rather than a meaningful headline
      number on its own.

    Any transform can also set "history_count" to fetch that many chart
    points (chronologically ordered under a "history" key), reusing the
    same raw observations already fetched for the current value -- for
    "yoy"/"mom_diff" this means recomputing the same transform at every
    point in the fetched window, not just the latest one.
    """
    base = {"name": meta["name"], "prefix": meta.get("prefix", ""), "unit": meta.get("unit", "")}
    transform = meta.get("transform", "level")
    scale = meta.get("scale", 1)
    history_count = meta.get("history_count")

    if transform == "yoy":
        min_count = 14
        fetch_count = max(min_count, history_count + 12) if history_count else min_count

        try:
            observations = fetch_latest_observations(meta["id"], api_key, count=fetch_count)
        except Exception:
            observations = []

        if len(observations) < 13:
            return {**base, "error": "no data"}

        yoy = (float(observations[0]["value"]) / float(observations[12]["value"]) - 1) * 100
        change = None
        if len(observations) >= 14:
            prev_yoy = (float(observations[1]["value"]) / float(observations[13]["value"]) - 1) * 100
            change = round(yoy - prev_yoy, 4)

        result = {
            **base,
            "date": observations[0]["date"],
            "value": round(yoy, 4),
            "prev_value": None,
            "change": change,
        }

        if history_count:
            points = [
                {
                    "date": observations[i]["date"],
                    "value": round((float(observations[i]["value"]) / float(observations[i + 12]["value"]) - 1) * 100, 4),
                }
                for i in range(len(observations) - 12)
            ]
            result["history"] = list(reversed(points[:history_count]))

        return result

    if transform == "mom_diff":
        min_count = 3
        fetch_count = max(min_count, history_count + 1) if history_count else min_count

        try:
            observations = fetch_latest_observations(meta["id"], api_key, count=fetch_count)
        except Exception:
            observations = []

        if len(observations) < 2:
            return {**base, "error": "no data"}

        latest_level = float(observations[0]["value"]) * scale
        prev_level = float(observations[1]["value"]) * scale
        value = round(latest_level - prev_level, 4)

        change = None
        if len(observations) >= 3:
            prev_prev_level = float(observations[2]["value"]) * scale
            prev_diff = prev_level - prev_prev_level
            change = round(value - prev_diff, 4)

        result = {
            **base,
            "date": observations[0]["date"],
            "value": value,
            "prev_value": None,
            "change": change,
        }

        if history_count:
            points = [
                {
                    "date": observations[i]["date"],
                    "value": round((float(observations[i]["value"]) - float(observations[i + 1]["value"])) * scale, 4),
                }
                for i in range(len(observations) - 1)
            ]
            result["history"] = list(reversed(points[:history_count]))

        return result

    fetch_count = max(2, history_count) if history_count else 2

    try:
        observations = fetch_latest_observations(meta["id"], api_key, count=fetch_count)
    except Exception:
        observations = []

    if not observations:
        return {**base, "error": "no data"}

    latest = observations[0]
    value = round(float(latest["value"]) * scale, 4)
    prev_value = round(float(observations[1]["value"]) * scale, 4) if len(observations) > 1 else None
    change = round(value - prev_value, 4) if prev_value is not None else None

    result = {**base, "date": latest["date"], "value": value, "prev_value": prev_value, "change": change}

    if history_count:
        # observations are newest-first; store history chronologically (oldest first).
        result["history"] = [
            {"date": obs["date"], "value": round(float(obs["value"]) * scale, 4)}
            for obs in reversed(observations)
        ]

    return result


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
