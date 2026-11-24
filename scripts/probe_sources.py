#!/usr/bin/env python3
"""只读探测公开数据源；不落盘原始数据。"""
import csv
import datetime as dt
import io
import json
import sys
import urllib.request

URLS = {
    'summary': 'https://prifi.info/api/v1/summary',
    'history': 'https://prifi.info/api/v1/history',
    'activity': 'https://prifi.info/api/v1/activity',
    'supply': 'https://prifi.info/api/v1/supply',
    'zec_summary': 'https://zecstats.org/api/zec/summary',
    'pools': 'https://zecstats.org/api/zec/pools.csv',
}
def day(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()
def profile(days, values):
    if len(days) != len(values):
        raise ValueError(f'日期和值长度不一致: {len(days)} != {len(values)}')
    available = [(day(t), v) for t, v in zip(days, values) if v is not None]
    return {'rows': len(values), 'nulls': values.count(None), 'first': available[0] if available else None, 'last': available[-1] if available else None}
def inspect(name, body):
    if name == 'pools':
        rows = list(csv.DictReader(io.StringIO(body)))
        if not rows: raise ValueError('空 CSV')
        dates = [r['day'] for r in rows]
        return {'rows': len(rows), 'first': rows[0], 'last': rows[-1], 'duplicate_days': len(dates)-len(set(dates)), 'empty': {k: sum(not r[k] for r in rows) for k in rows[0]}}
    j = json.loads(body)
    d = j if name == 'zec_summary' else j['data']
    result = {'generatedAt': d.get('generatedAt'), 'modifiedAt': j.get('modifiedAt')}
    if name == 'summary':
        result.update(assets=[a for a in d['assets'] if a['symbol'] in ('XMR','ZEC')], shielded=d['tiles']['shielded'], protocols=len(d['protocols']), protocol_null_tvl=sum(p.get('tvl') is None for p in d['protocols']), leaders=[{k:p.get(k) for k in ('name','tvl','chains','counted','observedAt')} for p in sorted(d['protocols'], key=lambda p:p.get('tvl') or 0, reverse=True)[:5]])
    elif name == 'history':
        result['series'] = {k:profile(d['days'], d['series'][k]) for k in ('floatXMR','floatZEC','shieldedZec','shieldedPct')}
    elif name == 'activity':
        result['charts'] = {k:{s['key']:profile(d['charts'][k]['days'],s['values']) for s in d['charts'][k]['series']} for k in ('monero','zcash')}
    elif name == 'supply':
        result['coins'] = {c['id']:{'supply':c['supply'], 'history':profile([c['history']['start']+i*c['history']['step'] for i in range(len(c['history']['values']))],c['history']['values'])} for c in d['coins'] if c['id'] in ('xmr','zec')}
    else:
        result.update(supply=d['supply'],pools=d['pools'],sources=d['sources'].get('pools'),warnings=d.get('warnings'))
    return result

def main():
    failed = False
    for name,url in URLS.items():
        out = {'endpoint':name,'url':url,'checkedAt':dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'SlowMoonShip-Privacy-Observatory/0.1 (research; github.com/slowmoonship)'})
            with urllib.request.urlopen(req,timeout=45) as response:
                out.update(status=response.status,content_type=response.headers.get('Content-Type'),cache_control=response.headers.get('Cache-Control'),body_bytes=len(body:=response.read()),result=inspect(name,body.decode('utf-8-sig')))
        except Exception as e:
            failed=True
            out['error']=f'{type(e).__name__}: {e}'
            if hasattr(e,'code'): out['status']=e.code
        print(json.dumps(out,ensure_ascii=False))
    return int(failed)
if __name__ == '__main__': sys.exit(main())
