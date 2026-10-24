"""Exposed native audit of unsupported initial actions, not agent acquisition.

All missing-support initial actions in the four already-exposed lookahead worlds
are independently executed in scratch copies. These resets are auditor work,
not invented autonomous experience. Outcomes do not train the evaluated model.
"""
import json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_lookahead_probe import adapter
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event
from packages.action_core.world import Sandbox


def run(output):
    old=[]
    for name in ('developmental-continual.json','developmental-online-eval.json'):
        old+=json.loads((ROOT/'evidence'/name).read_text())['records']
    examples=[json.loads((ROOT/'evidence/developmental-composition-probe.json').read_text())['rows'][0]['native_record']]
    examples += [r['record'] for r in json.loads((ROOT/'evidence/developmental-rewrite-scope.json').read_text())['rows'] if r['case'] in ('declared_absent','declared_present')]
    rows=[]
    with tempfile.TemporaryDirectory(prefix='atanor_frontier_audit_') as root:
        for i in range(4):
            cfg,aliases,ref,payload=configuration(3+i%2,115001+i,'coupled_full' if i<2 else 'independent_full')
            cfg={**cfg,'operations':cfg['operations']+[{'id':'rename','arity':2}]}
            template=Sandbox(Path(root)/f'view{i}',**cfg);model=adapter(old,examples,cfg['operations'])
            for n,action in enumerate(template.actions()):
                prediction=model.predict_cells(template.observe(),action)
                if not any(not v for _,_,v in prediction):continue
                body=Sandbox(Path(root)/f'probe{i}_{n}',**cfg);record=event(body,action)
                assert body._paths[ref].read_bytes()==payload
                rows.append({'world':i,'record':record,'changed':record['before']!=record['after']})
    result={'unsupported_actions':len(rows),'native_changed':sum(r['changed'] for r in rows),
            'native_success':sum(r['record']['success'] for r in rows),'rows':rows,
            'scope':'initial states only; scratch native diagnostic, no agent ability or reachable-frontier completeness claim'}
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':run(Path(sys.argv[1]))
