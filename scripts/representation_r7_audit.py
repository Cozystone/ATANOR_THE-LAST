"""Post-hoc R6 diagnosis; never trains on or changes the sealed test results."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Action,Sandbox
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.effect_hypotheses import inspect_effects

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--rows',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();raw=args.rows.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='ca5f8415449d9e97560d7e1112d95742f9bfd51d1401f99195080faf747234c9'
    root=Path(tempfile.mkdtemp(prefix='atanor_r7_posthoc_'));records=[];counts=Counter()
    for row in map(json.loads,raw.splitlines()):
        if row['arm']!='lookahead':continue
        model=RelationalLearner.restore(row['learner_snapshot']);original=model.snapshot()
        for ti,task in enumerate(row['tasks']):
            if task['collective'] or task['success']:continue
            cfg=json.loads(json.dumps(task['config']));cfg['initial']={k:bytes.fromhex(v) for k,v in cfg['initial'].items()}
            reference=cfg['paths'][int(cfg['protected'][0][1:])]
            target=next(k for k in cfg['initial'] if k!=reference);handle=f'n{cfg["paths"].index(target)}'
            body=Sandbox(root/f'{row["block"]}_{ti}',**cfg);body.step(Action('unlink',(handle,)))
            report=inspect_effects(model,body.observe(),Action('empty',(handle,)))
            counts[report['status']]+=1
            records.append({'block':row['block'],'task':ti,'report':report})
        assert model.snapshot()==original
    result={'scope':'Post-hoc diagnosis, no repair or capability claim','counts':dict(counts),
            'rows_sha256':hashlib.sha256(raw).hexdigest(),'records':records}
    with args.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({'counts':dict(counts),'scope':result['scope']},indent=2))
