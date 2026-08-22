import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_macro_data

FAKE_OBSERVATIONS = {
    "DGS10": [{"date": "2026-08-21", "value": "4.32"}, {"date": "2026-08-20", "value": "4.28"}],
    "NASDAQCOM": [{"date": "2026-08-21", "value": "21000.5"}, {"date": "2026-08-20", "value": "20950.1"}],
    "VIXCLS": [{"date": "2026-08-21", "value": "14.25"}],
    "FEDFUNDS": [],
}


def fake_fetch(series_id, api_key, count=2):
    return FAKE_OBSERVATIONS.get(series_id, [])[:count]


class FetchMacroDataTests(unittest.TestCase):
    def test_build_macro_data_computes_change(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        dgs10 = data["series"]["DGS10"]
        self.assertEqual(dgs10["value"], 4.32)
        self.assertEqual(dgs10["prev_value"], 4.28)
        self.assertAlmostEqual(dgs10["change"], 0.04)
        self.assertEqual(dgs10["date"], "2026-08-21")

    def test_build_macro_data_handles_single_observation(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        vix = data["series"]["VIXCLS"]
        self.assertEqual(vix["value"], 14.25)
        self.assertIsNone(vix["prev_value"])
        self.assertIsNone(vix["change"])

    def test_build_macro_data_handles_no_data(self):
        with patch("fetch_macro_data.fetch_latest_observations", side_effect=fake_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        self.assertEqual(data["series"]["FEDFUNDS"]["error"], "no data")

    def test_build_macro_data_handles_fetch_exception(self):
        def raising_fetch(series_id, api_key, count=2):
            raise RuntimeError("network error")

        with patch("fetch_macro_data.fetch_latest_observations", side_effect=raising_fetch):
            data = fetch_macro_data.build_macro_data("fake-key")

        self.assertEqual(data["series"]["DGS10"]["error"], "no data")

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

        shutil.rmtree(test_path.parent, ignore_errors=True)

    def test_main_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit):
                fetch_macro_data.main()


if __name__ == "__main__":
    unittest.main()
