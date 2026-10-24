"""DEV: continuous native life, no curated procedure history or body resets.

Two arms, same old192 model and initial body(seed127001,count4), eight supplied
outcome goals. Library starts empty; mine only completed successful OWN episodes.
No learning from predictions. Primitive control also retains its lived history.
Targets: empty{0}, restore, empty{1}, restore, empty{2,3}, restore,
empty{0,1}, restore. This is HUMAN curriculum, not autonomous goal selection.
6 native actions/episode,4096 cached model calls,width16,120s total. No retries.
Feasibility requires all16 successes, faithful predictions, actual library growth
and >=20% lower later(episode4+) queries without more native actions; otherwise
no developmental efficiency gain. All acquisition/induction costs included.
Same ongoing physics, not transfer/general agency. No production integration.
"""
import json,sys,tempfile,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox
from packages.action_core.planner import Goal
from packages.shared_world.trace_procedures import mine,instantiate
from scripts.developmental_procedure_probe import search
from scripts.developmental_task_eval import Adapter
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event


def run(output):
    if output.exists():raise FileExistsError(output)
    old=[]
    for name in ('developmental-continual.json','developmental-online-eval.json'):
        old+=json.loads((ROOT/'evidence'/name).read_text())['records']
    model=Adapter(old);rows=[];start=time.monotonic()
    cfg,aliases,ref,payload=configuration(4,127001)
    targets=({0},set(),{1},set(),{2,3},set(),{0,1},set())
    bound={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
           for folder in ('packages','scripts') for p in (ROOT/folder).rglob('*.py')}
    with tempfile.TemporaryDirectory(prefix='atanor_procedure_life_') as root:
        bodies={arm:Sandbox(Path(root)/arm,**cfg) for arm in ('primitive','online')}
        histories={arm:[] for arm in bodies}
        initial=bodies['online'].observe();full=initial.sizes[initial.handles.index(ref)]
        for n,empty in enumerate(targets):
            for arm in (('primitive','online') if n%2==0 else ('online','primitive')):
                if time.monotonic()-start>120:raise TimeoutError('120s cap')
                body=bodies[arm];view=body.observe();cpu=time.process_time()
                library=mine(histories[arm]) if arm=='online' else []
                induction=time.process_time()-cpu
                goal=Goal('supplied-outcome',sizes=tuple((h,0. if i in empty else full) for i,h in enumerate(aliases)))
                options=instantiate(library,view.handles,body.actions())+[(a,) for a in body.actions()]
                cpu=time.process_time()
                plan,predictions,queries=search(model,view,goal,options,budget=6,limit=4096,width=16)
                planning=time.process_time()-cpu;trace=[];faithful=True
                for action,prediction in zip(plan,predictions):
                    record=event(body,action);trace.append({**record,'prediction':prediction.to_dict()})
                    faithful &= record['after']==prediction.to_dict()
                    if not faithful:break
                success=all(body._paths[h].is_file() and body._paths[h].read_bytes()==(b'' if i in empty else payload) for i,h in enumerate(aliases))
                assert body._paths[ref].read_bytes()==payload
                if success and faithful:histories[arm].append(trace)
                rows.append(dict(ordinal=n,arm=arm,goal=goal.to_dict(),before=view.to_dict(),
                    trace=trace,success=success,faithful=faithful,library=library,
                    queries=queries,induction_cpu=induction,planning_cpu=planning))
    summary={arm:{'successes':sum(r['success'] for r in rows if r['arm']==arm),
        'queries':sum(r['queries'] for r in rows if r['arm']==arm),
        'later_queries':sum(r['queries'] for r in rows if r['arm']==arm and r['ordinal']>=4),
        'actions':sum(len(r['trace']) for r in rows if r['arm']==arm),
        'cpu':sum(r['planning_cpu']+r['induction_cpu'] for r in rows if r['arm']==arm)} for arm in bodies}
    a,b=summary['online'],summary['primitive']
    unchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in bound.items())
    passed=unchanged and all(r['faithful'] and r['success'] for r in rows) and any(r['library'] for r in rows) and a['later_queries']<=.8*b['later_queries'] and a['actions']<=b['actions']
    result=dict(verdict='DEV_LIFE_REUSE_GAIN' if passed else 'NO_DEV_LIFE_REUSE_GAIN',summary=summary,rows=rows,source_sha256=bound,source_unchanged=unchanged)
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({'verdict':result['verdict'],'summary':summary}))


if __name__=='__main__':run(Path(sys.argv[1]))
