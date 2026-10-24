"""Frozen exposed-history prequential consolidation diagnostic, not capability.

Source one continuous online lineage from revision-life; nonoverlapping pairs,
unsupported>2role pairs counted/skipped (learner schema limit), no success filter
before prediction. Existing12 historical sequence endpoints seed both models.
Frozen composite vs past-only consolidating composite, both fallback to SAME
old192 primitive model when composite unknown. Actual endpoints ingested ONLY
after scoring, success+continuity required for learning. No primitive learning.
GO: >=20%fewer model calls vs frozen, no more wrong and no less full-correct,
AND total prediction+consolidation CPU<=frozen. Otherwise NO-GO. No repeats/tuning.
Sequences are supplied from old logs, not claimed self-selected/planned afresh.
"""
import json,sys,time,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Frame,Action
from packages.shared_world.trace_procedures import mine,canonical
from packages.shared_world.procedure_effects import endpoints,symbol
from packages.shared_world.epistemic_lookahead import _query_projection
from scripts.developmental_task_eval import Adapter


def forecast(composite,primitive,before,sequence):
    calls=1;pred=composite.predict(before,[symbol(sequence)])[0]
    compressed=pred is not None
    if pred is None:
        current=before
        for action in sequence:
            pred=primitive.predict(current,[action])[0];calls+=1
            if pred is None:break
            current=_query_projection(pred[0])
    return (None if pred is None else _query_projection(pred[0]).to_dict()),calls,compressed


def run(output):
    if output.exists():raise FileExistsError(output)
    historical=json.loads((ROOT/'evidence/developmental-arbitration-v1/file.json').read_text())
    traces=[r['trace'] for r in historical['records'] if r['arm']=='after' and r['success']]
    seed=endpoints(traces,mine(traces));learned=list(seed)
    models={a:Adapter(seed) for a in ('frozen','consolidating')}
    old=[]
    for n in ('developmental-continual.json','developmental-online-eval.json'):old+=json.loads((ROOT/'evidence'/n).read_text())['records']
    primitive=Adapter(old);path=ROOT/'evidence/developmental-revision-life.json';raw=path.read_bytes()
    lived=[s for r in json.loads(raw)['rows'] if r['arm']=='online' for s in r['trace']]
    assert all(a['after']==b['before'] for a,b in zip(lived,lived[1:]))
    totals={a:Counter() for a in models};cpu=Counter();records=[];skipped=0
    for i in range(0,len(lived)-1,2):
        pair=lived[i:i+2];sequence=tuple(Action.from_dict(s['action']) for s in pair)
        if len(set(h for a in sequence for h in a.args))>2:skipped+=1;continue
        before=Frame.from_dict(pair[0]['before']);truth=pair[-1]['after'];row=dict(offset=i,sequence=[a.to_dict() for a in sequence],arms={})
        for arm in models:
            start=time.perf_counter();pred,calls,compressed=forecast(models[arm],primitive,before,sequence);cpu[arm]+=time.perf_counter()-start
            category='correct' if pred==truth else 'unknown' if pred is None else 'wrong'
            totals[arm].update({category:1,'calls':calls,'compressed':int(compressed)})
            row['arms'][arm]=dict(prediction=pred,calls=calls,compressed=compressed,category=category)
        start=time.perf_counter()
        added=endpoints([pair],[(canonical(sequence),1)])
        if added:learned+=added;models['consolidating']=Adapter(learned)
        cpu['consolidating']+=time.perf_counter()-start
        row['training_added_after_prediction']=len(added);records.append(row)
    a,b=totals['consolidating'],totals['frozen']
    passed=a['calls']<=.8*b['calls'] and a['wrong']<=b['wrong'] and a['correct']>=b['correct'] and cpu['consolidating']<=cpu['frozen']
    result=dict(verdict='EXPOSED_CONSOLIDATION_GAIN' if passed else 'NO_EXPOSED_CONSOLIDATION_GAIN',totals=totals,cpu=cpu,rows=records,skipped_arity=skipped,source_sha256=hashlib.sha256(raw).hexdigest())
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':run(Path(sys.argv[1]))
