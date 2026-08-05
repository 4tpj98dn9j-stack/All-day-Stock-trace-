"""Fetch today's OHLC for a fixed watchlist and report day-over-day close % change.

Intended to be run once per trading day (e.g. via cron/Task Scheduler). Each run
appends one row per ticker to daily_change_log.csv.

Usage:
    python daily_change_tracker.py
    python daily_change_tracker.py --tickers NOW TSLA SPCX QCOM PL INFQ --output daily_change_log.csv
"""

import argparse
import sys
from datetime import datetime

import pandas as pd
import yfinance as yf

DEFAULT_TICKERS = ["NOW", "TSLA", "SPCX", "QCOM", "PL", "INFQ"]
DEFAULT_OUTPUT = "daily_change_log.csv"


def parse_args():
    parser = argparse.ArgumentParser(description="Track daily close price change for a watchlist")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS, help="Ticker symbols to track")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="CSV log file to append results to")
    return parser.parse_args()


def get_change(ticker):
    """Return latest day's OHLC plus prev close and pct_change, for the most recent two trading days."""
    history = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
    if history.empty:
        return None

    history = history.dropna(subset=["Close"])
    if len(history) < 2:
        return None

    latest = history.iloc[-1]
    prev_close = history["Close"].iloc[-2]
    pct_change = (latest["Close"] - prev_close) / prev_close * 100
    latest_date = history.index[-1].strftime("%Y-%m-%d")
    return latest_date, latest["Open"], latest["High"], latest["Low"], latest["Close"], prev_close, pct_change


def main():
    args = parse_args()
    rows = []

    for ticker in args.tickers:
        result = get_change(ticker)
        if result is None:
            print(f"[WARN] Could not get enough data for '{ticker}', skipping.", file=sys.stderr)
            continue

        date, open_, high, low, close, prev_close, pct_change = result
        rows.append({
            "date": date,
            "ticker": ticker,
            "open": round(open_, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "prev_close": round(prev_close, 2),
            "pct_change": round(pct_change, 2),
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        sign = "+" if pct_change >= 0 else ""
        print(f"{ticker}: {close:.2f} ({sign}{pct_change:.2f}%) vs prev close {prev_close:.2f}")

    if not rows:
        print("No data collected; nothing written.", file=sys.stderr)
        sys.exit(1)

    new_data = pd.DataFrame(rows)
    try:
        existing = pd.read_csv(args.output)
        combined = pd.concat([existing, new_data], ignore_index=True)
    except FileNotFoundError:
        combined = new_data

    combined.to_csv(args.output, index=False)
    print(f"Appended {len(new_data)} rows to {args.output}")


if __name__ == "__main__":
    main()
