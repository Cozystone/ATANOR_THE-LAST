"""Frozen one-shot prediction-only revision check, not capability/agency.

Old192 vs old192+ONE actual mispredicted episode6 primitive step1 from sealed
continuous-life receipt. No grammar changes. Four fresh native mixed bodies,
seeds129001..129004,count3..6; empty second alias with first already empty.
All actions supplied diagnostically, not claimed agent-selected experiments.
GO: revised all cells singleton-correct, fewer wrong than frozen, all14208 old
cells retained. No evaluation learning/retry. Reports counts, raw observations.
"""
import json,sys,tempfile,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_conditional_eval import Model
from scripts.developmental_continual_probe import score
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event
from packages.action_core.world import Sandbox,Frame,Action


def run(output):
    if output.exists():raise FileExistsError(output)
    old=[];hashes={}
    for name in ('developmental-continual.json','developmental-online-eval.json','developmental-procedure-life.json'):
        raw=(ROOT/'evidence'/name).read_bytes();hashes[name]=hashlib.sha256(raw).hexdigest()
        if name!='developmental-procedure-life.json':old+=json.loads(raw)['records']
        else:life=json.loads(raw)
    counterexample=next(r for r in life['rows'] if r['ordinal']==6 and r['arm']=='primitive')['trace'][1]
    models={'frozen':Model(old),'revised':Model(old+[counterexample])}
    totals={a:Counter() for a in models};retention={a:Counter() for a in models};rows=[]
    with tempfile.TemporaryDirectory(prefix='atanor_revision_') as root:
        for n in range(4):
            cfg,aliases,ref,payload=configuration(3+n,129001+n,'independent_mixed')
            body=Sandbox(Path(root)/str(n),**cfg);before=body.observe();action=Action('empty',(aliases[1],))
            predictions={a:m.predict(before,action,True) for a,m in models.items()}
            record=event(body,action);after=Frame.from_dict(record['after'])
            for a in models:totals[a].update(score(predictions[a],after))
            assert body._paths[ref].read_bytes()==payload
            rows.append({**record,'predictions':predictions})
    for record in old:
        before,after=[Frame.from_dict(record[k]) for k in ('before','after')];action=Action.from_dict(record['action'])
        for a,m in models.items():retention[a].update(score(m.predict(before,action,True),after))
    passed=set(totals['revised'])=={'correct_singleton'} and totals['revised']['wrong']<totals['frozen']['wrong'] and retention['revised']==retention['frozen']
    result=dict(verdict='PREDICTION_REVISION_PASS' if passed else 'PREDICTION_REVISION_NO_GO',totals=totals,retention=retention,rows=rows,source_sha256=hashes)
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':run(Path(sys.argv[1]))
