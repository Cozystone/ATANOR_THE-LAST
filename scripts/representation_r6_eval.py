"""One frozen fresh-instance acquisition trial, four controls and cost accounting."""
import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.representation_r5_dev import run_arm
from scripts.representation_r1_eval import source_hashes,sha,save

def run(prereg,output):
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():
        raise RuntimeError('commit registration first')
    p=json.loads(prereg.read_text())
    if source_hashes()!=p['source_hashes']:
        raise RuntimeError('candidate binding mismatch')
    if sha(ROOT/'evidence/r2-discovery/receipt.json')!=p['projection_sha256']:
        raise RuntimeError('projection binding mismatch')
    save(prereg.with_suffix('.attempt.json'),{'started':time.time(),'output':str(output),'prereg_sha256':sha(prereg)})
    output.mkdir(parents=True,exist_ok=False)
    root=Path(tempfile.mkdtemp(prefix='atanor_r6_fresh_'))
    rng=random.Random(p['seed']);rows=[];start=time.perf_counter()
    with (output/'rows.jsonl').open('x') as f:
        for block in range(p['blocks']):
            seed=rng.getrandbits(30);arms=list(p['arms']);rng.shuffle(arms)
            for arm in arms:
                if time.time()>=p['deadline_unix']:
                    raise TimeoutError('hard cap, preserve partial attempt')
                cpu=time.process_time();wall=time.perf_counter()
                result=run_arm(root/f'{block}_{arm}',seed,arm,budget=p['acquisition_budget'])
                result.update(block=block,cpu_seconds=time.process_time()-cpu,wall_seconds=time.perf_counter()-wall)
                rows.append(result);f.write(json.dumps(result,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
                print('completed',block+1,arm,flush=True)
    scores={}
    for arm in p['arms']:
        part=[r for r in rows if r['arm']==arm]
        s={k:sum(r[k] for r in part) for k in ('n','successes','acquisition_actions','task_actions','total_native_actions','cpu_seconds')}
        s['actions_per_success']=s['total_native_actions']/s['successes'] if s['successes'] else None
        s['prediction_error']=sum(r['prediction_error'] for r in part)/len(part)
        scores[arm]=s
    bootstrap=random.Random(p['bootstrap_seed'])
    differences={}
    for control in ('none','random','active'):
        d=[(next(r['successes'] for r in rows if r['block']==b and r['arm']=='lookahead')-
             next(r['successes'] for r in rows if r['block']==b and r['arm']==control))/8 for b in range(p['blocks'])]
        samples=sorted(sum(bootstrap.choice(d) for _ in d)/len(d) for _ in range(10000))
        differences[control]={'lift':sum(d)/len(d),'lcb95':samples[500]}
    candidate=scores['lookahead'];ratio=candidate['actions_per_success']
    gates={'success_rate':candidate['successes']/candidate['n']>=.875,
        'none_lift':differences['none']['lift']>=.25 and differences['none']['lcb95']>=.1,
        'random_nonregression':differences['random']['lift']>=0 and differences['random']['lcb95']>=-.05,
        'active_nonregression':differences['active']['lift']>=0 and differences['active']['lcb95']>=-.05,
        'acquisition_charged_economy':ratio is not None and all(scores[a]['actions_per_success'] is None or ratio<=scores[a]['actions_per_success'] for a in ('none','random','active')),
        'budgets':all(r['acquisition_actions']<=32 and all(len(t['trace'])<=2 for t in r['tasks']) for r in rows),
        'only_actual_training':all(r['learner_snapshot']['revision']==len(r['acquisitions']) and
             all(x['before']==y['before'] and x['action']==y['action'] and x['after']==y['after']
                 for x,y in zip(r['learner_snapshot']['rows'],r['acquisitions'])) and
             len(r['learner_snapshot']['rows'])==len(r['acquisitions']) for r in rows),
        'source_unchanged':source_hashes()==p['source_hashes'],
        'projection_unchanged':sha(ROOT/'evidence/r2-discovery/receipt.json')==p['projection_sha256']}
    report={'verdict':'R6_LOCAL_CAPABILITY_GREEN' if all(gates.values()) else 'R6_LOCAL_CAPABILITY_RED',
        'gates':gates,'scores':scores,'differences':differences,'rows_sha256':sha(output/'rows.jsonl'),
        'prereg_sha256':sha(prereg),'wall_seconds':time.perf_counter()-start,
        'scope':'Fresh instances of exposed native mechanics; no external judge or OS-isolated blinding. Independent native audit required before sealing.'}
    save(output/'report.json',report);print(json.dumps(report,indent=2))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--prereg',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();run(args.prereg,args.output)
