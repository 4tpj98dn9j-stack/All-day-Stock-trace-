import csv
import sys
import unittest
from unittest.mock import patch

import pandas as pd

import fetch_stock_data


class FetchStockDataTests(unittest.TestCase):
    def test_fetch_and_save_writes_expected_columns(self):
        idx = pd.date_range("2026-07-28", periods=3, freq="B", tz="America/New_York")
        fake_hist = pd.DataFrame({
            "Open": [180.1, 181.5, 179.8],
            "High": [182.0, 182.3, 181.0],
            "Low": [179.5, 180.9, 178.6],
            "Close": [181.2, 179.9, 181.9],
            "Volume": [52341200, 48122300, 61033400],
        }, index=idx)

        output_path = "/tmp/test_fetch_stock_data_output.csv"
        with patch("fetch_stock_data.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = fake_hist
            fetch_stock_data.fetch_and_save("AAPL", "5d", output_path)

        with open(output_path, newline="") as f:
            rows = list(csv.reader(f))

        self.assertEqual(rows[0], ["date", "open", "high", "low", "close", "volume"])
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[1][0], "2026-07-28")

    def test_fetch_and_save_exits_on_empty_data(self):
        with patch("fetch_stock_data.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = pd.DataFrame()
            with self.assertRaises(SystemExit):
                fetch_stock_data.fetch_and_save("BADTICKER", "5d", "/tmp/unused.csv")


if __name__ == "__main__":
    unittest.main()
