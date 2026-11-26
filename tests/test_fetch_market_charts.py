import json
import shutil
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import fetch_market_charts as mc

TODAY = date(2026, 11, 26)
START = date(2026, 5, 27)


def points(*pairs):
    return dict(pairs)


class VxTermStructureTests(unittest.TestCase):
    # Four monthly contracts; settles are made up but distinct per contract so
    # a mis-roll shows up as the wrong number.
    CONTRACTS = [
        ("2026-10-21", "a.csv"),
        ("2026-11-18", "b.csv"),
        ("2026-12-16", "c.csv"),
        ("2027-01-20", "d.csv"),
    ]
    SETTLES = {
        "2026-10-21": {"2026-10-20": 20.0},
        "2026-11-18": {"2026-10-20": 21.0, "2026-11-17": 24.7, "2026-11-18": 24.9},
        "2026-12-16": {"2026-10-20": 22.0, "2026-11-17": 22.7, "2026-11-18": 23.0},
        "2027-01-20": {"2026-11-17": 22.6, "2026-11-18": 22.8},
    }

    def build(self):
        return mc.build_vx_term_structure(self.CONTRACTS, self.SETTLES, START)

    def test_front_month_is_the_nearest_unexpired_contract(self):
        series, _ = self.build()

        self.assertEqual(series["VX1"]["2026-10-20"], 20.0)
        self.assertEqual(series["VX2"]["2026-10-20"], 21.0)
        self.assertEqual(series["VX3"]["2026-10-20"], 22.0)
        self.assertEqual(series["VX1"]["2026-11-17"], 24.7)

    def test_rolls_on_expiry_day(self):
        series, _ = self.build()

        # The Nov contract settles on the morning of 11/18, so that day the
        # Dec contract is already the front month.
        self.assertEqual(series["VX1"]["2026-11-18"], 23.0)
        self.assertEqual(series["VX2"]["2026-11-18"], 22.8)
        self.assertNotIn("2026-11-18", series["VX3"])

    def test_reports_each_ranks_latest_contract(self):
        _, expiry = self.build()

        self.assertEqual(expiry["VX1"], "2026-12-16")
        self.assertEqual(expiry["VX2"], "2027-01-20")

    def test_ignores_trade_dates_before_the_window(self):
        series, _ = mc.build_vx_term_structure(self.CONTRACTS, self.SETTLES, date(2026, 11, 1))

        self.assertNotIn("2026-10-20", series["VX1"])


class LatestSummaryTests(unittest.TestCase):
    def test_pct_change(self):
        latest = mc.latest_summary(
            {"change": "pct"}, points(("2026-11-24", 100.0), ("2026-11-25", 98.0)), {}
        )
        self.assertEqual(latest["date"], "2026-11-25")
        self.assertEqual(latest["value"], 98.0)
        self.assertEqual(latest["change"], -2.0)

    def test_bp_change_for_rates(self):
        latest = mc.latest_summary(
            {"change": "bp"}, points(("2026-11-24", 4.92), ("2026-11-25", 4.905)), {}
        )
        self.assertAlmostEqual(latest["change"], -1.5)

    def test_abs_change(self):
        latest = mc.latest_summary(
            {"change": "abs"}, points(("2026-11-24", -0.36), ("2026-11-25", -0.33)), {}
        )
        self.assertAlmostEqual(latest["change"], 0.03)

    def test_single_point_has_no_change(self):
        latest = mc.latest_summary({"change": "pct"}, points(("2026-11-25", 1.0)), {})
        self.assertIsNone(latest["change"])

    def test_no_points_is_none(self):
        self.assertIsNone(mc.latest_summary({"change": "pct"}, {}, {}))

    def test_target_range_display(self):
        raw = {"DFEDTARL": points(("2026-11-25", 3.75))}
        latest = mc.latest_summary(
            {"change": "bp", "range_lower": "DFEDTARL"}, points(("2026-11-25", 4.0)), raw
        )
        self.assertEqual(latest["display"], "3.75~4.00%")


