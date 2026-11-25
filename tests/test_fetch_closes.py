import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import fetch_closes

# get_change() tuples: (date, open, high, low, close, prev_close, pct_change).
# Every index and holding is on the same session unless a test says otherwise.
SESSION = "2026-11-25"
INDEX_RESULTS = {
    "^GSPC": (SESSION, 0, 0, 0, 7200.0, 7100.0, 1.41),
    "^DJI": (SESSION, 0, 0, 0, 49500.0, 49000.0, 1.02),
    "^IXIC": (SESSION, 0, 0, 0, 24000.0, 23800.0, 0.84),
    "^NDX": (SESSION, 0, 0, 0, 26600.0, 26400.0, 0.76),
    "NQ=F": (SESSION, 0, 0, 0, 26650.0, 26420.0, 0.87),
    "^RUT": (SESSION, 0, 0, 0, 2670.0, 2650.0, 0.75),
    "^VIX": (SESSION, 0, 0, 0, 25.0, 28.0, -10.71),
}
HOLDING_RESULTS = {
    "NOW": (SESSION, 0, 0, 0, 92.0, 90.0, 2.22),
    "TSLA": (SESSION, 0, 0, 0, 390.0, 384.0, 1.56),
    "SPCX": (SESSION, 0, 0, 0, 145.0, 143.5, 1.05),
    "INFQ": (SESSION, 0, 0, 0, 7.7, 7.6, 1.32),
    "PL": (SESSION, 0, 0, 0, 12.2, 12.0, 1.67),
    "QCOM": (SESSION, 0, 0, 0, 162.0, 160.0, 1.25),
}


def results_with(**overrides):
    """A get_change() fake over the default results, with per-symbol
    overrides (None meaning the fetch failed). Symbols that aren't valid
    keyword names, like "^GSPC", go in via **{...}.
    """
    table = {**INDEX_RESULTS, **HOLDING_RESULTS, **overrides}
    return lambda symbol: table.get(symbol)


class FetchFastQuoteTests(unittest.TestCase):
    def fast_info(self, payload):
        ticker = MagicMock()
        ticker.fast_info = payload
        return patch("fetch_closes.yf.Ticker", return_value=ticker)

    def test_returns_last_price_and_previous_close(self):
        with self.fast_info({"last_price": 910.5, "previous_close": 902.0}):
            self.assertEqual(fetch_closes.fetch_fast_quote("NOW"), (910.5, 902.0))

    def test_returns_none_when_a_field_is_missing(self):
        with self.fast_info({"last_price": 910.5}):
            self.assertIsNone(fetch_closes.fetch_fast_quote("NOW"))

    def test_returns_none_on_a_zero_price(self):
        # A zero previous close would make the pct change blow up.
        with self.fast_info({"last_price": 910.5, "previous_close": 0}):
            self.assertIsNone(fetch_closes.fetch_fast_quote("NOW"))

    def test_returns_none_when_the_call_fails(self):
        with patch("fetch_closes.yf.Ticker", side_effect=RuntimeError("network error")):
            self.assertIsNone(fetch_closes.fetch_fast_quote("NOW"))


class ResolveCloseTests(unittest.TestCase):
    BEHIND = ("2026-11-24", 0, 0, 0, 88.0, 90.0, -2.22)

    def test_current_bar_is_used_as_is(self):
        with patch("fetch_closes.fetch_fast_quote") as quote:
            entry = fetch_closes.resolve_close("NOW", HOLDING_RESULTS["NOW"], SESSION)

        quote.assert_not_called()
        self.assertEqual(entry["date"], SESSION)
        self.assertEqual(entry["close"], 92.0)
        self.assertEqual(entry["source"], "history")
        self.assertFalse(entry["stale"])

    def test_bar_behind_the_reference_is_replaced_by_the_live_quote(self):
        with patch("fetch_closes.fetch_fast_quote", return_value=(93.0, 92.0)) as quote:
            entry = fetch_closes.resolve_close("NOW", self.BEHIND, SESSION)

        quote.assert_called_once_with("NOW")
        # Dated to the session it stands in for, and labelled as a quote.
        self.assertEqual(entry["date"], SESSION)
        self.assertEqual(entry["close"], 93.0)
        self.assertEqual(entry["prev_close"], 92.0)
        self.assertAlmostEqual(entry["pct_change"], 1.087, places=3)
        self.assertEqual(entry["source"], "fast_info")
        self.assertFalse(entry["stale"])

    def test_bar_behind_with_no_quote_is_kept_but_marked_stale(self):
        with patch("fetch_closes.fetch_fast_quote", return_value=None):
            entry = fetch_closes.resolve_close("NOW", self.BEHIND, SESSION)

        self.assertEqual(entry["date"], "2026-11-24")
        self.assertEqual(entry["close"], 88.0)
        self.assertEqual(entry["source"], "history")
        self.assertTrue(entry["stale"])

    def test_without_a_reference_nothing_is_called_stale(self):
        with patch("fetch_closes.fetch_fast_quote") as quote:
            entry = fetch_closes.resolve_close("NOW", self.BEHIND, None)

        quote.assert_not_called()
        self.assertFalse(entry["stale"])


