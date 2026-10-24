"""Frozen-history model comparison; no extra action or R10 retry."""
import hashlib,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_conditional_eval import Model
from scripts.representation_r3_dev import configuration
from packages.action_core.world import Sandbox,Action
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.effect_hypotheses import inspect_effects

def run(source,output):
    raw=source.read_bytes();data=json.loads(raw)
    modern=Model(data['records']);legacy=RelationalLearner.restore(data['snapshot'])
    cfg,_,reference,payload=configuration(3,119031); rows=[]
    with tempfile.TemporaryDirectory(prefix='atanor_reinspect_') as root:
        body=Sandbox(Path(root)/'native',**cfg)
        for record in data['records']:
            assert body.observe().to_dict()==record['before']
            assert body.step(Action.from_dict(record['action']))==record['success']
            assert body.observe().to_dict()==record['after']
        for action in body.actions():
            frame=body.observe();cells=modern.predict(frame,action,True)
            rows.append({'action':action.to_dict(),'legacy_status':inspect_effects(legacy,frame,action)['status'],
                         'unknown':sum(not v for _,_,v in cells),
                         'disagreements':[(f,a,v) for f,a,v in cells if len(v)>1]})
        assert body._paths[reference].read_bytes()==payload
    result={'source_sha256':hashlib.sha256(raw).hexdigest(),'rows':rows,
            'actions_with_disagreement':sum(bool(r['disagreements']) for r in rows),
            'scope':'exposed same-history diagnostic; no experiment selected/executed'}
    assert source.read_bytes()==raw
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))

if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
