#!/usr/bin/env python3
"""Refresh the bounded display snapshot from Coin Metrics Community Data."""

import argparse
import datetime as dt
import json
import re
import tempfile
from decimal import Decimal, localcontext
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from update_data import CM, fetch

ASSETS = ("xmr", "zec")
DISPLAY_DAYS = 1095
LOOKBACK_DAYS = 365
INPUTS = ("TxCnt", "BlkCnt", "FeeTotNtv", "IssTotNtv", "SplyCur", "PriceUSD", "HashRate")
FIELDS = (
    "tx_ma7", "tx_ma30", "block_count", "fee_native", "fee_mean_native",
    "fee_usd", "fee_mean_usd", "issuance", "supply_growth_365d", "hashrate",
)
FILENAME = "network-economics.json"
METADATA = {
    "source": "Coin Metrics Community Data",
    "source_url": CM,
    "source_license": "CC BY-NC 4.0",
    "license_url": "https://creativecommons.org/licenses/by-nc/4.0/",
    "calculation_version": "1",
    "inputs": {
        "tx_ma7": ["TxCnt"], "tx_ma30": ["TxCnt"], "block_count": ["BlkCnt"],
        "fee_native": ["FeeTotNtv"], "fee_mean_native": ["FeeTotNtv", "TxCnt"],
        "fee_usd": ["FeeTotNtv", "PriceUSD"], "fee_mean_usd": ["FeeTotNtv", "PriceUSD", "TxCnt"],
        "issuance": ["IssTotNtv"], "supply_growth_365d": ["SplyCur"], "hashrate": ["HashRate"],
    },
    "methodology": {
        "tx_ma7": "连续 7 个完整 UTC 日的 TxCnt 算术平均，含当日。窗口缺一天即为空。",
        "tx_ma30": "连续 30 个完整 UTC 日的 TxCnt 算术平均，含当日。窗口缺一天即为空。",
        "block_count": "UTC 日主链区块数（BlkCnt）。Zcash NU7 自 2026-11-06 起将目标间隔从 75 秒改为 25 秒。",
        "fee_native": "FeeTotNtv，UTC 日支付的手续费总额，包含按协议移出流通的部分。",
        "fee_mean_native": "FeeTotNtv ÷ TxCnt，以同日非 coinbase 网络交易数推算；包含零费交易。零交易日或输入缺失时为空。",
        "fee_usd": "FeeTotNtv × PriceUSD。使用当日结束时的 UTC 参考价；价格非正或输入缺失时为空。",
        "fee_mean_usd": "FeeTotNtv × PriceUSD ÷ TxCnt。按 UTC 日收盘参考价和网络交易数推算，零交易日、价格非正或输入缺失时为空。",
        "issuance": "IssTotNtv，来源定义的当日总发行量，涵盖协议分配。ZEC 的矿工实得收入范围更窄。",
        "supply_growth_365d": "100 ×（当日 SplyCur ÷ 365 个自然日前的 SplyCur − 1），缺少准确对应日或分母非正时为空。",
        "hashrate": "Coin Metrics 日均算力估计。XMR 为 H/s，ZEC 为 GSol/s，仅用于各链自身历史。ZEC 的 NU7 切换日对不同估计方法较敏感。",
    },
}
NUMBER = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")
UTC_DAY = re.compile(r"\d{4}-\d{2}-\d{2}T00:00:00(?:\.0+)?Z")


def days(start, end):
    return [start + dt.timedelta(days=offset) for offset in range((end - start).days + 1)]


def source_url(asset, start, end):
    return CM + "?" + urlencode(dict(assets=asset, metrics=",".join(INPUTS), frequency="1d",
                                     start_time=start, end_time=end, page_size=500))


def fetch_days(asset, start, end):
    url = source_url(asset, start, end)
    seen, rows = set(), {}
    while url:
        if url in seen or len(seen) >= 8 or urlsplit(url)._replace(query="").geturl() != CM:
            raise ValueError("Unexpected Coin Metrics pagination link")
        seen.add(url)
        page = json.loads(fetch(url))
        if not page["data"]:
            raise ValueError(f"Empty Coin Metrics page for {asset}")
        for raw in page["data"]:
            if raw["asset"] != asset or not UTC_DAY.fullmatch(raw["time"]):
                raise ValueError(f"Unexpected asset or UTC day for {asset}")
            day = dt.date.fromisoformat(raw["time"][:10])
            if not start <= day <= end or day in rows:
                raise ValueError(f"Unexpected or duplicate day: {asset}/{day}")
            row = {}
            for key in INPUTS:
                value = raw[key]
                if value is not None and (not isinstance(value, str) or len(value) > 64
                                          or not NUMBER.fullmatch(value) or Decimal(value) < 0):
                    raise ValueError(f"Invalid {key} at {asset}/{day}")
                if value is not None and key in ("TxCnt", "BlkCnt") and not value.isdecimal():
                    raise ValueError(f"Non-integer {key} at {asset}/{day}")
                row[key] = Decimal(value) if value is not None else None
            rows[day] = row
        url = page.get("next_page_url")
    if start not in rows or end not in rows or any(rows[end][field] is None for field in INPUTS):
        raise ValueError(f"Coin Metrics did not provide both boundaries and a complete last day for {asset}")
    print(f"{asset}: {len(seen)} pages, {len(rows)}/{(end - start).days + 1} UTC asset-days", flush=True)
    return rows


def divide(numerator, denominator):
    return numerator / denominator if numerator is not None and denominator is not None and denominator > 0 else None


