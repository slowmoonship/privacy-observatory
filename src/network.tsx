import {useMemo, useState} from 'react';
import {assetNames, assets, Chart, formatNumber, latest, RangeSelect, type Asset, type DailySeries, type Point} from './charts';
import {DatasetLinks, type Dataset} from './datasets';

export const coinMetricsDocs = "https://github.com/coinmetrics/product-docs/blob/master/docs/packages/coin-metrics-community-data.md";

export type Economics = {
  source: string;
  source_url: string;
  source_license: string;
  license_url: string;
  methodology: Record<string, string>;
  data_as_of: string;
  fetched_at: string;
  coverage_start: string;
  coverage_end: string;
  data_status: 'available';
  columns: string[];
  series: Record<Asset, [string, ...(string | null)[]][]>;
};

const activity = [
  {id: 'transaction_count', label: '每日交易数', unit: '笔'},
  {id: 'tx_ma7', label: '7 日交易均线', unit: '笔/日'},
  {id: 'tx_ma30', label: '30 日交易均线', unit: '笔/日'},
  {id: 'block_count', label: '每日区块数', unit: '块'},
];

const economics = [
  {id: 'fee_native', label: '手续费总额', native: true, digits: 6},
  {id: 'fee_mean_native', label: '平均每笔手续费', native: true, digits: 9},
  {id: 'fee_usd', label: '手续费总额估值', unit: 'USD', digits: 2},
  {id: 'fee_mean_usd', label: '平均每笔手续费估值', unit: 'USD/笔', digits: 6},
  {id: 'issuance', label: '每日发行量', native: true, digits: 6},
  {id: 'current_supply_native', label: '供应量趋势', native: true, digits: 4},
  {id: 'supply_growth_365d', label: '365 日供应增长率', unit: '%', digits: 4},
];

const legacyMethods: Record<string, string> = {
  transaction_count: 'TxCnt 按完整 UTC 日统计，排除 coinbase。一笔网络交易可以包括多笔支付。',
  current_supply_native: 'Coin Metrics SplyCur 的当前供应量。ZEC 节点的全链已发行供应（含 Lockbox）采用不同口径。',
};

function series(econ: Economics | undefined, network: DailySeries | undefined, asset: Asset, id: string): Point[] {
  if (id in legacyMethods) return network?.[asset]?.[id] ?? [];
  const index = econ?.columns.indexOf(id) ?? -1;
  return index < 0 ? [] : (econ?.series[asset] ?? []).map(row => [row[0], row[index + 1]]);
}

function MetricTile({items, unit, digits}: {
  items: {asset: Asset; points: Point[]}[]; unit: string; digits: number;
}) {
  return <div className="chart-latest">{items.map(({asset, points}) => {
    const point = latest(points);
    return <div key={asset} data-series={asset} data-date={point?.[0]} data-value={point?.[1] ?? undefined}>
      <span>{assetNames[asset]}{point && ' · ' + point[0] + ' UTC'}</span>
      <strong>{point ? `${formatNumber(Number(point[1]), digits)} ${unit}` : '暂无观测'}</strong>
    </div>;
  })}</div>;
}

function ChartSource({data, points, legacy}: {data?: Economics; points: {points: Point[]}[]; legacy?: boolean}) {
  const dates = points.flatMap(item => item.points.filter(([, value]) => value !== null).map(([day]) => day)).sort();
  const stale = data && Date.now() - Date.parse(data.data_as_of + 'T00:00:00Z') > 4 * 86400000;
  return <div className="chart-source">
    <a href={coinMetricsDocs}>{data?.source ?? 'Coin Metrics Community Data'} ↗</a>
    <a href={data?.license_url ?? 'https://creativecommons.org/licenses/by-nc/4.0/'}>CC BY-NC 4.0 ↗</a>
    {dates.length > 0 && <span>有效覆盖 {dates[0]} 至 {dates.at(-1)} · UTC 日频</span>}
    {!legacy && data && <span>抓取 {data.fetched_at.slice(0, 16).replace('T', ' ')} UTC{stale && ' · 快照较旧'}</span>}
  </div>;
}

