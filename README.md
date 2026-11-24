# SlowMoonShip Privacy Observatory

中文隐私资产研究站，聚焦 Monero 与 Zcash。正式网站与研究下载均用于非商业用途。

- [生产网站](https://slowmoonship.github.io/privacy-observatory/)
- [数据集目录](https://slowmoonship.github.io/privacy-observatory/#datasets)
- [V0.2 版本与数据说明](docs/v0.2-release.md)
- [V0.1 历史版本](https://github.com/slowmoonship/privacy-observatory/releases/tag/v0.1.0)

## 本地构建

安装 Node.js 22、Python 3.12，然后在仓库根目录执行：

    npm ci
    python3 -m pip install -r scripts/requirements-datasets.txt
    npm run build -- --base=/privacy-observatory/

本地开发可用 npm run dev。公开静态文件由白名单生成并验证，构建只读仓库内审核过的公开输入。CI 手动与计划任务使用同一生产逻辑。

## 来源及口径

市值和网络活动采用 Coin Metrics Community Data，经本站标准化和类型转换。CSV、Parquet 与网页来自同一版本化快照。Coin Metrics 和历史对照所用 PriFi 的 CC BY-NC 4.0 限制继续适用。协议目录引用各项目官方部署事实，不包含 TVL。Zcash 价值池及全链发行供应暂缓展示。[Coin Metrics 许可](https://github.com/coinmetrics/data#license) · [PriFi 授权](https://prifi.info/data/) · [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)
