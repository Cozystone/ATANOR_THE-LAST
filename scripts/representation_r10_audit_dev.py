"""Replay the existing DEV transcript; never select a new acquisition or retry."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Action
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.effect_hypotheses import inspect_effects
from scripts.representation_r3_dev import configuration


def audit(source,output):
    raw=source.read_bytes(); data=json.loads(raw)
    records=data['records']; rows=data['snapshot']['rows']
    assert len(records)==len(rows)==data['snapshot']['revision']==6
    assert all(all(record[k]==row[k] for k in ('before','action','after')) and row['history']==[]
               for record,row in zip(records,rows))
    cfg,_,ref,payload=configuration(3,119031)
    with tempfile.TemporaryDirectory(prefix='atanor_r10_audit_') as root:
        body=Sandbox(Path(root)/'native',**cfg)
        for record in records:
            assert body.observe().to_dict()==record['before']
            assert body.step(Action.from_dict(record['action']))==record['success']
            assert body.observe().to_dict()==record['after']
            assert body._paths[ref].read_bytes()==payload
        # Read-only post-result diagnosis on the already observed final state.
        model=RelationalLearner.restore(data['snapshot']);statuses={}
        for action in body.actions():
            status=inspect_effects(model,body.observe(),action)['status']
            statuses[status]=statuses.get(status,0)+1
    assert data['actions']==6 and data['eliminated_candidates']==0
    result={'replay':'PASS','actual_only_snapshot':'PASS','native_steps':6,
            'source_sha256':hashlib.sha256(raw).hexdigest(),'final_state_status_counts':statuses,
            'scope':'native transcript reexecution; uses existing body/model, not independent external judge',
            'new_acquisition_or_fresh_trial':False}
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,indent=2)
    print(json.dumps(result))


if __name__=='__main__':audit(Path(sys.argv[1]),Path(sys.argv[2]))
