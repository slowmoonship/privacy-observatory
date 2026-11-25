import {useEffect, useState} from 'react';
import {DatasetLinks, sitePath, type Dataset} from './datasets';
import {percent, poolView, shieldedPools, zecAmount} from './zcashSnapshot';

const labels = {sprout: 'Sprout', sapling: 'Sapling', orchard: 'Orchard', ironwood: 'Ironwood',
  transparent: 'Transparent', lockbox: 'Lockbox'};
const shielded = new Set<string>(shieldedPools);

function ShieldedShareWidget() {
  const [visible, setVisible] = useState(false);
  return <aside className="pool-widget" aria-label="第三方屏蔽供应快照">
    <h3>第三方屏蔽供应快照</h3>
    <p>由 <a href="https://zeczcash.com/shielded" referrerPolicy="no-referrer">ZecZcash</a> 提供。
      日期和延迟状态见挂件。点击加载会直接访问第三方站点。</p>
    {visible
      ? <iframe src="https://zeczcash.com/embed/shielded-supply?theme=light"
          title="ZecZcash · Zcash 屏蔽供应占比"
          width="440" height="200" referrerPolicy="no-referrer"
          sandbox="allow-popups allow-popups-to-escape-sandbox"/>
      : <button type="button" onClick={() => setVisible(true)}>加载 ZecZcash 挂件</button>}
  </aside>;
}

export function ZcashPools({dataset}: {dataset?: Dataset}) {
  const [view, setView] = useState<ReturnType<typeof poolView>>();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const request = new AbortController();
    fetch(sitePath('datasets/zcash-pool-status.json'), {signal: request.signal}).then(response => {
      if (!response.ok) throw Error('snapshot request');
      return response.json();
    }).then(data => setView(poolView(data))).catch(() => {
      if (!request.signal.aborted) setFailed(true);
    });
    return () => request.abort();
  }, []);

  return <section id="pools">
    <div className="section-heading"><div><h2>Zcash 隐私采用</h2>
      <p>同一区块的四个屏蔽池账面余额与全链已发行供应。</p></div></div>
    <article className="card pool-hold" data-pool-state={failed ? 'invalid' : view?.state ?? 'loading'}>
      {failed ? <><h3>价值池快照无法验证</h3><p role="status">读取失败或未通过区块身份、时间及六池整数余额校验。</p></>
      : !view ? <p role="status">正在检查价值池快照…</p>
      : view.state === 'unavailable' ? <><h3>价值池观测暂未开放</h3><p role="status">{view.reason}</p></>
      : <>
        {view.state === 'stale' && <p className="warning" role="status">快照已过期 · 以下数值来自最后一次通过校验的区块。</p>}
        <div className="pool-stats">
          <div><small>全链已发行供应</small><strong data-pool-total={view.total.toString()}>{zecAmount(view.total)} ZEC</strong></div>
          <div><small>屏蔽池账面余额</small><strong data-pool-shielded={view.shielded.toString()}>{zecAmount(view.shielded)} ZEC</strong></div>
          <div><small>屏蔽供应占比</small><strong data-pool-share>{percent(view.shielded, view.total)}</strong></div>
        </div>
        <p>区块 {view.snapshot.block_height.toLocaleString('zh-CN')} · {view.snapshot.block_timestamp.replace('T', ' ').replace('Z', ' UTC')}</p>
        <p className="snapshot-meta">区块哈希 <code>{view.snapshot.block_hash}</code> · 抓取于 {view.snapshot.fetched_at}</p>
        <dl className="pool-balances">
          {view.balances.map(({pool, balance}) => <div key={pool} data-pool={pool}>
            <dt>{labels[pool]}{pool === 'sprout' && view.sproutFrozen ? ' · 不可支出' : ''}</dt>
            <dd>{zecAmount(balance)} ZEC{shielded.has(pool) && <small>屏蔽池余额的 {percent(balance, view.shielded)}</small>}</dd>
          </div>)}
        </dl>
        <p><a href={view.snapshot.source_url}>{view.snapshot.source} ↗</a> · {view.snapshot.source_license}</p>
      </>}
      {view?.state === 'unavailable' && <ShieldedShareWidget/>}
      <p className="evidence">Sprout 在 NU7 后不可支出，仍计入账面余额。Transparent 与 Lockbox 单列。NSM 排除在已发行供应之外。这里采用节点的发行供应口径，与 Coin Metrics SplyCur 分列。</p>
      <p><a href="https://zips.z.cash/zip-0259">NU7 规则 ↗</a> · <a href="https://zebra.zfnd.org/next/dev/rfcs/0012-value-pools.html">Zebra 价值池规则 ↗</a></p>
      <DatasetLinks data={dataset}/>
    </article>
  </section>;
}
