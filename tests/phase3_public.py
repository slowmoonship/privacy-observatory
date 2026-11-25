"""Public snapshot checks. Run explicitly with the pinned PyArrow dependency."""
import argparse
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

import pyarrow as pa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from export_public_inputs import export
from prepare_public_site import CATALOG, PROTOCOL_DEPLOYMENTS, POOL_STATUS, POOL_STATUS_FILE, emit, read, validate_source, verify_dist

ARGS = None


class PublicSiteTests(unittest.TestCase):
    def test_artifact_and_chart_projection(self):
        verify_dist(ARGS.dist)
        release = ARGS.dist / "datasets"
        chart = read(release / "chart-data.json")
        catalog = {item["id"]: item for item in read(release / "index.json")}
        self.assertEqual(set(catalog), set(CATALOG))
        for name, policy in CATALOG.items():
            item = catalog[name]
            folder = release / name
            self.assertEqual(item["status"], policy["status"])
            if policy["status"] == "Blocked":
                self.assertFalse(item["downloads"])
                self.assertNotIn(name, chart)
                continue
            rows, _, _ = validate_source(folder, name, read(folder / "manifest.json"))
            self.assertEqual(item["rows"], len(rows))
            if name == "privacy_protocol_registry":
                self.assertEqual(len(rows), len(PROTOCOL_DEPLOYMENTS))
                self.assertIn("零知识", (folder / f"{name}.csv").read_text(encoding="utf-8"))
                self.assertEqual(chart[name], rows)
                continue
            for asset, metrics in chart[name].items():
                subset = sorted((r for r in rows if r["asset_id"] == asset), key=lambda r: r["date_utc"])
                for metric, points in metrics.items():
                    self.assertEqual(points, [[str(r["date_utc"]), str(r[metric]) if r[metric] is not None else None]
                                              for r in subset])
                    self.assertEqual(item["coverage"][asset]["valid"][metric]["end"],
                                     [day for day, v in points if v is not None][-1])
                if "transaction_count" in metrics:
                    self.assertTrue(all(type(r["transaction_count"]) is int for r in subset))

    def test_public_pool_status_does_not_contain_any_observations(self):
        self.assertEqual(read(ARGS.dist / "datasets" / POOL_STATUS_FILE), POOL_STATUS)
        with tempfile.TemporaryDirectory() as scratch:
            source = Path(scratch) / "inputs"
            shutil.copytree(ROOT / "datasets", source)
            (source / POOL_STATUS_FILE).write_text('{"status":"available","chain_supply_zat":"1"}')
            (source / "restricted-evidence.json").write_text('{"restricted":true}')
            tree = Path(scratch) / "public"
            emit(source, tree)
            self.assertEqual(read(tree / "datasets" / POOL_STATUS_FILE), POOL_STATUS)
            self.assertFalse((tree / "datasets/restricted-evidence.json").exists())

    def test_no_internal_inputs_needed_for_repeat(self):
        with tempfile.TemporaryDirectory() as scratch:
            parent = Path(scratch)
            inputs, out = parent / "clean-inputs", parent / "generated"
            export(ARGS.dist, inputs)
            self.assertEqual([p.name for p in (inputs / "zcash_value_pools_daily").iterdir()], ["manifest.json"])
            emit(inputs, out)
            for p in out.rglob("*"):
                if p.is_file():
                    self.assertEqual(p.read_bytes(), (ARGS.dist / p.relative_to(out)).read_bytes())

    def test_rejects_extra_file_and_edited_manifest_member(self):
        with tempfile.TemporaryDirectory() as scratch:
            artifact = Path(scratch) / "artifact"
            shutil.copytree(ARGS.dist, artifact)
            extra = artifact / "data/pools.json"
            extra.parent.mkdir()
            extra.write_text("{}")
            with self.assertRaisesRegex(ValueError, "Unexpected or missing"):
                verify_dist(artifact)
            extra.unlink()
            candidate = artifact / "datasets/index.json"
            candidate.write_text("[]")
            with self.assertRaisesRegex(ValueError, "Unexpected public content"):
                verify_dist(artifact)

    def test_actual_browser_downloads(self):
        if ARGS.downloads is None:
            self.skipTest("Pass --downloads after running the browser tests")
        for view in ("desktop", "mobile"):
            for name, policy in CATALOG.items():
                if policy["status"] == "Blocked":
                    continue
                manifest = read(ARGS.dist / "datasets" / name / "manifest.json")
                with tempfile.TemporaryDirectory() as scratch:
                    folder = Path(scratch)
                    for filename in (f"{name}.csv", f"{name}.parquet", "schema.json"):
                        origin = (ARGS.downloads / view if filename != "schema.json" else
                                  ARGS.dist / "datasets" / name) / filename
                        (folder / filename).write_bytes(origin.read_bytes())
                    rows, schema, nulls = validate_source(folder, name, manifest)
                self.assertEqual(len(rows), manifest["rows"])
                if name == "privacy_market_daily":
                    market = next(field for field in schema["fields"] if field["name"] == "market_cap_usd")
                    self.assertEqual(market["type"], str(pa.decimal128(38, 27)))
                    self.assertTrue(nulls["market_cap_usd"] > 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--downloads", type=Path)
    ARGS = parser.parse_args()
    unittest.main(argv=[sys.argv[0]], verbosity=2)
