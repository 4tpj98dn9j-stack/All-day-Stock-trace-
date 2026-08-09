"""Flask app serving a live stock portfolio dashboard backed by Yahoo Finance quotes.

Usage:
    python app.py
    (open http://localhost:5000)
"""

import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, render_template

from daily_change_tracker import get_change

app = Flask(__name__)

TICKERS = ["NOW", "TSLA", "SPCX", "INFQ", "PL", "QCOM"]

INDICES = [
    {"symbol": "^IXIC", "name": "나스닥종합지수"},
    {"symbol": "^NDX", "name": "나스닥100"},
    {"symbol": "^VIX", "name": "VIX"},
]

NEWS_LIMIT = 5


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/quotes")
def quotes():
    results = []
    for ticker in TICKERS:
        try:
            result = get_change(ticker)
        except Exception:
            result = None

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
        try:
            result = get_change(symbol)
        except Exception:
            result = None

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
        pct_by_symbol.get("^IXIC"), pct_by_symbol.get("^NDX"), pct_by_symbol.get("^VIX"),
    )
    return jsonify({"indices": indices, "summary": summary})


def build_market_summary(ixic_pct, ndx_pct, vix_pct):
    """Rule-based one-line market recap, e.g. '나스닥 하락 마감, 기술주 전반 약세'."""
    if ixic_pct is None:
        return "나스닥 시황 정보를 불러올 수 없습니다."

    if ixic_pct > 0.05:
        direction = "상승"
    elif ixic_pct < -0.05:
        direction = "하락"
    else:
        direction = "보합"

    if ndx_pct is None:
        tech_word = "혼조"
    elif ndx_pct > 0.05:
        tech_word = "강세"
    elif ndx_pct < -0.05:
        tech_word = "약세"
    else:
        tech_word = "보합"

    vix_phrase = ""
    if vix_pct is not None:
        if vix_pct > 5:
            vix_phrase = ", 변동성 확대"
        elif vix_pct < -5:
            vix_phrase = ", 변동성 완화"

    return f"나스닥 {direction} 마감, 기술주 전반 {tech_word}{vix_phrase}"


@app.route("/api/index/<symbol>")
def index_detail(symbol):
    meta = next((m for m in INDICES if m["symbol"].lstrip("^").upper() == symbol.lstrip("^").upper()), None)
    if meta is None:
        return jsonify({"error": "unknown index"}), 404

    try:
        result = get_change(meta["symbol"])
    except Exception:
        result = None

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
        "options": fetch_options_summary(meta["symbol"], close),
    })


def fetch_options_summary(symbol, current_price, strikes_per_side=5):
    """Return the nearest-expiry option chain narrowed to strikes closest to current_price.

    Many index tickers (e.g. raw ^IXIC/^NDX) have no listed options at all, so this
    returns None whenever yfinance reports no expirations or the lookup fails.
    """
    try:
        ticker = yf.Ticker(symbol)
        expirations = ticker.options
        if not expirations:
            return None

        nearest_expiry = expirations[0]
        chain = ticker.option_chain(nearest_expiry)

        return {
            "expiration": nearest_expiry,
            "calls": _nearest_strikes(chain.calls, current_price, strikes_per_side),
            "puts": _nearest_strikes(chain.puts, current_price, strikes_per_side),
        }
    except Exception:
        return None


def _nearest_strikes(df, current_price, count):
    if df is None or df.empty:
        return []

    nearest = df.assign(_diff=(df["strike"] - current_price).abs()).nsmallest(count, "_diff").sort_values("strike")

    rows = []
    for row in nearest.itertuples():
        rows.append({
            "strike": round(float(row.strike), 2),
            "last_price": None if pd.isna(row.lastPrice) else round(float(row.lastPrice), 2),
            "volume": None if pd.isna(row.volume) else int(row.volume),
            "open_interest": None if pd.isna(row.openInterest) else int(row.openInterest),
        })
    return rows


@app.route("/api/quote/<ticker>")
def quote_detail(ticker):
    ticker = ticker.upper()
    if ticker not in TICKERS:
        return jsonify({"error": "unknown ticker"}), 404

    try:
        result = get_change(ticker)
    except Exception:
        result = None

    if result is None:
        return jsonify({"ticker": ticker, "error": "no data"})

    date, open_, high, low, close, prev_close, pct_change = result

    volume = None
    try:
        history = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
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
    })


def fetch_news(ticker):
    """Return up to NEWS_LIMIT recent headlines, tolerant of yfinance's news schema changes."""
    try:
        raw_items = yf.Ticker(ticker).news or []
    except Exception:
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

    return news


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