export function ResearchChart({mode, data, network, dataset}: {
  mode: 'activity' | 'economics'; data?: Economics; network?: DailySeries; dataset?: Dataset;
}) {
  const isActivity = mode === 'activity';
  const options = isActivity ? activity : economics;
  const [field, setField] = useState(options[0].id);
  const [asset, setAsset] = useState<Asset>('xmr');
  const [range, setRange] = useState('365');
  const selected = options.find(option => option.id === field)!;
  const native = 'native' in selected && selected.native;
  const items = useMemo(() => (native ? [asset] : assets).map(coin =>
    ({asset: coin, points: series(data, network, coin, field)})), [native, asset, data, network, field]);
  const unit = native ? asset.toUpperCase() + (field === 'fee_mean_native' ? '/笔' : '')
    : ('unit' in selected ? selected.unit : undefined) ?? '';
  const digits = 'digits' in selected ? selected.digits ?? 2 : 2;
  const method = legacyMethods[field] ?? data?.methodology[field];
  const isLegacy = field in legacyMethods;

  return <section id={mode}>
    <div className="section-heading"><div>
      <h2>{isActivity ? '网络活动' : '网络经济学'}</h2>
      <p>{isActivity ? '看每日交易、平滑趋势及主链区块数。' : '比较交易费用、发行与供应变化。'}</p>
    </div></div>
    <article className="card chart-card research-chart" data-metric-id={field}>
      <div className="chart-head">
        <div><h3>{selected.label}</h3><p>{method ?? '展示数据暂不可用。'}</p></div>
        <div className="controls">
          <select aria-label={isActivity ? '网络活动指标' : '网络经济指标'} value={field} onChange={e => setField(e.target.value)}>
            {options.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}
          </select>
          {native && <select aria-label="原生币种" value={asset} onChange={e => setAsset(e.target.value as Asset)}>
            <option value="xmr">Monero · XMR</option><option value="zec">Zcash · ZEC</option>
          </select>}
          <RangeSelect label={isActivity ? '网络活动时间范围' : '网络经济时间范围'} value={range}
            onChange={setRange} full={isLegacy ? '完整历史' : '全部展示期'}/>
        </div>
      </div>
      <MetricTile items={items} unit={unit} digits={digits}/>
      <Chart items={items} range={range} unit={unit} label={selected.label} digits={digits}/>
      <ChartSource data={data} points={items} legacy={isLegacy}/>
      {isLegacy ? <DatasetLinks data={dataset} fullHistory/> : <p className="muted-note">网页展示数据 · V1.1 计划提供研究数据下载。</p>}
    </article>
  </section>;
}

export function Hashrate({data}: {data?: Economics}) {
  const [asset, setAsset] = useState<Asset>('xmr');
  const [range, setRange] = useState('365');
  const items = useMemo(() => [{asset, points: series(data, undefined, asset, 'hashrate')}], [asset, data]);
  const unit = asset === 'xmr' ? 'H/s' : 'GSol/s';
  return <article className="card chart-card research-chart" data-metric-id="hashrate">
    <div className="chart-head"><div>
      <h3>{assetNames[asset]} 算力趋势</h3>
      <p>各链采用不同 PoW 算法，图表仅供观察所选链自身的估计趋势。
        {asset === 'zec' && ' NU7（2026-11-06）切换当日，估计值对计算方法较敏感。'}</p>
    </div><div className="controls">
      <select aria-label="算力网络" value={asset} onChange={e => setAsset(e.target.value as Asset)}>
        <option value="xmr">Monero · RandomX</option><option value="zec">Zcash · Equihash</option>
      </select>
      <RangeSelect label="算力时间范围" value={range} onChange={setRange} full="全部展示期"/>
    </div></div>
    <MetricTile items={items} unit={unit} digits={2}/>
    <Chart items={items} range={range} unit={unit} label={assetNames[asset] + ' 算力趋势'}/>
    <ChartSource data={data} points={items}/>
    <p className="muted-note">网页展示数据 · V1.1 计划提供研究数据下载。</p>
  </article>;
}
