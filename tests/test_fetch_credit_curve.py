import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_credit_curve

# Daily observations run newest-first. These span just over a year so the
# "1년 전" snapshot has something to land on, and they deliberately skip the
# exact anniversary date to exercise the on-or-before lookup.
FAKE_OBSERVATIONS = {
    "BAMLC1A0C13Y": [
        {"date": "2026-11-05", "value": "0.50"},
        {"date": "2026-08-06", "value": "0.55"},
        {"date": "2025-11-04", "value": "0.60"},
    ],
    "BAMLC2A0C35Y": [
        {"date": "2026-11-05", "value": "0.70"},
        {"date": "2026-08-06", "value": "0.75"},
        {"date": "2025-11-04", "value": "0.80"},
    ],
    "BAMLC3A0C57Y": [
        {"date": "2026-11-05", "value": "0.85"},
        {"date": "2026-08-06", "value": "0.90"},
        {"date": "2025-11-04", "value": "0.95"},
    ],
    "BAMLC4A0C710Y": [
        {"date": "2026-11-05", "value": "1.00"},
        {"date": "2026-08-06", "value": "1.05"},
        {"date": "2025-11-04", "value": "1.10"},
    ],
    "BAMLC7A0C1015Y": [
        {"date": "2026-11-05", "value": "1.15"},
        {"date": "2026-08-06", "value": "1.20"},
        {"date": "2025-11-04", "value": "1.25"},
    ],
    "BAMLC8A0C15PY": [
        {"date": "2026-11-05", "value": "1.30"},
        {"date": "2026-08-06", "value": "1.35"},
        {"date": "2025-11-04", "value": "1.40"},
    ],
}


def fake_fetch(series_id, api_key, count=2):
    return FAKE_OBSERVATIONS[series_id][:count]


class ValueOnOrBeforeTests(unittest.TestCase):
    OBSERVATIONS = [
        {"date": "2026-11-05", "value": "1.23"},
        {"date": "2026-11-02", "value": "1.20"},
    ]

    def test_takes_an_exact_date_match(self):
        result = fetch_credit_curve.value_on_or_before(
            self.OBSERVATIONS, fetch_credit_curve.date.fromisoformat("2026-11-05")
        )
        self.assertEqual(result, {"date": "2026-11-05", "value": 123.0})

    def test_falls_back_to_the_nearest_earlier_observation(self):
        # A weekend target: the index only publishes on business days.
        result = fetch_credit_curve.value_on_or_before(
            self.OBSERVATIONS, fetch_credit_curve.date.fromisoformat("2026-11-04")
        )
        self.assertEqual(result, {"date": "2026-11-02", "value": 120.0})

    def test_returns_none_when_nothing_is_old_enough(self):
        result = fetch_credit_curve.value_on_or_before(
            self.OBSERVATIONS, fetch_credit_curve.date.fromisoformat("2026-01-01")
        )
        self.assertIsNone(result)

    def test_converts_percent_to_basis_points(self):
        result = fetch_credit_curve.value_on_or_before(
            [{"date": "2026-11-05", "value": "0.87"}],
            fetch_credit_curve.date.fromisoformat("2026-11-05"),
        )
        self.assertEqual(result["value"], 87.0)


class BuildCreditCurveTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("fetch_credit_curve.fetch_latest_observations", side_effect=fake_fetch)
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_builds_one_value_per_bucket_per_snapshot(self):
        data = fetch_credit_curve.build_credit_curve("key")

        self.assertEqual(data["buckets"], ["1-3년", "3-5년", "5-7년", "7-10년", "10-15년", "15년+"])
        self.assertEqual([s["name"] for s in data["snapshots"]], ["현재", "3개월 전", "1년 전"])
        for snapshot in data["snapshots"]:
            self.assertEqual(len(snapshot["values"]), len(data["buckets"]))

    def test_current_snapshot_slopes_upward_with_maturity(self):
        data = fetch_credit_curve.build_credit_curve("key")

        current = next(s for s in data["snapshots"] if s["name"] == "현재")
        self.assertEqual(current["values"], [50.0, 70.0, 85.0, 100.0, 115.0, 130.0])

    def test_year_ago_snapshot_uses_the_older_observations(self):
        data = fetch_credit_curve.build_credit_curve("key")

        year_ago = next(s for s in data["snapshots"] if s["name"] == "1년 전")
        self.assertEqual(year_ago["date"], "2025-11-04")
        self.assertEqual(year_ago["values"], [60.0, 80.0, 95.0, 110.0, 125.0, 140.0])

    def test_stays_within_the_three_colour_palette(self):
        self.assertLessEqual(len(fetch_credit_curve.SNAPSHOTS), 3)

    def test_survives_a_failed_fetch(self):
        with patch("fetch_credit_curve.fetch_latest_observations", side_effect=RuntimeError("boom")):
            data = fetch_credit_curve.build_credit_curve("key")

        self.assertIsNone(data["latest_date"])
        self.assertEqual(data["snapshots"], [])

    def test_main_writes_the_json_file(self):
        test_dir = Path("/tmp/credit_curve_test_output")
        shutil.rmtree(test_dir, ignore_errors=True)

        with patch("fetch_credit_curve.OUTPUT_PATH", test_dir / "credit_curve.json"), \
             patch.dict("os.environ", {"FRED_API_KEY": "key"}):
            fetch_credit_curve.main()

        written = json.loads((test_dir / "credit_curve.json").read_text(encoding="utf-8"))
        self.assertEqual(written["latest_date"], "2026-11-05")
        self.assertEqual(written["unit"], "bp")

        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
