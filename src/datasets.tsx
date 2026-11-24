export const datasetIds = {
 market: 'privacy_market_daily',
 tx: 'privacy_network_daily',
 protocols: 'privacy_protocol_registry',
 pools: 'zcash_value_pools_daily',
} as const;

export type Dataset = {
 id: string; title: string; summary: string; grain: string; status: string; limitations: string;
 source: {name: string; url: string; license: string; license_url: string | null};
 version: string; rows: number; updated: string; assessed_utc: string;
 coverage: Record<string, {start: string; end: string; rows: number;
   valid?: Record<string, {start: string; end: string}>}>;
 downloads: Record<string, string>;
 documents: Record<string, string>;
};

export const sitePath = (path: string) => import.meta.env.BASE_URL + path;
const filePath = (data: Dataset, file: string) => sitePath('datasets/' + data.id + '/' + file);

export function DatasetLinks({data, fullHistory = false}: {data?: Dataset; fullHistory?: boolean}) {
 if (!data) return null;
 const formats = Object.entries(data.downloads);
 return <div className="dataset-links">
   {formats.map(([format, file]) => <a key={format} href={filePath(data, file)} download>{format.toUpperCase()} 下载</a>)}
   <a href={filePath(data, data.documents.schema)}>{data.status === 'Blocked' ? '字段范围' : '数据字典'}</a>
   <a href={filePath(data, data.documents.methodology)}>统计口径</a>
   <a href={filePath(data, data.documents.quality)}>质量报告</a>
   <a href={filePath(data, data.documents.manifest)}>Manifest</a>
   <a href={data.source.url}>来源</a>
   {data.source.license_url && <a href={data.source.license_url}>{data.source.license}</a>}
   {fullHistory && formats.length > 0 && <span>下载包含完整历史，与图表时间筛选无关。</span>}
 </div>;
}

const statusLabels: Record<string, string> = {
 Ready: '可下载', 'Ready with limitations': '可下载 · 有限制', Blocked: '暂未开放',
};

export function DatasetCatalog({items}: {items: Dataset[]}) {
 return <section id="datasets">
   <div className="section-heading"><div><h2>数据集目录</h2><p>按数据集查看覆盖范围、统计口径与发布状态。</p></div></div>
   <div className="dataset-grid">{items.map(item => <article className="card dataset-card" key={item.id}>
     <div className="dataset-heading"><div><h3>{item.title}</h3><code>{item.id}</code></div>
       <span className={'release-status' + (item.status === 'Blocked' ? ' on-hold' : '')}>{statusLabels[item.status]}</span>
     </div>
     <p>{item.summary}</p>
     <dl className="dataset-meta">
       <div><dt>数据粒度</dt><dd>{item.grain}</dd></div>
       <div><dt>行数</dt><dd>{item.rows.toLocaleString('zh-CN')}</dd></div>
       <div><dt>{Object.keys(item.coverage).length ? '数据截至' : '目录核验日'}</dt><dd>{item.updated} UTC</dd></div>
       <div><dt>版本</dt><dd>{item.version}</dd></div>
       <div><dt>数据来源</dt><dd>{item.source.name}</dd></div>
       <div><dt>许可证</dt><dd>{item.source.license}</dd></div>
     </dl>
     {Object.entries(item.coverage).map(([asset, period]) => <p className="dataset-coverage" key={asset}>
       {asset.toUpperCase()}：{period.start} 至 {period.end} UTC
       {period.valid?.market_cap_usd?.start && period.valid.market_cap_usd.start !== period.start &&
         <span> · 市值有效期自 {period.valid.market_cap_usd.start}</span>}
     </p>)}
     <p className="dataset-limits">{item.limitations}</p>
     <DatasetLinks data={item}/>
   </article>)}</div>
 </section>;
}
