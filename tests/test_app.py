import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

import app


class FakeResponse:
    """Minimal stand-in for requests.Response used to mock Tradier API calls."""

    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class DashboardAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        app._CACHE.clear()

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
        mock_ticker.info = {
            "marketCap": 1_500_000_000_000,
            "trailingPE": 28.4,
            "trailingEps": 6.1,
            "beta": 1.3,
            "fiftyTwoWeekHigh": 220.5,
            "fiftyTwoWeekLow": 140.2,
            "averageVolume": 45_000_000,
        }

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
        self.assertEqual(data["stats"]["market_cap"], 1_500_000_000_000)
        self.assertEqual(data["stats"]["pe_ratio"], 28.4)
        self.assertEqual(data["stats"]["week52_high"], 220.5)
        self.assertEqual(data["stats"]["week52_low"], 140.2)

    def test_quote_detail_unknown_ticker_returns_404(self):
        response = self.client.get("/api/quote/NOTREAL")
        self.assertEqual(response.status_code, 404)

    def test_quote_detail_handles_missing_data(self):
        with patch("app.get_change", return_value=None):
            response = self.client.get(f"/api/quote/{app.TICKERS[0]}")
            data = response.get_json()

        self.assertEqual(data["error"], "no data")

    def test_quote_history_returns_points(self):
        idx = pd.date_range("2026-07-01", periods=3, freq="B", tz="America/New_York")
        fake_history = pd.DataFrame({"Close": [180.5, 181.25, 179.9]}, index=idx)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = fake_history

        with patch("app.yf.Ticker", return_value=mock_ticker):
            response = self.client.get(f"/api/quote/{app.TICKERS[0]}/history?range=1mo")
            data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["range"], "1mo")
        self.assertEqual(len(data["points"]), 3)
        self.assertEqual(data["points"][0]["close"], 180.5)
        mock_ticker.history.assert_called_once_with(period="1mo", interval="1d", auto_adjust=True)

    def test_quote_history_defaults_range(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame({"Close": []})

        with patch("app.yf.Ticker", return_value=mock_ticker):
            response = self.client.get(f"/api/quote/{app.TICKERS[0]}/history")

        self.assertEqual(response.status_code, 200)
        default_config = app.CHART_RANGES[app.DEFAULT_CHART_RANGE]
        mock_ticker.history.assert_called_once_with(
            period=default_config["period"], interval=default_config["interval"], auto_adjust=True,
        )

    def test_quote_history_uses_intraday_interval_and_time_format(self):
        idx = pd.date_range("2026-08-05 09:30", periods=2, freq="5min", tz="America/New_York")
        fake_history = pd.DataFrame({"Close": [180.1, 180.4]}, index=idx)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = fake_history

        with patch("app.yf.Ticker", return_value=mock_ticker):
            response = self.client.get(f"/api/quote/{app.TICKERS[0]}/history?range=1d")
            data = response.get_json()

        self.assertEqual(response.status_code, 200)
        mock_ticker.history.assert_called_once_with(period="1d", interval="5m", auto_adjust=True)
        self.assertEqual(data["points"][0]["date"], "2026-08-05 09:30")

    def test_quote_history_rejects_invalid_range(self):
        response = self.client.get(f"/api/quote/{app.TICKERS[0]}/history?range=15y")
        self.assertEqual(response.status_code, 400)

    def test_quote_history_unknown_ticker_returns_404(self):
        response = self.client.get("/api/quote/NOTREAL/history")
        self.assertEqual(response.status_code, 404)

    def test_quote_history_handles_exceptions(self):
        with patch("app.yf.Ticker", side_effect=RuntimeError("network error")):
            response = self.client.get(f"/api/quote/{app.TICKERS[0]}/history")
            data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["points"], [])

    def test_fetch_stats_returns_known_fields(self):
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "marketCap": 987_000_000_000,
            "trailingPE": 31.2,
            "trailingEps": 4.5,
            "beta": 1.1,
            "fiftyTwoWeekHigh": 300.0,
            "fiftyTwoWeekLow": 180.0,
            "averageVolume": 12_000_000,
            "someOtherField": "ignored",
        }

        with patch("app.yf.Ticker", return_value=mock_ticker):
            stats = app.fetch_stats(app.TICKERS[0])

        self.assertEqual(stats, {
            "market_cap": 987_000_000_000,
            "pe_ratio": 31.2,
            "eps": 4.5,
            "beta": 1.1,
            "week52_high": 300.0,
            "week52_low": 180.0,
            "avg_volume": 12_000_000,
        })

    def test_fetch_stats_defaults_missing_fields_to_none(self):
        mock_ticker = MagicMock()
        mock_ticker.info = {}

        with patch("app.yf.Ticker", return_value=mock_ticker):
            stats = app.fetch_stats(app.TICKERS[0])

        self.assertTrue(all(v is None for v in stats.values()))

    def test_fetch_stats_handles_exceptions(self):
        with patch("app.yf.Ticker", side_effect=RuntimeError("network error")):
            self.assertIsNone(app.fetch_stats(app.TICKERS[0]))

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

    def test_cached_get_change_reuses_result_within_ttl(self):
        fake_result = ("2026-08-05", 100.0, 105.0, 99.0, 102.0, 100.0, 2.0)
        with patch("app.get_change", return_value=fake_result) as mock_get_change:
            first = app._cached_get_change("NOW")
            second = app._cached_get_change("NOW")

        self.assertEqual(first, fake_result)
        self.assertEqual(second, fake_result)
        mock_get_change.assert_called_once_with("NOW")

    def test_cached_get_change_refetches_after_ttl_expiry(self):
        fake_result = ("2026-08-05", 100.0, 105.0, 99.0, 102.0, 100.0, 2.0)
        with patch("app.get_change", return_value=fake_result) as mock_get_change:
            app._cached_get_change("NOW")
            # simulate the cache entry having expired
            key = ("get_change", "NOW")
            value, _ = app._CACHE[key]
            app._CACHE[key] = (value, 0)
            app._cached_get_change("NOW")

        self.assertEqual(mock_get_change.call_count, 2)

    def test_cached_raw_option_chain_reused_across_different_prices(self):
        exp_response = FakeResponse({"expirations": {"date": ["2026-08-15"]}})
        chain_response = FakeResponse({"options": {"option": [
            {"strike": 19.0, "last": 2.1, "volume": 100, "open_interest": 500, "option_type": "call"},
            {"strike": 20.0, "last": 1.5, "volume": 200, "open_interest": 600, "option_type": "call"},
            {"strike": 19.0, "last": 0.2, "volume": 80, "open_interest": 300, "option_type": "put"},
            {"strike": 20.0, "last": 0.5, "volume": 90, "open_interest": 350, "option_type": "put"},
        ]}})

        with patch.object(app, "TRADIER_API_TOKEN", "test-token"), \
             patch("app.requests.get", side_effect=[exp_response, chain_response]) as mock_get:
            app.fetch_options_summary("^VIX", 19.5)
            app.fetch_options_summary("^VIX", 20.1)

        # expirations + chain should only be fetched once (2 calls total) even
        # though the price used for narrowing strikes differed between calls.
        self.assertEqual(mock_get.call_count, 2)

    def test_fetch_options_summary_returns_unavailable_without_token(self):
        with patch.object(app, "TRADIER_API_TOKEN", None), \
             patch("app.requests.get") as mock_get:
            result = app.fetch_options_summary("^VIX", 20.0)

        self.assertEqual(result, {"status": "unavailable"})
        mock_get.assert_not_called()

    def test_index_detail_returns_ohlc_and_options(self):
        fake_result = ("2026-08-05", 18.0, 22.0, 17.5, 21.0, 18.0, 16.67)
        exp_response = FakeResponse({"expirations": {"date": ["2026-08-15"]}})
        contracts = (
            [
                {"strike": s, "last": p, "volume": v, "open_interest": oi, "option_type": "call"}
                for s, p, v, oi in [
                    (19.0, 2.1, 100, 500), (20.0, 1.5, 200, 600), (21.0, 1.0, 300, 700),
                    (22.0, 0.6, 150, 400), (23.0, 0.3, 50, 200), (24.0, 0.1, 10, 100),
                ]
            ]
            + [
                {"strike": s, "last": p, "volume": v, "open_interest": oi, "option_type": "put"}
                for s, p, v, oi in [(19.0, 0.2, 80, 300), (20.0, 0.5, 90, 350), (21.0, 0.9, 60, 250)]
            ]
        )
        chain_response = FakeResponse({"options": {"option": contracts}})

        with patch("app.get_change", return_value=fake_result), \
             patch.object(app, "TRADIER_API_TOKEN", "test-token"), \
             patch("app.requests.get", side_effect=[exp_response, chain_response]):
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

        # No TRADIER_API_TOKEN configured -> options are reported unavailable
        # without any outbound request at all.
        with patch("app.get_change", return_value=fake_result):
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

    def test_fetch_options_summary_handles_expirations_exception(self):
        with patch.object(app, "TRADIER_API_TOKEN", "test-token"), \
             patch("app.requests.get", side_effect=RuntimeError("network error")):
            self.assertEqual(app.fetch_options_summary("^VIX", 20.0), {"status": "error"})

    def test_fetch_options_summary_handles_no_expirations(self):
        exp_response = FakeResponse({"expirations": None})

        with patch.object(app, "TRADIER_API_TOKEN", "test-token"), \
             patch("app.requests.get", return_value=exp_response):
            self.assertEqual(app.fetch_options_summary("^VIX", 20.0), {"status": "unavailable"})

    def test_fetch_options_summary_handles_chain_lookup_exception(self):
        exp_response = FakeResponse({"expirations": {"date": ["2026-08-15"]}})

        with patch.object(app, "TRADIER_API_TOKEN", "test-token"), \
             patch("app.requests.get", side_effect=[exp_response, RuntimeError("rate limited")]):
            self.assertEqual(app.fetch_options_summary("^VIX", 20.0), {"status": "error"})


if __name__ == "__main__":
    unittest.main()
