"""Frozen one-shot native prediction gate, NOT task/agency/generalization claim.

First48 archived SQL transitions fit dependency; all192 fit unchanged rich Model.
Four fresh instances151001..151004, n4/5, prefill1/2,48random actions each.
No online learning/tuning. Candidate receives baseline PREDICTED unary sets only.
PASS: no extra wrong cells, >=32 extra correct singleton cells, no complete-
correct-transition loss, identical independent native replay, <=3x prediction CPU.
Single output directory exclusive reservation,120s hard wall cap. Old data/source
hashes checked unchanged. Temporary in-memory databases only. No production edits.
"""
import hashlib,importlib.util,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_conditional_eval import Model
from scripts.developmental_fk_tasks import context
from scripts.developmental_fk_schema_tasks import schema_encode
from scripts.developmental_observation_dependencies import Dependencies
from scripts.developmental_continual_probe import score
from packages.action_core.world import Action,Frame


def run(source,output):
    output.mkdir(exist_ok=False)
    training_path=ROOT/'evidence/developmental-fk-schema-tasks.json'
    bound_paths=(source,training_path,Path(__file__),
                 ROOT/'scripts/developmental_observation_dependencies.py',
                 ROOT/'scripts/developmental_conditional_eval.py',
                 ROOT/'scripts/developmental_fk_schema_tasks.py',
                 ROOT/'scripts/developmental_fk_tasks.py',
                 ROOT/'packages/shared_world/conditional_support.py')
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in bound_paths}
    (output/'attempt.json').write_text(json.dumps(dict(protocol=__doc__,hashes=hashes)))
    records=json.loads(training_path.read_text())['training']
    base=Model(records,numeric_context=context); dependency=Dependencies()
    for r in records[:48]:
        for key in ('before','after'): dependency.learn(Frame.from_dict(r[key]))
    spec=importlib.util.spec_from_file_location('owned_native_fk',source)
    native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
    totals={a:Counter() for a in ('baseline','factored')};cpu=Counter();complete=Counter()
    rows=[];start=time.monotonic()
    for episode in range(4):
        seed=151001+episode;n=4+episode%2;prefill=1+episode//2
        body=native.FKWorld(seed,n=n,prefill=prefill)
        rng=random.Random(seed);episode_rows=[]
        try:
            for step in range(48):
                if time.monotonic()-start>120: raise TimeoutError('fixed wall cap')
                before=schema_encode(body)
                action=Action(rng.choice(body.actions),(f'n{rng.randrange(n)}',))
                tick=time.process_time();p=base.predict(before,action,True)
                elapsed=time.process_time()-tick;cpu['baseline']+=elapsed
                tick=time.process_time();q=dependency.forecast(p)
                cpu['factored']+=elapsed+time.process_time()-tick
                # Both predictions complete before any native action dispatch.
                ok=body.do(action.op,int(action.args[0][1:]));after=schema_encode(body)
                for arm,prediction in [('baseline',p),('factored',q)]:
                    s=score(prediction,after);totals[arm].update(s)
                    complete[arm]+=s.get('correct_singleton',0)==len(prediction)
                episode_rows.append(dict(step=step,before=before.to_dict(),action=action.to_dict(),
                    after=after.to_dict(),success=ok,baseline=p,factored=q))
        finally: body.dispose()
        replay=native.FKWorld(seed,n=n,prefill=prefill)
        try:
            for r in episode_rows:
                assert schema_encode(replay).to_dict()==r['before']
                a=r['action'];assert replay.do(a['op'],int(a['args'][0][1:]))==r['success']
                assert schema_encode(replay).to_dict()==r['after']
        finally: replay.dispose()
        rows.append(dict(seed=seed,n=n,prefill=prefill,trace=episode_rows,replay=True))
    assert hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in bound_paths}
    passed=(totals['factored']['wrong']<=totals['baseline']['wrong'] and
            totals['factored']['correct_singleton']>=totals['baseline']['correct_singleton']+32 and
            complete['factored']>=complete['baseline'] and cpu['factored']<=3*cpu['baseline'])
    report=dict(protocol=__doc__,verdict='PREDICTION_GAIN' if passed else 'NO_GO',totals=totals,
                complete_transitions=complete,cpu=cpu,source_sha256=hashes,rules=dependency.rules,
                episodes=rows,scope='fresh instances of known mechanics; no task utility/cross-body transfer')
    with (output/'report.json').open('x') as stream:json.dump(report,stream,sort_keys=True)
    print(json.dumps({k:v for k,v in report.items() if k not in ('episodes','protocol','source_sha256')}))


if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
