"""One frozen counterexample-normalized diagnostic; no learner changes or tasks."""
import hashlib
import json
from pathlib import Path
import sys
import time
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.developmental_plastic_world import PlasticWorld
from scripts.developmental_plastic_eval import frame
from scripts.plastic_law_world import LawWorld, SOURCE

COUNTS=(0,1,2,4,8)
LAWS=('null','cascade')


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def witness(seed,n,prefill,law):
    """Two actual databases, no synthetic target generation or learned oracle."""
    a=LawWorld(seed,n,prefill,'restrict');b=LawWorld(seed,n,prefill,law)
    try:
        before=frame(b);assert before==frame(a)
        assert not a.do('delete',0);assert b.do('delete',0)
        old=frame(a);after=frame(b)
        assert old['kinds']!=after['kinds']
        return dict(seed=seed,n=n,prefill=prefill,law=law,before=before,action=[3,0],
                    after=after,old_after=old,
                    changed=[i for i,(x,y) in enumerate(zip(old['kinds'],after['kinds'])) if x!=y])
    finally:a.dispose();b.dispose()


def stable_acquisition(rows,arm,life=None):
    def passing(count):
        data=[r for r in rows if r['arm']==arm and r['count']==count and (life is None or r['life']==life)]
        if sum(r['changed_exact'] for r in data)<.75*len(data):return False
        # Population threshold cannot hide a completely failing life.
        return all(sum(r['changed_exact'] for r in data if r['life']==i)>=.5*sum(r['life']==i for r in data)
                   for i in {r['life'] for r in data})
    return next((c for c in COUNTS if all(passing(d) for d in COUNTS if d>=c)),None)


def classify(fresh,experienced):
    if fresh is None and experienced is None:return 'UNRESOLVED_WITHIN_8'
    if fresh is None:return 'EXPERIENCED_FASTER_WITHIN_BUDGET'
    if experienced is None:return 'EXPERIENCED_SLOWER_WITHIN_BUDGET'
    if experienced<fresh:return 'EXPERIENCED_FASTER_WITHIN_BUDGET'
    if experienced>fresh:return 'EXPERIENCED_SLOWER_WITHIN_BUDGET'
    return 'SAME_OBSERVED_THRESHOLD_NOT_EQUIVALENCE'


def run(out):
    out.mkdir(exist_ok=False)
    checkpoints=[ROOT/f'evidence/developmental-plastic-life-v1/life-{i}-passive-1024.pt' for i in range(4)]
    paths=[SOURCE,Path(__file__),ROOT/'scripts/developmental_plastic_world.py',
           ROOT/'scripts/developmental_plastic_eval.py',ROOT/'scripts/plastic_law_world.py',
           ROOT/'packages/shared_world/sql_schema_sensor.py',
           ROOT/'docs/ATANOR_COUNTEREXAMPLE_V1_PREREGISTRATION.md']+checkpoints
    hashes={str(p):digest(p) for p in paths}
    (out/'attempt.json').write_text(json.dumps(dict(hashes=hashes)),encoding='utf-8')
    start=time.monotonic();probes=[];events=[];stats=[]
    def cap():
        if time.monotonic()-start>600:raise TimeoutError('10min cap, no retry')
    def append(name,row):
        with (out/name).open('a',encoding='utf-8') as f:f.write(json.dumps(row,separators=(',',':'))+'\n')
    for li,law in enumerate(LAWS):
        for life in range(4):
            model_states=torch.load(checkpoints[life],weights_only=True)
            models=dict(fresh=PlasticWorld(610000+life),experienced=PlasticWorld.restore(model_states))
            old_updates={a:m.updates for a,m in models.items()};cpus={a:0. for a in models}
            for a,m in models.items():m.enter_body(4)
            for count in range(9):
                cap()
                if count in COUNTS:
                    for arm,m in models.items():
                        path=out/f'{law}-{life}-{arm}-{count}.pt';torch.save(m.checkpoint(),path)
                        state=torch.load(path,weights_only=True)
                        for q in range(4):
                            w=witness(1050000+li*1000+life*20+q,5+q%2,1+q%3,law)
                            restored=PlasticWorld.restore(state);restored.enter_body(w['n'])
                            p,_=restored.forecasts(w['before'],[w['action']]);p=p[0]
                            # Compare in-memory and reloaded checkpoint forecasts on same body.
                            direct=PlasticWorld.restore(m.checkpoint());direct.enter_body(w['n'])
                            assert torch.equal(p,direct.forecasts(w['before'],[w['action']])[0][0])
                            pred=p.argmax(-1).tolist();truth=w['after']['kinds'];mask=w['changed']
                            row=dict(law=law,life=life,arm=arm,count=count,probe=q,
                                     witness=w,prediction=pred,probabilities=p.tolist(),
                                     changed_exact=all(pred[i]==truth[i] for i in mask),
                                     whole_exact=pred==truth,old_exact=pred==w['old_after']['kinds'],
                                     changed_true_probability=sum(float(p[i,truth[i]]) for i in mask)/len(mask))
                            probes.append(row);append('probes.jsonl',row)
                        stats.append(dict(law=law,life=life,arm=arm,count=count,
                                          updates=m.updates-old_updates[arm],cpu_seconds=cpus[arm],
                                          checkpoint_sha256=digest(path)))
                if count==8:break
                w=witness(1040000+li*1000+life*20+count,4,1+count%3,law)
                row=dict(law=law,life=life,ordinal=count+1,witness=w)
                for arm,m in models.items():
                    # Each trial is a new body, not a hidden unrecorded state reset.
                    m.enter_body(4);cpu=time.process_time()
                    m.learn(w['before'],w['action'],w['after']);cpus[arm]+=time.process_time()-cpu
                events.append(row);append('events.jsonl',row)
    # Verify every training and probe witness independently against rebuilt native DBs.
    all_witnesses=[r['witness'] for r in events]+[r['witness'] for r in probes]
    for w in all_witnesses:
        cap();assert witness(w['seed'],w['n'],w['prefill'],w['law'])==w
    summaries=[];outcomes={}
    for law in LAWS:
        rows=[r for r in probes if r['law']==law]
        for count in COUNTS:
            for arm in models:
                data=[r for r in rows if r['count']==count and r['arm']==arm]
                summaries.append(dict(law=law,count=count,arm=arm,denominator=len(data),
                    changed_correct=sum(r['changed_exact'] for r in data),
                    whole_correct=sum(r['whole_exact'] for r in data),old_correct=sum(r['old_exact'] for r in data),
                    mean_changed_true_probability=sum(r['changed_true_probability'] for r in data)/len(data)))
        acquisition={a:stable_acquisition(rows,a) for a in models}
        per_life=[{a:stable_acquisition(rows,a,i) for a in models} for i in range(4)]
        outcomes[law]=dict(acquisition=acquisition,classification=classify(**acquisition),per_life=per_life)
    intact=all(digest(Path(p))==h for p,h in hashes.items());assert intact
    report=dict(status='DIAGNOSTIC_COMPLETE',outcomes=outcomes,summaries=summaries,stats=stats,
                actual_counterexamples=len(events),probe_rows=len(probes),native_witnesses_reverified=len(all_witnesses),
                source_unchanged=intact,restart_forecasts_equal=True,hashes=hashes,wall_seconds=time.monotonic()-start,
                scope='Directed actual counterexamples, observed-grid stability only; not autonomous discovery or meta-learning proof')
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','outcomes','summaries','wall_seconds')}))


if __name__=='__main__':run(Path(sys.argv[1]))
