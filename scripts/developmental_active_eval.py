"""Fixed one-step disagreement acquisition; no operator experiment menu.

Random fallback is explicitly counted, not labelled intelligent experiment design.
Separate evaluation bodies are supplied tests, never acquisition reset services.
"""
import hashlib,json,random,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_task_eval import Adapter
from scripts.representation_r3_dev import configuration,make_goal,native_success
from packages.action_core.world import Sandbox,Action
from packages.shared_world.partial_goal import arbitrate

def event(body,action):
    before=body.observe();success=body.step(action);after=body.observe()
    return {'before':before.to_dict(),'action':action.to_dict(),'after':after.to_dict(),'success':success}

def run(output):
    output.mkdir(exist_ok=False); lives=[];start=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='atanor_active_') as root:
        for life in range(4):
            seed=95001+life;cfg,_,ref,payload=configuration(3,seed)
            common=Sandbox(Path(root)/f'bootstrap{life}',**cfg);rng=random.Random(seed)
            bootstrap=[event(common,rng.choice(common.actions())) for _ in range(6)]
            for arm in ('none','random','active'):
                body=Sandbox(Path(root)/f'acquire{life}_{arm}',**cfg)
                for old in bootstrap:
                    assert event(body,Action.from_dict(old['action']))==old
                history=list(bootstrap);model=Adapter(history); acquisition=[];rng=random.Random(seed+100)
                cpu=time.process_time()
                for step in range(0 if arm=='none' else 26):
                    if time.monotonic()-start>240:raise TimeoutError('DEV hard cap240s')
                    before=body.observe();actions=body.actions();scores=[]
                    if arm=='active':
                        for action in actions:
                            scores.append(sum(len(v)>1 for _,_,v in model.predict_cells(before,action)))
                    best=max(scores,default=0)
                    chosen=rng.choice([a for a,s in zip(actions,scores) if s==best]) if best else rng.choice(actions)
                    record=event(body,chosen)
                    history.append(record);model=Adapter(history)
                    assert body._paths[ref].read_bytes()==payload
                    acquisition.append({**record,'disagreement_cells':best,
                                        'mode':'disagreement' if best else 'random'})
                learn_cpu=time.process_time()-cpu;tasks=[]
                for task in range(8):
                    if time.monotonic()-start>240:raise TimeoutError('DEV hard cap240s')
                    testcfg,aliases,reference,testpayload=configuration(3+task%2,97001+life*20+task)
                    test=Sandbox(Path(root)/f'task{life}_{arm}_{task}',**testcfg)
                    collective=task%4>=2;goal=make_goal(test,aliases,collective);trace=[]
                    for step in range(2):
                        action,prediction,queries=arbitrate(model,test.observe(),goal,test.actions(),horizon=2,limit=32768)
                        if action is None:break
                        trace.append(event(test,action));assert test._paths[reference].read_bytes()==testpayload
                        if native_success(test,aliases,reference,testpayload,collective):break
                    tasks.append({'task':task,'success':native_success(test,aliases,reference,testpayload,collective),'trace':trace})
                lives.append({'life':life,'arm':arm,'bootstrap':bootstrap,'acquisition':acquisition,
                              'learning_cpu':learn_cpu,'tasks':tasks})
    summary={}
    for arm in ('none','random','active'):
        rows=[r for r in lives if r['arm']==arm]
        success=sum(t['success'] for r in rows for t in r['tasks'])
        actions=sum(len(r['bootstrap'])+len(r['acquisition'])+sum(len(t['trace']) for t in r['tasks']) for r in rows)
        summary[arm]={'success':success,'total_actions':actions,'actions_per_success':actions/success if success else None,
                      'disagreement_actions':sum(a['mode']=='disagreement' for r in rows for a in r['acquisition'])}
    a,b,c=(summary[k] for k in ('active','random','none'))
    lift=a['success']>=b['success']+4 and a['success']>=c['success']+4
    economy=all(a['actions_per_success'] is not None and x['actions_per_success'] is not None
                and a['actions_per_success']<=.9*x['actions_per_success'] for x in (b,c))
    result={'verdict':'ACTIVE_GAIN' if lift and economy else 'NO_ACTIVE_GAIN',
            'task_lift_gate':lift,'economy_gate':economy,'summary':summary,'lives':lives,
            'scope':'DEV one-step disagreement selection, random fallback; not generality or autonomous curricula'}
    with (output/'report.json').open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k!='lives'}))

if __name__=='__main__':run(Path(sys.argv[1]))
