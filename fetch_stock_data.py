"""Fetch historical OHLCV data for a ticker from Yahoo Finance and save to CSV.

Output columns match easyinvesting.app's CSV export: date,open,high,low,close,volume
(split/dividend-adjusted, same convention Yahoo Finance uses).

Usage:
    python fetch_stock_data.py --ticker AAPL --period 6mo
    python fetch_stock_data.py --ticker AAPL --period 1y --output aapl.csv

Ticker and period can also be entered interactively if omitted.
"""

import argparse
import sys

import yfinance as yf

VALID_PERIODS = {
    "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Download OHLCV data from Yahoo Finance")
    parser.add_argument("--ticker", help="Ticker symbol, e.g. AAPL")
    parser.add_argument(
        "--period",
        help=f"Lookback period. One of: {', '.join(sorted(VALID_PERIODS))}",
    )
    parser.add_argument("--output", help="Output CSV path (default: <ticker>_<period>.csv)")
    return parser.parse_args()


def prompt_if_missing(value, prompt_text):
    return value if value else input(prompt_text).strip()


def fetch_and_save(ticker, period, output_path):
    data = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    if data.empty:
        print(f"No data returned for ticker '{ticker}' with period '{period}'.", file=sys.stderr)
        sys.exit(1)

    result = data[["Open", "High", "Low", "Close", "Volume"]].copy()
    result.index = result.index.strftime("%Y-%m-%d")
    result.index.name = "date"
    result.columns = ["open", "high", "low", "close", "volume"]
    result.to_csv(output_path)
    print(f"Saved {len(result)} rows to {output_path}")


def main():
    args = parse_args()

    ticker = prompt_if_missing(args.ticker, "Ticker symbol (e.g. AAPL): ").upper()
    period = prompt_if_missing(args.period, "Period (e.g. 1mo, 6mo, 1y, max): ").lower()

    if period not in VALID_PERIODS:
        print(f"Invalid period '{period}'. Must be one of: {', '.join(sorted(VALID_PERIODS))}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output or f"{ticker}_{period}.csv"
    fetch_and_save(ticker, period, output_path)


if __name__ == "__main__":
    main()
