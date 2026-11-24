# Phase 2 本地验收

2026-11-24，真实 Chromium / Playwright，本地 Vite 服务；截图为 desktop.png（1440×900）和 mobile.png（390×844）。

- 页面加载无 JavaScript pageerror，两张 ECharts canvas 均存在且显示真实曲线；桌面 scrollWidth 1440、移动 390，与视口相同，无横向溢出。
- 历史市值切换至交易活动、选择近 90 天均成功；悬停显示日期和两条交易值（抽查 2026-10-17：XMR 23,799、ZEC 6,100）。来源链接及中文单位显示正常。
- 页面 XMR 34,099、ZEC 5,667 笔与 `public/data/activity.json` 抽样一致；日数据截至 2026-11-23 UTC。其他数值以各文件的实际观测时间为准，实时值可能在截图后更新。
- 浏览器模拟 pools.json HTTP 500：出现“屏蔽池”不可用提示，屏蔽总量显示破折号而非 0。Python 模拟来源异常时保留上次成功文件；缺失日期变为 null，图表 `connectNulls=false`。
- 页面按数据观测时间超过三天显示可能过期，未将抓取时间作为观测时间；用浏览器拦截静态文件并注入旧日期，确认两条过期提示；注入 null 后图表仍渲染。空值、缺失和错误处理不等于对所有上游异常的穷尽验证。
- `npm run build` 通过；ECharts 完整包有大于 500 kB 构建提示，可在后续按需引入优化。
