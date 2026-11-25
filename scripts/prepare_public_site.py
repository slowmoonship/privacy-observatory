#!/usr/bin/env python3
"""Create and verify the allowlisted data files for the static site."""
import argparse
import datetime as dt
import hashlib
import html
import json
import re
import tempfile
from pathlib import Path
import shutil

from network_economics import FILENAME as ECONOMICS, validate as validate_economics

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".cache/public-site"
CATALOG = {
    "privacy_market_daily": dict(title="每日市值", status="Ready", summary="Monero 与 Zcash 每日美元市值。",
        method="使用 Coin Metrics CapMrktCurUSD，保留 UTC 日期、缺失与原始美元精度。网页数值经显示舍入。",
        finding="PriFi 的百万美元字段按千美元舍入可复现两个资产的共同有效日，未发现超出半档的差异。"),
    "privacy_network_daily": dict(title="每日网络活动", status="Ready with limitations",
        summary="两链非 Coinbase 交易数及 Coin Metrics 当前供应量。",
        method="TxCnt 使用完整 UTC 日。SplyCur 是 Coin Metrics 的当前供应量。ZEC 的 SplyCur 与含 Lockbox 的 Zcash 全链发行供应不可直接比较。",
        finding="XMR 交易数与 PriFi 共同日期全等。ZEC 交易数存在来源差异。2018-04-26 和 2026-11-23 的两组结果可由不同 UTC 时间归桶复现，其余 3,530 个差异日未逐日归因。"),
    "privacy_protocol_registry": dict(title="隐私协议目录", status="Ready",
        summary="当前网页所列协议的主网部署记录。",
        method="每行对应一个协议及一条链，按核验日期整理官方主网地址、角色、机制和资产类型。",
        finding="主网部署的角色和官方出处逐行列出。Base 的 ScopeLift Umbra 和 Solana 的 Umbra Privacy 为不同项目。目录只记录核验范围内的部署事实。"),
    "zcash_value_pools_daily": dict(title="Zcash 每日价值池", status="Blocked",
        summary="ZecStats 来源的每日价值池和全链供应观测。",
        method="以 UTC 日为粒度。屏蔽余额包含 Sprout、Sapling、Orchard 和 Ironwood。Lockbox 单独核算。",
        finding="五个源记录的六池余额合计与同行供应不一致。少量观测的报告高度与余额匹配候选块不同；缺少源时间或唯一块身份时保留未知。上游再分发权待确认，数据暂未开放。"),
}
COIN = {"name": "Coin Metrics Community Data", "url": "https://github.com/coinmetrics/data#license",
        "license": "CC BY-NC 4.0（限非商业）", "license_url": "https://creativecommons.org/licenses/by-nc/4.0/"}
POOL = {"name": "ZecStats", "url": "https://zecstats.org/data", "license": "来源声明 CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/"}
PROTOCOLS = {"name": "各协议官方部署资料", "url": "https://docs.railgun.org/wiki/learn/helpful-links",
             "license": "部署事实整理，原文与代码适用各自条款", "license_url": None}
COIN_INPUT = {"publisher": COIN["name"], "license": "CC-BY-NC-4.0",
              "url": "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"}
DAILY_KEYS = ("date_utc", "asset_id", "is_complete_utc_day")
EXPECTED_COLUMNS = {
    "privacy_market_daily": {*DAILY_KEYS, "market_cap_usd"},
    "privacy_network_daily": {*DAILY_KEYS, "transaction_count", "current_supply_native"},
    "privacy_protocol_registry": {
        "protocol_id", "protocol_name", "chain_id", "chain_name", "privacy_mechanism",
        "deployment_role", "deployment_address", "website_url", "deployment_source_url",
        "mechanism_source_url", "supported_assets", "verified_utc",
    },
}
PROTOCOL_DEPLOYMENTS = {
    ("railgun", "eip155:1"), ("railgun", "eip155:56"), ("railgun", "eip155:137"),
    ("railgun", "eip155:42161"), ("privacy-pools", "eip155:1"),
    ("privacy-cash", "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"),
    ("privacy-pools", "eip155:56"),
    ("tornado-cash", "eip155:1"), ("tornado-cash", "eip155:56"),
    ("tornado-cash", "eip155:42161"), ("tornado-cash", "eip155:10"),
    ("scopelift-umbra", "eip155:8453"),
    ("umbra-privacy", "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"),
}
PROTOCOL_OFFICIAL = {"docs.railgun.org", "docs.privacypools.com", "github.com",
                     "docs.umbraprivacy.com", "docs.nimbusprivacy.xyz", "www.umbraprivacy.com"}
