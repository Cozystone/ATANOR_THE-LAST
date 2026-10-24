"""Exposed acquisition screen; outcomes never enter experiment selector inputs."""
import argparse
import json
from pathlib import Path
import random
import sys
import tempfile
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.representation_r3_dev import configuration, make_goal, native_success
from scripts.representation_r1_dev import SCHEMA
from packages.action_core.world import Sandbox
from packages.action_core.episode import encode_config
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.planning import choose
from packages.shared_world.experiment_choice import select

PATTERNS = ('coupled_full','coupled_empty','detached_absent','detached_empty',
            'independent_full','independent_mixed')

def pool(root, seed):
    root.mkdir(parents=True,exist_ok=False)
    rows = []
    for count in (2,3):
        for index, pattern in enumerate(PATTERNS):
            cfg, _, _, _ = configuration(count, seed+count*101+index, pattern, b'x'*23)
            body = Sandbox(root/f'view_{count}_{index}',**cfg)
            before = body.observe()
            rows.extend((cfg,before,action) for action in body.actions())
    return rows

def loss(prediction, actual):
    total = 0.
    for weight, state in prediction.outcomes:
        parts = [np.mean(np.abs(np.asarray(state.kinds)-np.eye(3)[actual.kinds])),
                 np.mean(np.abs(np.asarray(state.sizes)-actual.sizes)),
                 np.mean(np.abs(np.asarray(state.equal)-actual.equal))]
        parts.extend(np.mean(np.abs(np.asarray(state.relations[k])-actual.relations[k])) for k in actual.relations)
        total += weight*float(np.mean(parts))
    return total

def evaluate(model, heldout, root, seed, *, learn_tasks=False):
    root.mkdir(parents=True,exist_ok=False)
    errors = [loss(model.predict(b,[a])[0][0],after) for b,a,after in heldout]
    tasks = []
    for j in range(4):
        for collective in (False,True):
            cfg, aliases, reference, payload = configuration(4+j%2,seed+j*191)
            body = Sandbox(root/f'task_{j}_{collective}',**cfg)
            goal, trace = make_goal(body,aliases,collective), []
            for step in range(2):
                if native_success(body,aliases,reference,payload,collective):
                    break
                action,forecast,nodes = choose(model,body.observe(),goal,body.actions(),horizon=2,limit=32768)
                before = body.observe()
                succeeded = body.step(action)
                if learn_tasks:
                    model.learn(f'task-{j}-{collective}-{step}',before,action,body.observe())
                trace.append({'before':before.to_dict(),'action':action.to_dict(),'prediction':forecast.to_dict(),
                              'after':body.observe().to_dict(),'succeeded':succeeded,'nodes':nodes})
            tasks.append({'collective':collective,'success':native_success(body,aliases,reference,payload,collective),
                          'trace':trace,'config':encode_config(cfg),'native_root':str(body.root)})
    return {'prediction_error':float(np.mean(errors)),'prediction_n':len(errors),
            'successes':sum(t['success'] for t in tasks),'n':len(tasks),
            'task_actions':sum(len(t['trace']) for t in tasks),'tasks':tasks}

def run(output, seed=44017):
    output.mkdir(parents=True,exist_ok=False)
    root = Path(tempfile.mkdtemp(prefix='atanor_r4_dev_'))
    start = time.process_time()
    candidates = pool(root/'available',seed)
    (root/'validation_results').mkdir()
    heldout = []
    for index,(cfg,before,action) in enumerate(pool(root/'validation',seed+19007)):
        body = Sandbox(root/'validation_results'/str(index),**cfg)
        body.step(action)
        heldout.append((before,action,body.observe()))
    records = {}
    for arm in ('active','random'):
        (root/arm/'acquisitions').mkdir(parents=True)
        model = RelationalLearner(schema=SCHEMA,partitioned=True)
        remaining = list(candidates)
        rng = random.Random(seed+71)
        acquisitions, checkpoints, selection_calls = [], {}, 0
        for budget in range(33):
            if budget in (0,4,8,16,32):
                snapshot = model.snapshot()
                measured = evaluate(model,heldout,root/arm/f'eval_{budget}',seed+39007)
                assert model.snapshot() == snapshot
                measured['acquisition_actions'] = budget
                measured['total_native_actions'] = budget+measured['task_actions']
                checkpoints[str(budget)] = measured
                print(arm,budget,{k:v for k,v in measured.items() if k!='tasks'},flush=True)
            if budget == 32:
                break
            public = [(before,action) for cfg,before,action in remaining]
            index = select(model,public,remaining=32-budget,rng=rng) if arm=='active' else rng.randrange(len(remaining))
            selection_calls += len(public) if arm=='active' else 0
            cfg,before,action = remaining.pop(index)
            body = Sandbox(root/arm/'acquisitions'/str(budget),**cfg)
            assert body.observe().to_dict() == before.to_dict()
            prediction = model.predict(before,[action])[0][0]
            succeeded = body.step(action)
            after = body.observe()
            model.learn(f'acquired-{budget}',before,action,after)
            acquisitions.append({'before':before.to_dict(),'action':action.to_dict(),'after':after.to_dict(),
                'prediction':prediction.to_dict(),'succeeded':succeeded,'native_root':str(body.root),'config':encode_config(cfg)})
        records[arm] = {'checkpoints':checkpoints,'acquisitions':acquisitions,'selection_prediction_calls':selection_calls}
    a,r = (records[k]['checkpoints'] for k in ('active','random'))
    active_error = sum(a[str(b)]['prediction_error'] for b in (8,16,32))/3
    random_error = sum(r[str(b)]['prediction_error'] for b in (8,16,32))/3
    ready = active_error < random_error and a['32']['successes'] >= r['32']['successes']
    report = {'verdict':'R4_DEV_READY' if ready else 'R4_DEV_NO_GO','capability_claim':False,
        'active_mean_error':active_error,'random_mean_error':random_error,
        'cpu_seconds':time.process_time()-start,'seed':seed,'native_root':str(root),
        'limit':'DEV only; supervisor supplies contexts, permits, observations and resets. No economic gain claimed.',
        'checkpoints':{arm:value['checkpoints'] for arm,value in records.items()}}
    (output/'records.json').write_text(json.dumps(records,sort_keys=True))
    (output/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='checkpoints'},indent=2),flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    run(args.output)
