import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import daily_report

FAKE_INDEX_RESULTS = {
    "^IXIC": ("2026-08-15", 15000.0, 15100.0, 14900.0, 14950.0, 15100.0, -0.99),
    "^NDX": ("2026-08-15", 18000.0, 18100.0, 17800.0, 17850.0, 18100.0, -1.38),
    "^VIX": ("2026-08-15", 18.0, 22.0, 17.5, 21.0, 18.0, 16.67),
}
FAKE_TICKER_RESULTS = {
    "NOW": ("2026-08-15", 900.0, 905.0, 895.0, 902.0, 905.0, -0.33),
    "TSLA": ("2026-08-15", 300.0, 305.0, 298.0, 302.0, 301.5, 0.17),
    "SPCX": ("2026-08-15", 114.0, 116.0, 113.0, 116.0, 115.5, 0.43),
    "INFQ": ("2026-08-15", 11.5, 12.0, 11.2, 11.9, 11.8, 0.85),
    "PL": ("2026-08-15", 23.0, 24.0, 22.5, 23.7, 23.4, 1.28),
    "QCOM": ("2026-08-15", 160.0, 165.0, 159.0, 162.68, 161.5, 0.73),
}


FAKE_STATS = {
    "NOW": {"target_mean_price": 950.0},
    "QCOM": {"target_mean_price": 178.95},
}


def fake_get_change(symbol):
    return FAKE_INDEX_RESULTS.get(symbol) or FAKE_TICKER_RESULTS.get(symbol)


def fake_fetch_stats(ticker):
    return FAKE_STATS.get(ticker, {})


class DailyReportTests(unittest.TestCase):
    def test_build_report_includes_indices_and_tickers(self):
        with patch("daily_report.get_change", side_effect=fake_get_change), \
             patch("daily_report.fetch_stats", side_effect=fake_fetch_stats):
            report = daily_report.build_report("2026-08-15")

        self.assertIn("# 2026-08-15 마감 리포트", report)
        self.assertIn("나스닥종합지수: 14,950.00 (-0.99%)", report)
        self.assertIn("나스닥 하락 마감", report)
        self.assertIn("변동성 확대", report)
        # VIX is intentionally omitted from the bullet list -- shown in the
        # macro-data section instead -- but its pct change still feeds the
        # summary sentence above (checked via "변동성 확대").
        self.assertNotIn("VIX:", report)
        self.assertIn(
            "| QCOM | $162.68 | +$1.18 | +0.73% | $178.95 (+10%) | $300.00 (+84%) |", report,
        )
        # regression check: negative change must render as "-$3.00", not "$-3.00"
        self.assertIn(
            "| NOW | $902.00 | -$3.00 | -0.33% | $950.00 (+5%) | $180.00 (-80%) |", report,
        )
        # ticker with no analyst target data falls back to "-"
        self.assertIn("| TSLA | $302.00 | +$0.50 | +0.17% | - | $480.00 (+59%) |", report)
        # per-ticker news is intentionally omitted -- redundant with the
        # card-click modal on the dashboard
        self.assertNotIn("종목별 최근 뉴스", report)

    def test_build_report_handles_missing_data(self):
        with patch("daily_report.get_change", return_value=None), \
             patch("daily_report.fetch_stats", return_value={}):
            report = daily_report.build_report("2026-08-15")

        self.assertIn("데이터 없음", report)
        self.assertIn("| NOW | - | - | - | - | - |", report)

    def test_main_writes_dated_file(self):
        test_dir = Path("/tmp/daily_report_test_output")
        shutil.rmtree(test_dir, ignore_errors=True)

        with patch("daily_report.OUTPUT_DIR", test_dir), \
             patch("daily_report.get_change", side_effect=fake_get_change), \
             patch("daily_report.fetch_stats", return_value={}), \
             patch("daily_report.datetime") as mock_datetime:
            mock_datetime.now.return_value.date.return_value.isoformat.return_value = "2026-08-15"
            daily_report.main()

        output_file = test_dir / "2026-08-15.md"
        self.assertTrue(output_file.exists())
        self.assertIn("2026-08-15 마감 리포트", output_file.read_text(encoding="utf-8"))

        shutil.rmtree(test_dir, ignore_errors=True)

    def test_format_target_price_computes_upside(self):
        self.assertEqual(
            daily_report.format_target_price(162.68, {"target_mean_price": 178.95}),
            "$178.95 (+10%)",
        )

    def test_format_target_price_computes_downside(self):
        self.assertEqual(
            daily_report.format_target_price(200.0, {"target_mean_price": 180.0}),
            "$180.00 (-10%)",
        )

    def test_format_target_price_handles_missing_stats(self):
        self.assertEqual(daily_report.format_target_price(100.0, {}), "-")
        self.assertEqual(daily_report.format_target_price(100.0, None), "-")

    def test_format_price_target_computes_upside(self):
        self.assertEqual(daily_report.format_price_target(100.0, 150.0), "$150.00 (+50%)")

    def test_format_price_target_handles_missing_target(self):
        self.assertEqual(daily_report.format_price_target(100.0, None), "-")

    def test_personal_targets_cover_every_ticker(self):
        from app import TICKERS
        for ticker in TICKERS:
            self.assertIn(ticker, daily_report.PERSONAL_TARGETS)


if __name__ == "__main__":
    unittest.main()