POOL_STATUS_FILE = "zcash-pool-status.json"
POOL_STATUS = {"status": "unavailable", "reason": "当前快照的公开展示和低频生产访问授权待确认。"}
DOCUMENTS = ("schema.json", "methodology.html", "quality_report.html", "manifest.json")
SUPPORT = {f"datasets/{name}" for name in ("index.json", "chart-data.json", ECONOMICS, POOL_STATUS_FILE)}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def public_files():
    return SUPPORT | {
        f"datasets/{name}/{filename}"
        for name, policy in CATALOG.items() for filename in DOCUMENTS + (
            (f"{name}.csv", f"{name}.parquet") if policy["status"] != "Blocked" else ())
    }


def validate_source(folder, name, manifest):
    import pyarrow as pa
    import pyarrow.csv as csv
    import pyarrow.parquet as parquet

    schema_file = read(folder / "schema.json")
    for filename in ("schema.json", f"{name}.csv", f"{name}.parquet"):
        if digest(folder / filename) != manifest["files"][filename]:
            raise ValueError(f"Input hash mismatch: {name}/{filename}")
    binary = parquet.read_table(folder / f"{name}.parquet")
    binary.validate(full=True)
    schema = binary.schema
    if set(schema.names) != EXPECTED_COLUMNS[name]:
        raise ValueError(f"Unexpected columns: {name}")
    expected_keys = ["asset_id", "date_utc"] if "asset_id" in schema.names else ["protocol_id", "chain_id"]
    if schema_file["primary_key"] != expected_keys:
        raise ValueError(f"Unexpected primary key definition: {name}")
    if [(f.name, str(f.type), f.nullable) for f in schema] != [
        (f["name"], f["type"], f["nullable"]) for f in schema_file["fields"]
    ]:
        raise ValueError(f"Schema mismatch: {name}")
    textual = csv.read_csv(folder / f"{name}.csv", convert_options=csv.ConvertOptions(
        column_types=schema, strings_can_be_null=True, null_values=[""]))
    if not textual.cast(schema).equals(binary) or binary.num_rows != manifest["rows"]:
        raise ValueError(f"CSV/Parquet mismatch: {name}")
    rows = binary.to_pylist()
    keys = [tuple(r[k] for k in schema_file["primary_key"]) for r in rows]
    if not rows or any(None in key for key in keys) or len(set(keys)) != len(keys):
        raise ValueError(f"Invalid primary key: {name}")
    if any(binary[f.name].null_count for f in schema if not f.nullable):
        raise ValueError(f"Missing required value: {name}")
    if "asset_id" in schema.names and {r["asset_id"] for r in rows} != {"xmr", "zec"}:
        raise ValueError(f"Unexpected asset coverage: {name}")
    if name == "privacy_protocol_registry":
        from urllib.parse import urlsplit

        if set(keys) != PROTOCOL_DEPLOYMENTS or any(
                urlsplit(row[k] or "").scheme != "https"
                or urlsplit(row[k] or "").netloc not in PROTOCOL_OFFICIAL
                for row in rows for k in ("deployment_source_url", "mechanism_source_url")):
            raise ValueError("Unapproved protocol registry scope or source")
        for row in rows:
            date = dt.date.fromisoformat(row["verified_utc"])
            address_pattern = (r"0x[a-fA-F0-9]{40}" if row["chain_id"].startswith("eip155:")
                               else r"[1-9A-HJ-NP-Za-km-z]{32,44}")
            if (date > dt.datetime.now(dt.timezone.utc).date() or
                not re.fullmatch(address_pattern, row["deployment_address"] or "") or
                not row["privacy_mechanism"] or not row["deployment_role"] or not row["supported_assets"] or
                urlsplit(row["website_url"]).scheme != "https" or not urlsplit(row["website_url"]).hostname):
                raise ValueError("Incomplete protocol deployment")
    expected_types = {
        "market_cap_usd": pa.decimal128(38, 27), "current_supply_native": pa.decimal128(24, 12),
        "transaction_count": pa.int64(),
    }
    for key, dtype in expected_types.items():
        if key in schema.names and (schema.field(key).type != dtype or
                any(r[key] is not None and r[key] < 0 for r in rows)):
            raise ValueError(f"Invalid metric: {name}/{key}")
    return rows, schema_file, {f.name: binary[f.name].null_count for f in schema}


