"""Snapshot the latest closes for the watchlist and major indices into data/closes.json.

Usage:
    python fetch_closes.py
    # writes data/closes.json

Runs twice each weekday after the US close via .github/workflows/closes-data.yml.
Yahoo doesn't always have every symbol's final daily bar ready right after the
bell, so the first pass catches the close quickly and the second, two hours
later, fills in anything that was still behind.

A holding is "behind" when its newest daily bar is older than the S&P 500's --
the index trades every session, so its latest bar defines which session is
current. A holding that's behind gets one retry through fast_info, Yahoo's
lightweight quote, which often has the close before the daily history does.
If that fails too, the old numbers are kept but marked "stale": true.

This module is also where daily_report.py gets that rule from, so the report
and this snapshot can't disagree about which prices are current.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

from app import INDICES, TICKERS
from daily_change_tracker import get_change

OUTPUT_PATH = Path("data/closes.json")

# The index whose last trading day defines "current" for everything else.
REFERENCE_SYMBOL = "^GSPC"


def fetch_fast_quote(ticker):
    """Return (last_price, previous_close) from Yahoo's lightweight quote.

    Yahoo's daily-bar history and its quote endpoint don't always move in
    step -- the history can still be a day behind while the quote is
    current. So when a holding's newest bar is older than the reference
    index's, this is the second chance before the row is called stale.

    Returns None if the quote is missing, zero, or the call fails.
    """
    try:
        fast_info = yf.Ticker(ticker).fast_info
        last_price = fast_info["last_price"]
        prev_close = fast_info["previous_close"]
    except Exception:
        return None

    if not last_price or not prev_close:
        return None
    return float(last_price), float(prev_close)


def is_behind(date, reference_date):
    """Whether a bar dated `date` predates the reference session.

    ISO dates compare correctly as strings. With no reference date there's
    nothing to be behind, so nothing is.
    """
    return reference_date is not None and date < reference_date


def _entry(date, close, prev_close):
    return {
        "date": date,
        "close": round(float(close), 4),
        "prev_close": round(float(prev_close), 4),
        "pct_change": round((float(close) - float(prev_close)) / float(prev_close) * 100, 4),
    }


def resolve_close(ticker, result, reference_date):
    """Turn a get_change() result into a close entry checked against the
    reference session.

    Returns {date, close, prev_close, pct_change, source, stale}, where
    source is "history" (the daily bar) or "fast_info" (the live quote that
    replaced a bar that was behind). A fast_info entry carries the reference
    date, since that's the session it stands in for.
    """
    latest_date, _, _, _, close, prev_close, _ = result
    entry = {**_entry(latest_date, close, prev_close), "source": "history", "stale": False}

    if is_behind(latest_date, reference_date):
        quote = fetch_fast_quote(ticker)
        if quote:
            entry = {**_entry(reference_date, *quote), "source": "fast_info", "stale": False}
        else:
            # Keep the old numbers -- they're the best available -- but say so.
            entry["stale"] = True

    return entry


def _rank(entry):
    # Newer session first; within the same session, a fresh entry beats a
    # stale one.
    return (entry["date"], not entry.get("stale", False))


def merge_entry(previous, new):
    """Pick between this run's entry and the one already on disk.

    The job runs twice a day, so a second pass that hits a Yahoo hiccup must
    not overwrite a good first-pass close with a worse one. The previous
    entry is kept only when it's strictly better; on a tie the new one wins,
    since it was fetched later and is at least as settled.
    """
    if new is None:
        return previous
    if previous is not None and _rank(previous) > _rank(new):
        return previous
    return new


def load_previous(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def build_closes(previous=None):
    previous = previous or {}
    previous_indices = previous.get("indices", {})
    previous_holdings = previous.get("holdings", {})

    indices = {}
    for meta in INDICES:
        symbol = meta["symbol"]
        result = get_change(symbol)
        new = {"name": meta["name"], **_entry(result[0], result[4], result[5])} if result else None
        merged = merge_entry(previous_indices.get(symbol), new)
        if merged is not None:
            indices[symbol] = merged

    # Taken after merging, so a run where ^GSPC itself fails still has the
    # last known session to check holdings against.
    reference = indices.get(REFERENCE_SYMBOL)
    reference_date = reference["date"] if reference else None

    holdings = {}
    for ticker in TICKERS:
        result = get_change(ticker)
        new = resolve_close(ticker, result, reference_date) if result else None
        merged = merge_entry(previous_holdings.get(ticker), new)
        if merged is None:
            continue
        # Re-derived for every holding, including ones carried over from an
        # earlier run: an entry that was current for an older session is
        # stale once the reference has moved on.
        merged = {**merged, "stale": is_behind(merged["date"], reference_date)}
        holdings[ticker] = merged

    return {
        "reference_symbol": REFERENCE_SYMBOL,
        "reference_date": reference_date,
        "indices": indices,
        "holdings": holdings,
    }


def main():
    previous = load_previous(OUTPUT_PATH)
    data = build_closes(previous)

    # Most second passes change nothing; skipping the write keeps
    # updated_at meaning "when the prices last changed" and avoids a no-op
    # commit every evening.
    unchanged = {k: v for k, v in previous.items() if k != "updated_at"} == data
    if unchanged:
        print(f"No changes to {OUTPUT_PATH} (reference: {data['reference_date']})")
        return

    data = {"updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **data}
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stale = [ticker for ticker, entry in data["holdings"].items() if entry["stale"]]
    print(
        f"Saved closes to {OUTPUT_PATH} (reference: {data['reference_date']}"
        + (f", stale: {', '.join(stale)}" if stale else "")
        + ")"
    )


if __name__ == "__main__":
    main()
