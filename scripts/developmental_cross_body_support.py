"""Exposed transfer feasibility audit, not native task or transfer achievement.

Read the sealed continuing file-life checkpoint, retain all203 real records.
Compare cold vs warm models on the first16 existing SQL observations, predicting
BEFORE each same target record is learned. Also inspect exact lookup-key overlap
across all192SQL records. No sensor/operation relabeling or world-ID router.
"""
import hashlib,json,sqlite3,sys
from collections import Counter
from contextlib import closing
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_effect_families import EffectFamilies
from scripts.developmental_continual_probe import score
from scripts.developmental_rooted_probe import rooted,cells
from packages.shared_world.index_rewrite import signature,fields
from packages.shared_world.contextual_rewrite import context
from packages.action_core.world import Frame,Action


def run(output):
    source=ROOT/'evidence/developmental-exploring-life-v1/online.sqlite'
    target=ROOT/'evidence/developmental-fk-schema-tasks.json'
    with closing(sqlite3.connect('file:'+source.as_posix()+'?mode=ro&immutable=1',uri=True)) as db:
        checkpoint=json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])['model']
    records=json.loads(target.read_text())['training']
    prior=EffectFamilies(checkpoint['records']); local=set();structural=set()
    for record in records:
        frame=Frame.from_dict(record['before']);action=Action.from_dict(record['action'])
        local.update(rooted(frame,action,f,a)[0] for f,a in cells(frame))
        key,args=signature(frame,action);names,_=context(frame,args)
        structural.update((key,names,name) for name in fields(frame))
    models={'cold':EffectFamilies([]),'warm':prior};totals={a:Counter() for a in models};rows=[]
    for i,record in enumerate(records[:16]):
        before=Frame.from_dict(record['before']);after=Frame.from_dict(record['after']);action=Action.from_dict(record['action'])
        predictions={a:m.predict(before,action) for a,m in models.items()}
        scores={a:dict(score(p,after)) for a,p in predictions.items()}
        rows.append(dict(index=i,same_predictions=predictions['cold']==predictions['warm'],scores=scores))
        for a,m in models.items():totals[a].update(scores[a]);m.learn([record])
    result=dict(scope=__doc__,source_records=len(checkpoint['records']),target_records=len(records),
        local_target_keys=len(local),local_overlap=len(local & set(prior.local.rules)),
        # prior was updated in-place above; report overlap against untouched source!
        rows=rows,totals=totals,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        target_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    untouched=EffectFamilies(checkpoint['records'])
    result.update(local_overlap=len(local & set(untouched.local.rules)),
        structural_target_keys=len(structural),structural_overlap=len(structural & set(untouched.structural.rules)))
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k not in ('scope','rows')}))
    print('same_prefix_predictions',sum(r['same_predictions'] for r in rows),len(rows))


if __name__=='__main__':run(Path(sys.argv[1]))
