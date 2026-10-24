"""DEV whole-observation bridge and task gate over historical native SQLite.

Frame fields are an explicit sensor codec here: kinds=existing categorical state,
equal=observed state equality, r0=actual reference edges, size=unmeasured zero.
No filesystem prediction weights/rules transferred. No outcome rule in the codec.
"""
import hashlib, importlib.util, json, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.developmental_fk_learning import observe
from scripts.developmental_task_eval import Adapter
from packages.action_core.world import Frame, Action
from packages.action_core.planner import Goal
from packages.shared_world.planning import choose

def encode(body):
    states,edges=observe(body); n=len(states)
    return Frame(states,[0.]*n,[[int(a==b) for b in states] for a in states],
                 [[0]*n for _ in states],tuple(f'n{i}' for i in range(n)),{'r_0':edges})

def context(frame,nodes):
    values=[frame.sizes[i] for i in nodes]
    matrices={'equal':frame.equal,**frame.relations}
    for category in range(3):
        mask=[int(s==category) for s in frame.kinds]
        values.append(sum(mask))
        for node in nodes:
            for _,matrix in sorted(matrices.items()):
                values.extend((sum(matrix[node][j]*mask[j] for j in range(len(mask))),
                               sum(matrix[j][node]*mask[j] for j in range(len(mask)))))
    return tuple(values)

def run(source,learning,output,encoder=encode,seed_base=84001,policy_comparison=False,arbitration=False):
    raws=[p.read_bytes() for p in (source,learning)]
    spec=importlib.util.spec_from_file_location('fk_native',source)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    old=json.loads(raws[1])['training']; training=[]
    body=module.FKWorld(82001,n=4,prefill=2)
    try:
        for row in old:
            before=encoder(body)
            assert before.kinds==row['states'] and before.relations['r_0']==row['edges']
            action=Action(row['action'],(f"n{row['target']}",))
            assert body.do(row['action'],row['target'])==row['success']
            after=encoder(body); assert after.kinds==row['after']
            training.append({'before':before.to_dict(),'action':action.to_dict(),'after':after.to_dict()})
    finally:body.dispose()
    schema=[{'id':op,'arity':1} for op in module.FK_ACTIONS]
    models={'local':Adapter(training,schema=schema,numeric_context=context if policy_comparison else None),
            'relational':Adapter(training,schema=schema,numeric_context=context)}
    records=[]; start=time.monotonic()
    for ordinal in range(16):
        n=4+ordinal%2; seed=seed_base+ordinal; prefill=1+(ordinal//2)%2
        for arm in ('local','relational') if ordinal%2==0 else ('relational','local'):
            body=module.FKWorld(seed,n=n,prefill=prefill)
            try:
                initial=body.config(); target=list(initial)
                if ordinal<8: target=[0]+[1]*(n-1)
                else: target[next(i for i in range(1,n) if target[i]==1)]=2
                goal=Goal('opaque-goal',kinds=tuple((f'n{i}',s) for i,s in enumerate(target)))
                trace=[]; cpu=time.process_time()
                for step in range(4):
                    if time.monotonic()-start>120: raise TimeoutError('fixed DEV cap120s')
                    frame=encoder(body)
                    actions=[Action(op,(f'n{i}',)) for op in module.FK_ACTIONS for i in range(n)]
                    progress=None
                    if policy_comparison and arm=='relational':
                        from packages.shared_world.partial_goal import select,arbitrate
                        progress=(arbitrate(models[arm],frame,goal,actions,horizon=3,width=8,limit=32768)
                                  if arbitration else select(models[arm],frame,goal,actions))
                    action,prediction,queries=(progress if progress is not None else
                        choose(models[arm],frame,goal,actions,horizon=3,width=8,limit=32768,allow_partial=True))
                    if action is None:
                        trace.append({'stop':'unsupported','queries':queries});break
                    ok=body.do(action.op,int(action.args[0][1:]))
                    trace.append({'before':frame.to_dict(),'action':action.to_dict(),'success':ok,
                                  'prediction':prediction.to_dict(),'after':encoder(body).to_dict(),'queries':queries})
                    if list(body.config())==target:break
                records.append({'ordinal':ordinal,'arm':arm,'target':target,
                    'success':list(body.config())==target,'trace':trace,'cpu':time.process_time()-cpu})
            finally:body.dispose()
    summary={arm:{'success':sum(r['success'] for r in records if r['arm']==arm),
                   'actions':sum('action' in t for r in records if r['arm']==arm for t in r['trace'])} for arm in models}
    result={'scope':'DEV SQL whole-state planning, no cross-domain knowledge transfer',
        'arms':{'local':'same relational model/original planner','relational':'same relational model/partial goal policy'} if policy_comparison else None,
        'verdict':'TASK_GAIN' if summary['relational']['success']>=summary['local']['success']+4 else 'NO_TASK_GAIN',
        'summary':summary,'source_sha256':[hashlib.sha256(raw).hexdigest() for raw in raws],
        'training':training,'records':records}
    assert [p.read_bytes() for p in (source,learning)]==raws
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k not in ('training','records')}))

if __name__=='__main__':run(*(Path(p) for p in sys.argv[1:]))
