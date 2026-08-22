import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

import app


class DashboardAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        app._CACHE.clear()

    def test_index_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_daily_report_endpoint_returns_latest_file(self):
        test_dir = Path("/tmp/test_daily_report_dir")
        shutil.rmtree(test_dir, ignore_errors=True)
        test_dir.mkdir()
        (test_dir / "2026-08-14.md").write_text("# older report", encoding="utf-8")
        (test_dir / "2026-08-15.md").write_text("# newest report", encoding="utf-8")

        try:
            with patch.object(app, "DAILY_REPORT_DIR", test_dir):
                response = self.client.get("/api/daily-report")
                data = response.get_json()

            self.assertEqual(response.status_code, 200)
            self.assertEqual(data["date"], "2026-08-15")
            self.assertEqual(data["content"], "# newest report")
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_daily_report_endpoint_handles_missing_directory(self):
        with patch.object(app, "DAILY_REPORT_DIR", Path("/tmp/does-not-exist-daily-report-dir")):
            response = self.client.get("/api/daily-report")
            data = response.get_json()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(data["error"], "no report")

    def test_daily_report_endpoint_handles_empty_directory(self):
        test_dir = Path("/tmp/test_daily_report_empty_dir")
        shutil.rmtree(test_dir, ignore_errors=True)
        test_dir.mkdir()

        try:
            with patch.object(app, "DAILY_REPORT_DIR", test_dir):
                response = self.client.get("/api/daily-report")
                data = response.get_json()

            self.assertEqual(response.status_code, 404)
            self.assertEqual(data["error"], "no report")
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_macro_data_endpoint_returns_file_contents(self):
        test_path = Path("/tmp/test_macro_data.json")
        test_path.write_text(
            '{"updated_at": "2026-08-22T22:00:00Z", "series": {"DGS10": {"value": 4.32}}}',
            encoding="utf-8",
        )

        try:
            with patch.object(app, "MACRO_DATA_PATH", test_path):
                response = self.client.get("/api/macro-data")
                data = response.get_json()

            self.assertEqual(response.status_code, 200)
            self.assertEqual(data["series"]["DGS10"]["value"], 4.32)
        finally:
            test_path.unlink(missing_ok=True)

    def test_macro_data_endpoint_handles_missing_file(self):
        with patch.object(app, "MACRO_DATA_PATH", Path("/tmp/does-not-exist-macro.json")):
            response = self.client.get("/api/macro-data")
            data = response.get_json()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(data["error"], "no data")

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
            "targetMeanPrice": 210.5,
            "numberOfAnalystOpinions": 24,
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
            "target_mean_price": 210.5,
            "analyst_count": 24,
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
            "^GSPC": ("2026-08-05", 5500.0, 5550.0, 5450.0, 5490.0, 5550.0, -1.08),
            "^DJI": ("2026-08-05", 40000.0, 40200.0, 39700.0, 39900.0, 40200.0, -0.75),
            "^IXIC": ("2026-08-05", 15000.0, 15100.0, 14900.0, 14950.0, 15100.0, -0.99),
            "^NDX": ("2026-08-05", 18000.0, 18100.0, 17800.0, 17850.0, 18100.0, -1.38),
            "^RUT": ("2026-08-05", 2100.0, 2120.0, 2080.0, 2090.0, 2120.0, -1.42),
            "^VIX": ("2026-08-05", 18.0, 22.0, 17.5, 21.0, 18.0, 16.67),
        }

        with patch("app.get_change", side_effect=lambda symbol: fake_results[symbol]):
            response = self.client.get("/api/market-summary")
            data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data["indices"]), 6)
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
        self.assertEqual(data["summary"], "미국 주식시장 시황 정보를 불러올 수 없습니다.")

    def test_build_market_summary_up_and_calm(self):
        summary = app.build_market_summary(gspc_pct=1.2, dji_pct=0.5, ndx_pct=1.5, rut_pct=1.0, vix_pct=-8.0)
        self.assertIn("상승", summary)
        self.assertIn("기술주가 대형 우량주 대비 강세", summary)
        self.assertIn("변동성 완화", summary)

    def test_build_market_summary_flat(self):
        summary = app.build_market_summary(gspc_pct=0.01, dji_pct=0.0, ndx_pct=0.0, rut_pct=0.0, vix_pct=1.0)
        self.assertIn("보합", summary)

    def test_build_market_summary_small_cap_divergence(self):
        summary = app.build_market_summary(gspc_pct=0.2, dji_pct=0.2, ndx_pct=0.2, rut_pct=-1.0, vix_pct=None)
        self.assertIn("소형주 상대적 약세", summary)

    def test_build_market_summary_handles_missing_secondary_indices(self):
        # dji/ndx/rut/vix missing shouldn't crash -- just no extra clauses.
        summary = app.build_market_summary(gspc_pct=0.8, dji_pct=None, ndx_pct=None, rut_pct=None, vix_pct=None)
        self.assertEqual(summary, "미국 증시 상승 마감")

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

    def test_index_detail_returns_ohlc(self):
        fake_result = ("2026-08-05", 18.0, 22.0, 17.5, 21.0, 18.0, 16.67)

        with patch("app.get_change", return_value=fake_result):
            response = self.client.get("/api/index/%5EVIX")
            data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["symbol"], "^VIX")
        self.assertEqual(data["close"], 21.0)
        self.assertNotIn("options", data)

    def test_index_detail_unknown_symbol_returns_404(self):
        response = self.client.get("/api/index/FAKE")
        self.assertEqual(response.status_code, 404)

    def test_index_detail_handles_missing_data(self):
        with patch("app.get_change", return_value=None):
            response = self.client.get("/api/index/%5EVIX")
            data = response.get_json()

        self.assertEqual(data["error"], "no data")


if __name__ == "__main__":
    unittest.main()
