import copy, datetime as dt, importlib.util, json, os, pathlib, tempfile, unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('updater',ROOT/'scripts/update_data.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.out=pathlib.Path(self.temp.name)/'public'/'data'; self.out.mkdir(parents=True)
        self.status=pathlib.Path(self.temp.name)/'status.json'
        self.original={}
        for group in m.GROUPS:
            text=(ROOT/'public'/'data'/f'{group}.json').read_text(); (self.out/f'{group}.json').write_text(text)
            self.original[group]=json.loads(text)['metrics']
        snapshot_now=max(dt.datetime.fromisoformat(item['data_as_of'].replace('Z','+00:00')) for group in self.original.values() for item in group.values())+dt.timedelta(hours=1)
        self.patches=[patch.object(m,'OUT',self.out),patch.object(m,'NOW',snapshot_now),patch.dict(os.environ,{'DATA_STATUS_PATH':str(self.status)})]
        for p in self.patches: p.start(); self.addCleanup(p.stop)
    def run_case(self, failures=(), invalid=None, empty=False):
        funcs={}
        for group in self.original:
            data=copy.deepcopy(self.original[group])
            # Make a meaningful change in each successful group.
            key=next(iter(data)); data[key]['methodology']+=' test'
            if group in failures: funcs[group]=lambda: (_ for _ in ()).throw(OSError('simulated outage'))
            elif invalid and group==invalid[0]:
                def bad(data=data,kind=invalid[1]):
                    if kind=='schema': return {'bad':{}}
                    if kind=='empty': data['xmr_tx']['points']=[]
                    if kind=='stale': data['xmr_tx']['data_as_of']='2020-01-01T00:00:00Z'
                    return data
                funcs[group]=bad
            else: funcs[group]=lambda data=data:data
        before={g:(self.out/f'{g}.json').read_bytes() for g in funcs}
        if empty:
            for g in funcs: (self.out/f'{g}.json').unlink()
        with patch.object(m,'GROUPS',funcs): code=m.main()
        report=json.loads(self.status.read_text())
        for group in failures:
            if not empty: self.assertEqual(before[group],(self.out/f'{group}.json').read_bytes())
        return code,report,before
    def test_all_success(self):
        code,r,_=self.run_case(); self.assertEqual((code,r['status'],r['publishable']),(0,'success',True))
    def test_each_source_failure(self):
        for group in ('market','activity','pools'):
            with self.subTest(group=group):
                for g,data in self.original.items():
                    (self.out/f'{g}.json').write_text(json.dumps({'generated_at':m.FETCHED,'metrics':data},ensure_ascii=False))
                code,r,before=self.run_case((group,)); self.assertEqual((code,r['status'],r['publishable']),(2,'partial',True))
                self.assertTrue(any((self.out/f'{g}.json').read_bytes()!=before[g] for g in before if g!=group))
    def test_all_fail(self):
        code,r,_=self.run_case(tuple(self.original)); self.assertEqual((code,r['status'],r['publishable']),(1,'failure',False))
    def test_bad_structure_empty_and_stale(self):
        for kind in ('schema','empty','stale'):
            with self.subTest(kind=kind):
                before=(self.out/'activity.json').read_bytes(); code,r,_=self.run_case(invalid=('activity',kind)); self.assertEqual(code,2); self.assertEqual(before,(self.out/'activity.json').read_bytes()); self.assertEqual(r['groups']['activity']['status'],'failed')
    def test_clean_directory_with_source_failure(self):
        code,r,_=self.run_case(('market',),empty=True); self.assertEqual(code,1); self.assertFalse(r['publishable'])
    def test_clean_directory_success(self):
        code,r,_=self.run_case(empty=True); self.assertEqual(code,0); self.assertTrue(r['publishable'])
    def test_no_business_changes(self):
        funcs={g:(lambda d=copy.deepcopy(data):d) for g,data in self.original.items()}
        before={g:(self.out/f'{g}.json').read_bytes() for g in funcs}
        with patch.object(m,'GROUPS',funcs): self.assertEqual(m.main(),0)
        self.assertTrue(all((self.out/f'{g}.json').read_bytes()==before[g] for g in funcs))
    def test_source_parser_http200_bad_schema(self):
        with patch.object(m,'getjson',return_value={'data':{}}):
            with self.assertRaises((KeyError,StopIteration)): m.prifi()
    def test_null_gap(self):
        self.assertEqual(m.daily_gaps([['2026-01-01',2],['2026-01-03',3]])[1],['2026-01-02',None])
if __name__=='__main__': unittest.main()
