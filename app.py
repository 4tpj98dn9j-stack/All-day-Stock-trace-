"""Flask app serving a live stock portfolio dashboard backed by Yahoo Finance quotes.

Usage:
    python app.py
    (open http://localhost:5000)
"""

import json
import time
from pathlib import Path

import yfinance as yf
from flask import Flask, jsonify, render_template, request

from daily_change_tracker import get_change

app = Flask(__name__)

TICKERS = ["NOW", "TSLA", "SPCX", "INFQ", "PL", "QCOM"]

INDICES = [
    {"symbol": "^GSPC", "name": "S&P500"},
    {"symbol": "^DJI", "name": "다우지수"},
    {"symbol": "^IXIC", "name": "나스닥종합지수"},
    {"symbol": "^NDX", "name": "나스닥100"},
    {"symbol": "^RUT", "name": "러셀2000"},
    {"symbol": "^VIX", "name": "VIX"},
]

DAILY_REPORT_DIR = Path("daily")
MACRO_DATA_PATH = Path("data/macro.json")

NEWS_LIMIT = 5

# Yahoo Finance (via yfinance) rate-limits aggressively. Every route below is
# cached in-process for a short TTL so repeated clicks/refreshes reuse the
# same data instead of hammering Yahoo on every request.
_CACHE = {}
QUOTE_CACHE_TTL = 30
DETAIL_CACHE_TTL = 300
HISTORY_CACHE_TTL = 60


def _cache_get(key):
    entry = _CACHE.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.monotonic() >= expires_at:
        del _CACHE[key]
        return None
    return value


def _cache_set(key, value, ttl_seconds):
    _CACHE[key] = (value, time.monotonic() + ttl_seconds)


def _cached_get_change(symbol):
    key = ("get_change", symbol)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    try:
        result = get_change(symbol)
    except Exception:
        result = None

    _cache_set(key, result, QUOTE_CACHE_TTL)
    return result


def _cached_recent_history(ticker):
    key = ("recent_history", ticker)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    try:
        history = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
    except Exception:
        history = None

    _cache_set(key, history, QUOTE_CACHE_TTL)
    return history


CHART_RANGES = {
    "1d": {"period": "1d", "interval": "5m"},
    "1w": {"period": "5d", "interval": "15m"},
    "1mo": {"period": "1mo", "interval": "1d"},
    "3mo": {"period": "3mo", "interval": "1d"},
    "6mo": {"period": "6mo", "interval": "1d"},
    "ytd": {"period": "ytd", "interval": "1d"},
    "1y": {"period": "1y", "interval": "1d"},
    "2y": {"period": "2y", "interval": "1d"},
    "5y": {"period": "5y", "interval": "1wk"},
    "10y": {"period": "10y", "interval": "1wk"},
    "max": {"period": "max", "interval": "1mo"},
}
INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
DEFAULT_CHART_RANGE = "3mo"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/daily-report")
def daily_report_endpoint():
    """Return the most recently committed daily/<date>.md report (see daily_report.py)."""
    if not DAILY_REPORT_DIR.is_dir():
        return jsonify({"error": "no report"}), 404

    files = sorted(DAILY_REPORT_DIR.glob("*.md"))
    if not files:
        return jsonify({"error": "no report"}), 404

    latest = files[-1]
    try:
        content = latest.read_text(encoding="utf-8")
    except Exception as exc:
        app.logger.warning("Failed to read daily report %s: %s", latest, exc)
        return jsonify({"error": "no report"}), 404

    return jsonify({"date": latest.stem, "content": content})


