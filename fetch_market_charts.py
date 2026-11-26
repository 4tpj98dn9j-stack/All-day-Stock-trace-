"""Fetch six months of daily series for the dashboard's market comparison cards.

Usage:
    export FRED_API_KEY=...   # or set it in a local .env file
    python fetch_market_charts.py
    # writes data/market_charts.json

Seven cards -- equities, FX, oil/inflation, Treasury yields, VIX term
structure, credit spreads and bond ETFs -- each drawn from Yahoo Finance,
FRED or CBOE. Like the other data files, this runs on a GitHub runner (in
.github/workflows/macro-data.yml) and the Flask app only reads the committed
JSON, so the charts don't depend on Render's unreliable route to Yahoo. The
trade-off is that "latest" means the last close, not an intraday price.

The file holds raw values aligned on one date axis per card. How a panel is
drawn -- rebased to the window's first day, squeezed into its own min-max
range, or plotted as-is -- is the panel's "mode", applied in the browser, so
the tooltip can always show the real number.
"""

import csv
import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yfinance as yf
from dotenv import load_dotenv

from fetch_macro_data import fetch_latest_observations

load_dotenv()

OUTPUT_PATH = Path("data/market_charts.json")

WINDOW_DAYS = 183  # ~6 months
# Daily FRED series skip weekends but mark holidays "."; this many valid
# observations comfortably covers the window.
FRED_FETCH_COUNT = 260

CBOE_PRODUCT_LIST_URL = (
    "https://www.cboe.com/us/futures/market_statistics/historical_data/product/list/VX/"
)
CBOE_CDN = "https://cdn.cboe.com/"
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; all-day-stock-trace)"}
# Contracts expiring this far past the window can still be F3 on its last day.
VX_LOOKAHEAD_DAYS = 120


def yahoo(key, name, **fmt):
    return {"key": key, "name": name, "source": "yahoo", **fmt}


def fred(key, name, **fmt):
    return {"key": key, "name": name, "source": "fred", **fmt}


