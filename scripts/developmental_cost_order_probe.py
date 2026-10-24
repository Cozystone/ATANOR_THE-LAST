"""Frozen DEV cost-order check; four outcomes on each of three continuous bodies.

Seed133001,count4; empty{0,1},restore,empty{2,3},restore. No body resets. Same
old192 model, same mined historical procedures,6native actions,4096model calls
per goal,120s cap. Arms primitive beam, macro-first beam, native-cost macro search.
GO only cost-order4/4, no extra native actions vs primitive, and <=80% primitive
queries. Native predictions and final bytes checked. No retries/test learning.
This isolates planning, not autonomous procedure acquisition or self-model.
"""
import json,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox
from packages.action_core.planner import Goal
from packages.shared_world.trace_procedures import mine,instantiate
from packages.shared_world.cost_ordered_search import search as cost_search
from scripts.developmental_procedure_probe import search
from scripts.developmental_task_eval import Adapter
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event


def run(output):
    if output.exists():raise FileExistsError(output)
    old=[]
    for name in ('developmental-continual.json','developmental-online-eval.json'):
        old+=json.loads((ROOT/'evidence'/name).read_text())['records']
    model=Adapter(old);raw=json.loads((ROOT/'evidence/developmental-arbitration-v1/file.json').read_text())
    library=mine([r['trace'] for r in raw['records'] if r['arm']=='after' and r['success']])
    cfg,aliases,ref,payload=configuration(4,133001);rows=[];start=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='atanor_cost_order_') as root:
        bodies={a:Sandbox(Path(root)/a,**cfg) for a in ('primitive','macro','cost')}
        initial=bodies['cost'].observe();full=initial.sizes[initial.handles.index(ref)]
        for n,empty in enumerate(({0,1},set(),{2,3},set())):
            arms=list(bodies);arms=arms[n%3:]+arms[:n%3]
            for arm in arms:
                if time.monotonic()-start>120:raise TimeoutError('120s cap')
                body=bodies[arm];view=body.observe()
                goal=Goal('supplied',sizes=tuple((h,0. if i in empty else full) for i,h in enumerate(aliases)))
                options=[(a,) for a in body.actions()]
                if arm!='primitive':options=instantiate(library,view.handles,body.actions())+options
                cpu=time.process_time()
                plan,predictions,queries=(cost_search if arm=='cost' else search)(model,view,goal,options,budget=6,limit=4096)
                cpu=time.process_time()-cpu;trace=[];faithful=True
                for action,prediction in zip(plan,predictions):
                    record=event(body,action);trace.append({**record,'prediction':prediction.to_dict()})
                    faithful &= record['after']==prediction.to_dict()
                    if not faithful:break
                success=all(body._paths[h].is_file() and body._paths[h].read_bytes()==(b'' if i in empty else payload) for i,h in enumerate(aliases))
                assert body._paths[ref].read_bytes()==payload
                rows.append(dict(ordinal=n,arm=arm,trace=trace,success=success,faithful=faithful,queries=queries,cpu=cpu))
    summary={a:dict(successes=sum(r['success'] for r in rows if r['arm']==a),actions=sum(len(r['trace']) for r in rows if r['arm']==a),
        queries=sum(r['queries'] for r in rows if r['arm']==a),cpu=sum(r['cpu'] for r in rows if r['arm']==a)) for a in bodies}
    a,b=summary['cost'],summary['primitive']
    passed=a['successes']==4 and a['actions']<=b['actions'] and a['queries']<=.8*b['queries'] and all(r['faithful'] for r in rows if r['arm']=='cost')
    result=dict(verdict='DEV_COST_ORDER_GAIN' if passed else 'NO_DEV_COST_ORDER_GAIN',summary=summary,rows=rows)
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':run(Path(sys.argv[1]))
