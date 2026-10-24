"""Frozen finite-law panel, not an unbiased distribution of all possible laws."""
import json
from pathlib import Path
import random
import statistics
import sys
import time
import torch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.plasticity_law_suite import NEW_LAWS,LAWS,case
from scripts.adaptation_pair_isolation import compose,digest
from scripts.developmental_plastic_world import PlasticWorld
from scripts.developmental_plastic_eval import frame
from scripts.plastic_law_world import LawWorld,native,SOURCE

COUNTS=(0,1,2,4,8,16)
ARMS=('fresh','weights_adam')


def acquire(rows,law,arm,life=None):
    result=None
    for count in reversed(COUNTS):
        q=[r for r in rows if (r['law'],r['arm'],r['count'])==(law,arm,count) and (life is None or r['life']==life)]
        if not q or sum(r['whole_exact'] for r in q)<.75*len(q):break
        if any(sum(r['whole_exact'] for r in q if r['life']==i)<.5*sum(r['life']==i for r in q) for i in {r['life'] for r in q}):break
        result=count
    return result


def evaluate_gates(rows):
    costs={a:{law:[acquire(rows,law,a,i) for i in range(8)] for law in NEW_LAWS} for a in ARMS}
    capped=lambda x:17 if x is None else x
    flat={a:[capped(c) for values in costs[a].values() for c in values] for a in ARMS}
    means={a:statistics.mean(flat[a]) for a in ARMS};medians={a:statistics.median(flat[a]) for a in ARMS}
    lawmeans={law:{a:statistics.mean(capped(v) for v in costs[a][law]) for a in ARMS} for law in NEW_LAWS}
    severe=lambda f,e:e>2*f and e-f>=4
    negative=sum(severe(f,e) for f,e in zip(flat['fresh'],flat['weights_adam']))
    retention={}
    for law in NEW_LAWS:
        retention[law]={c:statistics.mean(r['common_correct']/r['common_count'] for r in rows if (r['law'],r['arm'],r['count'])==(law,'weights_adam',c)) for c in (0,16)}
    before=statistics.mean(v[0] for v in retention.values());after=statistics.mean(v[16] for v in retention.values())
    improved_lives=sum(statistics.mean(capped(costs['weights_adam'][law][i]) for law in NEW_LAWS)<statistics.mean(capped(costs['fresh'][law][i]) for law in NEW_LAWS) for i in range(8))
    gates=dict(mean_gain=means['weights_adam']<=.8*means['fresh'],
        median_gain=medians['weights_adam']<=.75*medians['fresh'],
        four_laws=sum(m['weights_adam']<m['fresh'] for m in lawmeans.values())>=4,
        six_histories=improved_lives>=6,severe_pairs=negative<=4,
        no_severe_law=not any(severe(m['fresh'],m['weights_adam']) for m in lawmeans.values()),
        retention_nonvacuous=before>=.8,retention_macro=after>=before-.05,
        retention_each=all(v[16]>=v[0]-.1 for v in retention.values()))
    return dict(gates=gates,costs=costs,means=means,medians=medians,lawmeans=lawmeans,
                severe_negative_pairs=negative,improved_histories=improved_lives,retention=retention)


