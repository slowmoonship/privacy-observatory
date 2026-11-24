#!/usr/bin/env python3
"""Fetch independent validated groups; failed groups retain their last successful file."""
import csv, datetime as dt, io, json, math, os, pathlib, tempfile, urllib.request, urllib.error, time, sys
from urllib.parse import urlencode

OUT = pathlib.Path(__file__).resolve().parents[1] / 'public/data'
NOW = dt.datetime.now(dt.timezone.utc)
FETCHED = NOW.isoformat()
PRI = 'https://prifi.info/api/v1/'
ZEC = 'https://zecstats.org/api/zec/'
CM = 'https://community-api.coinmetrics.io/v4/timeseries/asset-metrics'
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'SlowMoonShip-Privacy-Observatory/0.1 (non-commercial research)'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=30) as r: return r.read().decode('utf-8-sig')
        except (urllib.error.URLError, TimeoutError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429,500,502,503,504): raise
            if attempt == 2: raise
            time.sleep(2 ** attempt)
def getjson(url): return json.loads(fetch(url))
def stamp(t): return dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat()
def num(v):
    if isinstance(v,bool): raise ValueError('boolean number')
    n=float(v)
    if not math.isfinite(n) or n<0: raise ValueError('invalid value')
    return n
def metric(id,value,unit,source,url,license,method,asof,points=None):
    value=num(value); dt.datetime.fromisoformat(asof.replace('Z','+00:00'))
    if points is not None:
        if not points: raise ValueError('empty series')
        dates=[p[0] for p in points]
        if dates != sorted(set(dates)): raise ValueError('unsorted or duplicated days')
        for date,v in points:
            dt.date.fromisoformat(date)
            if v is not None: num(v)
        valid=[p[0] for p in points if p[1] is not None]
        if not valid: raise ValueError('all values missing')
    else: valid=[asof[:10]]
    return dict(metric_id=id,value=value,unit=unit,source=source,source_url=url,source_license=license,methodology=method,data_as_of=asof,fetched_at=FETCHED,coverage_start=valid[0],coverage_end=valid[-1],data_status='ok',points=points)
def daily_gaps(points):
    if not points: return points
    first=dt.date.fromisoformat(points[0][0]); last=dt.date.fromisoformat(points[-1][0]); lookup=dict(points)
    if len(lookup)!=len(points): raise ValueError('duplicate dates')
    return [[(first+dt.timedelta(days=i)).isoformat(),lookup.get((first+dt.timedelta(days=i)).isoformat())] for i in range((last-first).days+1)]

def prifi():
    h=getjson(PRI+'history')['data']; supply=getjson(PRI+'supply')['data']; out={}
    if h['units']['usd'] != 'millions of US dollars': raise ValueError('unexpected market history units')
    for coin in ('xmr','zec'):
        vals=h['series']['float'+coin.upper()]; days=h['days']
        if len(vals)!=len(days) or not days: raise ValueError('history length mismatch or empty')
        points=[[stamp(t)[:10],None if v is None else num(v)*1000000] for t,v in zip(days,vals)]
        last=next(p for p in reversed(points) if p[1] is not None)
        asof=last[0]+'T00:00:00+00:00'
        out[coin+'_market_history']=metric(coin+'_market_history',last[1],'USD','PriFi.info / Coin Metrics Community Data',PRI+'history','CC BY-NC 4.0','每日市值，原始单位百万美元，转换为美元',asof,points)
        out[coin+'_market']=metric(coin+'_market',last[1],'USD','PriFi.info / Coin Metrics Community Data',PRI+'history','CC BY-NC 4.0','最近可用日市值，非实时市值',asof)
    c=next(x for x in supply['coins'] if x['id']=='xmr')['supply']
    if c['source'] != 'Coin Metrics': raise ValueError('XMR supply upstream changed; licence needs review')
    out['xmr_supply']=metric('xmr_supply',c['value'],'XMR','PriFi.info / Coin Metrics Community Data',PRI+'supply','CC BY-NC 4.0','Coin Metrics 供应量估计',stamp(c['day']))
    return out
def activity():
    start=(NOW.date()-dt.timedelta(days=365)).isoformat()
    url=CM+'?'+urlencode(dict(assets='xmr,zec',metrics='TxCnt',frequency='1d',start_time=start,page_size=10000))
    d=getjson(url)
    if d.get('next_page_url'): raise ValueError('unexpected pagination')
    out={}
    for coin in ('xmr','zec'):
        points=sorted([[r['time'][:10],num(r['TxCnt'])] for r in d['data'] if r['asset']==coin and r.get('TxCnt') is not None])
        points=daily_gaps(points)
        last=next(p for p in reversed(points) if p[1] is not None)
        out[coin+'_tx']=metric(coin+'_tx',last[1],'笔/日','Coin Metrics Community Data',url,'CC BY-NC 4.0','每日非 Coinbase 链上交易数；不代表人数或隐私交易数',last[0]+'T00:00:00+00:00',points)
    return out
