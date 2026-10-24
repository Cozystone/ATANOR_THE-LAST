"""Frozen one-shot law adaptation test; candidate unchanged. See preregistration."""
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.developmental_plastic_world import PlasticWorld
from scripts.developmental_plastic_eval import frame
from scripts.plastic_law_world import LawWorld, native, SOURCE

AGES=(0,8,32,128,512)
LAWS=('null','cascade')


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def run(out):
    out.mkdir(exist_ok=False)
    paths=[SOURCE,Path(__file__),ROOT/'scripts/plastic_law_world.py',
           ROOT/'scripts/developmental_plastic_world.py',ROOT/'scripts/developmental_plastic_eval.py',
           ROOT/'packages/shared_world/sql_schema_sensor.py',
           ROOT/'docs/ATANOR_LAW_TRANSFER_V1_PREREGISTRATION.md']
    paths += [ROOT/f'evidence/developmental-plastic-life-v1/life-{i}-passive-1024.pt' for i in range(4)]
    hashes={str(p):sha(p) for p in paths}
    (out/'attempt.json').write_text(json.dumps(dict(hashes=hashes)),encoding='utf-8')
    started=time.monotonic(); results=[]; probes=[]; training=[]; verified=0
    def cap():
        if time.monotonic()-started>1800: raise TimeoutError('30min hard cap; no retry')
    def save(name,row):
        with (out/name).open('a',encoding='utf-8') as f: f.write(json.dumps(row,separators=(',',':'))+'\n')
    def verify(seed,n,prefill,law,events):
        nonlocal verified
        body=LawWorld(seed,n,prefill,law)
        try:
            for e in events:
                assert frame(body)==e['before']
                assert bool(body.do(native.FK_ACTIONS[e['action'][0]],e['action'][1]))==e['accepted']
                assert frame(body)==e['after']; verified+=1
        finally: body.dispose()

    def measure(states,law,li,life,age):
        for task in range(4):
            seed=930000+li*1000+life*10+task; n=5+task%2; prefill=1+task%2
            # Independent native witness defines changed-law goal, not a plan supplied to learner.
            old=LawWorld(seed,n,prefill,'restrict'); new=LawWorld(seed,n,prefill,law)
            try:
                observation=frame(new); assert frame(old)==observation
                assert not old.do('delete',0); assert new.do('delete',0)
                truth=frame(new)['kinds']; old_truth=frame(old)['kinds']
                goal=truth if task<2 else list(native.fk_goal(seed+10000,n))
            finally: old.dispose();new.dispose()
            for arm in (('fresh','experienced') if (life+task)%2==0 else ('experienced','fresh')):
                cap(); model=PlasticWorld.restore(states[arm]);model.enter_body(n)
                p,_=model.forecasts(observation,[[3,0]])
                prediction=p[0].argmax(-1).tolist()
                probe=dict(law=law,life=life,age=age,task=task,arm=arm,
                           prediction=prediction,new_truth=truth,old_truth=old_truth,
                           new_correct=prediction==truth,old_correct=prediction==old_truth)
                probes.append(probe);save('probes.jsonl',probe)
                # Probe has no learning/activation side effect. All task adaptation is branch-local.
                body=LawWorld(seed,n,prefill,law);rng=random.Random(seed+20000)
                events=[]; cpu=time.process_time();updates=model.updates;queries=model.model_queries
                try:
                    before=frame(body)
                    while before['kinds']!=goal and len(events)<32:
                        cap(); allowed=[[o,i] for o in range(4) for i in range(n)]
                        action=model.choose_task(before,allowed,goal,rng)
                        forecast,_=model.forecasts(before,[action])
                        accepted=bool(body.do(native.FK_ACTIONS[action[0]],action[1]));after=frame(body)
                        model.learn(before,action,after)
                        events.append(dict(before=before,action=action,accepted=accepted,after=after,
                                           forecast=forecast[0].tolist()))
                        before=after
                    success=before['kinds']==goal
                finally: body.dispose()
                row=dict(law=law,life=life,age=age,arm=arm,task=task,seed=seed,n=n,prefill=prefill,
                         cohort='changed' if task<2 else 'general',goal=goal,success=success,
                         actions=len(events),cost=len(events) if success else 33,
                         updates=model.updates-updates,queries=model.model_queries-queries,
                         cpu_seconds=time.process_time()-cpu,events=events)
                verify(seed,n,prefill,law,events);save('tasks.jsonl',row)
                results.append({k:v for k,v in row.items() if k!='events'})

    for li,law in enumerate(LAWS):
        for life in range(4):
            loaded=torch.load(paths[-4+life],weights_only=True)
            models={'fresh':PlasticWorld(610000+life),'experienced':PlasticWorld.restore(loaded)}
            seed=910000+li*1000+life*10
            bodies={a:LawWorld(seed,4,2,law) for a in models}
            for m in models.values(): m.enter_body(4)
            rng=random.Random(seed+100); traces={a:[] for a in models};cpus={a:0. for a in models}
            try:
                for age in range(513):
                    if age in AGES:
                        states={a:m.checkpoint() for a,m in models.items()}
                        for arm,state in states.items():
                            path=out/f'{law}-{life}-{arm}-{age}.pt';torch.save(state,path)
                            restored=PlasticWorld.restore(torch.load(path,weights_only=True))
                            assert torch.equal(models[arm].forecasts(frame(bodies[arm]),[[3,0]])[0],
                                               restored.forecasts(frame(bodies[arm]),[[3,0]])[0])
                            training.append(dict(law=law,life=life,arm=arm,age=age,cpu_seconds=cpus[arm],
                                                 updates=state['updates']-(6141 if arm=='experienced' else 0),
                                                 checkpoint_sha256=sha(path)))
                        measure(states,law,li,life,age)
                    if age==512: break
                    action=[rng.randrange(4),rng.randrange(4)]
                    # Identical actual B experience for both arms, not policy-induced data confounding.
                    for arm,model in models.items():
                        cap();cpu=time.process_time();body=bodies[arm];before=frame(body)
                        accepted=bool(body.do(native.FK_ACTIONS[action[0]],action[1]));after=frame(body)
                        model.learn(before,action,after);cpus[arm]+=time.process_time()-cpu
                        traces[arm].append(dict(before=before,action=action,accepted=accepted,after=after))
                    assert traces['fresh'][-1]==traces['experienced'][-1]
                for arm,events in traces.items():
                    verify(seed,4,2,law,events);save('life.jsonl',dict(law=law,life=life,arm=arm,seed=seed,events=events))
            finally:
                for b in bodies.values(): b.dispose()
            print(json.dumps(dict(law=law,completed_life=life,seconds=time.monotonic()-started)),flush=True)

    def selected(law,arm,age=None,cohort=None,life=None):
        return [r for r in results if r['law']==law and r['arm']==arm and (age is None or r['age']==age)
                and (cohort is None or r['cohort']==cohort) and (life is None or r['life']==life)]
    def cost(law,arm,cohort=None,life=None):
        rows=selected(law,arm,cohort=cohort,life=life);return sum(r['cost'] for r in rows)/len(rows)
    def accuracy(law,arm,age,old=False):
        rows=[r for r in probes if (r['law'],r['arm'],r['age'])==(law,arm,age)]
        return sum(r['old_correct' if old else 'new_correct'] for r in rows)/len(rows)
    def acquisition(law,arm):
        return next((a for a in AGES if accuracy(law,arm,a)>=.75),513)
    summaries=[]; gates={}
    for law in LAWS:
        for arm in models:
            for age in AGES:
                rows=selected(law,arm,age)
                summaries.append(dict(law=law,arm=arm,age=age,success=sum(r['success'] for r in rows),count=len(rows),
                    mean_cost=sum(r['cost'] for r in rows)/len(rows),
                    changed_success=sum(r['success'] for r in rows if r['cohort']=='changed'),
                    changed_mean_cost=sum(r['cost'] for r in rows if r['cohort']=='changed')/8,
                    changed_probe_accuracy=accuracy(law,arm,age)))
        gates[law]=dict(
            old_answer_conflict=accuracy(law,'experienced',0,True)>=.75 and accuracy(law,'experienced',0)<=.25,
            changed_cost_gain=cost(law,'experienced','changed')<=.8*cost(law,'fresh','changed'),
            total_cost_gain=cost(law,'experienced')<=.8*cost(law,'fresh'),
            faster_new_law=acquisition(law,'experienced')<acquisition(law,'fresh') and acquisition(law,'experienced')<=128,
            final_success_noninferior=sum(r['success'] for r in selected(law,'experienced',512))>=sum(r['success'] for r in selected(law,'fresh',512)),
            paired_lives=sum(cost(law,'experienced','changed',i)<cost(law,'fresh','changed',i) for i in range(4))>=3
                and all(cost(law,'experienced','changed',i)<=1.1*cost(law,'fresh','changed',i) for i in range(4)))
    unchanged=all(sha(Path(p))==h for p,h in hashes.items())
    report=dict(verdict='BOUNDED_LAW_ADAPTATION_POSITIVE' if unchanged and all(all(g.values()) for g in gates.values()) else 'NO_GO',
                gates=gates,summaries=summaries,training=training,source_unchanged=unchanged,
                native_verified=verified,restart_forecasts=True,hashes=hashes,
                wall_seconds=time.monotonic()-started,
                acquisition={law:{a:acquisition(law,a) for a in models} for law in LAWS},
                scope='Two related SQLite FK laws, not broad meta-learning or independent mechanics transfer')
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('verdict','gates','acquisition','summaries','wall_seconds')}),flush=True)


if __name__=='__main__': run(Path(sys.argv[1]))
