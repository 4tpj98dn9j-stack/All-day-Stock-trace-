"""Generate a dated markdown report: watchlist prices/news plus a NASDAQ market recap.

Usage:
    python daily_report.py
    # writes daily/<YYYY-MM-DD>.md

Intended to run once per trading day after market close via
.github/workflows/daily-report.yml (GitHub's runners have normal internet
access to Yahoo Finance, unlike this project's other dev/CI sandboxes).
"""

from datetime import datetime, timezone
from pathlib import Path

from app import INDICES, TICKERS, build_market_summary, fetch_news
from daily_change_tracker import get_change

NEWS_PER_TICKER = 2
OUTPUT_DIR = Path("daily")


def build_report(today):
    lines = [f"# {today} 마감 리포트", ""]

    lines.append("## 나스닥 시황")
    lines.append("")
    pct_by_symbol = {}
    for meta in INDICES:
        result = get_change(meta["symbol"])
        if result is None:
            lines.append(f"- {meta['name']}: 데이터 없음")
            pct_by_symbol[meta["symbol"]] = None
            continue
        _, _, _, _, close, prev_close, pct_change = result
        sign = "+" if pct_change >= 0 else ""
        lines.append(f"- {meta['name']}: {close:,.2f} ({sign}{pct_change:.2f}%)")
        pct_by_symbol[meta["symbol"]] = pct_change

    summary = build_market_summary(
        pct_by_symbol.get("^IXIC"), pct_by_symbol.get("^NDX"), pct_by_symbol.get("^VIX"),
    )
    lines.append("")
    lines.append(f"> {summary}")
    lines.append("")

    lines.append("## 보유 종목 시세")
    lines.append("")
    lines.append("| 종목 | 종가 | 전일 대비 | 등락률 |")
    lines.append("| --- | --- | --- | --- |")
    for ticker in TICKERS:
        result = get_change(ticker)
        if result is None:
            lines.append(f"| {ticker} | - | - | - |")
            continue
        _, _, _, _, close, prev_close, pct_change = result
        change = close - prev_close
        change_sign = "+" if change >= 0 else "-"
        pct_sign = "+" if pct_change >= 0 else ""
        lines.append(f"| {ticker} | ${close:,.2f} | {change_sign}${abs(change):,.2f} | {pct_sign}{pct_change:.2f}% |")
    lines.append("")

    lines.append("## 종목별 최근 뉴스")
    lines.append("")
    for ticker in TICKERS:
        lines.append(f"### {ticker}")
        news_items = fetch_news(ticker)[:NEWS_PER_TICKER]
        if not news_items:
            lines.append("- 관련 뉴스 없음")
        else:
            for item in news_items:
                suffix = f" ({item['publisher']})" if item.get("publisher") else ""
                lines.append(f"- [{item['title']}]({item['link']}){suffix}")
        lines.append("")

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
