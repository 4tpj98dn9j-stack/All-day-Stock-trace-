"""Generate a dated markdown report: a NASDAQ market recap plus watchlist prices.

Usage:
    python daily_report.py
    # writes daily/<YYYY-MM-DD>.md

Intended to run once per trading day after market close via
.github/workflows/daily-report.yml (GitHub's runners have normal internet
access to Yahoo Finance, unlike this project's other dev/CI sandboxes).
"""

from datetime import datetime, timezone
from pathlib import Path

from app import INDICES, MARKET_SUMMARY_DISPLAY_SYMBOLS, TICKERS, build_market_summary, fetch_stats
from daily_change_tracker import get_change

OUTPUT_DIR = Path("daily")

# Personal 3-year price targets, independent of analyst consensus.
PERSONAL_TARGETS = {
    "NOW": 180.0,
    "TSLA": 480.0,
    "SPCX": 500.0,
    "INFQ": 100.0,
    "PL": 120.0,
    "QCOM": 300.0,
}


def format_price_target(close, target):
    """Format a target price with upside/downside vs. close, e.g. "$140.25 (+13%)"."""
    if target is None:
        return "-"
    upside_pct = (target - close) / close * 100
    sign = "+" if upside_pct >= 0 else ""
    return f"${target:,.2f} ({sign}{upside_pct:.0f}%)"


def format_target_price(close, stats):
    """Format analyst consensus target price with upside/downside vs. close, e.g. "$140.25 (+13%)"."""
    target = stats.get("target_mean_price") if stats else None
    return format_price_target(close, target)


def build_report(today):
    lines = [f"# {today} 마감 리포트", ""]

    lines.append("## 나스닥 시황")
    lines.append("")
    pct_by_symbol = {}
    for meta in INDICES:
        symbol = meta["symbol"]
        result = get_change(symbol)
        if result is None:
            pct_by_symbol[symbol] = None
            if symbol in MARKET_SUMMARY_DISPLAY_SYMBOLS:
                lines.append(f"- {meta['name']}: 데이터 없음")
            continue
        _, _, _, _, close, prev_close, pct_change = result
        pct_by_symbol[symbol] = pct_change
        if symbol in MARKET_SUMMARY_DISPLAY_SYMBOLS:
            sign = "+" if pct_change >= 0 else ""
            lines.append(f"- {meta['name']}: {close:,.2f} ({sign}{pct_change:.2f}%)")

    summary = build_market_summary(
        pct_by_symbol.get("^IXIC"), pct_by_symbol.get("^NDX"), pct_by_symbol.get("^VIX"),
    )
    lines.append("")
    lines.append(f"> {summary}")
    lines.append("")

    lines.append("## 보유 종목 시세")
    lines.append("")
    lines.append("| 종목 | 종가 | 전일 대비 | 등락률 | 목표주가(컨센서스) | 개인 목표가(3년) |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for ticker in TICKERS:
        result = get_change(ticker)
        if result is None:
            lines.append(f"| {ticker} | - | - | - | - | - |")
            continue
        _, _, _, _, close, prev_close, pct_change = result
        change = close - prev_close
        change_sign = "+" if change >= 0 else "-"
        pct_sign = "+" if pct_change >= 0 else ""
        target_text = format_target_price(close, fetch_stats(ticker))
        personal_text = format_price_target(close, PERSONAL_TARGETS.get(ticker))
        lines.append(
            f"| {ticker} | ${close:,.2f} | {change_sign}${abs(change):,.2f} | "
            f"{pct_sign}{pct_change:.2f}% | {target_text} | {personal_text} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main():
    today = datetime.now(timezone.utc).date().isoformat()
    report = build_report(today)

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / f"{today}.md"
    output_path.write_text(report, encoding="utf-8")
    print(f"Saved report to {output_path}")


if __name__ == "__main__":
    main()
