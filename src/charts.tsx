import {useEffect, useRef} from 'react';
import {init, use} from 'echarts/core';
import {LineChart} from 'echarts/charts';
import {GridComponent, LegendComponent, TooltipComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';

use([LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

export type Point = [string, string | null];
export type DailySeries = Record<string, Record<string, Point[]>>;
export type Asset = 'xmr' | 'zec';
export const assetNames = {xmr: 'Monero', zec: 'Zcash'};
export const assets = ['xmr', 'zec'] as const;

export function formatNumber(value?: number, digits = 2) {
  return value === undefined ? '—' : new Intl.NumberFormat('zh-CN', {maximumFractionDigits: digits}).format(value);
}

function axisNumber(value: number) {
  if (Math.abs(value) < 1 && value !== 0) return Number(value.toPrecision(3)).toString();
  return new Intl.NumberFormat('zh-CN', {notation: 'compact', maximumFractionDigits: 2}).format(value);
}

export function latest(points: Point[] = []) {
  for (let index = points.length - 1; index >= 0; index--) {
    if (points[index][1] !== null) return points[index];
  }
  return undefined;
}

export function Chart({items, range, unit, label, digits = 2}: {
  items: {asset: Asset; points?: Point[]}[];
  range: string;
  unit: string;
  label: string;
  digits?: number;
}) {
  const element = useRef<HTMLDivElement>(null);
  const hasData = items.some(item => item.points?.some(([, value]) => value !== null));
  useEffect(() => {
    if (!element.current || !hasData) return;
    const chart = init(element.current);
    const end = items.map(item => item.points?.at(-1)?.[0] ?? '').sort().at(-1);
    const cutoff = end && range !== 'all'
      ? new Date(Date.parse(end + 'T00:00:00Z') - (Number(range) - 1) * 86400000).toISOString().slice(0, 10) : '';
    chart.setOption({
      useUTC: true,
      animation: false,
      tooltip: {trigger: 'axis', confine: true, valueFormatter: (value: unknown) =>
        value == null ? '暂无数据' : `${formatNumber(Number(value), digits)} ${unit}`},
      legend: {top: 0, textStyle: {color: '#505954'}},
      grid: {left: 8, right: 17, top: 52, bottom: 24, containLabel: true},
      xAxis: {type: 'time', axisLabel: {color: '#77827b', hideOverlap: true}},
      yAxis: {type: 'value', scale: true, name: unit, nameTextStyle: {color: '#59665d'},
        axisLabel: {color: '#77827b', formatter: axisNumber}, splitLine: {lineStyle: {color: '#edf0ec'}}},
      series: items.map(({asset, points}) => ({
        name: assetNames[asset], type: 'line', showSymbol: false, connectNulls: false,
        color: asset === 'xmr' ? '#d0653b' : '#5575a8',
        data: (points ?? []).filter(([day]) => day >= cutoff).map(([day, value]) => [day, value === null ? null : Number(value)]),
      })),
    });
    const resize = new ResizeObserver(() => chart.resize());
    resize.observe(element.current);
    return () => {resize.disconnect(); chart.dispose();};
  }, [items, range, unit, digits, hasData]);
  return hasData
    ? <div className="chart" ref={element} role="img" aria-label={`${label} · ${unit} · UTC`}/>
    : <p className="chart-empty" role="status">暂无可验证的图表数据。</p>;
}

export function RangeSelect({label, value, onChange, full = '全部'}: {
  label: string; value: string; onChange: (value: string) => void; full?: string;
}) {
  return <select aria-label={label} value={value} onChange={e => onChange(e.target.value)}>
    <option value="90">近 90 天</option><option value="365">近 1 年</option><option value="all">{full}</option>
  </select>;
}