def run(out):
    out.mkdir(exist_ok=False)
    paths=[Path(__file__),SOURCE,ROOT/'scripts/plasticity_law_suite.py',ROOT/'scripts/adaptation_pair_isolation.py',
        ROOT/'scripts/developmental_plastic_world.py',ROOT/'scripts/developmental_plastic_eval.py',
        ROOT/'scripts/plastic_law_world.py',ROOT/'packages/shared_world/sql_schema_sensor.py',
        ROOT/'docs/ATANOR_DEVELOPMENTAL_PLASTICITY_V1_PREREGISTRATION.md']
    hashes={str(p):digest(p) for p in paths};start=time.monotonic()
    (out/'attempt.json').write_text(json.dumps(dict(hashes=hashes)),encoding='utf-8')
    rows=[];catalog={};a_verified=0
    def cap():
        if time.monotonic()-start>1200:raise TimeoutError('20min cap, no retry')
    def save(name,row):
        with (out/name).open('a',encoding='utf-8') as f:f.write(json.dumps(row,separators=(',',':'))+'\n')
    def get(law,seed,n):
        key=f'{law}:{seed}:{n}'
        if key not in catalog:
            cap();catalog[key]=case(law,seed,n);save('cases.jsonl',dict(id=key,data=catalog[key]))
        return key,catalog[key]
    for life in range(8):
        seed=830200+life;model=PlasticWorld(seed);model.enter_body(4)
        body=LawWorld(seed,4,2,'restrict');rng=random.Random(seed+100);trace=[]
        actions=[[o,i] for o in range(4) for i in range(4)]
        try:
            for step in range(1024):
                cap();before=frame(body);action=rng.choice(actions)
                accepted=bool(body.do(native.FK_ACTIONS[action[0]],action[1]));after=frame(body)
                model.learn(before,action,after);trace.append(dict(before=before,action=action,accepted=accepted,after=after))
        finally:body.dispose()
        old=model.checkpoint();torch.save(old,out/f'A-{life}.pt');save('A_life.jsonl',dict(life=life,seed=seed,events=trace))
        replay=LawWorld(seed,4,2,'restrict')
        try:
            for e in trace:
                assert frame(replay)==e['before'];assert bool(replay.do(native.FK_ACTIONS[e['action'][0]],e['action'][1]))==e['accepted']
                assert frame(replay)==e['after'];a_verified+=1
        finally:replay.dispose()
        for li,law in enumerate(LAWS):
            states=compose(old);models={a:PlasticWorld.restore(states[a]) for a in ARMS}
            for m in models.values():m.enter_body(4)
            for count in range(17):
                cap()
                if count in COUNTS:
                    for arm,m in models.items():
                        path=out/f'{law}-{life}-{arm}-{count}.pt';torch.save(m.checkpoint(),path)
                        restored=torch.load(path,weights_only=True)
                        for q in range(4):
                            key,c=get(law,1250000+li*10000+life*40+q,5+q%2)
                            clone=PlasticWorld.restore(restored);clone.enter_body(c['n'])
                            probabilities=clone.forecasts(c['before'],c['actions'])[0]
                            direct=PlasticWorld.restore(m.checkpoint());direct.enter_body(c['n'])
                            assert torch.equal(probabilities,direct.forecasts(c['before'],c['actions'])[0])
                            predicted=probabilities.argmax(-1).tolist();idx=c['primary'];truth=c['new'][idx]['after']['kinds']
                            row=dict(law=law,life=life,arm=arm,count=count,probe=q,case_id=key,
                                predictions=predicted,primary_probabilities=probabilities[idx].tolist(),
                                changed_exact=all(predicted[idx][i]==truth[i] for i in c['changed']),
                                whole_exact=predicted[idx]==truth,
                                common_correct=sum(predicted[i]==c['new'][i]['after']['kinds'] for i in c['common']),common_count=len(c['common']))
                            rows.append(row);save('probes.jsonl',row)
                if count==16:break
                key,c=get(law,1240000+li*10000+life*40+count,4);idx=c['primary']
                for m in models.values():m.enter_body(4);m.learn(c['before'],c['actions'][idx],c['new'][idx]['after'])
                save('events.jsonl',dict(law=law,life=life,ordinal=count+1,case_id=key))
        print(json.dumps(dict(completed_life=life,seconds=time.monotonic()-start)),flush=True)
    for c in catalog.values():cap();assert c==case(c['law'],c['seed'],c['n'])
    metrics=evaluate_gates(rows);assert all(digest(Path(p))==h for p,h in hashes.items())
    outcomes={law:{a:acquire(rows,law,a) for a in ARMS} for law in LAWS}
    summaries=[]
    for law in LAWS:
        for a in ARMS:
            for count in COUNTS:
                q=[r for r in rows if (r['law'],r['arm'],r['count'])==(law,a,count)]
                summaries.append(dict(law=law,arm=a,count=count,n=len(q),whole=sum(r['whole_exact'] for r in q),
                    changed=sum(r['changed_exact'] for r in q),common=sum(r['common_correct'] for r in q),common_n=sum(r['common_count'] for r in q)))
    report=dict(verdict='BOUNDED_PANEL_PASS' if all(metrics['gates'].values()) else 'PLASTICITY_NO_GO',
        metrics=metrics,outcomes=outcomes,summaries=summaries,hashes=hashes,source_unchanged=True,restart_equal=True,
        actual_A_reverified=a_verified,unique_native_cases_reverified=len(catalog),probe_rows=len(rows),
        wall_seconds=time.monotonic()-start,scope='Six curated unseen SQL laws; two exposed controls excluded from gates; not universal law distribution')
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('verdict','metrics','outcomes','wall_seconds')}),flush=True)


if __name__=='__main__':run(Path(sys.argv[1]))