class MergeEntryTests(unittest.TestCase):
    FRESH = {"date": SESSION, "close": 92.0, "stale": False}
    STALE = {"date": "2026-11-24", "close": 88.0, "stale": True}

    def test_a_stale_second_pass_does_not_overwrite_a_fresh_first_pass(self):
        self.assertIs(fetch_closes.merge_entry(self.FRESH, self.STALE), self.FRESH)

    def test_a_fresh_second_pass_replaces_a_stale_first_pass(self):
        self.assertIs(fetch_closes.merge_entry(self.STALE, self.FRESH), self.FRESH)

    def test_a_failed_fetch_keeps_what_is_on_disk(self):
        self.assertIs(fetch_closes.merge_entry(self.FRESH, None), self.FRESH)

    def test_a_tie_goes_to_the_newer_fetch(self):
        refetched = {**self.FRESH, "close": 92.5}
        self.assertIs(fetch_closes.merge_entry(self.FRESH, refetched), refetched)

    def test_nothing_on_either_side_stays_nothing(self):
        self.assertIsNone(fetch_closes.merge_entry(None, None))


class BuildClosesTests(unittest.TestCase):
    def build(self, get_change, previous=None, quote=None):
        with patch("fetch_closes.get_change", side_effect=get_change), \
             patch("fetch_closes.fetch_fast_quote", return_value=quote):
            return fetch_closes.build_closes(previous)

    def test_covers_every_index_and_holding(self):
        data = self.build(results_with())

        self.assertEqual(data["reference_symbol"], "^GSPC")
        self.assertEqual(data["reference_date"], SESSION)
        self.assertEqual(set(data["indices"]), set(INDEX_RESULTS))
        self.assertEqual(set(data["holdings"]), set(HOLDING_RESULTS))
        self.assertEqual(data["indices"]["^GSPC"]["name"], "S&P500")
        self.assertEqual(data["indices"]["^GSPC"]["close"], 7200.0)
        self.assertEqual(data["indices"]["^GSPC"]["prev_close"], 7100.0)
        self.assertFalse(any(h["stale"] for h in data["holdings"].values()))

    def test_holding_behind_the_index_is_retried_then_marked_stale(self):
        data = self.build(results_with(PL=("2026-11-24", 0, 0, 0, 11.8, 12.0, -1.67)))

        self.assertTrue(data["holdings"]["PL"]["stale"])
        self.assertEqual(data["holdings"]["PL"]["date"], "2026-11-24")
        self.assertFalse(data["holdings"]["NOW"]["stale"])

    def test_holding_behind_the_index_is_rescued_by_the_quote(self):
        data = self.build(
            results_with(PL=("2026-11-24", 0, 0, 0, 11.8, 12.0, -1.67)), quote=(12.3, 12.0)
        )

        self.assertFalse(data["holdings"]["PL"]["stale"])
        self.assertEqual(data["holdings"]["PL"]["source"], "fast_info")
        self.assertEqual(data["holdings"]["PL"]["date"], SESSION)
        self.assertEqual(data["holdings"]["PL"]["close"], 12.3)

    def test_second_pass_keeps_a_good_first_pass_close(self):
        first = self.build(results_with())
        # Yahoo hiccups on the second pass: PL comes back a session behind
        # and the quote fails too.
        second = self.build(
            results_with(PL=("2026-11-24", 0, 0, 0, 11.8, 12.0, -1.67)), previous=first
        )

        self.assertEqual(second["holdings"]["PL"], first["holdings"]["PL"])
        self.assertFalse(second["holdings"]["PL"]["stale"])

    def test_failed_reference_index_falls_back_to_the_previous_run(self):
        first = self.build(results_with())
        second = self.build(
            results_with(**{"^GSPC": None, "PL": ("2026-11-24", 0, 0, 0, 11.8, 12.0, -1.67)}),
            previous=first,
        )

        # ^GSPC failed this run, so the last known session still anchors the
        # staleness check instead of the check being skipped.
        self.assertEqual(second["reference_date"], SESSION)
        self.assertEqual(second["indices"]["^GSPC"], first["indices"]["^GSPC"])

    def test_carried_over_holding_goes_stale_when_the_session_moves_on(self):
        yesterday = self.build(results_with())
        next_session = "2026-11-26"
        today = {k: (next_session, *v[1:]) for k, v in INDEX_RESULTS.items()}
        # Every holding updates except PL, whose fetch fails outright.
        holdings = {k: (next_session, *v[1:]) for k, v in HOLDING_RESULTS.items()}
        holdings["PL"] = None

        data = self.build(lambda s: {**today, **holdings}.get(s), previous=yesterday)

        # Yesterday's PL entry was current for its session but is behind now.
        self.assertEqual(data["holdings"]["PL"]["date"], SESSION)
        self.assertTrue(data["holdings"]["PL"]["stale"])
        self.assertFalse(data["holdings"]["NOW"]["stale"])


class MainTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path("/tmp/closes_test_output")
        shutil.rmtree(self.dir, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = self.dir / "closes.json"

    def run_main(self, get_change):
        with patch("fetch_closes.OUTPUT_PATH", self.path), \
             patch("fetch_closes.get_change", side_effect=get_change), \
             patch("fetch_closes.fetch_fast_quote", return_value=None):
            fetch_closes.main()

    def test_writes_the_snapshot(self):
        self.run_main(results_with())

        written = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertIn("updated_at", written)
        self.assertEqual(written["reference_date"], SESSION)
        self.assertEqual(len(written["holdings"]), 6)

    def test_an_unchanged_second_pass_leaves_the_file_alone(self):
        self.run_main(results_with())
        first_text = self.path.read_text(encoding="utf-8")

        self.run_main(results_with())

        # Same prices: no rewrite, so updated_at doesn't churn and the
        # workflow has nothing to commit.
        self.assertEqual(self.path.read_text(encoding="utf-8"), first_text)

    def test_a_changed_price_is_written(self):
        self.run_main(results_with())
        self.run_main(results_with(NOW=(SESSION, 0, 0, 0, 92.5, 90.0, 2.78)))

        written = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(written["holdings"]["NOW"]["close"], 92.5)


if __name__ == "__main__":
    unittest.main()
