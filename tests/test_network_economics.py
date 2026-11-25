import datetime as dt
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import network_economics as economics

DAY = dt.date(2026, 11, 23)
NOW = dt.datetime(2026, 11, 24, 15, tzinfo=dt.timezone.utc)
RAW = dict(zip(economics.INPUTS, map(Decimal, [4, 12, 2, 3, 21, 7, 5])))


def result(rows, day=DAY):
    return dict(zip(economics.FIELDS, economics.metrics(rows, day)))


def raw_day(day):
    return {"asset": "xmr", "time": day.isoformat() + "T00:00:00Z", **dict.fromkeys(economics.INPUTS, "3")}


class EconomicsTests(unittest.TestCase):
    def test_paged_utc_rows_and_explicit_missing_day(self):
        first = DAY - dt.timedelta(days=2)
        urls = []
        next_url = economics.CM + "?next_page_token=example"
        responses = [
            {"data": [raw_day(first)], "next_page_url": next_url},
            {"data": [raw_day(DAY)]},
        ]

        def fetch(url):
            urls.append(url)
            return json.dumps(responses[len(urls) - 1])

        with patch.object(economics, "fetch", side_effect=fetch):
            rows = economics.fetch_days("xmr", first, DAY)
        self.assertEqual(set(rows), {first, DAY})
        self.assertEqual(urls[1], next_url)
        self.assertIn("frequency=1d", urls[0])

    def test_rejects_duplicate_incomplete_and_off_host_pagination(self):
        row = raw_day(DAY)
        for page, message in [
            ({"data": [row, row]}, "duplicate"),
            ({"data": [{**row, "BlkCnt": "1.5"}]}, "Non-integer"),
            ({"data": [{**row, "PriceUSD": None}]}, "complete last day"),
            ({"data": [{**row, "SplyCur": "NaN"}]}, "Invalid SplyCur"),
            ({"data": [row], "next_page_url": "https://example.org/"}, "pagination"),
        ]:
            with self.subTest(page=page), patch.object(economics, "fetch", return_value=json.dumps(page)):
                with self.assertRaisesRegex(ValueError, message):
                    economics.fetch_days("xmr", DAY, DAY)

    def test_rolling_fee_issuance_growth_and_hashrate(self):
        rows = {DAY - dt.timedelta(days=offset): {**RAW, "TxCnt": Decimal(offset + 4)}
                for offset in range(30)}
        rows[DAY - dt.timedelta(days=365)] = {"SplyCur": Decimal(20)}
        values = result(rows)
        self.assertEqual(values, {
            "tx_ma7": Decimal(7), "tx_ma30": Decimal("18.5"), "block_count": Decimal(12),
            "fee_native": Decimal(2), "fee_mean_native": Decimal("0.5"), "fee_usd": Decimal(14),
            "fee_mean_usd": Decimal("3.5"), "issuance": Decimal(3),
            "supply_growth_365d": Decimal(5), "hashrate": Decimal(5),
        })
        del rows[DAY - dt.timedelta(days=1)]
        self.assertIsNone(result(rows)["tx_ma7"])
        self.assertIsNone(result(rows)["tx_ma30"])

    def test_denominators_and_exact_calendar_offset(self):
        rows = {DAY: {**RAW, "PriceUSD": Decimal(0), "TxCnt": Decimal(0)},
                DAY - dt.timedelta(days=364): {"SplyCur": Decimal(21)}}
        values = result(rows)
        for field in ("fee_mean_native", "fee_usd", "fee_mean_usd", "supply_growth_365d"):
            self.assertIsNone(values[field])
        rows[DAY - dt.timedelta(days=365)] = {"SplyCur": Decimal(0)}
        self.assertIsNone(result(rows)["supply_growth_365d"])
        rows[DAY]["TxCnt"] = Decimal(4)
        rows[DAY]["FeeTotNtv"] = Decimal(0)
        rows[DAY]["PriceUSD"] = Decimal(1)
        self.assertEqual(result(rows)["fee_mean_usd"], Decimal(0))

    def test_production_rejects_missing_utc_day_or_disagreement(self):
        start = DAY - dt.timedelta(days=economics.DISPLAY_DAYS + economics.LOOKBACK_DAYS - 1)
        rows = dict.fromkeys(economics.days(start, DAY), RAW)
        aligned = {(asset, day): (RAW["TxCnt"], RAW["SplyCur"])
                   for asset in economics.ASSETS for day in rows}
        with patch.object(economics, "fetch_days", return_value=rows):
            self.assertEqual(economics.build(DAY, NOW, aligned)["data_as_of"], DAY.isoformat())
        missing = DAY - dt.timedelta(days=2)
        with patch.object(economics, "fetch_days", return_value={d: row for d, row in rows.items() if d != missing}):
            with self.assertRaisesRegex(ValueError, "coverage"):
                economics.build(DAY, NOW, aligned)
        aligned["xmr", DAY] = (Decimal(9), RAW["SplyCur"])
        with patch.object(economics, "fetch_days", return_value=rows):
            with self.assertRaisesRegex(ValueError, "shared inputs disagree"):
                economics.build(DAY, NOW, aligned)

    def test_stale_and_newly_missing_values_preserve_published_file(self):
        from copy import deepcopy

        data = json.loads((ROOT / "datasets" / economics.FILENAME).read_text())
        day = dt.date.fromisoformat(data["data_as_of"])
        now = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(6), dt.timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / economics.FILENAME
            path.write_text(json.dumps(data))
            before = path.read_bytes()
            with patch.object(economics, "build") as build:
                with self.assertRaisesRegex(ValueError, "most recent complete"):
                    economics.refresh(path, day, now + dt.timedelta(days=1))
                build.assert_not_called()
            degraded = deepcopy(data)
            degraded["series"]["zec"][1][3] = None
            with patch.object(economics, "build", return_value=degraded):
                with self.assertRaisesRegex(ValueError, "Coverage regressed"):
                    economics.refresh(path, day, now)
            self.assertEqual(path.read_bytes(), before)
            revised = deepcopy(data)
            original = revised["series"]["zec"][1][3]
            revised["series"]["zec"][1][3] = str(int(original) + 1)
            with patch.object(economics, "build", return_value=revised):
                self.assertTrue(economics.refresh(path, day, now))
            self.assertEqual(json.loads(path.read_text()), revised)

    def test_invalid_provenance_and_future_obs_are_rejected(self):
        data = json.loads((ROOT / "datasets" / economics.FILENAME).read_text())
        for changes in ({"source_license": "internal"}, {"fetched_at": "2020-01-01T00:00:00Z"},
                        {"restricted_input": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                economics.validate(data | changes)

    def test_no_timestamp_only_write_and_failure_preserves_snapshot(self):
        data = json.loads((ROOT / "datasets" / economics.FILENAME).read_text())
        day = dt.date.fromisoformat(data["data_as_of"])
        now = dt.datetime.fromisoformat(data["fetched_at"]) + dt.timedelta(seconds=1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / economics.FILENAME
            with patch.object(economics, "build", return_value=data):
                self.assertTrue(economics.refresh(path, day, now))
            before = path.read_bytes()
            with patch.object(economics, "build", return_value=data | {"fetched_at": now.isoformat()}):
                self.assertFalse(economics.refresh(path, day, now))
            with patch.object(economics, "build", side_effect=TimeoutError("upstream")):
                with self.assertRaises(TimeoutError):
                    economics.refresh(path, day, now)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
