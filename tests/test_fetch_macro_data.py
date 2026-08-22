import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_macro_data

FAKE_OBSERVATIONS = {
    "DGS10": [{"date": "2026-08-21", "value": "4.32"}, {"date": "2026-08-20", "value": "4.28"}],
    "FEDFUNDS": [{"date": "2026-07-01", "value": "3.63"}, {"date": "2026-06-01", "value": "3.63"}],
    # 14 months, newest first: index 0 = latest, 12 = same month last year
    # (for YoY), 13 = one month before that (for the prior period's YoY).
    "CPIAUCSL": [
        {"date": "2026-07-01", "value": "110.0"},
        {"date": "2026-06-01", "value": "108.0"},
        {"date": "2026-05-01", "value": "105.0"},
        {"date": "2026-04-01", "value": "105.0"},
        {"date": "2026-03-01", "value": "105.0"},
        {"date": "2026-02-01", "value": "105.0"},
        {"date": "2026-01-01", "value": "105.0"},
        {"date": "2025-12-01", "value": "105.0"},
        {"date": "2025-11-01", "value": "105.0"},
        {"date": "2025-10-01", "value": "105.0"},
        {"date": "2025-09-01", "value": "105.0"},
        {"date": "2025-08-01", "value": "105.0"},
        {"date": "2025-07-01", "value": "100.0"},
        {"date": "2025-06-01", "value": "99.0"},
    ],
    "RPONTSYD": [{"date": "2026-08-21", "value": "12.5"}, {"date": "2026-08-20", "value": "8.0"}],
    "WALCL": [{"date": "2026-08-20", "value": "6634567"}, {"date": "2026-08-13", "value": "6640123"}],
}


def fake_fetch(series_id, api_key, count=2):
    return FAKE_OBSERVATIONS.get(series_id, [])[:count]


class FetchMacroDataTests(unittest.TestCase):
    def test_build_macro_data_level_series(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        dgs10 = data["series"]["DGS10"]
        self.assertEqual(dgs10["value"], 4.32)
        self.assertEqual(dgs10["prev_value"], 4.28)
        self.assertAlmostEqual(dgs10["change"], 0.04)
        self.assertEqual(dgs10["date"], "2026-08-21")
        self.assertEqual(dgs10["prefix"], "")
        self.assertEqual(dgs10["unit"], "%")

    def test_build_macro_data_cpi_yoy(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        cpi = data["series"]["CPIAUCSL"]
        # yoy = 110.0 / 100.0 - 1 = 10%; prev_yoy = 108.0 / 99.0 - 1 ~= 9.0909%
        self.assertAlmostEqual(cpi["value"], 10.0)
        self.assertAlmostEqual(cpi["change"], 0.9091, places=4)
        self.assertIsNone(cpi["prev_value"])
        self.assertEqual(cpi["date"], "2026-07-01")

    def test_build_macro_data_scales_walcl_to_trillions(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        walcl = data["series"]["WALCL"]
        self.assertAlmostEqual(walcl["value"], 6.6346, places=4)
        self.assertEqual(walcl["prefix"], "$")
        self.assertEqual(walcl["unit"], "T")

    def test_build_macro_data_walcl_includes_chronological_history(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        history = data["series"]["WALCL"]["history"]
        # FAKE_OBSERVATIONS["WALCL"] is newest-first; history must be oldest-first.
        self.assertEqual([p["date"] for p in history], ["2026-08-13", "2026-08-20"])
        self.assertAlmostEqual(history[-1]["value"], 6.6346, places=4)

    def test_other_series_have_no_history(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        self.assertNotIn("history", data["series"]["DGS10"])

    def test_build_macro_data_srf_prefix_and_unit(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        srf = data["series"]["RPONTSYD"]
        self.assertEqual(srf["value"], 12.5)
        self.assertEqual(srf["change"], 4.5)
        self.assertEqual(srf["prefix"], "$")
        self.assertEqual(srf["unit"], "B")

    def test_build_series_entry_requests_history_count_for_walcl(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch) as mock_fetch:
            walcl_meta = next(m for m in fetch_macro_data.MACRO_SERIES if m["id"] == "WALCL")
            fetch_macro_data.build_series_entry(walcl_meta, "fake-key")

        mock_fetch.assert_called_once_with("WALCL", "fake-key", count=260)

    def test_build_macro_data_handles_no_data(self):
        def fetch_with_empty_fedfunds(series_id, api_key, count=2):
            if series_id == "FEDFUNDS":
                return []
            return FAKE_OBSERVATIONS.get(series_id, [])[:count]

        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fetch_with_empty_fedfunds):
            data = fetch_macro_data.build_macro_data("fake-key")

        self.assertEqual(data["series"]["FEDFUNDS"]["error"], "no data")

    def test_build_macro_data_handles_fetch_exception(self):
        def raising_fetch(series_id, api_key, count=2):
            raise RuntimeError("network error")

        with patch("fetch_macro_data.fetch_latest_observations", side_effect=raising_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        self.assertEqual(data["series"]["DGS10"]["error"], "no data")
        self.assertEqual(data["series"]["CPIAUCSL"]["error"], "no data")

    def test_build_macro_data_cpi_handles_insufficient_history(self):
        def short_fetch(series_id, api_key, count=2):
            if series_id == "CPIAUCSL":
                return FAKE_OBSERVATIONS["CPIAUCSL"][:5]
            return FAKE_OBSERVATIONS.get(series_id, [])[:count]

        with patch("fetch_macro_data.fetch_latest_observations", side_effect=short_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        self.assertEqual(data["series"]["CPIAUCSL"]["error"], "no data")

    def test_fetch_latest_observations_filters_missing_values(self):
        fake_response_json = {
            "observations": [
                {"date": "2026-08-21", "value": "."},
                {"date": "2026-08-20", "value": "4.28"},
                {"date": "2026-08-19", "value": "4.25"},
            ]
        }

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return fake_response_json

        with patch("fetch_macro_data.requests.get", return_value=FakeResponse()):
            result = fetch_macro_data.fetch_latest_observations("DGS10", "fake-key")

        self.assertEqual(result, [
            {"date": "2026-08-20", "value": "4.28"},
            {"date": "2026-08-19", "value": "4.25"},
        ])

    def test_fetch_latest_observations_requests_larger_limit_for_higher_count(self):
        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"observations": []}

        with patch("fetch_macro_data.requests.get", return_value=FakeResponse()) as mock_get:
            fetch_macro_data.fetch_latest_observations("CPIAUCSL", "fake-key", count=14)

        self.assertEqual(mock_get.call_args.kwargs["params"]["limit"], 28)

    def test_main_writes_json_file(self):
        test_path = Path("/tmp/macro_data_test_output/macro.json")
        shutil.rmtree(test_path.parent, ignore_errors=True)

        with patch("fetch_macro_data.OUTPUT_PATH", test_path), \
             patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch), \
             patch.dict("os.environ", {"FRED_API_KEY": "fake-key"}):
            fetch_macro_data.main()

        self.assertTrue(test_path.exists())
        saved = json.loads(test_path.read_text(encoding="utf-8"))
        self.assertIn("DGS10", saved["series"])
        self.assertIn("WALCL", saved["series"])

        shutil.rmtree(test_path.parent, ignore_errors=True)

    def test_main_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit):
                fetch_macro_data.main()


if __name__ == "__main__":
    unittest.main()
