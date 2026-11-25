#!/usr/bin/env python3
"""Write a clean build-input tree from the validated public artifact."""
import argparse
import shutil
from pathlib import Path

from prepare_public_site import CATALOG, COIN_INPUT, ECONOMICS, digest, read, verify_dist, write


def export(dist, output):
    verify_dist(dist)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(dist / "datasets" / ECONOMICS, output / ECONOMICS)
    for name, policy in CATALOG.items():
        public = dist / "datasets" / name
        entry = read(public / "manifest.json")
        target = output / name
        target.mkdir()
        manifest = {
            "dataset": name, "version": entry["version"], "rows": entry["rows"], "coverage": entry["coverage"],
            "release_qualification": {"status": entry["status"], "assessed_utc": entry["assessed_utc"]},
        }
        if policy["status"] != "Blocked":
            files = (f"{name}.csv", f"{name}.parquet", "schema.json")
            for filename in files:
                shutil.copyfile(public / filename, target / filename)
            manifest["files"] = {filename: digest(target / filename) for filename in files}
            manifest["sources"] = [] if name == "privacy_protocol_registry" else [COIN_INPUT]
        if "refresh" in entry:
            manifest["refresh"] = entry["refresh"]
        write(target / "manifest.json", manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path)
    parser.add_argument("output", type=Path, help="new directory for clean inputs")
    args = parser.parse_args()
    export(args.dist, args.output)