@app.route("/api/macro-data")
def macro_data_endpoint():
    """Return the most recently committed data/macro.json (see fetch_macro_data.py)."""
    if not MACRO_DATA_PATH.is_file():
        return jsonify({"error": "no data"}), 404

    try:
        content = json.loads(MACRO_DATA_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        app.logger.warning("Failed to read macro data %s: %s", MACRO_DATA_PATH, exc)
        return jsonify({"error": "no data"}), 404

    return jsonify(content)


@app.route("/api/quotes")
def quotes():
    results = []
    for ticker in TICKERS:
        result = _cached_get_change(ticker)

        if result is None:
            results.append({"ticker": ticker, "error": "no data"})
            continue

        _, _, _, _, close, prev_close, pct_change = result
        results.append({
            "ticker": ticker,
            "price": round(close, 2),
            "change": round(close - prev_close, 2),
            "change_pct": round(pct_change, 2),
        })
    return jsonify(results)


@app.route("/api/market-summary")
def market_summary():
    indices = []
    pct_by_symbol = {}

    for meta in INDICES:
        symbol = meta["symbol"]
        result = _cached_get_change(symbol)

        if result is None:
            indices.append({"symbol": symbol, "name": meta["name"], "error": "no data"})
            pct_by_symbol[symbol] = None
            continue

        _, _, _, _, close, prev_close, pct_change = result
        indices.append({
            "symbol": symbol,
            "name": meta["name"],
            "price": round(close, 2),
            "change": round(close - prev_close, 2),
            "change_pct": round(pct_change, 2),
        })
        pct_by_symbol[symbol] = pct_change

    summary = build_market_summary(
        gspc_pct=pct_by_symbol.get("^GSPC"),
        dji_pct=pct_by_symbol.get("^DJI"),
        ndx_pct=pct_by_symbol.get("^NDX"),
        rut_pct=pct_by_symbol.get("^RUT"),
        vix_pct=pct_by_symbol.get("^VIX"),
    )
    return jsonify({"indices": indices, "summary": summary})


def _direction_word(pct, flat_word="보합"):
    if pct > 0.05:
        return "상승"
    if pct < -0.05:
        return "하락"
    return flat_word


def build_market_summary(gspc_pct, dji_pct, ndx_pct, rut_pct, vix_pct):
    """Rule-based one-line market briefing across large-cap, tech, and
    small-cap benchmarks, e.g. '미국 증시 하락 마감, 기술주가 대형 우량주
    대비 약세, 소형주 상대적 약세, 변동성 확대'.
    """
    if gspc_pct is None:
        return "미국 주식시장 시황 정보를 불러올 수 없습니다."

    parts = [f"미국 증시 {_direction_word(gspc_pct)} 마감"]

    # Tech (Nasdaq 100) vs. blue-chip (Dow) divergence.
    if ndx_pct is not None and dji_pct is not None:
        spread = ndx_pct - dji_pct
        if spread > 0.5:
            parts.append("기술주가 대형 우량주 대비 강세")
        elif spread < -0.5:
            parts.append("기술주가 대형 우량주 대비 약세")

    # Small-cap (Russell 2000) vs. broad market (S&P 500) divergence.
    if rut_pct is not None:
        spread = rut_pct - gspc_pct
        if spread > 0.5:
            parts.append("소형주 상대적 강세")
        elif spread < -0.5:
            parts.append("소형주 상대적 약세")

    if vix_pct is not None:
        if vix_pct > 5:
            parts.append("변동성 확대")
        elif vix_pct < -5:
            parts.append("변동성 완화")

    return ", ".join(parts)


@app.route("/api/index/<symbol>")
def index_detail(symbol):
    meta = next((m for m in INDICES if m["symbol"].lstrip("^").upper() == symbol.lstrip("^").upper()), None)
    if meta is None:
        return jsonify({"error": "unknown index"}), 404

    result = _cached_get_change(meta["symbol"])

    if result is None:
        return jsonify({"symbol": meta["symbol"], "name": meta["name"], "error": "no data"})

    date, open_, high, low, close, prev_close, pct_change = result

    return jsonify({
        "symbol": meta["symbol"],
        "name": meta["name"],
        "date": date,
        "open": round(open_, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "close": round(close, 2),
        "prev_close": round(prev_close, 2),
        "change": round(close - prev_close, 2),
        "change_pct": round(pct_change, 2),
    })


@app.route("/api/quote/<ticker>")
def quote_detail(ticker):
    ticker = ticker.upper()
    if ticker not in TICKERS:
        return jsonify({"error": "unknown ticker"}), 404

    result = _cached_get_change(ticker)

    if result is None:
        return jsonify({"ticker": ticker, "error": "no data"})

    date, open_, high, low, close, prev_close, pct_change = result

    volume = None
    history = _cached_recent_history(ticker)
    if history is not None:
        try:
            volume = int(history["Volume"].dropna().iloc[-1])
        except Exception:
            pass

    return jsonify({
        "ticker": ticker,
        "date": date,
        "open": round(open_, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "close": round(close, 2),
        "volume": volume,
        "prev_close": round(prev_close, 2),
        "change": round(close - prev_close, 2),
        "change_pct": round(pct_change, 2),
        "news": fetch_news(ticker),
        "stats": fetch_stats(ticker),
    })


def fetch_stats(ticker):
    """Return supplementary fundamentals: market cap, PE, 52-week range, beta, EPS,
    avg volume, and analyst consensus target price.

    Backed by yfinance's Ticker.info, which is a broad, occasionally-missing-keys
    dict scraped from Yahoo's quote page -- any field can legitimately be absent
    for a given ticker, so every value defaults to None rather than raising.
    """
    key = ("stats", ticker)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    try:
        info = yf.Ticker(ticker).info
    except Exception as exc:
        app.logger.warning("Failed to fetch stats for %s: %s", ticker, exc)
        _cache_set(key, None, DETAIL_CACHE_TTL)
        return None

    result = {
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "eps": info.get("trailingEps"),
        "beta": info.get("beta"),
        "week52_high": info.get("fiftyTwoWeekHigh"),
        "week52_low": info.get("fiftyTwoWeekLow"),
        "avg_volume": info.get("averageVolume"),
        "target_mean_price": info.get("targetMeanPrice"),
        "analyst_count": info.get("numberOfAnalystOpinions"),
    }
    _cache_set(key, result, DETAIL_CACHE_TTL)
    return result


@app.route("/api/quote/<ticker>/history")
def quote_history(ticker):
    ticker = ticker.upper()
    if ticker not in TICKERS:
        return jsonify({"error": "unknown ticker"}), 404

    range_param = request.args.get("range", DEFAULT_CHART_RANGE)
    range_config = CHART_RANGES.get(range_param)
    if range_config is None:
        return jsonify({"error": "invalid range"}), 400

    points = _cached_chart_points(ticker, range_param, range_config)
    return jsonify({"ticker": ticker, "range": range_param, "points": points})


def _cached_chart_points(ticker, range_param, range_config):
    key = ("chart", ticker, range_param)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    interval = range_config["interval"]
    date_format = "%Y-%m-%d %H:%M" if interval in INTRADAY_INTERVALS else "%Y-%m-%d"

    try:
        history = yf.Ticker(ticker).history(
            period=range_config["period"], interval=interval, auto_adjust=True,
        )
        history = history.dropna(subset=["Close"])
    except Exception as exc:
        app.logger.warning("Failed to fetch chart history for %s (%s): %s", ticker, range_param, exc)
        _cache_set(key, [], HISTORY_CACHE_TTL)
        return []

    points = [
        {"date": idx.strftime(date_format), "close": round(float(close), 2)}
        for idx, close in history["Close"].items()
    ]
    _cache_set(key, points, HISTORY_CACHE_TTL)
    return points


def fetch_news(ticker):
    """Return up to NEWS_LIMIT recent headlines, tolerant of yfinance's news schema changes."""
    key = ("news", ticker)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    try:
        raw_items = yf.Ticker(ticker).news or []
    except Exception:
        _cache_set(key, [], DETAIL_CACHE_TTL)
        return []

    news = []
    for item in raw_items[:NEWS_LIMIT]:
        content = item.get("content", item)
        title = content.get("title") or item.get("title")
        canonical_url = content.get("canonicalUrl")
        link = (canonical_url.get("url") if isinstance(canonical_url, dict) else None) or item.get("link")
        provider = content.get("provider")
        publisher = (provider.get("displayName") if isinstance(provider, dict) else None) or item.get("publisher")

        if title and link:
            news.append({"title": title, "link": link, "publisher": publisher})

    _cache_set(key, news, DETAIL_CACHE_TTL)
    return news


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
