"""Exposed R5 readiness; shared native executor for later frozen comparison."""
import argparse
import json
from pathlib import Path
import random
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.representation_r4_dev import pool,evaluate
from scripts.representation_r3_dev import configuration,make_goal
from scripts.representation_r1_dev import SCHEMA
from packages.action_core.world import Sandbox
from packages.action_core.episode import encode_config
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.experiment_choice import select
from packages.shared_world.epistemic_coverage import select_for_frontier
from packages.shared_world.epistemic_lookahead import select_for_lookahead
from packages.shared_world.epistemic_discrimination import select_discriminating
from packages.shared_world.epistemic_goal_stop import select_for_requested_goals

def run_arm(root,seed,arm,*,budget=32,learn_tasks=False):
    root.mkdir()
    candidates=pool(root/'available',seed)
    frontier=[];agendas=[]
    for j in range(4):
        cfg,_,_,_=configuration(4+j%2,seed+39007+j*191)
        body=Sandbox(root/f'frontier_{j}',**cfg)
        frontier.extend((body.observe(),action) for action in body.actions())
        _,aliases,_,_=configuration(4+j%2,seed+39007+j*191)
        agendas.extend((body.observe(),make_goal(body,aliases,collective),body.actions()) for collective in (False,True))
    model=RelationalLearner(schema=SCHEMA,partitioned=True)
    rng=random.Random(seed+71)
    acquired=[]
    (root/'acquired').mkdir()
    for step in range(budget if arm not in ('none','online') else 0):
        public=[(before,action) for cfg,before,action in candidates]
        if arm=='focused':
            index=select_for_requested_goals(model,public,agendas,remaining=budget-step,rng=rng)
        elif arm=='discriminate':
            index=select_discriminating(model,public,frontier,remaining=budget-step,rng=rng)
        elif arm=='lookahead':
            index=select_for_lookahead(model,public,frontier,remaining=budget-step,rng=rng)
        elif arm=='coverage':
            index=select_for_frontier(model,public,frontier,remaining=budget-step,rng=rng)
        elif arm=='active':
            index=select(model,public,remaining=budget-step,rng=rng)
        elif arm=='random':
            index=rng.randrange(len(candidates))
        else:
            raise ValueError('unknown arm')
        if index is None:
            break
        cfg,before,action=candidates.pop(index)
        body=Sandbox(root/'acquired'/str(step),**cfg)
        assert body.observe().to_dict()==before.to_dict()
        prediction=model.predict(before,[action])[0][0]
        succeeded=body.step(action)
        after=body.observe()
        model.learn(step,before,action,after)
        acquired.append({'before':before.to_dict(),'action':action.to_dict(),'prediction':prediction.to_dict(),
            'after':after.to_dict(),'succeeded':succeeded,'config':encode_config(cfg),'native_root':str(body.root)})
    # Native held-out outcomes are constructed ONLY after selection has ended.
    heldout=[]
    (root/'validation_results').mkdir()
    for i,(cfg,before,action) in enumerate(pool(root/'validation',seed+19007)):
        body=Sandbox(root/'validation_results'/str(i),**cfg)
        body.step(action)
        heldout.append((before,action,body.observe()))
    snapshot=model.snapshot()
    result=evaluate(model,heldout,root/'tasks',seed+39007,learn_tasks=learn_tasks)
    if not learn_tasks:assert model.snapshot()==snapshot
    result.update(acquisition_actions=len(acquired),total_native_actions=len(acquired)+result['task_actions'],
                  acquisitions=acquired,arm=arm,seed=seed,learner_snapshot=model.snapshot(),pre_task_snapshot=snapshot,
                  learn_tasks=learn_tasks)
    result['actions_per_success']=result['total_native_actions']/result['successes'] if result['successes'] else None
    return result

def main(output):
    output.mkdir(parents=True,exist_ok=False)
    root=Path(tempfile.mkdtemp(prefix='atanor_r5_dev_'))
    start=time.process_time()
    result=run_arm(root/'coverage',44017,'coverage')
    ready=result['successes']>4 and result['actions_per_success']<3 and result['acquisition_actions']<32
    report={'verdict':'R5_DEV_READY' if ready else 'R5_DEV_NO_GO','capability_claim':False,
            'cpu_seconds':time.process_time()-start,'result':result}
    (output/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True))
    print(json.dumps({**report,'result':{k:v for k,v in result.items() if k not in ('tasks','acquisitions')}},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
