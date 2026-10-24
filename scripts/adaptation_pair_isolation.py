"""Diagnostic state interventions only; original learner code stays immutable."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.developmental_plastic_world import PlasticWorld
from scripts.counterexample_adaptation_eval import COUNTS, LAWS, witness, stable_acquisition
from scripts.plastic_law_world import SOURCE

ARMS=('fresh','full','weights_adam','weights_replay')


def compose(old):
    fresh=PlasticWorld(old['config']['seed']).checkpoint()
    states={a:copy.deepcopy(fresh) for a in ARMS}
    states['full']=copy.deepcopy(old)
    for a in ('weights_adam','weights_replay'):
        states[a]['models']=copy.deepcopy(old['models'])
    states['weights_adam']['optimizers']=copy.deepcopy(old['optimizers'])
    states['weights_replay']['replay']=copy.deepcopy(old['replay'])
    states['weights_replay']['rng']=copy.deepcopy(old['rng'])
    return states


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run(out):
    out.mkdir(exist_ok=False)
    previous=ROOT/'evidence/developmental-counterexample-v1/probes.jsonl'
    checkpoints=[ROOT/f'evidence/developmental-plastic-life-v1/life-{i}-passive-1024.pt' for i in range(4)]
    paths=[Path(__file__),SOURCE,previous,ROOT/'scripts/developmental_plastic_world.py',
           ROOT/'scripts/counterexample_adaptation_eval.py',ROOT/'scripts/developmental_plastic_eval.py',
           ROOT/'scripts/plastic_law_world.py',ROOT/'packages/shared_world/sql_schema_sensor.py',
           ROOT/'docs/ATANOR_PAIR_ISOLATION_V1_PREREGISTRATION.md']+checkpoints
    hashes={str(p):digest(p) for p in paths}
    (out/'attempt.json').write_text(json.dumps(dict(hashes=hashes)),encoding='utf-8')
    reference={tuple(r[k] for k in ('law','life','arm','count','probe')):r for r in
               [json.loads(s) for s in previous.read_text().splitlines()]}
    start=time.monotonic();rows=[];events=[];stats=[];controls=0
    def cap():
        if time.monotonic()-start>600:raise TimeoutError('10min cap; no retry')
    def append(name,row):
        with (out/name).open('a',encoding='utf-8') as f:f.write(json.dumps(row,separators=(',',':'))+'\n')
    for li,law in enumerate(LAWS):
        for life in range(4):
            old=torch.load(checkpoints[life],weights_only=True)
            models={a:PlasticWorld.restore(s) for a,s in compose(old).items()}
            initial_updates={a:m.updates for a,m in models.items()}
            for m in models.values():m.enter_body(4)
            for count in range(9):
                cap()
                if count in COUNTS:
                    for arm,m in models.items():
                        path=out/f'{law}-{life}-{arm}-{count}.pt';torch.save(m.checkpoint(),path)
                        saved=torch.load(path,weights_only=True)
                        for q in range(4):
                            w=witness(1050000+li*1000+life*20+q,5+q%2,1+q%3,law)
                            probe=PlasticWorld.restore(saved);probe.enter_body(w['n'])
                            p=probe.forecasts(w['before'],[w['action']])[0][0]
                            direct=PlasticWorld.restore(m.checkpoint());direct.enter_body(w['n'])
                            assert torch.equal(p,direct.forecasts(w['before'],[w['action']])[0][0])
                            pred=p.argmax(-1).tolist();truth=w['after']['kinds'];mask=w['changed']
                            row=dict(law=law,life=life,arm=arm,count=count,probe=q,witness=w,
                                prediction=pred,probabilities=p.tolist(),changed_exact=all(pred[i]==truth[i] for i in mask),
                                whole_exact=pred==truth,old_exact=pred==w['old_after']['kinds'])
                            if arm in ('fresh','full'):
                                ref=reference[(law,life,'experienced' if arm=='full' else arm,count,q)]
                                assert row['probabilities']==ref['probabilities'], 'control failed to reproduce: stop'
                                assert w==ref['witness'];controls+=1
                            append('probes.jsonl',row);rows.append(row)
                        stats.append(dict(law=law,life=life,arm=arm,count=count,
                                          new_optimizer_steps=m.updates-initial_updates[arm],
                                          checkpoint_sha256=digest(path)))
                if count==8:break
                w=witness(1040000+li*1000+life*20+count,4,1+count%3,law)
                for m in models.values():
                    m.enter_body(4);m.learn(w['before'],w['action'],w['after'])
                row=dict(law=law,life=life,ordinal=count+1,witness=w);events.append(row);append('events.jsonl',row)
            print(json.dumps(dict(law=law,life=life,seconds=time.monotonic()-start)),flush=True)
    # Every unique native trial reexecuted; probes identical across arms/counts by construction.
    unique={json.dumps(r['witness'],sort_keys=True):r['witness'] for r in rows+events}
    for w in unique.values():
        cap();assert w==witness(w['seed'],w['n'],w['prefill'],w['law'])
    summaries=[];outcomes={}
    for law in LAWS:
        selected=[r for r in rows if r['law']==law]
        outcomes[law]={a:dict(acquisition=stable_acquisition(selected,a),
                             per_life=[stable_acquisition(selected,a,i) for i in range(4)]) for a in ARMS}
        for a in ARMS:
            for c in COUNTS:
                q=[r for r in selected if r['arm']==a and r['count']==c]
                summaries.append(dict(law=law,arm=a,count=c,denominator=len(q),
                    changed_correct=sum(r['changed_exact'] for r in q),whole_correct=sum(r['whole_exact'] for r in q)))
    assert all(digest(Path(p))==h for p,h in hashes.items())
    report=dict(status='EXPOSED_TWO_PAIR_DIAGNOSTIC',outcomes=outcomes,summaries=summaries,
                stats=stats,source_unchanged=True,restart_equal=True,control_probability_matches=controls,
                probe_rows=len(rows),shared_counterexamples=len(events),native_unique_verified=len(unique),
                hashes=hashes,wall_seconds=time.monotonic()-start)
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','outcomes','control_probability_matches','wall_seconds')}))


if __name__=='__main__':run(Path(sys.argv[1]))
