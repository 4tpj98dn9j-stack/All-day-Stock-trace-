"""Fetch the US investment-grade corporate spread curve by maturity from FRED.

Usage:
    export FRED_API_KEY=...   # or set it in a local .env file
    python fetch_credit_curve.py
    # writes data/credit_curve.json

ICE BofA publishes option-adjusted spreads for the US Corporate index cut
into maturity buckets (1-3yr through 15+yr), and separately cut by rating
(AAA/AA/A/BBB). FRED carries both cuts, but NOT the cross-section: there is
no "BBB, 10-15 year" series. So this builds the term structure for the index
as a whole -- how much extra spread investors demand for lending longer --
and the rating tiers are shown as their own indicators in the macro section.

Three snapshots (today, three months back, a year back) are stored so the
chart shows both the shape of the curve and how it has moved, which is what
a single current curve can't tell you.

Runs daily alongside fetch_macro_data.py in .github/workflows/macro-data.yml.
"""

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from fetch_macro_data import fetch_latest_observations

load_dotenv()

OUTPUT_PATH = Path("data/credit_curve.json")

# Enough daily observations to reach back a year with room for the gaps
# FRED leaves on weekends and holidays.
LOOKBACK_OBSERVATIONS = 400

# Ordered short to long -- the x axis of the curve.
MATURITY_BUCKETS = [
    {"id": "BAMLC1A0C13Y", "label": "1-3년"},
    {"id": "BAMLC2A0C35Y", "label": "3-5년"},
    {"id": "BAMLC3A0C57Y", "label": "5-7년"},
    {"id": "BAMLC4A0C710Y", "label": "7-10년"},
    {"id": "BAMLC7A0C1015Y", "label": "10-15년"},
    {"id": "BAMLC8A0C15PY", "label": "15년+"},
]

# Days back from the newest observation. Max three snapshots -- that's the
# categorical palette's limit in static/script.js.
SNAPSHOTS = [
    {"name": "현재", "days_ago": 0},
    {"name": "3개월 전", "days_ago": 91},
    {"name": "1년 전", "days_ago": 365},
]


def value_on_or_before(observations, target):
    """Spread at `target`, or the nearest earlier observation.

    `observations` is newest-first, as fetch_latest_observations returns it.
    Index spreads are only published on business days, so an exact date match
    would miss whenever the target lands on a weekend or holiday.
    """
    for obs in observations:
        if date.fromisoformat(obs["date"]) <= target:
            # FRED quotes these in percent; the curve is drawn in basis
            # points, which is how credit spreads are normally discussed.
            return {"date": obs["date"], "value": round(float(obs["value"]) * 100, 1)}
    return None


def build_credit_curve(api_key):
    observations_by_bucket = {}
    for bucket in MATURITY_BUCKETS:
        try:
            observations_by_bucket[bucket["id"]] = fetch_latest_observations(
                bucket["id"], api_key, count=LOOKBACK_OBSERVATIONS
            )
        except Exception:
            observations_by_bucket[bucket["id"]] = []

    # Anchor every snapshot to the same date so the three curves are
    # genuinely comparable, even if one bucket published a day later.
    newest = [
        obs[0]["date"] for obs in observations_by_bucket.values() if obs
    ]
    latest_date = min(newest) if newest else None

    snapshots = []
    if latest_date:
        anchor = date.fromisoformat(latest_date)
        for snapshot in SNAPSHOTS:
            target = anchor - timedelta(days=snapshot["days_ago"])
            points = [
                value_on_or_before(observations_by_bucket[bucket["id"]], target)
                for bucket in MATURITY_BUCKETS
            ]
            if not any(points):
                continue
            snapshots.append(
                {
                    "name": snapshot["name"],
                    "date": next(p["date"] for p in points if p),
                    "values": [p["value"] if p else None for p in points],
                }
            )

    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "ICE BofA US Corporate Index (FRED)",
        "unit": "bp",
        "latest_date": latest_date,
        "buckets": [bucket["label"] for bucket in MATURITY_BUCKETS],
        "snapshots": snapshots,
    }


def main():
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise SystemExit("FRED_API_KEY environment variable is required (see README)")

    data = build_credit_curve(api_key)

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved credit curve to {OUTPUT_PATH} (latest: {data['latest_date']})")


if __name__ == "__main__":
    main()
