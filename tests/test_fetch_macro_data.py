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
    "BAMLH0A0HYM2": [{"date": "2026-08-21", "value": "3.20"}, {"date": "2026-08-20", "value": "3.15"}],
    "BAA10Y": [{"date": "2026-08-21", "value": "1.85"}, {"date": "2026-08-20", "value": "1.80"}],
    "NFCI": [{"date": "2026-08-14", "value": "-0.35"}, {"date": "2026-08-07", "value": "-0.30"}],
    "STLFSI4": [{"date": "2026-08-14", "value": "-0.55"}, {"date": "2026-08-07", "value": "-0.50"}],
    "T5YIE": [{"date": "2026-08-21", "value": "2.35"}, {"date": "2026-08-20", "value": "2.30"}],
    "T10YIE": [{"date": "2026-08-21", "value": "2.40"}, {"date": "2026-08-20", "value": "2.38"}],
    "T5YIFR": [{"date": "2026-08-21", "value": "2.20"}, {"date": "2026-08-20", "value": "2.18"}],
    "DTWEXBGS": [{"date": "2026-08-21", "value": "121.50"}, {"date": "2026-08-20", "value": "121.80"}],
    "UNRATE": [{"date": "2026-07-01", "value": "4.20"}, {"date": "2026-06-01", "value": "4.10"}],
    "ICSA": [{"date": "2026-08-16", "value": "220000"}, {"date": "2026-08-09", "value": "215000"}],
    "UMCSENT": [{"date": "2026-08-01", "value": "68.5"}, {"date": "2026-07-01", "value": "67.0"}],
    # month-over-month diff: 0-1 = 180, 1-2 = 154, change = 180 - 154 = 26.
    "PAYEMS": [
        {"date": "2026-07-01", "value": "161234"},
        {"date": "2026-06-01", "value": "161054"},
        {"date": "2026-05-01", "value": "160900"},
    ],
    # 14 months, newest first, same YoY layout as CPIAUCSL above.
    "INDPRO": [
        {"date": "2026-07-01", "value": "108.0"},
        {"date": "2026-06-01", "value": "107.0"},
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
        {"date": "2025-07-01", "value": "104.0"},
        {"date": "2025-06-01", "value": "103.0"},
    ],
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

    def test_build_macro_data_covers_all_configured_series(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        expected_ids = {meta["id"] for meta in fetch_macro_data.MACRO_SERIES}
        self.assertEqual(set(data["series"].keys()), expected_ids)
        self.assertNotIn("VIXCLS", data["series"])
        self.assertNotIn("NASDAQCOM", data["series"])

    def test_build_macro_data_simple_level_series(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        cases = {
            "BAMLH0A0HYM2": (3.20, 0.05),
            "BAA10Y": (1.85, 0.05),
            "NFCI": (-0.35, -0.05),
            "STLFSI4": (-0.55, -0.05),
            "T5YIE": (2.35, 0.05),
            "T10YIE": (2.40, 0.02),
            "T5YIFR": (2.20, 0.02),
            "DTWEXBGS": (121.50, -0.30),
            "UNRATE": (4.20, 0.10),
            "UMCSENT": (68.5, 1.5),
        }
        for series_id, (expected_value, expected_change) in cases.items():
            entry = data["series"][series_id]
            self.assertAlmostEqual(entry["value"], expected_value, msg=series_id)
            self.assertAlmostEqual(entry["change"], expected_change, msg=series_id)

    def test_build_macro_data_scales_icsa_to_thousands(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        icsa = data["series"]["ICSA"]
        self.assertAlmostEqual(icsa["value"], 220.0)
        self.assertAlmostEqual(icsa["change"], 5.0)
        self.assertEqual(icsa["unit"], "K")

    def test_build_macro_data_payems_mom_diff(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        payems = data["series"]["PAYEMS"]
        self.assertAlmostEqual(payems["value"], 180.0)
        self.assertAlmostEqual(payems["change"], 26.0)
        self.assertIsNone(payems["prev_value"])
        self.assertEqual(payems["date"], "2026-07-01")

    def test_build_macro_data_indpro_yoy(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        indpro = data["series"]["INDPRO"]
        self.assertAlmostEqual(indpro["value"], 3.8462, places=4)
        self.assertAlmostEqual(indpro["change"], -0.0373, places=4)

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
