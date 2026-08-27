"""Offline tests for the option-chain parser and the retry/priming logic."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from collector.nse_client import IST, LEG_FIELDS, NSEClient, NSEError, parse_chain
from tests.sample_payload import build_payload


class ParseChainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = build_payload()
        self.rows = parse_chain(self.payload, "BANKNIFTY")

    def test_row_count_accounts_for_every_leg(self) -> None:
        # 3 expiries x 61 strikes x 2 sides, minus the 2 dropped legs per expiry.
        self.assertEqual(len(self.rows), 3 * (61 * 2 - 2))

    def test_all_expiries_kept(self) -> None:
        self.assertEqual(
            {r["expiry_date"] for r in self.rows},
            {"30-Sep-2026", "28-Oct-2026", "25-Nov-2026"},
        )

    def test_full_strike_range_kept_not_just_atm(self) -> None:
        strikes = {r["strike_price"] for r in self.rows}
        self.assertEqual(len(strikes), 61)
        self.assertEqual(max(strikes) - min(strikes), 6000)

    def test_every_leg_field_present(self) -> None:
        for field in LEG_FIELDS:
            self.assertIn(field, self.rows[0], f"missing {field}")

    def test_metadata_columns(self) -> None:
        row = self.rows[0]
        self.assertEqual(row["symbol"], "BANKNIFTY")
        self.assertEqual(row["nse_timestamp"], "27-Aug-2026 14:30:01")
        self.assertEqual(row["spot"], 54321.45)
        self.assertIn(row["option_type"], ("CE", "PE"))

    def test_collected_at_is_ist_aware(self) -> None:
        ts = self.rows[0]["collected_at_ist"]
        self.assertIsNotNone(ts.tzinfo)
        self.assertEqual(ts.utcoffset().total_seconds(), 5.5 * 3600)

    def test_explicit_collection_time_is_used(self) -> None:
        when = datetime(2026, 8, 27, 14, 30, tzinfo=IST)
        rows = parse_chain(self.payload, "BANKNIFTY", collected_at=when)
        self.assertTrue(all(r["collected_at_ist"] == when for r in rows))

    def test_strike_with_one_side_only_yields_one_row(self) -> None:
        lowest = min(r["strike_price"] for r in self.rows)
        sides = [r["option_type"] for r in self.rows
                 if r["strike_price"] == lowest and r["expiry_date"] == "30-Sep-2026"]
        self.assertEqual(sides, ["PE"])

    def test_empty_payload_raises(self) -> None:
        with self.assertRaises(NSEError):
            parse_chain({"records": {"data": []}}, "BANKNIFTY")

    def test_dataframe_round_trips_through_parquet(self) -> None:
        import pandas as pd
        import tempfile

        df = pd.DataFrame(self.rows)
        with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
            df.to_parquet(tmp.name, compression="snappy", index=False)
            back = pd.read_parquet(tmp.name)
        self.assertEqual(len(back), len(df))
        self.assertEqual(list(back.columns), list(df.columns))
        self.assertEqual(back["collected_at_ist"].iloc[0], df["collected_at_ist"].iloc[0])


def _response(status: int, json_body=None, raise_json: bool = False):
    resp = mock.Mock()
    resp.status_code = status
    if raise_json:
        resp.json.side_effect = ValueError("Expecting value")
    else:
        resp.json.return_value = json_body
    return resp


class FetchRetryTests(unittest.TestCase):
    """The network is mocked; only our retry/priming behaviour is under test."""

    def setUp(self) -> None:
        patcher = mock.patch("collector.nse_client.time.sleep")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _client(self) -> NSEClient:
        client = NSEClient(max_attempts=3)
        client.prime = mock.Mock(side_effect=lambda: setattr(client, "session", mock.Mock()))
        return client

    def test_success_first_try(self) -> None:
        client = self._client()
        client.prime()
        client.session.get.return_value = _response(200, build_payload())
        payload = client.fetch_raw("BANKNIFTY")
        self.assertEqual(payload["records"]["underlyingValue"], 54321.45)

    def test_403_triggers_reprime_then_succeeds(self) -> None:
        client = self._client()
        client.prime()
        first_session = client.session
        first_session.get.return_value = _response(403)

        def reprime():
            new = mock.Mock()
            new.get.return_value = _response(200, build_payload())
            client.session = new

        client.prime = mock.Mock(side_effect=reprime)
        payload = client.fetch_raw("BANKNIFTY")
        self.assertTrue(payload["records"]["data"])
        client.prime.assert_called()

    def test_gives_up_after_max_attempts(self) -> None:
        client = self._client()
        client.prime()
        client.session.get.return_value = _response(429)
        with self.assertRaises(NSEError) as ctx:
            client.fetch_raw("BANKNIFTY")
        self.assertIn("after 3 attempts", str(ctx.exception))

    def test_html_block_page_is_not_mistaken_for_data(self) -> None:
        client = self._client()
        client.prime()
        client.session.get.return_value = _response(200, raise_json=True)
        with self.assertRaises(NSEError):
            client.fetch_raw("BANKNIFTY")

    def test_empty_chain_is_reported_not_silently_returned(self) -> None:
        client = self._client()
        client.prime()
        client.session.get.return_value = _response(200, {"records": {"data": []}})
        with self.assertRaises(NSEError):
            client.fetch_raw("BANKNIFTY")

    def test_network_error_is_retried(self) -> None:
        client = self._client()
        calls = {"n": 0}

        def reprime():
            session = mock.Mock()
            calls["n"] += 1
            if calls["n"] == 1:
                session.get.side_effect = requests.ConnectionError("boom")
            else:
                session.get.return_value = _response(200, build_payload())
            client.session = session

        client.prime = mock.Mock(side_effect=reprime)
        payload = client.fetch_raw("BANKNIFTY")
        self.assertTrue(payload["records"]["data"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