def zcash():
    s=getjson(ZEC+'summary'); p=s['pools']; source=s['sources']['pools']
    if not source['ok'] or source['stale']: raise ValueError('pool source stale or unavailable')
    rows=list(csv.DictReader(io.StringIO(fetch(ZEC+'pools.csv'))))
    out={}
    out['zec_supply']=metric('zec_supply',s['supply']['total'],'ZEC','ZecStats',ZEC+'summary','CC BY 4.0','链上供应量',p['updatedAt'])
    for k,unit,label in [('shieldedTotal','ZEC','四屏蔽池余额之和'),('shieldedPct','%','屏蔽余额占供应比例')]:
        out[k]=metric(k,p[k],unit,'ZecStats',ZEC+'summary','CC BY 4.0',label,p['updatedAt'])
    for pool in ('sprout','sapling','orchard','ironwood'):
        points=daily_gaps([[r['day'],num(r[pool]) if r[pool] else None] for r in rows])
        out[pool]=metric(pool,p[pool],'ZEC','ZecStats',ZEC+'pools.csv','CC BY 4.0','UTC 每日最后观测；当天可能未完成',p['updatedAt'],points)
    return out

GROUPS={'market':prifi,'activity':activity,'pools':zcash}
REQUIRED={'market':{'xmr_market','zec_market','xmr_supply','xmr_market_history','zec_market_history'}, 'activity':{'xmr_tx','zec_tx'}, 'pools':{'zec_supply','shieldedTotal','shieldedPct','sprout','sapling','orchard','ironwood'}}
def validate(name,data,now=None):
    now=now or NOW
    if set(data)!=REQUIRED[name]: raise ValueError('missing or unexpected metrics')
    for key,m in data.items():
        if m['metric_id'] != key or m['data_status'] != 'ok': raise ValueError('invalid metric metadata')
        num(m['value'])
        unit = ('USD' if key.endswith(('_market','_market_history')) else '笔/日' if key.endswith('_tx') else '%' if key=='shieldedPct' else 'XMR' if key=='xmr_supply' else 'ZEC')
        if m['unit'] != unit: raise ValueError(f'{key}: unexpected unit')
        expected_license = 'CC BY 4.0' if name == 'pools' else 'CC BY-NC 4.0'
        expected_source = 'ZecStats' if name == 'pools' else 'Coin Metrics Community Data' if name == 'activity' else 'PriFi.info / Coin Metrics Community Data'
        if m['source_license'] != expected_license or m['source'] != expected_source: raise ValueError('unapproved source or licence')
        date=dt.datetime.fromisoformat(m['data_as_of'].replace('Z','+00:00'))
        if date.tzinfo is None or date > now+dt.timedelta(minutes=10) or now-date>dt.timedelta(days=4): raise ValueError(f'{key}: stale or future data')
        if m['points'] is not None:
            points=m['points']; dates=[x[0] for x in points]
            if not points or dates!=sorted(set(dates)): raise ValueError('invalid history')
            for day,value in points:
                if dt.date.fromisoformat(day)>now.date(): raise ValueError('future history')
                if value is not None: num(value)
            valid=[(day,v) for day,v in points if v is not None]
            if not valid or valid[-1][0] != m['coverage_end']: raise ValueError('invalid coverage')
            if key.endswith(('_tx','_market_history')) and valid[-1][1] != m['value']: raise ValueError('latest value mismatch')
    if name=='market':
        for coin in ('xmr','zec'):
            if (data[coin+'_market']['value'],data[coin+'_market']['data_as_of']) != (data[coin+'_market_history']['value'],data[coin+'_market_history']['data_as_of']): raise ValueError('market and history disagree')
    if name=='activity':
        x,z=data['xmr_tx'],data['zec_tx']
        if (x['coverage_start'],x['coverage_end']) != (z['coverage_start'],z['coverage_end']): raise ValueError('transaction date ranges differ')
    if name=='pools' and data['shieldedPct']['value']>100: raise ValueError('invalid percent')
def business(data):
    if isinstance(data,dict): return {k:business(v) for k,v in data.items() if k not in ('generated_at','fetched_at')}
    if isinstance(data,list): return [business(v) for v in data]
    return data
def atomic_json(path,data):
    text=json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    temp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as f:
            temp=f.name; f.write(text); f.flush(); os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if temp and os.path.exists(temp): os.unlink(temp)
def main():
    OUT.mkdir(parents=True,exist_ok=True); results={}
    for name,fn in GROUPS.items():
        path=OUT/(name+'.json')
        try:
            data=fn(); validate(name,data)
            new={'generated_at':FETCHED,'metrics':data}
            try: old=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,ValueError): old=None
            changed=old is None or business(old)!=business(new)
            if changed: atomic_json(path,new)
            results[name]={'status':'success','changed':changed}; print(name,'success', 'changed' if changed else 'unchanged')
        except Exception as exc:
            results[name]={'status':'failed','changed':False,'error':f'{type(exc).__name__}: {exc}'}
            print(name,'FAILED; previous data retained:',exc,file=sys.stderr)
    success=sum(r['status']=='success' for r in results.values())
    status='success' if success==3 else 'partial' if success else 'failure'
    usable=True
    for name in GROUPS:
        try: validate(name,json.loads((OUT/(name+'.json')).read_text(encoding='utf-8'))['metrics'])
        except Exception as exc:
            usable=False; results[name]['snapshot_error']=f'{type(exc).__name__}: {exc}'
    report={'checked_at':FETCHED,'status':status,'publishable':usable and success>0,'groups':results}
    status_path=pathlib.Path(os.environ.get('DATA_STATUS_PATH',str(OUT.parent.parent/'data-status.json')))
    status_path.parent.mkdir(parents=True,exist_ok=True); atomic_json(status_path,report)
    print(json.dumps(report,ensure_ascii=False))
    return 0 if status=='success' and usable else 2 if status=='partial' and usable else 1
if __name__=='__main__': raise SystemExit(main())
