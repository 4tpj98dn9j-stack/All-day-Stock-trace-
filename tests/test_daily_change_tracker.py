import csv
import os
import unittest
from unittest.mock import patch

import pandas as pd

import daily_change_tracker


def make_history(base, periods=5):
    idx = pd.date_range("2026-08-03", periods=periods, freq="B", tz="America/New_York")
    return pd.DataFrame({
        "Open": [base + i * 0.3 for i in range(periods)],
        "High": [base + i * 0.3 + 1.0 for i in range(periods)],
        "Low": [base + i * 0.3 - 1.0 for i in range(periods)],
        "Close": [base + i * 0.5 for i in range(periods)],
        "Volume": [1000000 + i * 10000 for i in range(periods)],
    }, index=idx)


class DailyChangeTrackerTests(unittest.TestCase):
    def test_get_change_computes_pct_change(self):
        with patch("daily_change_tracker.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = make_history(base=100)
            date, open_, high, low, close, prev_close, pct_change = daily_change_tracker.get_change("TEST")

        self.assertEqual(close, 102.0)
        self.assertEqual(prev_close, 101.5)
        self.assertAlmostEqual(pct_change, (102.0 - 101.5) / 101.5 * 100)

    def test_get_change_returns_none_on_insufficient_data(self):
        with patch("daily_change_tracker.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = make_history(base=100, periods=1)
            self.assertIsNone(daily_change_tracker.get_change("TEST"))

    def test_main_writes_and_appends_csv(self):
        output_path = "/tmp/test_daily_change_log.csv"
        try:
            os.remove(output_path)
        except FileNotFoundError:
            pass

        def fake_ticker(symbol):
            class FakeTicker:
                def history(self, period="5d", auto_adjust=True):
                    return make_history(base=hash(symbol) % 100 + 50)
            return FakeTicker()

        import sys
        sys.argv = ["daily_change_tracker.py", "--tickers", "AAA", "BBB", "--output", output_path]
        with patch("daily_change_tracker.yf.Ticker", side_effect=fake_ticker):
            daily_change_tracker.main()
            with open(output_path, newline="") as f:
                rows_after_first_run = list(csv.reader(f))
            daily_change_tracker.main()
            with open(output_path, newline="") as f:
                rows_after_second_run = list(csv.reader(f))

        self.assertEqual(rows_after_first_run[0], [
            "date", "ticker", "open", "high", "low", "close", "prev_close", "pct_change", "fetched_at",
        ])
        self.assertEqual(len(rows_after_first_run), 3)
        self.assertEqual(len(rows_after_second_run), 5)


if __name__ == "__main__":
    unittest.main()
