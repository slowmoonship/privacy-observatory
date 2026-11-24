#!/usr/bin/env python3
"""Refresh two full Coin Metrics histories into a separate, validated site input tree."""
import argparse
import csv
import datetime as dt
import json
import re
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import pyarrow as pa
import pyarrow.parquet as pq

from prepare_public_site import ROOT, coverage, digest, emit, read, validate_source, write
from update_data import CM, fetch

ASSETS = ("xmr", "zec")
START = {"xmr": dt.date(2014, 4, 18), "zec": dt.date(2016, 10, 28)}
METRICS = {"CapMrktCurUSD": "market_cap_usd", "TxCnt": "transaction_count", "SplyCur": "current_supply_native"}
DAILY = {
    "privacy_market_daily": ("market_cap_usd",),
    "privacy_network_daily": ("transaction_count", "current_supply_native"),
}
VERSION = "0.2.0"
AUDIT_DATE = "2026-11-24"
AUDIT_END = "2026-11-23"


def fetch_days(asset, end):
    url = CM + "?" + urlencode(dict(assets=asset, metrics=",".join(METRICS), frequency="1d",
        start_time=START[asset].isoformat(), end_time=end.isoformat(), page_size=1000))
    seen = set()
    rows = []
    while url:
        if url in seen or len(seen) >= 32 or urlsplit(url)._replace(query="").geturl() != CM:
            raise ValueError("Unexpected Coin Metrics pagination link")
        seen.add(url)
        response = json.loads(fetch(url))
        page = response["data"]
        if not page:
            raise ValueError(f"Empty Coin Metrics page: {asset}")
        for raw in page:
            if raw["asset"] != asset or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T00:00:00(?:\.0+)?Z", raw["time"]):
                raise ValueError(f"Invalid Coin Metrics identity or UTC date: {asset}")
            day = dt.date.fromisoformat(raw["time"][:10])
            row = dict(asset_id=asset, date_utc=day, is_complete_utc_day=True)
            for key, field in METRICS.items():
                value = raw.get(key)
                if value is None:
                    row[field] = None
                elif not isinstance(value, str):
                    raise ValueError(f"Non-text value in {asset}/{key} on {day}")
                elif key == "TxCnt":
                    if not re.fullmatch(r"[0-9]+", value):
                        raise ValueError(f"Noninteger TxCnt in {asset} on {day}")
                    row[field] = int(value)
                else:
                    number = Decimal(value)
                    if not number.is_finite() or number < 0:
                        raise ValueError(f"Invalid amount in {asset}/{key} on {day}")
                    row[field] = number
            rows.append(row)
        url = response.get("next_page_url")
    rows.sort(key=lambda row: row["date_utc"])
    dates = [r["date_utc"] for r in rows]
    expected = [START[asset] + dt.timedelta(days=i) for i in range((end - START[asset]).days + 1)]
    if dates != expected or any(rows[-1][field] is None for field in METRICS.values()):
        raise ValueError(f"Incomplete Coin Metrics history for {asset}: need complete through {end}, received through "
                         f"{dates[-1] if dates else 'none'}")
    print(f"source=Coin Metrics Community Data asset={asset} pages={len(seen)} rows={len(rows)} "
          f"coverage={dates[0]}..{dates[-1]}", flush=True)
    return rows


def merge_audit(old, fields, revised):
    prior = old.get("refresh", {}).get("historical_audit", {})
    dates = sorted({day for day, field_names in revised.items()
                    if day <= AUDIT_END and set(field_names) & set(fields)})
    first = min([dates[0]] + [prior["affected_from"]] if prior.get("affected_from") else dates) if dates else prior.get("affected_from")
    last = max([dates[-1]] + [prior["affected_through"]] if prior.get("affected_through") else dates) if dates else prior.get("affected_through")
    return {"assessed_utc": AUDIT_DATE, "sample_through_utc": AUDIT_END, "evidence_version": "phase2-2026-11-24",
            "affected_from": first, "affected_through": last,
            "status": "historical_values_revised_not_reaudited" if first else "original_scope_not_reaudited"}


def refresh_table(folder, name, incoming, end):
    manifest_file = folder / "manifest.json"
    manifest = read(manifest_file)
    old, _, _ = validate_source(folder, name, manifest)
    csv_path, parquet_path = (folder / f"{name}.{ext}" for ext in ("csv", "parquet"))
    schema = pq.read_schema(parquet_path)
    rows = [{key: row[key] for key in schema.names} for row in incoming]
    table = pa.Table.from_pylist(rows, schema=schema)
    if rows != table.to_pylist():
        raise ValueError(f"Loss of precision: {name}")
    new_by_key = {(r["asset_id"], r["date_utc"]): r for r in rows}
    fields = DAILY[name]
    revised = {}
    revised_row_count = 0
    for row in old:
        key = (row["asset_id"], row["date_utc"])
        current = new_by_key.get(key)
        if current is None or any(row[f] is not None and current[f] is None for f in fields):
            raise ValueError(f"Coverage regressed: {name} {key}")
        changed = {f for f in fields if row[f] != current[f]}
        if changed:
            revised.setdefault(key[1].isoformat(), set()).update(changed)
            revised_row_count += 1
    if old == rows and manifest["version"] == VERSION and "refresh" in manifest:
        print(f"dataset={name} unchanged; persisted observation date={manifest['refresh']['observed_through_utc']}")
        return
    if old != rows:
        with csv_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, schema.names, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        pq.write_table(table, parquet_path, compression="zstd", compression_level=3, version="2.6")
    dates = sorted(revised)
    manifest.update(version=VERSION, rows=len(rows), coverage=coverage(rows, fields), refresh={
        "observed_through_utc": end.isoformat(),
        "new_rows": len(rows) - len(old),
        "revised_rows": revised_row_count,
        "revision_first_utc": dates[0] if dates else None,
        "revision_last_utc": dates[-1] if dates else None,
        "historical_audit": merge_audit(manifest, fields, revised),
    })
    manifest["files"].update({p.name: digest(p) for p in (csv_path, parquet_path)})
    write(manifest_file, manifest)
    validate_source(folder, name, manifest)
    print(f"dataset={name} rows={len(rows)} new_rows={len(rows) - len(old)} revised_rows={revised_row_count} "
          f"revision_first={dates[0] if dates else '-'} revision_last={dates[-1] if dates else '-'}")


def refresh(source, destination, end):
    if destination.exists():
        raise ValueError("Output must be a new directory")
    for name in DAILY:
        old = read(source / name / "manifest.json")
        dates = [old["coverage"][asset]["end"] for asset in ASSETS]
        print(f"retained snapshot {name}: XMR={dates[0]} ZEC={dates[1]}", flush=True)
    incoming = [row for asset in ASSETS for row in fetch_days(asset, end)]
    with tempfile.TemporaryDirectory(dir=destination.parent) as scratch:
        stage = Path(scratch) / "inputs"
        shutil.copytree(source, stage)
        for name in DAILY:
            refresh_table(stage / name, name, incoming, end)
        emit(stage, Path(scratch) / "verify")
        stage.rename(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "datasets")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    end = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    try:
        refresh(args.source, args.output, end)
    except Exception as exc:
        raise SystemExit(f"Coin Metrics refresh/publication rejected for {end}. Previous complete inputs retained. {exc}") from exc


if __name__ == "__main__":
    main()