class CardStatusTests(unittest.TestCase):
    def test_rates_normal(self):
        status = mc.card_status("rates", {"T10Y2Y": {"value": 0.24}, "T10Y3M": {"value": 0.51}})
        self.assertEqual(status["level"], "normal")
        self.assertIn("역전 아님", status["text"])
        self.assertIn("+0.24%p", status["text"])

    def test_rates_inverted(self):
        status = mc.card_status("rates", {"T10Y2Y": {"value": -0.1}, "T10Y3M": {"value": 0.5}})
        self.assertEqual(status["level"], "warning")
        self.assertIn("역전", status["text"])

    def test_vix_backwardation_from_ratio(self):
        status = mc.card_status("vix", {"VIX/VIX3M": {"value": 1.076}, "F2-F1": {"value": 0.2}})
        self.assertEqual(status["level"], "warning")
        self.assertIn("백워데이션", status["text"])

    def test_vix_backwardation_from_futures(self):
        status = mc.card_status("vix", {"VIX/VIX3M": {"value": 0.9}, "F2-F1": {"value": -0.33}})
        self.assertEqual(status["level"], "warning")

    def test_vix_contango(self):
        status = mc.card_status("vix", {"VIX/VIX3M": {"value": 0.88}, "F2-F1": {"value": 1.2}})
        self.assertEqual(status["level"], "normal")
        self.assertIn("콘탱고", status["text"])

    def test_cards_without_thresholds_have_no_status(self):
        self.assertIsNone(mc.card_status("equity", {}))


def fake_yahoo(symbol, start):
    if symbol == "^KS11":
        # A Korean holiday the US market doesn't share, and vice versa.
        return points(("2026-11-24", 4700.0), ("2026-11-26", 4726.5))
    if symbol == "^VIX":
        return points(("2026-11-24", 26.6), ("2026-11-25", 28.29))
    if symbol == "^VIX3M":
        return points(("2026-11-24", 26.0), ("2026-11-25", 26.29))
    return points(("2026-11-24", 100.0), ("2026-11-25", 101.0))


def fake_fred(series_id, api_key, start):
    values = {"T10Y2Y": 0.24, "T10Y3M": 0.51, "DFEDTARU": 4.0, "DFEDTARL": 3.75}
    v = values.get(series_id, 2.0)
    return points(("2026-11-24", v), ("2026-11-25", v))


def fake_vx(start, today):
    series = {
        "VX1": points(("2026-11-24", 24.0), ("2026-11-25", 23.98)),
        "VX2": points(("2026-11-24", 23.6), ("2026-11-25", 23.64)),
        "VX3": points(("2026-11-24", 23.5), ("2026-11-25", 23.52)),
    }
    return series, {"VX1": "2026-12-16", "VX2": "2027-01-20", "VX3": "2027-02-17"}


