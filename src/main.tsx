import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import * as echarts from 'echarts';
import './style.css';
import {DatasetCatalog, DatasetLinks, datasetIds, sitePath, type Dataset} from './datasets';
type Metric = {value: number; raw: string; day: string; points: [string, number | null][]};
type DailySeries = Record<string, Record<string, [string, string | null][]>>;
type Protocol = {protocol_id: string; protocol_name: string; chain_name: string; website_url: string};
type ChartData = {
 privacy_market_daily: DailySeries;
 privacy_network_daily: DailySeries;
 privacy_protocol_registry: Protocol[];
};
const colors=['#ef8354','#597ab1','#559787','#a796c3'];

function metric(series: DailySeries | undefined, asset: string, field: string): Metric | undefined {
 const points = series?.[asset]?.[field];
 const latest = points?.slice().reverse().find(([, value]) => value !== null);
 if (!latest || !points) return undefined;
 return {value: Number(latest[1]), raw: latest[1]!, day: latest[0],
   points: points.map(([day, value]) => [day, value === null ? null : Number(value)])};
}

async function readSite<T>(file: string): Promise<T> {
 const response = await fetch(sitePath('datasets/' + file));
 if (!response.ok) throw Error(file);
 return response.json();
}
const fmt=(v:number|undefined, digits=2)=>v===undefined?'—':new Intl.NumberFormat('zh-CN',{maximumFractionDigits:digits}).format(v);
const money=(v:number|undefined)=>v===undefined?'—':'$'+fmt(v/1e8,2)+' 亿';
function Chart({items,range,unit}:{items:{name:string,m?:Metric}[],range:string,unit:string}){
 const el=useRef<HTMLDivElement>(null);
 useEffect(()=>{if(!el.current)return;const chart=echarts.init(el.current);const available=items.filter(x=>x.m?.points); const all=available.flatMap(x=>x.m!.points!.map(p=>p[0])); const end=all.sort().at(-1); const cutoff=end&&range!=='all'?new Date(Date.parse(end+'T00:00:00Z')-(Number(range)-1)*86400000).toISOString().slice(0,10):'';
 chart.setOption({useUTC:true,color:colors,tooltip:{trigger:'axis',valueFormatter:(v:unknown)=>v==null?'暂无数据':fmt(Number(v),2)+' '+unit},legend:{top:0,textStyle:{color:'#505954'}},grid:{left:10,right:18,top:50,bottom:25,containLabel:true},xAxis:{type:'time',axisLine:{lineStyle:{color:'#d7ddd7'}},axisLabel:{color:'#77827b'}},yAxis:{type:'value',scale:true,axisLabel:{color:'#77827b',formatter:(v:number)=>unit==='USD'?(v/1e8).toFixed(0)+'亿':v>=1000000?(v/1000000).toFixed(1)+'M':fmt(v,0)},splitLine:{lineStyle:{color:'#edf0ec'}}},series:available.map(x=>({name:x.name,type:'line',showSymbol:false,connectNulls:false,data:x.m!.points!.filter(p=>p[0]>=cutoff).map(p=>[p[0],p[1]])}))});const resize=()=>chart.resize();window.addEventListener('resize',resize);return()=>{window.removeEventListener('resize',resize);chart.dispose()}},[items,range,unit]);
 return <div className="chart" ref={el} aria-label="历史数据图表"/>;
}
function App(){
 const [catalog,setCatalog] = useState<Dataset[]>([]);
 const [data,setData] = useState<ChartData>();
 const [error,setError] = useState(false);
 const [kind,setKind]=useState<'market'|'tx'>('market');
 const [range,setRange]=useState('365');
 useEffect(() => {
   readSite<Dataset[]>('index.json').then(setCatalog).catch(() => setError(true));
   readSite<ChartData>('chart-data.json').then(setData).catch(() => setError(true));
 }, []);
 const dataset = (id: string) => catalog.find(item => item.id === id);
 const market = (asset: string) => metric(data?.privacy_market_daily, asset, 'market_cap_usd');
 const network = (asset: string, field = 'transaction_count') => metric(data?.privacy_network_daily, asset, field);
 const chartItems = [{name:'Monero', m:kind === 'market' ? market('xmr') : network('xmr')},
   {name:'Zcash', m:kind === 'market' ? market('zec') : network('zec')}];
 const protocols = data?.privacy_protocol_registry ?? [];
 const protocolIds = [...new Set(protocols.map(row => row.protocol_id))].sort(
   (left, right) => ['railgun','privacy-pools','privacy-cash'].indexOf(left) -
                    ['railgun','privacy-pools','privacy-cash'].indexOf(right));
 return <><header><div className="wrap nav"><a className="brand" href="#top"><span className="mark">◒</span><span>SlowMoonShip <small>PRIVACY OBSERVATORY</small></span></a><nav><a href="#compare">资产对比</a><a href="#pools">屏蔽池</a><a href="#protocols">隐私协议</a><a href="#datasets">数据集</a><a href="#sources">数据说明</a></nav><span className="tag">研究项目 · V0.2</span></div></header>
 <main id="top" className="wrap"><section className="hero"><div><div className="eyebrow"><span className="dot"/> 独立研究 / PRIVACY OBSERVATORY</div><h1>看见隐私资产的<br/><em>数据与差异。</em></h1><p>以公开数据观察 Monero 与 Zcash。理解隐私技术、网络活动与资金分布，而不是简单地比较价格。</p><a className="hero-link" href="#compare">开始探索 <span>↘</span></a> <a className="hero-link data-shortcut" href="#datasets">数据集目录 ↘</a></div><div className="hero-art" aria-hidden="true"><div className="orbit one"/><div className="orbit two"/><div className="orbit three"/><div className="orb">◐</div><span>PRIVACY<br/>BY DESIGN</span><small>01 / 02</small></div></section>
 {error&&<div className="warning" role="status">部分研究数据暂不可用，缺失值保留为空。</div>}
 <section id="compare"><div className="section-heading"><div><div className="eyebrow">01 / THE COMPARISON</div><h2>两种路径，同一个问题</h2><p>Monero 默认保护交易隐私；Zcash 同时支持透明与屏蔽交易。</p></div><span className="section-side">NETWORK SNAPSHOT<br/>数据时间各异 · UTC</span></div>
 <div className="compare-grid">{(['xmr','zec'] as const).map((c,i) => {
   const cap = market(c), tx = network(c), supply = c === 'xmr' ? network(c,'current_supply_native') : undefined;
   return <article className="coin card" key={c} data-asset={c}>
     <div className="coin-head"><span className={'coin-icon '+c}>{i?'ⓩ':'ɱ'}</span><div><h3>{i?'Zcash':'Monero'}</h3><small>{c.toUpperCase()} / 隐私资产</small></div><span className="coin-no">0{i+1}</span></div>
     <div className="stats">
       <div><span>最近日市值</span><strong data-metric="market_cap_usd" title={cap?.raw}>{money(cap?.value)}</strong>{cap && <small>{cap.day} UTC</small>}</div>
       <div><span>{c==='xmr' ? '当前供应量（SplyCur）' : '全链发行供应'}</span>
         {c==='xmr' ? <><strong data-metric="current_supply_native" title={supply?.raw}>{fmt(supply?.value,0)} <small>XMR</small></strong>{supply && <small>{supply.day} UTC</small>}</> :
           <strong className="text-value">暂未展示</strong>}</div>
       <div><span>每日网络交易</span><strong data-metric="transaction_count" title={tx?.raw}>{fmt(tx?.value,0)} <small>笔</small></strong>{tx && <small>{tx.day} UTC</small>}</div>
       <div><span>隐私模式</span><strong className="text-value">{i?'可选屏蔽':'默认隐私'}</strong></div>
     </div>
     <div className="evidence">{c==='zec' ? '网络数据集的 ZEC SplyCur 与含 Lockbox 的全链发行供应口径不同。' : '供应量采用 Coin Metrics SplyCur。'} 交易数排除 Coinbase。</div>
   </article>;
 })}</div>
 <article className="card chart-card"><div className="chart-head"><div><div className="eyebrow">HISTORICAL DATA</div><h3>历史趋势</h3><p>按各自实际覆盖范围展示；缺失值不填补。</p></div><div className="controls"><div className="seg" aria-label="指标切换"><button className={kind==='market'?'active':''} onClick={()=>setKind('market')}>历史市值</button><button className={kind==='tx'?'active':''} onClick={()=>setKind('tx')}>交易活动</button></div><select aria-label="时间范围" value={range} onChange={e=>setRange(e.target.value)}><option value="90">近 90 天</option><option value="365">近 1 年</option><option value="all">全部</option></select></div></div><Chart items={chartItems} range={range} unit={kind==='market'?'USD':'笔'}/><DatasetLinks data={dataset(datasetIds[kind])} fullHistory/></article></section>
 <section id="pools"><div className="section-heading"><div><div className="eyebrow">02 / ZCASH SHIELDED POOLS</div><h2>屏蔽池内，发生了什么</h2><p>屏蔽供应量是池中余额。Lockbox 独立核算。</p></div></div>
   <article className="card pool-hold"><h3>价值池观测暂未开放</h3><p>上游再分发权待核实，价值池图表及全链发行供应暂缓展示。</p><DatasetLinks data={dataset(datasetIds.pools)}/></article>
 </section>
 <section id="design"><div className="section-heading"><div><div className="eyebrow">03 / DESIGN CHOICES</div><h2>理解背后的设计</h2><p>两条链做出了不同的技术与货币政策选择。</p></div></div><div className="design-grid"><article className="card"><span className="eyebrow">MONERO / XMR</span><h3>默认隐私</h3><p>通过环签名、隐匿地址与保密交易保护链上交易信息。默认隐私不代表可以测量出 100% 的匿名成功率。</p><p>主发行期结束后进入尾部发行，区块补贴约 0.6 XMR，长期提供矿工激励。</p><a href="https://www.getmonero.org/resources/about/" target="_blank" rel="noreferrer">Monero 官方说明 ↗</a></article><article className="card"><span className="eyebrow">ZCASH / ZEC</span><h3>可选的屏蔽交易</h3><p>零知识证明支持屏蔽池，同时保留透明交易；涉及屏蔽组件的混合交易仍可能暴露透明一侧。</p><p>发行上限为 2100 万 ZEC；发行规则随网络升级演进，不将未来提案当作既成事实。</p><a href="https://z.cash/learn/what-are-the-economics-of-zcash/" target="_blank" rel="noreferrer">Zcash 官方说明 ↗</a></article></div></section>
 <section id="protocols"><div className="section-heading"><div><div className="eyebrow">04 / BEYOND THE CHAINS</div><h2>公链上的隐私工具</h2><p>辅助观察 · 协议目录并非完整排名。TVL 授权链条尚待确认，暂不展示数值。</p></div></div><div className="protocols">{protocolIds.map((id,i) => {
   const rows = protocols.filter(row => row.protocol_id === id);
   return <a data-protocol={id} key={id} href={rows[0].website_url} target="_blank" rel="noreferrer">
     <span>{String(i+1).padStart(2,'0')}</span><strong>{rows[0].protocol_name}</strong>
     <small>{rows.map(row => row.chain_name).join(' · ')}</small><b>访问官网 ↗</b>
   </a>;
 })}</div><DatasetLinks data={dataset(datasetIds.protocols)}/></section>
 <DatasetCatalog items={catalog}/>
 <section id="sources" className="sources"><div><div className="eyebrow">05 / TRANSPARENCY</div><h2>关于这些数据</h2></div><div><p>市值与网络活动来自 Coin Metrics Community Data，按 CC BY-NC 4.0 用于非商业研究。网页与下载使用同一研究快照，保留原始数值并在网页格式化展示。数据可能延迟或发生修订。</p><p>涉及屏蔽组件的交易数包括混合交易；完全屏蔽交易是不同口径，目前均不展示。交易笔数不是用户数，跨链差异也不意味着隐私强弱。</p><div className="source-links"><a href="https://prifi.info/data/">PriFi 数据与许可 ↗</a><a href="https://docs.coinmetrics.io/">Coin Metrics 文档 ↗</a><a href="https://zecstats.org/data">ZecStats 数据 ↗</a><a href="https://creativecommons.org/licenses/by-nc/4.0/">CC BY-NC 4.0 ↗</a><a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0 ↗</a></div></div></section></main><footer><div className="wrap"><span>◒ &nbsp; SlowMoonShip / Privacy Observatory</span><span>公开数据 · 独立观察 · 不构成投资建议</span></div></footer></>}

createRoot(document.getElementById('root')!).render(<App/>);
