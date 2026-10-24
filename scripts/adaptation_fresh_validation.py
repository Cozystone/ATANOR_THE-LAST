"""Conditional fresh-history validation; design frozen before pair outcomes."""
import json
from pathlib import Path
import random
import sys
import time
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.adaptation_pair_isolation import compose, digest
from scripts.counterexample_adaptation_eval import COUNTS, LAWS, witness, stable_acquisition
from scripts.developmental_plastic_world import PlasticWorld
from scripts.developmental_plastic_eval import frame
from scripts.plastic_law_world import LawWorld, SOURCE, native


def choose(report):
    for arm in ('weights_adam','weights_replay'):
        a=report['outcomes']['null'][arm];b=report['outcomes']['cascade'][arm]
        if a['acquisition'] is not None and a['acquisition']<=4 and all(x is not None and x<=4 for x in a['per_life']) and b['acquisition'] is not None and b['acquisition']<=4:
            return arm
    raise ValueError('no pair qualified; no fresh validation authorized by protocol')


def verdicts(outcomes,summaries,selected):
    n=outcomes['null'];c=outcomes['cascade']
    f=n['fresh']['acquisition'];s=n[selected]['acquisition']
    sf=n[selected]['per_life'];ff=n['fresh']['per_life']
    def faster(a,b):return a is not None and (b is None or a<b)
    def notslower(a,b):return b is None or (a is not None and a<=b)
    gates=dict(null_fast=s is not None and s<=4,
               fresh_not_before8=f is None or f>=8,
               six_of_eight=sum(faster(a,b) for a,b in zip(sf,ff))>=6,
               no_life_slower=all(notslower(a,b) for a,b in zip(sf,ff)),
               cascade_noninferior=all(c[a]['acquisition'] is not None for a in ('fresh','full',selected)) and
                   all(c[selected]['acquisition']<=c[a]['acquisition'] for a in ('fresh','full')))
    def whole(law,arm):return next(x['whole_correct'] for x in summaries if (x['law'],x['arm'],x['count'])==(law,arm,8))
    gates['whole_noninferior']=all(whole(law,selected)>=whole(law,'fresh') for law in LAWS)
    return gates