class BuildMarketChartsTests(unittest.TestCase):
    def build(self, **overrides):
        with patch("fetch_market_charts.fetch_yahoo", side_effect=overrides.get("yahoo", fake_yahoo)), \
             patch("fetch_market_charts.fetch_fred", side_effect=overrides.get("fred", fake_fred)), \
             patch("fetch_market_charts.fetch_vx", side_effect=overrides.get("vx", fake_vx)):
            return mc.build_market_charts("key", today=TODAY)

    def card(self, data, card_id):
        return next(c for c in data["cards"] if c["id"] == card_id)

    def test_builds_all_seven_cards_in_order(self):
        data = self.build()

        self.assertEqual(
            [c["id"] for c in data["cards"]],
            ["equity", "fx", "oil", "rates", "vix", "credit", "bond_etf"],
        )
        self.assertEqual(data["window_start"], "2026-05-27")

    def test_values_align_on_the_union_of_dates(self):
        equity = self.card(self.build(), "equity")

        self.assertEqual(equity["dates"], ["2026-11-24", "2026-11-25", "2026-11-26"])
        kospi = equity["panels"][0]["series"][0]
        ndx = equity["panels"][0]["series"][3]
        self.assertEqual(kospi["values"], [4700.0, None, 4726.5])
        self.assertEqual(ndx["values"], [100.0, 101.0, None])

    def test_every_series_carries_display_metadata(self):
        for card in self.build()["cards"]:
            for panel in card["panels"]:
                self.assertIn(panel["mode"], ("rebased", "minmax", "level"))
                for s in panel["series"]:
                    self.assertEqual(len(s["values"]), len(card["dates"]))
                    self.assertIn(s["change"], ("pct", "bp", "abs"))
                    self.assertIsNotNone(s["latest"], s["key"])

    def test_derived_vix_series(self):
        vix = self.card(self.build(), "vix")
        ratio = vix["panels"][1]["series"][0]
        spread = vix["panels"][2]["series"][0]

        self.assertAlmostEqual(ratio["latest"]["value"], 28.29 / 26.29, places=3)
        self.assertAlmostEqual(spread["latest"]["value"], 23.64 - 23.98, places=4)
        self.assertEqual(vix["status"]["level"], "warning")

    def test_futures_are_labelled_with_their_expiry(self):
        vix = self.card(self.build(), "vix")
        f1 = vix["panels"][0]["series"][2]

        self.assertEqual(f1["latest"]["note"], "2026-12-16 만기")

    def test_fed_funds_shows_the_target_range(self):
        rates = self.card(self.build(), "rates")
        fed = rates["panels"][0]["series"][0]

        self.assertEqual(fed["latest"]["display"], "3.75~4.00%")
        self.assertEqual(rates["status"]["level"], "normal")

    def test_panel_defaults(self):
        data = self.build()

        self.assertTrue(self.card(data, "equity")["panels"][0]["include_zero"])
        self.assertFalse(self.card(data, "vix")["panels"][0]["include_zero"])
        self.assertEqual(self.card(data, "vix")["panels"][1]["ref_line"], 1)
        self.assertEqual(self.card(data, "rates")["panels"][1]["size"], "sub")

    def test_a_failed_source_leaves_its_series_empty_not_the_card(self):
        def flaky_yahoo(symbol, start):
            return {} if symbol == "^N225" else fake_yahoo(symbol, start)

        equity = self.card(self.build(yahoo=flaky_yahoo), "equity")
        nikkei = equity["panels"][0]["series"][1]

        self.assertIsNone(nikkei["latest"])
        self.assertTrue(all(v is None for v in nikkei["values"]))
        self.assertIsNotNone(equity["panels"][0]["series"][0]["latest"])

    def test_no_futures_still_builds_the_vix_card(self):
        vix = self.card(self.build(vx=lambda start, today: ({}, {})), "vix")

        self.assertIsNone(vix["panels"][0]["series"][2]["latest"])
        # Status falls back to the ratio alone.
        self.assertIn("VIX/VIX3M", vix["status"]["text"])
        self.assertNotIn("F2−F1", vix["status"]["text"])

    def test_shared_series_are_fetched_once(self):
        with patch("fetch_market_charts.fetch_yahoo", side_effect=fake_yahoo) as yahoo, \
             patch("fetch_market_charts.fetch_fred", side_effect=fake_fred), \
             patch("fetch_market_charts.fetch_vx", side_effect=fake_vx):
            mc.build_market_charts("key", today=TODAY)

        ndx_calls = [c for c in yahoo.call_args_list if c.args[0] == "^NDX"]
        self.assertEqual(len(ndx_calls), 1)

    def test_main_writes_the_file(self):
        out = Path("/tmp/market_charts_test_output")
        shutil.rmtree(out, ignore_errors=True)
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)

        with patch("fetch_market_charts.OUTPUT_PATH", out / "market_charts.json"), \
             patch.dict("os.environ", {"FRED_API_KEY": "key"}), \
             patch("fetch_market_charts.fetch_yahoo", side_effect=fake_yahoo), \
             patch("fetch_market_charts.fetch_fred", side_effect=fake_fred), \
             patch("fetch_market_charts.fetch_vx", side_effect=fake_vx):
            mc.main()

        written = json.loads((out / "market_charts.json").read_text(encoding="utf-8"))
        self.assertEqual(len(written["cards"]), 7)


if __name__ == "__main__":
    unittest.main()
