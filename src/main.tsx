import {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {assetNames, assets, Chart, formatNumber, latest, RangeSelect, type DailySeries} from './charts';
import {DatasetCatalog, DatasetLinks, datasetIds, sitePath, type Dataset} from './datasets';
import {coinMetricsDocs, Hashrate, ResearchChart, type Economics} from './network';
import {ZcashPools} from './zcashPools';
import './style.css';

type Protocol = {
  protocol_id: string;
  protocol_name: string;
  chain_id: string;
  chain_name: string;
  website_url: string;
  privacy_mechanism: string;
  deployment_address: string;
  deployment_role: string;
  deployment_source_url: string;
  mechanism_source_url: string;
  supported_assets: string;
  verified_utc: string;
};
type ChartData = {
  privacy_market_daily: DailySeries;
  privacy_network_daily: DailySeries;
  privacy_protocol_registry: Protocol[];
};

async function readSite<T>(file: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(sitePath('datasets/' + file), {signal});
  if (!response.ok) throw Error(file);
  return response.json();
}

const technique = [
  {label: '隐私模式', xmr: '常规交易默认使用链上隐私机制。', zec: '支持透明、屏蔽与混合交易，混合交易的透明一侧可见。'},
  {label: '发送者、接收者与金额', xmr: 'CLSAG 环签名混淆真实输入，一次性隐匿地址保护收款关联，RingCT 隐藏金额。',
    zec: '零知识证明验证屏蔽票据的支出与金额守恒，池内的接收者与金额保持隐藏，公开边界仍可留下线索。'},
  {label: '匿名集', xmr: '每个输入使用 16 个候选输出。有效隐私还受诱饵选择及外部信息影响。',
    zec: '匿名集按池及其历史票据讨论。余额和操作笔数本身无法衡量有效匿名集。'},
  {label: '选择性披露', xmr: '查看密钥可用于识别入账。核验出账可能需要 key image、交易证明或钱包数据。',
    zec: '可用能力取决于钱包和池协议，包括入账查看、完整查看或交易级披露。'},
  {label: 'PoW 与发行机制', xmr: 'RandomX，目标约 120 秒。无固定上限，尾部发行通常每块 0.6 XMR，区块权重惩罚可能降低补贴。',
    zec: 'Equihash，NU7 起目标约 25 秒。保留减半及 2,100 万上限，NSM 接收按协议移出流通的部分手续费。'},
  {label: '主网与开发状态', xmr: '主网使用 CLSAG、隐匿地址和 RingCT。FCMP++ 与 Carrot 已有 beta 压力测试，主网尚未生效。',
    zec: 'Sapling、Orchard、Ironwood 已部署。NU6.3 激活 Ironwood，NU7 后 Sprout 余额不可支出。'},
];

function Technology({data}: {data?: Economics}) {
  return <section id="design">
    <div className="section-heading"><div><h2>网络安全与技术</h2>
      <p>按链查看算力与协议设计。链上隐私保护范围取决于使用方式。</p></div></div>
    <Hashrate data={data}/>
    <div className="card technology">
      <div className="technology-labels"><strong>Monero · XMR</strong><strong>Zcash · ZEC</strong></div>
      {technique.map(row => <div className="technology-row" key={row.label}>
        <h3>{row.label}</h3><div><p>{row.xmr}</p><p>{row.zec}</p></div>
      </div>)}
      <div className="source-links">
        <a href="https://www.getmonero.org/resources/about/">Monero 技术 ↗</a>
        <a href="https://github.com/monero-project/monero/pull/11440">FCMP++ 进度 ↗</a>
        <a href="https://github.com/seraphis-migration/monero/releases">压力测试 ↗</a>
        <a href="https://zips.z.cash/zip-0316">Zcash 查看密钥 ↗</a>
        <a href="https://zips.z.cash/zip-0258">Ironwood ↗</a>
        <a href="https://zips.z.cash/zip-0259">NU7 ↗</a>
      </div>
      <p className="muted-note">技术资料核验于 2026-11-24 UTC。</p>
    </div>
  </section>;
}

const roles: Record<string, string> = {
  privacy_system_contract: '隐私系统合约', v2_entrypoint: 'v2 入口合约', solana_program: '主网 Program',
  classic_pool: 'Classic 存取池', stealth_payment_contract: '隐匿收款合约', shielded_pool_program: '屏蔽池 Program',
};

function Protocols({rows, dataset}: {rows: Protocol[]; dataset?: Dataset}) {
  const ids = [...new Set(rows.map(row => row.protocol_id))];
  return <section id="protocols">
    <div className="section-heading"><div><h2>主流公链隐私协议</h2>
      <p>代表性主网部署。展开查看机制、资产范围及官方出处。</p></div></div>
    <div className="protocol-directory">
      {ids.map(id => {
        const group = rows.filter(row => row.protocol_id === id);
        return <details className="card protocol" key={id} data-protocol={id}>
          <summary><strong>{group[0].protocol_name}</strong><span>{group.map(row => row.chain_name).join(' · ')}</span></summary>
          <p>{group[0].privacy_mechanism} · <a href={group[0].website_url}>项目主页 ↗</a></p>
          <ul>{group.map(row => <li key={row.chain_id}>
            <strong>{row.chain_name}</strong><p>{row.supported_assets}</p>
            <p>{roles[row.deployment_role] ?? row.deployment_role} <code>{row.deployment_address}</code></p>
            <p><a href={row.deployment_source_url}>部署文档 ↗</a> · <a href={row.mechanism_source_url}>机制文档 ↗</a> · {row.verified_utc} UTC</p>
          </li>)}</ul>
        </details>;
      })}
    </div>
    <DatasetLinks data={dataset}/>
  </section>;
}

function App() {
  const [catalog, setCatalog] = useState<Dataset[]>([]);
  const [data, setData] = useState<ChartData>();
  const [econ, setEcon] = useState<Economics>();
  const [error, setError] = useState(false);
  const [range, setRange] = useState('365');

  useEffect(() => {
    const request = new AbortController();
    const failed = () => {if (!request.signal.aborted) setError(true);};
    readSite<Dataset[]>('index.json', request.signal).then(setCatalog, failed);
    readSite<ChartData>('chart-data.json', request.signal).then(setData, failed);
    readSite<Economics>('network-economics.json', request.signal).then(setEcon, failed);
    return () => request.abort();
  }, []);

  const dataset = (id: string) => catalog.find(item => item.id === id);
  const market = useMemo(() => assets.map(asset =>
    ({asset, points: data?.privacy_market_daily[asset]?.market_cap_usd})), [data]);
  return <>
    <header><div className="wrap nav">
      <a className="brand" href="#top"><span className="mark">◒</span><span>SlowMoonShip <small>PRIVACY OBSERVATORY</small></span></a>
      <nav aria-label="页面导航"><a href="#compare">资产对比</a><a href="#activity">网络活动</a><a href="#pools">隐私采用</a>
        <a href="#economics">网络经济</a><a href="#design">技术</a><a href="#protocols">协议</a><a href="#datasets">数据集</a></nav>
    </div></header>
    <main id="top" className="wrap">
      <section className="hero">
        <div><div className="eyebrow"><span className="dot"/> PRIVACY OBSERVATORY</div>
          <h1>看见隐私资产的<br/><em>数据与差异。</em></h1>
          <p>以 Monero 与 Zcash 为核心，观察隐私设计、网络活动与资金分布。</p>
          <a className="hero-link" href="#compare">查看资产对比 <span>↘</span></a> <a className="hero-link data-shortcut" href="#datasets">数据集目录 ↘</a>
        </div>
        <div className="hero-art" aria-hidden="true"><div className="orbit one"/><div className="orbit two"/>
          <div className="orbit three"/><div className="orb">◐</div><span>PRIVACY<br/>BY DESIGN</span></div>
      </section>
      {error && <div className="warning" role="status">部分研究数据暂不可用，缺失值保留为空。</div>}
      <section id="compare">
        <div className="section-heading"><div><h2>Monero 与 Zcash</h2>
          <p>市值、交易与供应以各指标最近有效的 UTC 日为准。</p></div></div>
        <div className="compare-grid">{assets.map((asset, index) => {
          const cap = latest(market[index].points);
          const tx = latest(data?.privacy_network_daily[asset]?.transaction_count);
          const supply = latest(data?.privacy_network_daily[asset]?.current_supply_native);
          return <article className="coin card" key={asset} data-asset={asset}>
            <div className="coin-head"><span className={'coin-icon ' + asset}>{asset === 'xmr' ? 'ɱ' : 'ⓩ'}</span>
              <div><h3>{assetNames[asset]}</h3><small>{asset.toUpperCase()}</small></div></div>
            <div className="stats">
              <div><span>最近日市值</span><strong data-metric="market_cap_usd" title={cap?.[1] ?? undefined}>
                {cap ? '$' + formatNumber(Number(cap[1]) / 1e8) + ' 亿' : '—'}</strong>{cap && <small>{cap[0]} UTC</small>}</div>
              <div><span>当前供应量（SplyCur）</span><strong data-metric="current_supply_native" title={supply?.[1] ?? undefined}>
                {supply ? formatNumber(Number(supply[1]), 0) : '—'} <small>{asset.toUpperCase()}</small></strong>{supply && <small>{supply[0]} UTC</small>}</div>
              <div><span>每日网络交易</span><strong data-metric="transaction_count" title={tx?.[1] ?? undefined}>
                {tx ? formatNumber(Number(tx[1]), 0) : '—'} <small>笔</small></strong>{tx && <small>{tx[0]} UTC</small>}</div>
              <div><span>隐私模式</span><strong className="text-value">{asset === 'xmr' ? '默认隐私' : '可选屏蔽'}</strong></div>
            </div>
            <div className="evidence">{asset === 'xmr' ? '尾部发行 · 通常每块 0.6 XMR。' :
              '减半发行 · 上限 2,100 万 ZEC。SplyCur 与节点的全链已发行供应分列。'} 交易数排除 coinbase。</div>
          </article>;
        })}</div>
        <article className="card chart-card market-chart">
          <div className="chart-head"><div><h3>历史市值</h3><p>按 Coin Metrics 的当前供应市值，使用 USD 与 UTC 日频。</p></div>
            <div className="controls"><RangeSelect label="市值时间范围" value={range} onChange={setRange}/></div></div>
          <Chart items={market} range={range} unit="USD" label="历史市值"/>
          <div className="chart-source"><a href={coinMetricsDocs}>Coin Metrics Community Data ↗</a></div>
          <DatasetLinks data={dataset(datasetIds.market)} fullHistory/>
        </article>
      </section>
      <ResearchChart mode="activity" data={econ} network={data?.privacy_network_daily} dataset={dataset(datasetIds.tx)}/>
      <ZcashPools dataset={dataset(datasetIds.pools)}/>
      <ResearchChart mode="economics" data={econ} network={data?.privacy_network_daily} dataset={dataset(datasetIds.tx)}/>
      <Technology data={econ}/>
      <Protocols rows={data?.privacy_protocol_registry ?? []} dataset={dataset(datasetIds.protocols)}/>
      <DatasetCatalog items={catalog}/>
      <section id="sources" className="sources"><div><h2>关于这些数据</h2></div><div>
        <p>市场及网络数据来自 Coin Metrics Community Data，依据 CC BY-NC 4.0 用于非商业研究。本站进行日频筛选、衍生计算和显示舍入。对应 V0.2 研究数据集的原有指标与下载使用同一快照。</p>
        <p>新增指标随网页展示，完整研究数据集计划在 V1.1 提供。观测日期使用 UTC，抓取日期单列。</p>
        <div className="source-links"><a href={coinMetricsDocs}>Coin Metrics 文档 ↗</a>
          <a href="https://github.com/coinmetrics/docs-website/blob/master/asset-metrics/market/priceusd.md">PriceUSD 口径 ↗</a>
          <a href="https://creativecommons.org/licenses/by-nc/4.0/">CC BY-NC 4.0 ↗</a></div>
      </div></section>
    </main>
    <footer><div className="wrap"><span>◒ &nbsp; SlowMoonShip / Privacy Observatory</span><span>独立非商业研究</span></div></footer>
  </>;
}

createRoot(document.getElementById('root')!).render(<App/>);