def coverage(rows, fields):
    result = {}
    if not rows or "date_utc" not in rows[0]:
        return result
    for asset in ("xmr", "zec"):
        sub = [r for r in rows if r["asset_id"] == asset]
        days = sorted(r["date_utc"] for r in sub)
        if not days or (days[-1] - days[0]).days + 1 != len(days) or not all(
                r["is_complete_utc_day"] for r in sub):
            raise ValueError(f"Incomplete or discontinuous audit coverage: {asset}")
        values = {}
        for field in fields:
            valid = sorted(r["date_utc"] for r in sub if r[field] is not None)
            if not valid:
                raise ValueError(f"All values missing: {asset}/{field}")
            values[field] = {"start": str(valid[0]), "end": str(valid[-1]), "null_rows": len(sub) - len(valid)}
        result[asset] = {"start": str(days[0]), "end": str(days[-1]), "rows": len(days), "valid": values}
    return result


def html_document(path, title, paragraphs, details):
    tags = "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)
    table = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(str(v))}</dd>" for k, v in details.items())
    path.write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="UTF-8"><meta name="viewport" content="width=device-width">'
        f'<title>{html.escape(title)}</title><body><main><h1>{html.escape(title)}</h1>{tags}<dl>{table}</dl>'
        '<p><a href="../../#datasets">返回数据集目录</a></p></main></body></html>\n', encoding="utf-8")


def chart_rows(rows, fields):
    result = {}
    for asset in ("xmr", "zec"):
        sub = sorted((r for r in rows if r["asset_id"] == asset), key=lambda r: r["date_utc"])
        result[asset] = {
            name: [[str(r["date_utc"]), str(r[name]) if r[name] is not None else None] for r in sub]
            for name in fields
        }
    return result


def emit(source, target):
    parent = target / "datasets"
    parent.mkdir(parents=True)
    index, chart = [], {}
    for name, policy in CATALOG.items():
        origin = source / name
        manifest = read(origin / "manifest.json")
        qualification = manifest["release_qualification"]
        if qualification["status"] != policy["status"] or manifest["dataset"] != name:
            raise ValueError(f"Unexpected release qualification: {name}")
        dt.date.fromisoformat(qualification["assessed_utc"])
        if not (re.fullmatch(r"0\.2\.0(?:-phase[0-9]+)?", manifest["version"]) or
                (name == "privacy_protocol_registry" and manifest["version"] == "1.0.0")):
            raise ValueError(f"Unexpected dataset version: {name}")
        dest = parent / name
        dest.mkdir()
        files = {}
        if name == "zcash_value_pools_daily":
            period = manifest["coverage"]["zec"]
            for key in ("start", "end"):
                dt.date.fromisoformat(period[key])
            spans = {"zec": {key: period[key] for key in ("start", "end", "rows")}}
            attribution = POOL
            grain = "每个 UTC 日一个来源快照"
            write(dest / "schema.json", {"dataset": name, "grain": grain, "status": "Blocked",
                                          "scope": policy["summary"]})
            quality = {"公开下载": "暂未开放", "审计范围": "来源内部一致性和抽样区块时间"}
        else:
            rows, schema, nulls = validate_source(origin, name, manifest)
            fields = tuple(k for k in ("market_cap_usd", "transaction_count", "current_supply_native") if k in rows[0])
            spans = coverage(rows, fields)
            attribution = COIN if fields else PROTOCOLS
            sources = manifest["sources"]
            if fields and not (isinstance(sources, list) and len(sources) == 1
                               and all(sources[0].get(k) == v for k, v in COIN_INPUT.items())):
                raise ValueError(f"Unexpected upstream source or license: {name}")
            grain = schema["grain"]
            for extension in ("csv", "parquet"):
                filename = f"{name}.{extension}"
                shutil.copyfile(origin / filename, dest / filename)
                files[extension] = filename
            # Select public schema keys; retain no Phase 2 filesystem or evidence references.
            write(dest / "schema.json", {k: schema[k] for k in ("primary_key", "grain", "csv", "fields")})
            quality = {"检查": "主键唯一、必填非空、CSV 与 Parquet 全表一致",
                       "行数": len(rows), "各列空值": "，".join(f"{k} {v}" for k, v in nulls.items())}
            chart[name] = chart_rows(rows, fields) if fields else rows
        updated = max(span["end"] for span in spans.values()) if spans else qualification["assessed_utc"]
        item = {"id": name, "title": policy["title"], "summary": policy["summary"], "grain": grain,
                "status": policy["status"], "limitations": policy["finding"], "source": attribution,
                "version": manifest["version"], "rows": manifest["rows"], "coverage": spans,
                "updated": updated, "assessed_utc": qualification["assessed_utc"],
                "downloads": files, "documents": dict(zip(("schema", "methodology", "quality", "manifest"), DOCUMENTS))}
        html_document(dest / "methodology.html", policy["title"] + " · 统计口径",
                      [policy["method"], "整理方式为字段筛选、规范化与类型转换。"],
                      {"来源": attribution["name"], "来源链接": attribution["url"], "许可": attribution["license"]})
        findings = [policy["finding"]]
        refresh = manifest.get("refresh")
        if name in ("privacy_market_daily", "privacy_network_daily") and refresh:
            item["refresh"] = refresh
            quality.update({"数据观测截至（UTC）": refresh["observed_through_utc"],
                            "最后一次有变化的刷新新增行": refresh["new_rows"],
                            "最后一次有变化的刷新修订行": refresh["revised_rows"]})
            audit = refresh["historical_audit"]
            findings.append(f"历史专项审计 {audit['evidence_version']}，样本截至 {audit['sample_through_utc']} UTC。"
                            "日更只执行动态质量检查，专项审计未重跑。")
            if audit["affected_from"]:
                findings.append(f"审计样本期内曾修订 {audit['affected_from']} 至 {audit['affected_through']}。"
                                "旧专项结论仅适用于原审计快照。")
        if spans and name != "zcash_value_pools_daily":
            quality["UTC 日覆盖"] = "；".join(f"{asset.upper()} {span['start']} 至 {span['end']}"
                                            for asset, span in spans.items())
        if name == "privacy_network_daily":
            findings.append("两个样本均按块高排序，每块交易总数减一，再分别用块头时间与当前块加前 10 块的"
                            "时间中位数归入 UTC 日。两日完整抽样高度分别为 312492–313113 和 3601562–3605064。")
        html_document(dest / "quality_report.html", policy["title"] + " · 质量报告", findings, quality)
        write(dest / "manifest.json", item | {"files": {p.name: digest(p) for p in sorted(dest.iterdir())}})
        index.append(item)
    write(parent / "index.json", index)
    write(parent / "chart-data.json", chart)
    economics_path = source / ECONOMICS
    if economics_path.is_symlink():
        raise ValueError("Symlink in economics inputs")
    economics = validate_economics(read(economics_path))
    # Emit the checked object, never a directory of research inputs or fixtures.
    (parent / ECONOMICS).write_text(json.dumps(economics, ensure_ascii=False, separators=(",", ":")) + "\n",
                                    encoding="utf-8")
    write(parent / POOL_STATUS_FILE, POOL_STATUS)


