# 数据源审计

验证日期：2026-11-24，UTC 03:54–03:57；时间和数值为当时快照，不表示当前值。使用 Python 标准库与 curl 实际 GET；脚本复测结果如下，六项均成功，无请求失败。大小为该次响应字节数。

| 来源 | HTTP | 类型 | 大小 |
| --- | --- | --- | ---: |
| [PriFi summary](https://prifi.info/api/v1/summary) | 200 | application/json | 61017 |
| [PriFi history](https://prifi.info/api/v1/history) | 200 | application/json | 464867 |
| [PriFi activity](https://prifi.info/api/v1/activity) | 200 | application/json | 293898 |
| [PriFi supply](https://prifi.info/api/v1/supply) | 200 | application/json | 57676 |
| [ZecStats summary](https://zecstats.org/api/zec/summary) | 200 | application/json | 46200 |
| [ZecStats pools.csv](https://zecstats.org/api/zec/pools.csv) | 200 | text/csv | 15883 |

## 更新、许可和自动化

[PriFi API 文档](https://prifi.info/api/)：免密，summary 每 5 分钟、history 每日 01:20 UTC 后、activity 和 supply 每小时更新。`modifiedAt` 是文件改写时间，不等于每项数据观测时间；依据各数据的时间检查新鲜度。API 支持缓存验证；每日 Actions 请求量技术上适合。字段随版本变更，须检查类型、长度、时间和空值，失败时阻止发布虚假新数据。

[PriFi 数据条款和来源](https://prifi.info/data/)将其文件标为 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)，要求非商业使用、署名、链接许可、标明修改；开放源代码并不自动意味着非商业。来源包括 Coin Metrics Community Data（CC BY-NC 4.0）、DefiLlama 和 ZecStats。尤其 [PriFi 活动方法](https://prifi.info/activity/)说明 ZEC 交易数来自 ZecBlock，后者没有声明数据许可；PriFi 文件的总括许可并不能消除对上游权利的疑问。ZEC 交易历史在确认授权或找到许可明确的替代来源前，不建议再分发；DefiLlama 数据的上游许可及权利范围也应在发布前核实，不能仅凭聚合网站标签断定。XMR 交易数据源为 Coin Metrics，仍受非商业限制。

[ZecStats API](https://zecstats.org/api/)与[数据说明](https://zecstats.org/data)声明 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)，允许使用、改编和再分发，包括商业用途；须署名、链接许可、注明修改。建议展示 `Data: ZecStats (https://zecstats.org), CC BY 4.0` 并链接许可。summary 约两分钟刷新，CSV 每 UTC 日一行、缓存一小时；允许每日自动化，使用可识别 User-Agent，遵循缓存及 429 退避。summary 要检查 `sources.pools.ok`、`stale`、`fetchedAt`，并保留缺失为 null。文档声明数据来自 CipherScan 和站点存储；上游权利适用范围仍应在商业或大规模再分发前核实。

## 数据质量与解释

历史全轴有早于资产或数据源覆盖期的 null；不是零。池 CSV 118 行，日期 2026-07-30 至 2026-11-24；`lockbox` 有 1 个空值，其他列无空值；当天是未完成日，后续可能变化。实时池数据 `sources.pools.ok=true, stale=false`，但这是单次结果。历史价格/市值、现货市值、供应量可能来自不同上游和时间点，不应强制相等。

[交易方法](https://prifi.info/activity/)称两链的每日总数都排除 coinbase，以 UTC 日计，原则上可比较交易数量，但来源不同、分类细节未完全一致；例如 2026-11-21 ZEC 总数 ZecBlock 与 Coin Metrics 相差 3 笔。ZEC shielded 包括混合交易，不等于完全私密交易；各池计数可能重叠，不可相加。单笔交易不等于一个人或一笔付款，也不能用总交易数比较私密使用量。

TVL 排行只能按协议整体排序并展示部署链标签。`chains` 是部署集合，`tvl` 是协议总值，不是各链金额；不得复制到每条链求和。TVL 也可能与其他协议资产重复计算，例如 PriFi 对 Zama 的注释。协议入选和状态沿用 PriFi 定义，显示 `counted` 和是否包含 Tornado Cash，不能称为全行业完整排名。

## Phase 2 补充核验（2026-11-24）

- [Coin Metrics Community API](https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=zec%2Cxmr&metrics=TxCnt&frequency=1d&start_time=2026-08-01&page_size=10000) 实测返回 230 条 XMR/ZEC 每日记录，2026-08-01 至 2026-11-23，无分页；其中 ZEC 2026-11-23 为 5667。正式采集最近一年，按资产分别检验覆盖范围。字段 `data[].asset/time/TxCnt`，数值由字符串转为非负数。[Coin Metrics 官方文档](https://github.com/coinmetrics/product-docs/blob/master/docs/access-our-data/api/README.md)说明社区数据免费用于非商业用途；[PriFi 活动方法](https://prifi.info/activity/)注明 Coin Metrics Community Data 为 CC BY-NC 4.0，XMR TxCnt 排除 coinbase，ZEC TxCnt 用作总交易交叉检查。ZEC 样本与 ZecBlock 的 5678 有 11 笔差异，不应声称完全一致。该方案不提供已验证的涉及屏蔽组件或完全屏蔽数。
- [Zcash 节点 RPC 文档](https://zcash.github.io/rpc/)可读取区块，但没有现成每日历史聚合，搭建节点和全历史计算超出本阶段；[Google BigQuery 公共数据](https://cloud.google.com/blog/products/data-analytics/introducing-six-new-cryptocurrencies-in-bigquery-public-datasets-and-how-to-analyze-them)列出 Zcash 数据集，但本阶段未验证访问权限、最新覆盖及再分发条款。两者没有被当作已验证替代源。
- [PriFi 数据条款](https://prifi.info/data/)给予其文件 CC BY-NC 4.0；其 TVL 上游为 DefiLlama。[DefiLlama 服务条款](https://defillama.com/terms)描述个人非商业访问许可，未找到足以确认本项目公开再分发 TVL 的明确授权。故暂不显示 TVL；目录采用 PriFi 协议描述及链接，仅作为非商业引用，链名称是已确认的部署示例，不是完整清单。[Railgun](https://prifi.info/protocols/railgun/)、[Privacy Pools](https://prifi.info/protocols/privacy-pools/)、[Privacy Cash](https://prifi.info/protocols/privacy-cash/) 的来源和官方站点可复核。

## Phase 3 授权链条复核（2026-11-24）

[PriFi 的数据说明](https://prifi.info/data/)明确指出：历史市值来自 Coin Metrics Community Data，`floatXMR` 和 `floatZEC` 的单位是百万美元；实时市值来自 DefiLlama，且上游各自保留自己的条款。此前的实时市值及 PriFi ZEC 供应引用链不能仅凭 PriFi 文件许可视为无限公开再分发。本阶段不再持久化这两项：卡片改用同一历史序列的最近日市值，ZEC 供应改用 ZecStats `supply.total`。日市值乘以 1,000,000 转换为 USD；卡片与曲线均为 USD，日期为实际最近非空日。XMR 供应仅接受 PriFi 声明为 Coin Metrics 的记录，来源变化则拒绝更新。

非商业站点可依据 PriFi 与 Coin Metrics Community Data 的 CC BY-NC 4.0 发布这些经转换的数据，须署名、链接许可并说明修改；ZecStats 数据按其 CC BY 4.0 条款署名及说明修改。前述许可不能扩展到其他上游或商业用途。DefiLlama TVL 仍不展示；协议目录仅为 PriFi 研究的非商业摘录，并标注来源。发布前应复核各条款是否变更；本记录不是对所有上游权利的无限授权。

[Coin Metrics TxCnt 官方定义](https://docs.coinmetrics.io/network-data/network-data-overview/transactions/transactions)是记录在链上的交易数，排除协议产生的 coinbase，不等于支付次数或用户数。XMR 与 ZEC 的 `activity` 采用相同日期窗口，并在验证时要求覆盖首尾一致；中间缺日保留 null。CSV 池余额空白保留 null。`data_as_of` 是来源统计时间，`fetched_at` 是抓取时间，两者不能互换。