# Per-series display fields: decimals, prefix, suffix, and how the day's
# change is expressed -- "pct" (relative %), "bp" (rates, in basis points)
# or "abs" (plain difference).
CARDS = [
    {
        "id": "equity",
        "title": "증시 비교",
        "description": (
            "각 지수의 6개월 전 값을 0%로 맞춰 움직임을 겹쳐 그림(현지 통화 기준, 환율 미반영). "
            "시장마다 휴장일이 달라 빈 날은 이어서 그립니다."
        ),
        "panels": [
            {
                "mode": "rebased",
                "series": [
                    yahoo("^KS11", "코스피", decimals=0, change="pct"),
                    yahoo("^N225", "닛케이225", decimals=0, change="pct"),
                    yahoo("^TWII", "대만 가권", decimals=0, change="pct"),
                    yahoo("^NDX", "나스닥100", decimals=0, change="pct"),
                    yahoo("^GSPC", "S&P500", decimals=0, change="pct"),
                ],
            }
        ],
    },
    {
        "id": "fx",
        "title": "환율 비교",
        "description": (
            "6개월 전 대비 %. 모두 1달러당 가격이라 위로 갈수록 달러 강세(= 원·위안·엔 약세). "
            "달러/원이 달러인덱스보다 더 오르면 달러 강세 이상으로 원화가 따로 약한 것입니다."
        ),
        "panels": [
            {
                "mode": "rebased",
                "series": [
                    yahoo("DX-Y.NYB", "달러인덱스(DXY)", decimals=2, change="pct"),
                    yahoo("KRW=X", "달러/원", decimals=1, change="pct"),
                    yahoo("CNY=X", "달러/위안", decimals=4, change="pct"),
                    yahoo("JPY=X", "달러/엔", decimals=2, change="pct"),
                ],
            }
        ],
    },
    {
        "id": "oil",
        "title": "원유·물가",
        "description": (
            "단위가 서로 달라 각 선을 6개월 최저~최고 범위에 맞춰 겹쳐 그렸습니다 — 높이가 아니라 "
            "움직이는 방향을 비교하세요. 실제 값은 범례와 툴팁에 있습니다. "
            "기대인플레이션 = 10년 BEI(명목 10년 − TIPS), FRED 일별."
        ),
        "panels": [
            {
                "mode": "minmax",
                "series": [
                    yahoo("CL=F", "WTI 원유", decimals=2, prefix="$", change="pct"),
                    fred("T10YIE", "기대인플레이션(BEI)", decimals=2, suffix="%", change="bp"),
                    yahoo("^NDX", "나스닥100", decimals=0, change="pct"),
                ],
            }
        ],
    },
    {
        "id": "rates",
        "title": "미국채 수익률",
        "description": (
            "FRED 일별(1~2영업일 지연). 실질금리↑ = 성장주·나스닥에 부담. 10년 명목이 오를 때 "
            "실질금리가 끌어올리면 긴축·성장 기대, 기대인플레이션이 끌어올리면 물가 우려. "
            "금리차 0 아래 = 장단기 역전(경기침체 선행 신호)."
        ),
        "panels": [
            {
                "mode": "level",
                "series": [
                    fred("DFEDTARU", "기준금리", decimals=2, suffix="%", change="bp",
                         range_lower="DFEDTARL"),
                    fred("DGS3MO", "3개월", decimals=2, suffix="%", change="bp"),
                    fred("DGS2", "2년", decimals=2, suffix="%", change="bp"),
                    fred("DGS10", "10년", decimals=2, suffix="%", change="bp"),
                    fred("DFII10", "실질금리(TIPS)", decimals=2, suffix="%", change="bp"),
                ],
            },
            {
                "title": "장단기 금리차",
                "mode": "level",
                "size": "sub",
                "include_zero": True,
                "ref_line": 0,
                "series": [
                    fred("T10Y2Y", "10Y−2Y", decimals=2, suffix="%p", change="bp"),
                    fred("T10Y3M", "10Y−3M", decimals=2, suffix="%p", change="bp"),
                ],
            },
        ],
    },
    {
        "id": "vix",
        "title": "VIX 추이",
        "description": (
            "선물 = CBOE 일별 정산가, 근월·차월·원월은 만기가 가까운 순서. VIX/VIX3M이 1 위이거나 "
            "F2−F1이 0 아래면 백워데이션 — 단기 공포가 장기보다 큰 위험 신호입니다."
        ),
        "panels": [
            {
                "mode": "level",
                "series": [
                    yahoo("^VIX", "VIX 지수", decimals=2, change="pct"),
                    yahoo("^VIX3M", "VIX3M", decimals=2, change="pct"),
                    {"key": "VX1", "name": "근월(F1)", "source": "vx", "rank": 1, "decimals": 2, "change": "pct"},
                    {"key": "VX2", "name": "차월(F2)", "source": "vx", "rank": 2, "decimals": 2, "change": "pct"},
                    {"key": "VX3", "name": "원월(F3)", "source": "vx", "rank": 3, "decimals": 2, "change": "pct"},
                ],
            },
            {
                "title": "VIX/VIX3M (1 위 = 위험)",
                "mode": "level",
                "size": "sub",
                "ref_line": 1,
                "series": [
                    {"key": "VIX/VIX3M", "name": "VIX/VIX3M", "source": "ratio",
                     "of": ["^VIX", "^VIX3M"], "decimals": 3, "change": "pct"},
                ],
            },
            {
                "title": "F2−F1 (0 아래 = 위험)",
                "mode": "level",
                "size": "sub",
                "include_zero": True,
                "ref_line": 0,
                "series": [
                    {"key": "F2-F1", "name": "F2−F1", "source": "diff",
                     "of": ["VX2", "VX1"], "decimals": 2, "change": "abs"},
                ],
            },
        ],
    },
    {
        "id": "credit",
        "title": "회사채 신용스프레드",
        "description": (
            "단위가 달라 각 선을 6개월 최저~최고에 맞춰 겹쳐 그림 — 높이가 아니라 방향을 비교하세요"
            "(스프레드↑·나스닥↓가 같이 나오면 위험 확대). ICE BofA OAS(국채 대비 %), FRED 일별·"
            "1영업일 지연. 스프레드 확대(↑) = 신용위험 증가."
        ),
        "panels": [
            {
                "mode": "minmax",
                "series": [
                    fred("BAMLH0A3HYC", "CCC 이하 하이일드", decimals=2, suffix="%", change="bp"),
                    fred("BAMLH0A1HYBB", "BB 등급", decimals=2, suffix="%", change="bp"),
                    fred("BAMLC0A4CBBB", "BBB 회사채", decimals=2, suffix="%", change="bp"),
                    yahoo("^NDX", "나스닥100", decimals=0, change="pct"),
                ],
            }
        ],
    },
    {
        "id": "bond_etf",
        "title": "회사채 ETF 가격",
        "description": (
            "6개월 전 대비 %, 일별 종가 기준. HYGH·LQDH는 금리 헤지형이라 가격 움직임 ≈ "
            "신용스프레드 변화, USHY는 금리 영향까지 포함합니다."
        ),
        "panels": [
            {
                "mode": "rebased",
                "series": [
                    yahoo("HYGH", "HYGH (하이일드·금리헤지)", decimals=2, prefix="$", change="pct"),
                    yahoo("LQDH", "LQDH (투자등급·금리헤지)", decimals=2, prefix="$", change="pct"),
                    yahoo("USHY", "USHY (하이일드 전체)", decimals=2, prefix="$", change="pct"),
                ],
            }
        ],
    },
]


