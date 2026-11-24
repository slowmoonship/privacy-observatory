# SlowMoonShip Privacy Observatory

中文优先的隐私资产数据观察站。重点为 Monero 与 Zcash，隐私协议作为辅助。

- 网站：[slowmoonship.github.io/privacy-observatory/](https://slowmoonship.github.io/privacy-observatory/)
- [数据源审计与许可](docs/source-audit.md)
- [指标字典和实测样本](docs/metric-dictionary.md)
- [V0.1 范围与下一阶段计划](docs/v0.1-scope.md)

用 Python 3 标准库运行 `python3 scripts/probe_sources.py`；每行输出一个 JSON，包含请求状态、UTC 时间、关键指标覆盖和空值。网络或解析失败时继续检查其余端点并以非零状态退出。不保存原始响应，结果会随来源变化。

数据归各来源所有，PriFi.info 为 CC BY-NC 4.0，ZecStats 为 CC BY 4.0；上游个别来源未声明许可，发布前须处理文档中标出的权限问题。研究信息不构成投资建议。

## Phase 2 本地运行

本地页面已实现 XMR/ZEC 对比、真实历史图、Zcash 屏蔽池与辅助协议目录。数据由 PriFi、Coin Metrics Community Data 和 ZecStats 提供，详见审计及页面说明。PriFi/Coin Metrics 数据仅限非商业使用。

```bash
npm ci
python3 scripts/update_data.py
npm run dev
```

在浏览器打开终端打印的 `http://127.0.0.1:5173/`。数据文件已附带当时的实测快照，单个来源请求或校验失败时对应文件保持上次成功版本，脚本返回非零；页面按真实观测时间提示可能过期。`npm run build` 可验证生产构建。浏览器验收见 [验收报告](docs/acceptance/report.md)。每日自动更新与 GitHub Pages 由同一工作流处理；见 [数据更新与故障处理](docs/data-operations.md)、[Phase 3 验收](docs/phase3-acceptance.md)和 [Pages 发布指南](docs/pages-release.md)。

## 数据与统计口径

- [PriFi.info](https://prifi.info/data/) 的 XMR、ZEC 日度市值来自 Coin Metrics Community Data；原始单位为百万美元，本项目转换为美元。页面展示最近可用日，而非实时市值。XMR 供应量采用 PriFi 标明来自 Coin Metrics 的数值。
- [Coin Metrics Community Data](https://docs.coinmetrics.io/network-data/network-data-overview/transactions/transactions) 的 `TxCnt` 是按 UTC 日统计、不含 Coinbase 的链上网络交易数，并非支付次数或用户数；两资产使用相同日期范围。
- [ZecStats](https://zecstats.org/data) 的 ZEC 供应、屏蔽池余额和占比为第三方观测；池历史空值保留为空。具体数据时间、覆盖与局限见页面及[指标字典](docs/metric-dictionary.md)。

## 许可与署名

本项目代码许可证尚未选定；第三方数据许可不构成对项目代码的开源授权。请勿将本段视作代码许可证。

- Data: [PriFi.info](https://prifi.info/data/)，[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)；按 PriFi 要求同时标明原始来源。
- Source: [Coin Metrics Community Data](https://docs.coinmetrics.io/)，[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)。
- Data: [ZecStats](https://zecstats.org)，[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。

本项目筛选数据、转换市值单位并整理为静态 JSON。PriFi 与 Coin Metrics 数据仅限非商业用途；数据源各自的条款及上游权利仍然适用。协议 TVL 的再分发授权尚未确认，页面不展示该数据。完整来源、修改和限制见[数据源审计](docs/source-audit.md)。

## 版本规划

- V0.1：基于成熟来源的中文静态观察站；自动更新与发布尚待线上验收及授权。
- V0.2：补齐 V0.1 对应的开放数据集、方法、口径与下载。
- V1.0：扩展网页指标和功能。
- V1.1：补齐 V1.0 新增数据集。
