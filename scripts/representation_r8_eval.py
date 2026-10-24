"""One fresh four-arm trial with ordinary-work learning and actual-only audit."""
import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.representation_r5_dev import run_arm
from scripts.representation_r1_eval import source_hashes,sha,save

def actual_training(row):
    acquired=row['acquisitions'];before=row['pre_task_snapshot'];final=row['learner_snapshot']
    observations=list(acquired)
    if row['learn_tasks']:
        observations.extend(event for task in row['tasks'] for event in task['trace'])
    return (before['revision']==len(acquired)==len(before['rows']) and final['revision']==len(observations)==len(final['rows']) and
        all(all(x[k]==y[k] for k in ('before','action','after')) and x['history']==[] for x,y in zip(final['rows'],observations)) and
        all(all(x[k]==y[k] for k in ('before','action','after')) for x,y in zip(before['rows'],acquired)))

def run(prereg,output):
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise RuntimeError('commit registration first')
    p=json.loads(prereg.read_text())
    candidate=p.get('candidate','discriminate');controls=p.get('controls',['none','online','lookahead'])
    if source_hashes()!=p['source_hashes'] or sha(ROOT/'evidence/r2-discovery/receipt.json')!=p['projection_sha256']:
        raise RuntimeError('source/projection binding mismatch')
    save(prereg.with_suffix('.attempt.json'),{'started':time.time(),'output':str(output),'prereg_sha256':sha(prereg)})
    output.mkdir(parents=True,exist_ok=False);root=Path(tempfile.mkdtemp(prefix='atanor_r8_fresh_'))
    rng=random.Random(p['seed']);rows=[];start=time.perf_counter()
    with (output/'rows.jsonl').open('x') as f:
        for block in range(p['blocks']):
            seed=rng.getrandbits(30);arms=list(p['arms']);rng.shuffle(arms)
            for arm in arms:
                if time.time()>=p['deadline_unix']:raise TimeoutError('hard cap; no retry')
                cpu=time.process_time();wall=time.perf_counter()
                r=run_arm(root/f'{block}_{arm}',seed,arm,budget=32,learn_tasks=arm!='none')
                r.update(block=block,cpu_seconds=time.process_time()-cpu,wall_seconds=time.perf_counter()-wall)
                rows.append(r);f.write(json.dumps(r,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
                print('completed',block+1,arm,flush=True)
    scores={}
    for arm in p['arms']:
        part=[r for r in rows if r['arm']==arm]
        s={k:sum(r[k] for r in part) for k in ('n','successes','acquisition_actions','task_actions','total_native_actions','cpu_seconds')}
        s['actions_per_success']=s['total_native_actions']/s['successes'] if s['successes'] else None
        scores[arm]=s
    rng=random.Random(p['bootstrap_seed']);differences={}
    for control in controls:
        d=[(next(r['successes'] for r in rows if r['block']==b and r['arm']==candidate)-
             next(r['successes'] for r in rows if r['block']==b and r['arm']==control))/8 for b in range(p['blocks'])]
        boot=sorted(sum(rng.choice(d) for _ in d)/len(d) for _ in range(10000))
        differences[control]={'lift':sum(d)/len(d),'lcb95':boot[500]}
    s=scores[candidate];ratio=s['actions_per_success']
    gates={'success_rate':s['successes']/s['n']>=.875,
        'none_lift':differences['none']['lift']>=.25 and differences['none']['lcb95']>=.1,
        'online_nonregression':differences['online']['lift']>=0 and differences['online']['lcb95']>=-.05,
        controls[2]+'_nonregression':differences[controls[2]]['lift']>=0 and differences[controls[2]]['lcb95']>=-.05,
        'acquisition_charged_economy':ratio is not None and all(scores[a]['actions_per_success'] is None or ratio<=scores[a]['actions_per_success'] for a in controls),
        'budgets':all(r['acquisition_actions']<=32 and all(len(t['trace'])<=2 for t in r['tasks']) for r in rows),
        'actual_only_training':all(actual_training(r) for r in rows),
        'source_unchanged':source_hashes()==p['source_hashes'],
        'projection_unchanged':sha(ROOT/'evidence/r2-discovery/receipt.json')==p['projection_sha256']}
    report={'verdict':p.get('study_label','R8')+('_LOCAL_CAPABILITY_GREEN' if all(gates.values()) else '_LOCAL_CAPABILITY_RED'),
        'gates':gates,'scores':scores,'differences':differences,'rows_sha256':sha(output/'rows.jsonl'),
        'prereg_sha256':sha(prereg),'wall_seconds':time.perf_counter()-start,
        'scope':'New instances, exposed mechanics. Same eight-task horizon. Actual acquisition+task action costs, not fixture/reset/measurement overhead. Independent native audit required.'}
    save(output/'report.json',report);print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prereg',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run(args.prereg,args.output)