# --- fetching -------------------------------------------------------------

def fetch_yahoo(symbol, start):
    """{date: close} for one Yahoo symbol from `start`, or {} on failure."""
    try:
        closes = yf.Ticker(symbol).history(start=start.isoformat(), auto_adjust=True)["Close"].dropna()
    except Exception:
        return {}
    return {index.strftime("%Y-%m-%d"): round(float(value), 4) for index, value in closes.items()}


def fetch_fred(series_id, api_key, start):
    """{date: value} for one FRED series from `start`, or {} on failure.

    Weekends are dropped: a few FRED series (the fed funds target range)
    are published every calendar day, and their Saturdays and Sundays would
    otherwise widen the card's date axis with days nothing else trades on.
    """
    try:
        observations = fetch_latest_observations(series_id, api_key, count=FRED_FETCH_COUNT)
    except Exception:
        return {}
    return {
        obs["date"]: round(float(obs["value"]), 4)
        for obs in observations
        if obs["date"] >= start.isoformat()
        and datetime.strptime(obs["date"], "%Y-%m-%d").weekday() < 5
    }


def _http_get(url):
    response = requests.get(url, headers=HTTP_HEADERS, timeout=30)
    response.raise_for_status()
    return response


def fetch_vx_contracts():
    """Monthly VIX futures contracts as [(expire_date, csv_path)], oldest first.

    CBOE's product list also carries weeklies; the term structure here is
    the standard monthly F1/F2/F3, so those are dropped.
    """
    listing = _http_get(CBOE_PRODUCT_LIST_URL).json()
    contracts = [
        (item["expire_date"], item["path"])
        for year in listing.values()
        for item in year
        if item.get("duration_type") == "M"
    ]
    return sorted(set(contracts))


def fetch_vx_settles(path):
    """{trade_date: settle} from one contract's CBOE history CSV."""
    text = _http_get(CBOE_CDN + path).text
    settles = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            settle = float(row["Settle"])
        except (KeyError, TypeError, ValueError):
            continue
        if settle > 0:
            settles[row["Trade Date"]] = round(settle, 4)
    return settles


