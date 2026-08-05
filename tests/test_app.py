import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

import app


class DashboardAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_index_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_quotes_endpoint_returns_all_tickers(self):
        fake_result = ("2026-08-05", 100.0, 105.0, 99.0, 102.0, 100.0, 2.0)

        with patch("app.get_change", return_value=fake_result):
            response = self.client.get("/api/quotes")
            data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), len(app.TICKERS))
        self.assertEqual(data[0]["ticker"], app.TICKERS[0])
        self.assertEqual(data[0]["price"], 102.0)
        self.assertEqual(data[0]["change"], 2.0)
        self.assertEqual(data[0]["change_pct"], 2.0)

    def test_quotes_endpoint_handles_missing_data(self):
        with patch("app.get_change", return_value=None):
            response = self.client.get("/api/quotes")
            data = response.get_json()

        self.assertTrue(all("error" in item for item in data))

    def test_quotes_endpoint_handles_exceptions(self):
        with patch("app.get_change", side_effect=RuntimeError("network error")):
            response = self.client.get("/api/quotes")
            data = response.get_json()

        self.assertTrue(all("error" in item for item in data))

    def test_quote_detail_returns_ohlcv_and_news(self):
        fake_result = ("2026-08-05", 100.0, 105.0, 99.0, 102.0, 100.0, 2.0)
        fake_history = pd.DataFrame({"Volume": [900000, 1000000]})
        fake_news = [
            {
                "content": {
                    "title": "Sample headline",
                    "canonicalUrl": {"url": "https://example.com/news/1"},
                    "provider": {"displayName": "Example News"},
                }
            }
        ]
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = fake_history
        mock_ticker.news = fake_news

        with patch("app.get_change", return_value=fake_result), \
             patch("app.yf.Ticker", return_value=mock_ticker):
            response = self.client.get(f"/api/quote/{app.TICKERS[0]}")
            data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["open"], 100.0)
        self.assertEqual(data["high"], 105.0)
        self.assertEqual(data["low"], 99.0)
        self.assertEqual(data["volume"], 1000000)
        self.assertEqual(len(data["news"]), 1)
        self.assertEqual(data["news"][0]["title"], "Sample headline")
        self.assertEqual(data["news"][0]["link"], "https://example.com/news/1")

    def test_quote_detail_unknown_ticker_returns_404(self):
        response = self.client.get("/api/quote/NOTREAL")
        self.assertEqual(response.status_code, 404)

    def test_quote_detail_handles_missing_data(self):
        with patch("app.get_change", return_value=None):
            response = self.client.get(f"/api/quote/{app.TICKERS[0]}")
            data = response.get_json()

        self.assertEqual(data["error"], "no data")

    def test_fetch_news_tolerates_legacy_schema(self):
        mock_ticker = MagicMock()
        mock_ticker.news = [{"title": "Legacy headline", "link": "https://example.com/legacy", "publisher": "Old Wire"}]

        with patch("app.yf.Ticker", return_value=mock_ticker):
            news = app.fetch_news(app.TICKERS[0])

        self.assertEqual(news, [{"title": "Legacy headline", "link": "https://example.com/legacy", "publisher": "Old Wire"}])

    def test_fetch_news_handles_exceptions(self):
        with patch("app.yf.Ticker", side_effect=RuntimeError("network error")):
            self.assertEqual(app.fetch_news(app.TICKERS[0]), [])


if __name__ == "__main__":
    unittest.main()