def metrics(rows, day):
    row = rows.get(day, {})
    def rolling(length):
        values = [rows.get(day - dt.timedelta(days=i), {}).get("TxCnt") for i in range(length)]
        return sum(values) / length if all(value is not None for value in values) else None

    with localcontext() as ctx:
        ctx.prec = 24
        fee, tx, price = (row.get(key) for key in ("FeeTotNtv", "TxCnt", "PriceUSD"))
        usd = fee * price if fee is not None and price is not None and price > 0 else None
        base = rows.get(day - dt.timedelta(days=365), {}).get("SplyCur")
        growth = divide(row.get("SplyCur"), base)
        return (rolling(7), rolling(30), row.get("BlkCnt"), fee, divide(fee, tx),
                usd, divide(usd, tx), row.get("IssTotNtv"),
                (growth - 1) * 100 if growth is not None else None,
                row.get("HashRate"))


def build(end, now, network=None):
    start = end - dt.timedelta(days=DISPLAY_DAYS - 1)
    input_start = start - dt.timedelta(days=LOOKBACK_DAYS)
    series = {}
    for asset in ASSETS:
        raw = fetch_days(asset, input_start, end)
        if network is not None:
            for day in days(input_start, end):
                observation = raw.get(day)
                published = network.get((asset, day))
                if observation is None or published is None or (
                    observation["TxCnt"], observation["SplyCur"]
                ) != published:
                    raise ValueError(f"Daily coverage or shared inputs disagree: {asset}/{day}")
        series[asset] = [
            [day.isoformat(), *(None if value is None else format(value, "f") for value in metrics(raw, day))]
            for day in days(start, end)
        ]
    return {**METADATA, "data_as_of": end.isoformat(), "coverage_start": start.isoformat(),
            "coverage_end": end.isoformat(), "fetched_at": now.isoformat(), "data_status": "available",
            "columns": list(FIELDS), "series": series}


def validate(data):
    keys = set(METADATA) | {"data_as_of", "coverage_start", "coverage_end", "fetched_at",
                            "data_status", "columns", "series"}
    if set(data) != keys or any(data[k] != value for k, value in METADATA.items()):
        raise ValueError("Unexpected economics provenance or metadata")
    start, end = (dt.date.fromisoformat(data[k]) for k in ("coverage_start", "coverage_end"))
    fetched = dt.datetime.fromisoformat(data["fetched_at"])
    if fetched.utcoffset() != dt.timedelta(0) or end >= fetched.date() or data["data_as_of"] != end.isoformat():
        raise ValueError("Invalid economics timestamps")
    if (end - start).days + 1 != DISPLAY_DAYS or data["columns"] != list(FIELDS) or \
            set(data["series"]) != set(ASSETS) or data["data_status"] != "available":
        raise ValueError("Invalid economics scope")
    expected = [day.isoformat() for day in days(start, end)]
    for asset, rows in data["series"].items():
        if [r[0] for r in rows] != expected:
            raise ValueError(f"Invalid economics dates for {asset}")
        for row in rows:
            if len(row) != len(FIELDS) + 1:
                raise ValueError(f"Invalid economics row for {asset}")
            for field, value in zip(FIELDS, row[1:]):
                if value is not None and (not isinstance(value, str) or len(value) > 64
                                          or not NUMBER.fullmatch(value) or
                                          (Decimal(value) < 0 and field != "supply_growth_365d") or
                                          (field == "block_count" and not value.isdecimal())):
                    raise ValueError(f"Invalid {field} value")
                if row is rows[-1] and value is None:
                    raise ValueError(f"Missing latest display value: {asset}/{field}")
    return data


def refresh(path, end, now=None, *, network=None):
    now = (now or dt.datetime.now(dt.timezone.utc)).replace(microsecond=0)
    if now.utcoffset() != dt.timedelta(0) or end != now.date() - dt.timedelta(days=1):
        raise ValueError("Economics refresh requires the most recent complete UTC day")
    current = validate(build(end, now, network) if network is not None else build(end, now))
    if current["data_as_of"] != end.isoformat():
        raise ValueError("Economics observations do not reach the requested UTC cutoff")
    if path.exists():
        previous = validate(json.loads(path.read_text()))
        if previous["data_as_of"] > current["data_as_of"]:
            raise ValueError("Snapshot would move backwards")
        for asset in ASSETS:
            retained = {r[0]: r[1:] for r in current["series"][asset]}
            revised = []
            for date, *values in previous["series"][asset]:
                if date not in retained:
                    continue
                new_values = retained[date]
                if any(old is not None and new is None for old, new in zip(values, new_values)):
                    raise ValueError(f"Coverage regressed: {asset}/{date}")
                if values != new_values:
                    revised.append(date)
            print(f"economics {asset}: {len(revised)} revised overlapping days"
                  + (f" ({revised[0]}..{revised[-1]})" if revised else ""))
        if current | {"fetched_at": previous["fetched_at"]} == previous:
            return False
    with tempfile.TemporaryDirectory(dir=path.parent) as scratch:
        staged = Path(scratch) / path.name
        staged.write_text(json.dumps(current, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        staged.replace(path)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "datasets" / FILENAME)
    args = parser.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    try:
        changed = refresh(args.output, now.date() - dt.timedelta(days=1), now)
    except Exception as exc:
        raise SystemExit(f"Economics refresh rejected; prior snapshot retained. {exc}") from exc
    print("Economics snapshot updated." if changed else "Economics snapshot unchanged.")


if __name__ == "__main__":
    main()