def build_vx_term_structure(contracts, settles_by_expiry, start):
    """Continuous F1/F2/F3 series from per-contract settles.

    On each trade date the front month is the nearest contract that hasn't
    expired yet -- strictly after the trade date, since a VIX future settles
    on the morning of its expiry and stops being the front month that day.

    Returns ({"VX1": {date: v}, ...}, {"VX1": expire_date, ...}) where the
    second dict is each rank's contract on the latest date, for labelling.
    """
    expiries = sorted(expiry for expiry, _ in contracts if expiry in settles_by_expiry)
    trade_dates = sorted({
        trade_date
        for expiry in expiries
        for trade_date in settles_by_expiry[expiry]
        if trade_date >= start.isoformat()
    })

    series = {f"VX{rank}": {} for rank in (1, 2, 3)}
    latest_expiry = {}
    for trade_date in trade_dates:
        live = [expiry for expiry in expiries if expiry > trade_date]
        for rank, expiry in enumerate(live[:3], start=1):
            settle = settles_by_expiry[expiry].get(trade_date)
            if settle is not None:
                series[f"VX{rank}"][trade_date] = settle
                latest_expiry[f"VX{rank}"] = expiry
    return series, latest_expiry


def fetch_vx(start, today):
    """F1/F2/F3 continuous settles plus their current expiries; empty on failure."""
    empty = ({f"VX{rank}": {} for rank in (1, 2, 3)}, {})
    try:
        contracts = fetch_vx_contracts()
    except Exception:
        return empty

    horizon = (today + timedelta(days=VX_LOOKAHEAD_DAYS)).isoformat()
    relevant = [(e, p) for e, p in contracts if start.isoformat() <= e <= horizon]
    settles_by_expiry = {}
    for expiry, path in relevant:
        try:
            settles_by_expiry[expiry] = fetch_vx_settles(path)
        except Exception:
            continue
    return build_vx_term_structure(relevant, settles_by_expiry, start)


# --- shaping --------------------------------------------------------------

def change_value(kind, value, previous):
    if previous is None:
        return None
    if kind == "bp":
        return round((value - previous) * 100, 2)
    if kind == "abs":
        return round(value - previous, 4)
    if previous == 0:
        return None
    return round((value / previous - 1) * 100, 4)


def latest_summary(spec, points, raw):
    """Newest value, the one before it, and the change between them."""
    dates = sorted(points)
    if not dates:
        return None
    last = dates[-1]
    previous = points[dates[-2]] if len(dates) > 1 else None
    summary = {
        "date": last,
        "value": points[last],
        "prev_value": previous,
        "change": change_value(spec.get("change", "pct"), points[last], previous),
    }
    lower = raw.get(spec.get("range_lower"), {})
    if lower:
        # Show a target range like "3.75~4.00%" rather than just its top.
        summary["display"] = f"{lower[max(lower)]:.2f}~{points[last]:.2f}%"
    return summary


def card_status(card_id, latest):
    """One-line reading of the card's warning thresholds, where it has them."""
    if card_id == "rates":
        a, b = latest.get("T10Y2Y"), latest.get("T10Y3M")
        if a is None or b is None:
            return None
        inverted = a["value"] < 0 or b["value"] < 0
        return {
            "level": "warning" if inverted else "normal",
            "text": (
                f"10Y−2Y {a['value']:+.2f}%p · 10Y−3M {b['value']:+.2f}%p — "
                + ("장단기 금리 역전(경기침체 선행 신호)" if inverted else "역전 아님")
            ),
        }
    if card_id == "vix":
        ratio, spread = latest.get("VIX/VIX3M"), latest.get("F2-F1")
        if ratio is None and spread is None:
            return None
        backwardation = (ratio is not None and ratio["value"] > 1) or (
            spread is not None and spread["value"] < 0
        )
        parts = []
        if ratio is not None:
            parts.append(f"VIX/VIX3M {ratio['value']:.3f}")
        if spread is not None:
            parts.append(f"F2−F1 {spread['value']:+.2f}")
        return {
            "level": "warning" if backwardation else "normal",
            "text": " · ".join(parts) + " — "
            + ("백워데이션(단기 공포 > 장기, 위험 신호)" if backwardation else "콘탱고(정상)"),
        }
    return None


