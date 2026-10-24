"""One-shot DEV falsification, not another capability benchmark.

Frozen cases: flat/occupied/missing-source/directory-source/same-argument,
unequal-content/empty-source, and absent/present destination parent either hidden
or declared. One trained example, no adaptation; any wrong singleton blocks broad
use. Native parent creation in hidden-present is explicit evaluator preparation,
not learner experience. Compare identical sensor views with different outcomes.
"""
import json,sys,tempfile,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Frame,Action
from packages.shared_world.index_rewrite import IndexRewrite
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event
from scripts.developmental_continual_probe import score


def run(output):
    raw=(ROOT/'evidence/developmental-composition-probe.json').read_bytes()
    example=json.loads(raw)['rows'][0]['native_record'];model=IndexRewrite([example]);rows=[]
    cases=('flat','occupied','missing_source','directory_source','same_argument',
           'unequal_content','empty_source','hidden_absent','hidden_present','declared_absent','declared_present')
    with tempfile.TemporaryDirectory(prefix='atanor_rewrite_scope_') as root:
        for index,case in enumerate(cases):
            cfg,aliases,ref,payload=configuration(4,111001,'detached_absent')
            cfg={**cfg,'initial':dict(cfg['initial']),'paths':list(cfg['paths']),
                 'operations':cfg['operations']+[{'id':'rename','arity':2}]}
            dest,source=(cfg['paths'][int(h[1:])] for h in aliases[:2])
            if case=='occupied':cfg['initial'][dest]=b'different'
            if case in ('missing_source','directory_source'):
                cfg['initial_links']={};cfg['initial'].pop(source)
                if case=='directory_source':cfg['initial'][source]=None
            if case=='unequal_content':
                cfg['initial_links']={}
                for i,h in enumerate(aliases[2:]):cfg['initial'][cfg['paths'][int(h[1:])]]=bytes([i+9])*(i+7)
            if case=='empty_source':cfg['initial'][source]=b''
            if case.startswith(('hidden_','declared_')):
                cfg['paths'][int(aliases[0][1:])]='container/'+dest
                if case.startswith('declared_'):
                    cfg['paths'].append('container')
                    if case.endswith('present'):cfg['initial']['container']=None
            body=Sandbox(Path(root)/str(index),**cfg)
            if case=='hidden_present':(body.root/'container').mkdir()
            action=Action('rename',(aliases[1],aliases[1] if case=='same_argument' else aliases[0]))
            before=body.observe();prediction=model.predict(before,action)
            rejected=False
            try:record=event(body,action)
            except ValueError:
                rejected=True;record={'before':before.to_dict(),'after':body.observe().to_dict(),'action':action.to_dict(),'success':False}
            counts=score(prediction,Frame.from_dict(record['after']))
            rows.append({'case':case,'record':record,'prediction':prediction,'counts':counts,'schema_rejected':rejected})
            assert body._paths[ref].read_bytes()==payload
    a,b=(next(r for r in rows if r['case']==case) for case in ('hidden_absent','hidden_present'))
    alias=(a['record']['before']==b['record']['before'] and a['record']['action']==b['record']['action']
           and a['record']['after']!=b['record']['after'])
    wrong=sum(r['counts'].get('wrong',0) for r in rows)
    result={'verdict':'SCOPE_FALSIFIED' if wrong else 'BOUNDED_PROBE_CLEAR','wrong_cells':wrong,
            'sensor_alias_witness':alias,'source_sha256':hashlib.sha256(raw).hexdigest(),'rows':rows}
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
    print(json.dumps([{'case':r['case'],'counts':r['counts'],'rejected':r['schema_rejected']} for r in rows]))


if __name__=='__main__':run(Path(sys.argv[1]))
