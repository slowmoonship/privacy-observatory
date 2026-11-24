"""Offline refresh and fallback tests using only the public checkout inputs."""
import datetime as dt
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_public_site import digest, read, validate_source
from refresh_datasets import DAILY, fetch_days, merge_audit, refresh


class RefreshTests(unittest.TestCase):
    def test_audit_revision_preserves_original_cutoff(self):
        result = merge_audit({}, ["transaction_count"], {
            "2018-04-26": {"transaction_count"}, "2027-01-01": {"transaction_count"},
        })
        self.assertEqual(result["affected_from"], "2018-04-26")
        self.assertEqual(result["sample_through_utc"], "2026-11-23")

    def test_failed_refresh_preserves_snapshot(self):
        source = ROOT / "datasets"
        before = {p: digest(p) for p in source.rglob("*") if p.is_file()}
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / "next"
            with patch("refresh_datasets.fetch_days", side_effect=TimeoutError("test outage")):
                with self.assertRaises(TimeoutError):
                    refresh(source, out, dt.date(2026, 11, 23))
            self.assertFalse(out.exists())
        self.assertEqual(before, {p: digest(p) for p in before})

    def test_paginated_source_rejects_off_host_and_noninteger(self):
        import json

        row = {"asset": "xmr", "time": "2014-04-18T00:00:00Z", "TxCnt": "1.2"}
        with patch("refresh_datasets.fetch", return_value=json.dumps({"data": [row]})):
            with self.assertRaisesRegex(ValueError, "Noninteger"):
                fetch_days("xmr", dt.date(2014, 4, 18))
        row["TxCnt"] = "1"
        with patch("refresh_datasets.fetch", return_value=json.dumps({
            "data": [row], "next_page_url": "https://example.org/unapproved",
        })):
            with self.assertRaisesRegex(ValueError, "pagination"):
                fetch_days("xmr", dt.date(2014, 4, 18))

    def test_full_refresh_revision_and_repeat_are_deterministic(self):
        source = ROOT / "datasets"
        series = {}
        for name in DAILY:
            folder = source / name
            rows, _, _ = validate_source(folder, name, read(folder / "manifest.json"))
            for row in rows:
                key = (row["asset_id"], row["date_utc"])
                series.setdefault(key, {}).update(row)
        last = max(row["date_utc"] for row in series.values())
        original = min(series)
        series[original]["transaction_count"] += 1
        with tempfile.TemporaryDirectory() as work:
            first, second = Path(work) / "first", Path(work) / "second"
            with patch("refresh_datasets.fetch_days", side_effect=lambda asset, _: [
                row for key, row in sorted(series.items()) if key[0] == asset]):
                refresh(source, first, last)
                refresh(first, second, last)
            quality = read(first / "privacy_network_daily/manifest.json")["refresh"]
            self.assertEqual(quality["revised_rows"], 1)
            self.assertEqual(quality["historical_audit"]["affected_from"], original[1].isoformat())
            for file in first.rglob("*"):
                if file.is_file():
                    self.assertEqual(digest(file), digest(second / file.relative_to(first)))
            protocol = "privacy_protocol_registry/manifest.json"
            self.assertEqual(digest(first / protocol), digest(source / protocol))


if __name__ == "__main__":
    unittest.main(verbosity=2)