def fetch_raw(api_key, start, today):
    """Fetch every base series the cards use, once each, keyed by series key."""
    raw = {}
    specs = [s for card in CARDS for panel in card["panels"] for s in panel["series"]]
    for spec in specs:
        key = spec["key"]
        if key in raw:
            continue
        if spec["source"] == "yahoo":
            raw[key] = fetch_yahoo(key, start)
        elif spec["source"] == "fred":
            raw[key] = fetch_fred(key, api_key, start)
            lower = spec.get("range_lower")
            if lower and lower not in raw:
                raw[lower] = fetch_fred(lower, api_key, start)

    vx_series, vx_expiry = ({}, {})
    if any(s["source"] == "vx" for s in specs):
        vx_series, vx_expiry = fetch_vx(start, today)
        raw.update(vx_series)

    # Derived series come last, once their inputs exist.
    for spec in specs:
        if spec["source"] == "ratio":
            a, b = (raw.get(k, {}) for k in spec["of"])
            raw[spec["key"]] = {d: round(a[d] / b[d], 4) for d in a.keys() & b.keys() if b[d]}
        elif spec["source"] == "diff":
            a, b = (raw.get(k, {}) for k in spec["of"])
            raw[spec["key"]] = {d: round(a[d] - b[d], 4) for d in a.keys() & b.keys()}
    return raw, vx_expiry


def build_card(card, raw, vx_expiry):
    series_specs = [s for panel in card["panels"] for s in panel["series"]]
    dates = sorted({d for s in series_specs for d in raw.get(s["key"], {})})

    latest_by_key = {}
    panels = []
    for panel in card["panels"]:
        series = []
        for spec in panel["series"]:
            points = raw.get(spec["key"], {})
            latest = latest_summary(spec, points, raw)
            if latest and spec["key"] in vx_expiry:
                latest["note"] = f"{vx_expiry[spec['key']]} 만기"
            latest_by_key[spec["key"]] = latest
            series.append({
                "key": spec["key"],
                "name": spec["name"],
                "decimals": spec.get("decimals", 2),
                "prefix": spec.get("prefix", ""),
                "suffix": spec.get("suffix", ""),
                "change": spec.get("change", "pct"),
                "values": [points.get(d) for d in dates],
                "latest": latest,
            })
        panels.append({
            "title": panel.get("title"),
            "mode": panel["mode"],
            "size": panel.get("size", "main"),
            "include_zero": panel.get("include_zero", panel["mode"] != "level"),
            "ref_line": panel.get("ref_line"),
            "series": series,
        })

    return {
        "id": card["id"],
        "title": card["title"],
        "description": card["description"],
        "status": card_status(card["id"], {k: v for k, v in latest_by_key.items() if v}),
        "dates": dates,
        "panels": panels,
    }


def build_market_charts(api_key, today=None):
    today = today or datetime.now(timezone.utc).date()
    start = today - timedelta(days=WINDOW_DAYS)
    raw, vx_expiry = fetch_raw(api_key, start, today)
    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_start": start.isoformat(),
        "cards": [build_card(card, raw, vx_expiry) for card in CARDS],
    }


def main():
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise SystemExit("FRED_API_KEY environment variable is required (see README)")

    data = build_market_charts(api_key)

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    empty = [
        s["key"]
        for card in data["cards"]
        for panel in card["panels"]
        for s in panel["series"]
        if s["latest"] is None
    ]
    print(f"Saved market charts to {OUTPUT_PATH}" + (f" (no data: {', '.join(empty)})" if empty else ""))


if __name__ == "__main__":
    main()
