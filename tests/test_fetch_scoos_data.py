import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_scoos_data

# Quarterly observations, newest first -- the shape fetch_latest_observations
# returns for a FRED quarterly series.
FAKE_OBSERVATIONS = [
    {"date": "2026-07-01", "value": "-12.5"},
    {"date": "2026-04-01", "value": "5.26"},
    {"date": "2026-01-01", "value": "15.79"},
    {"date": "2025-10-01", "value": "11.76"},
]


def fake_fetch(series_id, api_key, count=2):
    return FAKE_OBSERVATIONS[:count]


class QuarterLabelTests(unittest.TestCase):
    def test_maps_first_month_of_quarter_to_quarter_number(self):
        self.assertEqual(fetch_scoos_data.quarter_label("2026-01-01"), "2026 Q1")
        self.assertEqual(fetch_scoos_data.quarter_label("2026-04-01"), "2026 Q2")
        self.assertEqual(fetch_scoos_data.quarter_label("2026-07-01"), "2026 Q3")
        self.assertEqual(fetch_scoos_data.quarter_label("2026-10-01"), "2026 Q4")


class BuildSeriesEntryTests(unittest.TestCase):
    def test_builds_value_change_and_chronological_history(self):
        meta = {"id": "EXHE3C5Q59NP", "name": "하이일드 회사채"}

        with patch("fetch_scoos_data.fetch_latest_observations", side_effect=fake_fetch):
            entry = fetch_scoos_data.build_series_entry(meta, "key")

        self.assertEqual(entry["id"], "EXHE3C5Q59NP")
        self.assertEqual(entry["name"], "하이일드 회사채")
        self.assertEqual(entry["date"], "2026-07-01")
        self.assertEqual(entry["value"], -12.5)
        self.assertEqual(entry["prev_value"], 5.26)
        self.assertEqual(entry["change"], -17.76)
        # History runs oldest -> newest, the order the charts read it in.
        self.assertEqual([p["date"] for p in entry["history"]][0], "2025-10-01")
        self.assertEqual([p["date"] for p in entry["history"]][-1], "2026-07-01")

    def test_marks_series_with_no_observations_as_errored(self):
        meta = {"id": "EXHE3C5Q59NP", "name": "하이일드 회사채"}

        with patch("fetch_scoos_data.fetch_latest_observations", return_value=[]):
            entry = fetch_scoos_data.build_series_entry(meta, "key")

        self.assertEqual(entry["error"], "no data")
        self.assertNotIn("value", entry)

    def test_survives_a_failed_fetch(self):
        meta = {"id": "EXHE3C5Q59NP", "name": "하이일드 회사채"}

        with patch("fetch_scoos_data.fetch_latest_observations", side_effect=RuntimeError("boom")):
            entry = fetch_scoos_data.build_series_entry(meta, "key")

        self.assertEqual(entry["error"], "no data")


class BuildScoosDataTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("fetch_scoos_data.fetch_latest_observations", side_effect=fake_fetch)
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_covers_every_configured_series(self):
        data = fetch_scoos_data.build_scoos_data("key")

        configured = [
            meta["id"]
            for group in fetch_scoos_data.SCOOS_GROUPS
            for panel in group["panels"]
            for meta in panel["series"]
        ]
        built = [
            entry["id"]
            for group in data["groups"]
            for panel in group["panels"]
            for entry in panel["series"]
        ]
        self.assertEqual(built, configured)

    def test_reports_the_latest_quarter_across_series(self):
        data = fetch_scoos_data.build_scoos_data("key")

        self.assertEqual(data["latest_date"], "2026-07-01")
        self.assertEqual(data["latest_quarter"], "2026 Q3")
        self.assertIn("SCOOS", data["source"])

    def test_keeps_group_and_panel_titles(self):
        data = fetch_scoos_data.build_scoos_data("key")

        self.assertEqual(
            [group["title"] for group in data["groups"]],
            ["기초시장 유동성·기능 개선 응답", "자금조달 수요 증가 응답"],
        )
        self.assertTrue(all(group["description"] for group in data["groups"]))
        self.assertTrue(
            all(panel["title"] for group in data["groups"] for panel in group["panels"])
        )

    def test_panels_stay_within_the_three_colour_palette(self):
        for group in fetch_scoos_data.SCOOS_GROUPS:
            for panel in group["panels"]:
                self.assertLessEqual(
                    len(panel["series"]), 3, f"{panel['title']} has too many series"
                )

    def test_main_writes_the_json_file(self):
        test_dir = Path("/tmp/scoos_data_test_output")
        shutil.rmtree(test_dir, ignore_errors=True)

        with patch("fetch_scoos_data.OUTPUT_PATH", test_dir / "scoos.json"), \
             patch.dict("os.environ", {"FRED_API_KEY": "key"}):
            fetch_scoos_data.main()

        written = json.loads((test_dir / "scoos.json").read_text(encoding="utf-8"))
        self.assertEqual(written["latest_quarter"], "2026 Q3")
        self.assertEqual(len(written["groups"]), 2)

        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