def verify_dist(dist):
    paths = {p.relative_to(dist).as_posix() for p in dist.rglob("*") if p.is_file() or p.is_symlink()}
    approved = public_files()
    if any(p.is_symlink() for p in dist.rglob("*")):
        raise ValueError("Symlink in public artifact")
    assets = paths - approved - {"index.html"}
    page = dist / "index.html"
    references = set(re.findall(r'(?:src|href)="[^"]*?(assets/index-[\w-]+\.(?:js|css))"', page.read_text())) if page.is_file() else set()
    if not approved <= paths or assets != references or len(assets) != 2 or not all(
            any(path.endswith(extension) for path in assets) for extension in (".js", ".css")):
        raise ValueError(f"Unexpected or missing public paths: {sorted(assets)}")
    for path in approved:
        candidate = dist / path
        if candidate.is_symlink() or digest(candidate) != digest(STAGE / path):
            raise ValueError(f"Unexpected public content: {path}")
    for name in CATALOG:
        folder = dist / "datasets" / name
        manifest = read(folder / "manifest.json")
        if manifest["files"] != {p.name: digest(p) for p in sorted(folder.iterdir()) if p.name != "manifest.json"}:
            raise ValueError(f"Invalid public manifest: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "datasets")
    parser.add_argument("--verify-dist", type=Path)
    args = parser.parse_args()
    if args.verify_dist:
        verify_dist(args.verify_dist)
        return
    STAGE.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=STAGE.parent) as scratch:
        stage = Path(scratch) / "site"
        emit(args.source, stage)
        if {p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()} != public_files():
            raise ValueError("Generated files differ from allowlist")
        if STAGE.exists():
            shutil.rmtree(STAGE)
        stage.rename(STAGE)


if __name__ == "__main__":
    main()
