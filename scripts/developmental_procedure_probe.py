"""Frozen DEV native utility: learned procedures vs primitive-only SAME search.

Mine all recurring2-step traces from after-arm arbitration file record ONLY.
2new composite goals(empty2 aliases while preserve others),seeds123001/123002,
count4/5. Same old192 model, same4native actions,2048primitive model queries,
width16 beam. Procedure execution cost is expanded primitive length. Cached
primitive queries count once in BOTH arms. Procedures are search edges, not new
body commands or unverified effects. Every real intermediate must match forecast.
GO if procedure solvesboth,no paired loss and >=20%fewer total queries than
primitive arm (or strictly more successes at same query cap). Otherwise no-go.
No test learning, no retries,120s cap. DEV only before fresh capability gate.
"""
import json,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox
from packages.action_core.planner import Goal
from packages.shared_world.trace_procedures import mine,instantiate
from packages.shared_world.epistemic_lookahead import _query_projection
from scripts.developmental_task_eval import Adapter
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event


def search(model,frame,goal,options,budget=4,limit=2048,width=16):
    cache={};used=0;frontier=[(frame,(),())];seen={repr(frame.to_dict()):0}
    for depth in range(budget):
        expanded=[]
        for state,prefix,witnesses in frontier:
            for sequence in options:
                if len(prefix)+len(sequence)>budget:continue
                current=state;predicted=[]
                for action in sequence:
                    key=(repr(current.to_dict()),action)
                    if key not in cache:
                        if used>=limit:return (),(),used
                        row=model.predict(current,[action])[0];used+=1
                        cache[key]=None if row is None or row[1]!=0 else _query_projection(row[0])
                    current=cache[key]
                    if current is None:break
                    predicted.append(current)
                if current is None:continue
                plan=prefix+sequence;path=witnesses+tuple(predicted)
                if goal.probability(current)==1:return plan,path,used
                key=repr(current.to_dict())
                if seen.get(key,budget+1)<=len(plan):continue
                seen[key]=len(plan)
                # Generic literal-count potential, no native action semantics.
                value=sum(current.kinds[current.handles.index(h)]==k for h,k in goal._required_kinds().items())
                value+=sum(abs(current.sizes[current.handles.index(h)]-v)<1e-12 for h,v in goal.sizes)
                expanded.append((value,current,plan,path))
        frontier=[(s,p,w) for _,s,p,w in sorted(expanded,key=lambda x:-x[0])[:width]]
        if not frontier:break
    return (),(),used


def run(output):
    raw=json.loads((ROOT/'evidence/developmental-arbitration-v1/file.json').read_text())
    library=mine([r['trace'] for r in raw['records'] if r['arm']=='after' and r['success']])
    old=[]
    for name in ('developmental-continual.json','developmental-online-eval.json'):
        old+=json.loads((ROOT/'evidence'/name).read_text())['records']
    model=Adapter(old);rows=[];start=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='atanor_procedure_dev_') as root:
        for n in range(2):
            cfg,aliases,ref,payload=configuration(4+n,123001+n)
            for arm in ('primitive','procedure'):
                if time.monotonic()-start>120:raise TimeoutError('registered120s cap')
                body=Sandbox(Path(root)/f'{n}_{arm}',**cfg);view=body.observe()
                goal=Goal('composed',sizes=tuple((h,0. if i<2 else view.sizes[view.handles.index(h)]) for i,h in enumerate(aliases)))
                options=[(a,) for a in body.actions()]
                if arm=='procedure':options=instantiate(library,view.handles,body.actions())+options
                plan,predictions,queries=search(model,view,goal,options);trace=[];faithful=True
                for action,prediction in zip(plan,predictions):
                    record=event(body,action);trace.append(record)
                    faithful &= record['after']==prediction.to_dict()
                    if not faithful:break
                success=all(body._paths[h].is_file() and body._paths[h].read_bytes()==(b'' if i<2 else payload) for i,h in enumerate(aliases))
                assert body._paths[ref].read_bytes()==payload
                rows.append({'ordinal':n,'arm':arm,'goal':goal.to_dict(),'queries':queries,'trace':trace,'faithful':faithful,'success':success})
    summary={arm:{'successes':sum(r['success'] for r in rows if r['arm']==arm),'queries':sum(r['queries'] for r in rows if r['arm']==arm),
        'actions':sum(len(r['trace']) for r in rows if r['arm']==arm)} for arm in ('primitive','procedure')}
    a,b=summary['procedure'],summary['primitive']
    passed=a['successes']==2 and all(r['faithful'] for r in rows) and (a['successes']>b['successes'] or a['queries']<=.8*b['queries'])
    result={'verdict':'DEV_PROCEDURE_GAIN' if passed else 'NO_DEV_PROCEDURE_GAIN','summary':summary,'library':library,'rows':rows,
        'scope':'trace-derived parameterized procedure, new composed goals; not agency, new mechanics or generality'}
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':run(Path(sys.argv[1]))
