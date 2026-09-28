"""Fetch the Fed's SCOOS dealer-financing survey from FRED and save it as JSON.

Usage:
    export FRED_API_KEY=...   # or set it in a local .env file
    python fetch_scoos_data.py
    # writes data/scoos.json

SCOOS (Senior Credit Officer Opinion Survey on Dealer Financing Terms) is a
quarterly Federal Reserve Board survey of the large dealers that finance
hedge funds, REITs and other leveraged market participants. It's the closest
thing to a direct read on whether the plumbing behind credit markets is
loosening or tightening, which market-price indicators (spreads, MOVE) only
show second-hand.

The Fed publishes the survey as HTML/PDF exhibits at
federalreserve.gov/data/scoos.htm, but the underlying numbers are also on
FRED as release 571. The exhibit charts' own "net percentage" lines are
there as EXHE<exhibit>C<chart>Q<question>NP series, so this pulls those
directly rather than recomputing them from the per-answer respondent counts
(SFQ*NR) -- same numbers the Fed prints, no reconstruction to get wrong.

"Net percentage" = share of dealers reporting an increase (or improvement)
minus the share reporting a decrease (or deterioration). Positive means more
dealers saw it rise than fall; it is not a level.

Runs once a quarter via .github/workflows/scoos-data.yml. As with
fetch_macro_data.py, the deployed Flask app only reads the committed
data/scoos.json -- it never calls FRED itself.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from fetch_macro_data import fetch_latest_observations

load_dotenv()

OUTPUT_PATH = Path("data/scoos.json")

# The survey started in 2011Q4 in its current form, so ~60 quarters covers
# the entire history of every series below.
QUARTERLY_HISTORY = 60

# Panel grouping follows FRED's own chart numbering, which mirrors the Fed's
# Exhibit 3 layout: charts 1-4 are the funding-demand panels, charts 5-6 the
# market-liquidity panels. Max three series per panel -- the categorical
# palette in static/script.js only validates to three.
SCOOS_GROUPS = [
    {
        "title": "기초시장 유동성·기능 개선 응답",
        "description": "딜러들이 해당 시장의 유동성·거래 기능이 좋아졌다고 답한 순비율. 플러스면 개선, 마이너스면 악화 응답이 더 많았다는 뜻입니다.",
        "panels": [
            {
                "title": "회사채·CMBS",
                "series": [
                    {"id": "EXHE3C5Q55NP", "name": "투자등급 회사채"},
                    {"id": "EXHE3C5Q59NP", "name": "하이일드 회사채"},
                    {"id": "EXHE3C5Q73NP", "name": "CMBS"},
                ],
            },
            {
                "title": "RMBS·소비자 ABS",
                "series": [
                    {"id": "EXHE3C6Q65NP", "name": "Agency RMBS"},
                    {"id": "EXHE3C6Q69NP", "name": "Non-agency RMBS"},
                    {"id": "EXHE3C6Q77NP", "name": "소비자 ABS"},
                ],
            },
        ],
    },
    {
        "title": "자금조달 수요 증가 응답",
        "description": "고객들의 해당 자산 자금조달(레버리지) 수요가 늘었다고 답한 순비율. 플러스가 이어지면 레버리지가 쌓이고 있다는 신호입니다.",
        "panels": [
            {
                "title": "회사채",
                "series": [
                    {"id": "EXHE3C1Q53NP", "name": "투자등급 회사채"},
                    {"id": "EXHE3C1Q57NP", "name": "하이일드 회사채"},
                ],
            },
            {
                "title": "주식·CMBS",
                "series": [
                    {"id": "EXHE3C2Q61NP", "name": "주식"},
                    {"id": "EXHE3C2Q71NP", "name": "CMBS"},
                ],
            },
            {
                "title": "RMBS",
                "series": [
                    {"id": "EXHE3C3Q63NP", "name": "Agency RMBS"},
                    {"id": "EXHE3C3Q67NP", "name": "Non-agency RMBS"},
                ],
            },
            {
                "title": "소비자 ABS",
                "series": [
                    {"id": "EXHE3C4Q75NP", "name": "소비자 ABS"},
                ],
            },
        ],
    },
]


def quarter_label(date_str):
    """"2026-07-01" -> "2026 Q3". FRED dates quarterly observations to the
    first month of the quarter.
    """
    year, month, _ = date_str.split("-")
    return f"{year} Q{(int(month) - 1) // 3 + 1}"


def build_series_entry(meta, api_key):
    """Fetch one net-percentage series, newest value plus full history."""
    entry = {"id": meta["id"], "name": meta["name"]}

    try:
        observations = fetch_latest_observations(
            meta["id"], api_key, count=QUARTERLY_HISTORY
        )
    except Exception:
        observations = []

    if not observations:
        return {**entry, "error": "no data"}

    points = [
        {"date": obs["date"], "value": round(float(obs["value"]), 2)}
        for obs in observations
    ]
    value = points[0]["value"]
    prev_value = points[1]["value"] if len(points) > 1 else None

    return {
        **entry,
        "date": points[0]["date"],
        "value": value,
        "prev_value": prev_value,
        "change": round(value - prev_value, 2) if prev_value is not None else None,
        # Stored chronologically, like the macro series' history.
        "history": list(reversed(points)),
    }


def build_scoos_data(api_key):
    groups = []
    latest_date = None

    for group in SCOOS_GROUPS:
        panels = []
        for panel in group["panels"]:
            series = [build_series_entry(meta, api_key) for meta in panel["series"]]
            for entry in series:
                if entry.get("date") and (latest_date is None or entry["date"] > latest_date):
                    latest_date = entry["date"]
            panels.append({"title": panel["title"], "series": series})
        groups.append(
            {
                "title": group["title"],
                "description": group["description"],
                "panels": panels,
            }
        )

    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Federal Reserve Board, SCOOS (FRED release 571)",
        "unit": "순비율(%)",
        "latest_date": latest_date,
        "latest_quarter": quarter_label(latest_date) if latest_date else None,
        "groups": groups,
    }


def main():
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise SystemExit("FRED_API_KEY environment variable is required (see README)")

    data = build_scoos_data(api_key)

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved SCOOS data to {OUTPUT_PATH} (latest: {data['latest_quarter']})")


if __name__ == "__main__":
    main()