def run(out):
    pair=ROOT/'evidence/developmental-pair-isolation-v1/report.json'
    selected=choose(json.loads(pair.read_text()));arms=('fresh','full',selected)
    out.mkdir(exist_ok=False)
    paths=[Path(__file__),pair,SOURCE,ROOT/'scripts/adaptation_pair_isolation.py',
           ROOT/'scripts/counterexample_adaptation_eval.py',ROOT/'scripts/developmental_plastic_world.py',
           ROOT/'scripts/developmental_plastic_eval.py',ROOT/'scripts/plastic_law_world.py',
           ROOT/'packages/shared_world/sql_schema_sensor.py',ROOT/'docs/ATANOR_PAIR_ISOLATION_V1_PREREGISTRATION.md']
    hashes={str(p):digest(p) for p in paths}
    (out/'attempt.json').write_text(json.dumps(dict(selected=selected,hashes=hashes)),encoding='utf-8')
    start=time.monotonic();rows=[];events=[];verified_a=0
    def cap():
        if time.monotonic()-start>600:raise TimeoutError('10min cap; no retry')
    def append(name,row):
        with (out/name).open('a',encoding='utf-8') as f:f.write(json.dumps(row,separators=(',',':'))+'\n')
    for life in range(8):
        seed=810100+life;m=PlasticWorld(seed);m.enter_body(4)
        body=LawWorld(seed,4,2,'restrict');rng=random.Random(seed+100)
        allowed=[[op,i] for op in range(4) for i in range(4)];atrace=[]
        try:
            for step in range(1024):
                cap();before=frame(body);action=rng.choice(allowed)
                accepted=bool(body.do(native.FK_ACTIONS[action[0]],action[1]));after=frame(body)
                m.learn(before,action,after)
                atrace.append(dict(before=before,action=action,accepted=accepted,after=after))
        finally:body.dispose()
        old=m.checkpoint();torch.save(old,out/f'A-{life}.pt');append('A_life.jsonl',dict(life=life,seed=seed,events=atrace))
        replay=LawWorld(seed,4,2,'restrict')
        try:
            for e in atrace:
                assert frame(replay)==e['before']
                assert bool(replay.do(native.FK_ACTIONS[e['action'][0]],e['action'][1]))==e['accepted']
                assert frame(replay)==e['after'];verified_a+=1
        finally:replay.dispose()
        for li,law in enumerate(LAWS):
            states=compose(old);models={a:PlasticWorld.restore(states[a]) for a in arms}
            for model in models.values():model.enter_body(4)
            for count in range(9):
                cap()
                if count in COUNTS:
                    for arm,model in models.items():
                        path=out/f'{law}-{life}-{arm}-{count}.pt';torch.save(model.checkpoint(),path)
                        saved=torch.load(path,weights_only=True)
                        for q in range(4):
                            w=witness(1150000+li*1000+life*20+q,5+q%2,1+q%3,law)
                            clone=PlasticWorld.restore(saved);clone.enter_body(w['n'])
                            p=clone.forecasts(w['before'],[w['action']])[0][0]
                            direct=PlasticWorld.restore(model.checkpoint());direct.enter_body(w['n'])
                            assert torch.equal(p,direct.forecasts(w['before'],[w['action']])[0][0])
                            pred=p.argmax(-1).tolist();truth=w['after']['kinds']
                            row=dict(law=law,life=life,arm=arm,count=count,probe=q,witness=w,
                                prediction=pred,probabilities=p.tolist(),
                                changed_exact=all(pred[i]==truth[i] for i in w['changed']),whole_exact=pred==truth)
                            rows.append(row);append('probes.jsonl',row)
                if count==8:break
                w=witness(1140000+li*1000+life*20+count,4,1+count%3,law)
                for model in models.values():model.enter_body(4);model.learn(w['before'],w['action'],w['after'])
                row=dict(law=law,life=life,ordinal=count+1,witness=w);events.append(row);append('events.jsonl',row)
        print(json.dumps(dict(completed_new_life=life,seconds=time.monotonic()-start)),flush=True)
    unique={json.dumps(r['witness'],sort_keys=True):r['witness'] for r in rows+events}
    for w in unique.values():cap();assert w==witness(w['seed'],w['n'],w['prefill'],w['law'])
    summaries=[];outcomes={}
    for law in LAWS:
        q=[r for r in rows if r['law']==law]
        outcomes[law]={a:dict(acquisition=stable_acquisition(q,a),per_life=[stable_acquisition(q,a,i) for i in range(8)]) for a in arms}
        for a in arms:
            for c in COUNTS:
                values=[r for r in q if r['arm']==a and r['count']==c]
                summaries.append(dict(law=law,arm=a,count=c,denominator=len(values),changed_correct=sum(r['changed_exact'] for r in values),whole_correct=sum(r['whole_exact'] for r in values)))
    gates=verdicts(outcomes,summaries,selected)
    assert all(digest(Path(p))==h for p,h in hashes.items())
    report=dict(verdict='FRESH_HISTORY_VALIDATION_PASS' if all(gates.values()) else 'VALIDATION_NO_GO',
                selected=selected,gates=gates,outcomes=outcomes,summaries=summaries,hashes=hashes,
                source_unchanged=True,restart_equal=True,native_A_verified=verified_a,native_B_unique_verified=len(unique),
                probe_rows=len(rows),actual_new_counterexamples=len(events),wall_seconds=time.monotonic()-start,
                scope='New initializations/A histories in same related native-law family; not new mechanism')
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('verdict','selected','gates','outcomes','wall_seconds')}))


if __name__=='__main__':run(Path(sys.argv[1]))
