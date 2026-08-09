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

    def test_market_summary_endpoint_returns_indices_and_summary(self):
        fake_results = {
            "^IXIC": ("2026-08-05", 15000.0, 15100.0, 14900.0, 14950.0, 15100.0, -0.99),
            "^NDX": ("2026-08-05", 18000.0, 18100.0, 17800.0, 17850.0, 18100.0, -1.38),
            "^VIX": ("2026-08-05", 18.0, 22.0, 17.5, 21.0, 18.0, 16.67),
        }

        with patch("app.get_change", side_effect=lambda symbol: fake_results[symbol]):
            response = self.client.get("/api/market-summary")
            data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data["indices"]), 3)
        ixic = next(i for i in data["indices"] if i["symbol"] == "^IXIC")
        self.assertEqual(ixic["name"], "나스닥종합지수")
        self.assertEqual(ixic["price"], 14950.0)
        self.assertEqual(ixic["change_pct"], -0.99)
        self.assertIn("하락", data["summary"])
        self.assertIn("약세", data["summary"])
        self.assertIn("변동성 확대", data["summary"])

    def test_market_summary_handles_missing_data(self):
        with patch("app.get_change", return_value=None):
            response = self.client.get("/api/market-summary")
            data = response.get_json()

        self.assertTrue(all("error" in item for item in data["indices"]))
        self.assertEqual(data["summary"], "나스닥 시황 정보를 불러올 수 없습니다.")

    def test_build_market_summary_up_and_calm(self):
        summary = app.build_market_summary(ixic_pct=1.2, ndx_pct=1.5, vix_pct=-8.0)
        self.assertIn("상승", summary)
        self.assertIn("강세", summary)
        self.assertIn("변동성 완화", summary)

    def test_build_market_summary_flat(self):
        summary = app.build_market_summary(ixic_pct=0.01, ndx_pct=0.0, vix_pct=1.0)
        self.assertIn("보합", summary)

    def test_index_detail_returns_ohlc_and_options(self):
        fake_result = ("2026-08-05", 18.0, 22.0, 17.5, 21.0, 18.0, 16.67)
        mock_ticker = MagicMock()
        mock_ticker.options = ["2026-08-15"]
        mock_chain = MagicMock()
        mock_chain.calls = pd.DataFrame({
            "strike": [19.0, 20.0, 21.0, 22.0, 23.0, 24.0],
            "lastPrice": [2.1, 1.5, 1.0, 0.6, 0.3, 0.1],
            "volume": [100, 200, 300, 150, 50, 10],
            "openInterest": [500, 600, 700, 400, 200, 100],
        })
        mock_chain.puts = pd.DataFrame({
            "strike": [19.0, 20.0, 21.0],
            "lastPrice": [0.2, 0.5, 0.9],
            "volume": [80, 90, 60],
            "openInterest": [300, 350, 250],
        })
        mock_ticker.option_chain.return_value = mock_chain

        with patch("app.get_change", return_value=fake_result), \
             patch("app.yf.Ticker", return_value=mock_ticker):
            response = self.client.get("/api/index/%5EVIX")
            data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["symbol"], "^VIX")
        self.assertEqual(data["close"], 21.0)
        self.assertEqual(data["options"]["status"], "ok")
        self.assertEqual(data["options"]["expiration"], "2026-08-15")
        self.assertEqual(len(data["options"]["calls"]), 5)
        self.assertEqual(len(data["options"]["puts"]), 3)
        # nearest-to-price (21.0) strike should be first after sorting by strike
        self.assertEqual(data["options"]["calls"][0]["strike"], 19.0)

    def test_index_detail_handles_no_options(self):
        fake_result = ("2026-08-05", 15000.0, 15100.0, 14900.0, 14950.0, 15100.0, -0.99)
        mock_ticker = MagicMock()
        mock_ticker.options = []

        with patch("app.get_change", return_value=fake_result), \
             patch("app.yf.Ticker", return_value=mock_ticker):
            response = self.client.get("/api/index/%5EIXIC")
            data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["options"], {"status": "unavailable"})

    def test_index_detail_unknown_symbol_returns_404(self):
        response = self.client.get("/api/index/FAKE")
        self.assertEqual(response.status_code, 404)

    def test_index_detail_handles_missing_data(self):
        with patch("app.get_change", return_value=None):
            response = self.client.get("/api/index/%5EVIX")
            data = response.get_json()

        self.assertEqual(data["error"], "no data")

    def test_fetch_options_summary_handles_exceptions(self):
        with patch("app.yf.Ticker", side_effect=RuntimeError("network error")):
            self.assertEqual(app.fetch_options_summary("^VIX", 20.0), {"status": "error"})

    def test_fetch_options_summary_handles_chain_lookup_exception(self):
        mock_ticker = MagicMock()
        mock_ticker.options = ["2026-08-15"]
        mock_ticker.option_chain.side_effect = RuntimeError("rate limited")

        with patch("app.yf.Ticker", return_value=mock_ticker):
            self.assertEqual(app.fetch_options_summary("^VIX", 20.0), {"status": "error"})


if __name__ == "__main__":
    unittest.main()
