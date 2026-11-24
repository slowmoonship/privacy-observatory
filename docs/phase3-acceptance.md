# Phase 3 本地验收

2026-11-24。此记录仅代表本地验证；GitHub Actions Runner、远程权限、artifact 服务及线上部署尚未运行。

- 工作目录 `/home/alex/slowmoonship/privacy-observatory`。`.git` 在当前沙箱是 0555 只读空 tmpfs 挂载，遮盖底层路径；`git rev-parse/status/log/remote/worktree` 都无法识别仓库。不能推断底层没有仓库或历史，也未初始化、删除或重置。
- 三个真实来源采集均成功，`scripts/check_data.py` 三组通过；独立的 `/tmp/privacy-phase3-clean` 无旧快照启动真实采集，三组成功并产生快照。数据抽样：2026-11-22 XMR 日市值 9,058,307,000 USD、ZEC 13,475,570,000 USD；2026-11-23 两链 TxCnt 34,099、5,667；最近一年共同覆盖 2025-11-24 至 2026-11-23。
- `python3 -m unittest discover -s tests -v`：9 项通过。模拟 PriFi、Coin Metrics、ZecStats 各自失败时，失败组快照逐字节不变，其他组可更新，总状态 partial；全失败为 failure 且不可发布。HTTP 200 结构错误、空历史、过期数据被拒并保留上次成功快照。干净目录模拟部分失败会因无可用旧快照阻断；全成功可建立全部快照。无业务变化时不改写。模拟不等于线上故障测试。
- 构建 `npm run build -- --base=/privacy-observatory/` 成功；用本地静态 HTTP 服务托管实际 dist，并用真实 Chromium 在 1440×900、390×844 打开 `/privacy-observatory/`、刷新，确认脚本/样式/JSON 无 4xx、两个图表和交易指标切换正常、无页面异常、无横向溢出。测试脚本 `tests/pages-browser.cjs`。构建仍有 ECharts 包体提示。
- Workflow 权限、artifact 上传、分支保护、自动提交冲突及计划调度均未在 GitHub 验证；无部署动作。来源更新、上游许可变更、网络访问与 GitHub 上的真实 token 权限仍需线上核验。
