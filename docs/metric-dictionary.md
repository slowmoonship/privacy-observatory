# 指标字典与实测

以下样本来自 2026-11-24 UTC 03:54 左右的实测。PriFi 字段均相对 JSON 根 `data`；ZecStats 字段相对根。历史缺失数是整个共同日期轴上的 null，包含上市前空档；最近数据指最后非空值。PriFi 数据许可及上游限制、更新频率和 Actions 条件见[审计](source-audit.md)。

| 指标 | 接口与字段 | 样本、口径、覆盖和缺失 |
| --- | --- | --- |
| XMR、ZEC 当前市值 | PriFi summary `assets[]` 按 `symbol` 选取 `mcap`, `observedAt` | XMR 9,165,287,468.02；ZEC 12,904,436,592.69 美元；观测 2026-11-24，两个字段均非空。单时点，无历史；文件每 5 分钟。 |
| XMR 历史市值 | PriFi history `days`, `series.floatXMR` | 百万美元，2014-05-20 至 2026-11-22；末值 9058.307；4571 点中 1 null。每日 UTC。 |
| ZEC 历史市值 | 同上 `series.floatZEC` | 百万美元，2016-10-29 至 2026-11-22；末值 13475.570；4571 点中 894 null。每日 UTC。 |
| XMR 每日交易 | PriFi activity `charts.monero.days`, `series[key=tx].values` | UTC 日、不含 coinbase；2014-04-18 至 2026-11-23；末值 34099；4603 点中 0 null。小时更新；Coin Metrics。 |
| ZEC 每日交易 | PriFi activity `charts.zcash.days`, `series[key=total].values` | UTC 日、不含 coinbase；2016-10-28 至 2026-11-23；末值 5678；3679 点中 0 null。小时更新；ZecBlock 未声明数据许可，发布待确认。 |
| ZEC 涉及屏蔽池交易 | 同上 `series[key=shielded].values` | 相同日期范围、3679 点 0 null；2026-11-23 为 2431。包括混合交易，是总数子集，不代表全部交易或完全屏蔽交易。上游许可待确认。 |
| XMR 供应量 | PriFi supply `coins[id=xmr].supply.value/day/source` | 18,337,951 XMR，2026-11-23，Coin Metrics；`history.start/step/values` 每周，2014-05-26 至 2026-11-23，653 点 0 null；文件每小时。 |
| ZEC 供应量 | PriFi supply `coins[id=zec].supply.value/day/source` | 17,058,525 ZEC，2026-11-24，zeczcash.com / ZecStats；周历史 2018-10-30 至 2026-11-24，422 点 0 null。实时备选 ZecStats `supply.total` 17,058,589.54585973 ZEC；时间不同不能强求一致。 |
| ZEC 屏蔽供应及占比 | ZecStats summary `pools.shieldedTotal`, `pools.shieldedPct`, `pools.updatedAt` | 4,937,463.21708447 ZEC，28.9441468992%，2026-11-24；均非空，单时点。四屏蔽池余额之和占供应比例，非私密交易量。约两分钟刷新。 |
| ZEC 屏蔽供给历史 | PriFi history `series.shieldedZec`, `series.shieldedPct`, `days` | 2018-10-29 至 2026-11-21；末值 4,935,034 ZEC、28.937%；各 4571 点中 1625 null。每日更新。 |
| ZEC 各池历史 | ZecStats pools.csv `day`, `sprout`, `sapling`, `orchard`, `ironwood`, `height` | ZEC，UTC 每日最后一次观测；2026-07-30 至 2026-11-24 共 118 行；四池均 0 空值，`lockbox` 1 空值。末日 Sprout 12224.21094946、Sapling 417700.36874895、Orchard 319309.04651619、Ironwood 4188225.31084185；末日未结束。 |
| 协议 TVL 排行 | PriFi summary `protocols[].name/tvl/chains/counted/status/observedAt` | 美元、协议整体当前 TVL；49 项，TVL null 0；Tornado Cash 585,274,882.43，Railgun 100,910,565.47；2026-11-24。非历史排行；计入与否需显示，许可及上游权利见审计。 |
| 代表性协议 | 同上 `protocols[].chains`、`name` | Ethereum：Tornado Cash、Railgun；Solana：Privacy Cash（1,397,362.57 美元，跨链总 TVL）、Umbra Privacy。部署链为标签，不提供分链金额；同上刷新与许可。 |

说明：summary 单时点空值检查仅覆盖所列字段；不可推断历史无缺失。历史市值 USD 百万，当前市值 USD，转换时须统一。历史日期按对应非空值确定，并非承诺全时段连续。`history.days` 中最后一天各序列可能尚未更新。

## Phase 3 当前页面口径变更

为避免持久化授权未确认的 DefiLlama 实时市值，页面 `xmr_market`、`zec_market` 使用 PriFi `history.series.floatXMR/floatZEC` 最近非空日（Coin Metrics Community Data），由百万美元乘 1,000,000，标为“最近日市值”；与历史曲线末值及日期完全一致，不再声称是实时值。`zec_supply` 改为 ZecStats `supply.total`，使用池来源观测时间；XMR 供应仍为 PriFi 中明确标示 Coin Metrics 的记录。其他 Phase 1 表格是当时审计样本，不是当前页面字段配置。两币交易数现均为 Coin Metrics `TxCnt`，同一 UTC 日范围；详见[数据源审计](source-audit.md)。
