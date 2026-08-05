"""Flask app serving a live stock portfolio dashboard backed by Yahoo Finance quotes.

Usage:
    python app.py
    (open http://localhost:5000)
"""

import yfinance as yf
from flask import Flask, jsonify, render_template

from daily_change_tracker import get_change

app = Flask(__name__)

TICKERS = ["NOW", "TSLA", "SPCX", "INFQ", "PL", "QCOM"]

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
