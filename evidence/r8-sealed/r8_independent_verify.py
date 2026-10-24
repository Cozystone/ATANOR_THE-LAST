"""Independent native audit including online task learning; no candidate imports."""
import json
from pathlib import Path
import random
import tempfile
from r6_independent_verify import config,construct,execute,PATTERNS
from r3_independent_verify import observe,sha

BASE=Path('D:/ATANOR-experiments/2026-09-17');ROOT=BASE/'representation-r8';OUT=BASE/'r8-fresh-v1'

def main():
    p=json.loads((ROOT/'docs/R8_PREREG_V1.json').read_text());report=json.loads((OUT/'report.json').read_text())
    rows=[json.loads(x) for x in (OUT/'rows.jsonl').read_text().splitlines()]
    assert len(rows)==p['blocks']*4 and sha((OUT/'rows.jsonl').read_bytes())==report['rows_sha256']
    for name,digest in p['source_hashes'].items():assert sha((ROOT/name).read_bytes())==digest
    assert sha((ROOT/'evidence/r2-discovery/receipt.json').read_bytes())==p['projection_sha256']
    spec=json.loads((ROOT/'evidence/r2-discovery/receipt.json').read_text())['projection']
    root=Path(tempfile.mkdtemp(prefix='atanor_r8_independent_'));rng=random.Random(p['seed'])
    actual=[];ordinal=0;acquisition_count=task_count=0
    for block in range(p['blocks']):
        seed=rng.getrandbits(30);arms=list(p['arms']);rng.shuffle(arms)
        allowed=[config(n,seed+n*101+i,spec,pattern,b'x'*23)[0] for n in (2,3) for i,pattern in enumerate(PATTERNS)]
        for arm in arms:
            row=rows[ordinal];assert (row['block'],row['seed'],row['arm'])==(block,seed,arm)
            assert row['learn_tasks']==(arm!='none')
            acquired=row['acquisitions'];assert len(acquired)<=32
            if arm in ('online','none'):assert not acquired
            pre=row['pre_task_snapshot'];final=row['learner_snapshot']
            assert pre['revision']==len(acquired)==len(pre['rows'])
            assert set(pre['seen'])==set(range(len(acquired)))
            seen=set();observations=[];event_ids=list(range(len(acquired)))
            for i,event in enumerate(acquired):
                cfg=event['config'];assert cfg in allowed
                key=json.dumps([cfg,event['action']],sort_keys=True);assert key not in seen;seen.add(key)
                paths=construct(root/str(ordinal)/'acquire'/str(i),cfg)
                assert observe(paths,spec)[0]==event['before']
                assert execute(paths,event['action'],cfg['protected'])==event['succeeded']
                assert observe(paths,spec)[0]==event['after']
                assert observe([Path(event['native_root'])/name for name in cfg['paths']],spec)==observe(paths,spec)
                assert pre['rows'][i]['history']==[]
                assert all(pre['rows'][i][k]==event[k] for k in ('before','action','after'))
                observations.append(event);acquisition_count+=1
            successes=actions=0;assert len(row['tasks'])==8
            for t,task in enumerate(row['tasks']):
                j=t//2;collective=bool(t%2)
                cfg,aliases,reference,payload=config(4+j%2,seed+39007+j*191,spec)
                assert task['config']==cfg and task['collective']==collective
                paths=construct(root/str(ordinal)/'task'/str(t),cfg)
                expected={h:b'' if collective or i==0 else payload for i,h in enumerate(aliases)};expected[reference]=payload
                def success():return all(paths[int(h[1:])].is_file() and paths[int(h[1:])].read_bytes()==v for h,v in expected.items())
                assert len(task['trace'])<=2
                for step,event in enumerate(task['trace']):
                    assert not success()
                    assert observe(paths,spec)[0]==event['before']
                    assert execute(paths,event['action'],cfg['protected'])==event['succeeded']
                    assert observe(paths,spec)[0]==event['after'];actions+=1
                    if row['learn_tasks']:
                        observations.append(event);event_ids.append(f'task-{j}-{collective}-{step}')
                assert success()==task['success'];successes+=success();task_count+=1
                assert observe([Path(task['native_root'])/name for name in cfg['paths']],spec)==observe(paths,spec)
            assert final['revision']==len(observations)==len(final['rows']) and set(final['seen'])==set(event_ids)
            for learned,observed in zip(final['rows'],observations):
                assert learned['history']==[] and all(learned[k]==observed[k] for k in ('before','action','after'))
            assert successes==row['successes'] and actions==row['task_actions']
            assert len(acquired)==row['acquisition_actions'] and actions+len(acquired)==row['total_native_actions']
            actual.append((block,arm,successes,actions,len(acquired)));ordinal+=1
    for arm in p['arms']:
        part=[r for r in actual if r[1]==arm];s=report['scores'][arm]
        assert s['successes']==sum(r[2] for r in part) and s['n']==8*len(part)
        assert s['task_actions']==sum(r[3] for r in part) and s['acquisition_actions']==sum(r[4] for r in part)
        assert s['total_native_actions']==s['task_actions']+s['acquisition_actions']
        assert s['actions_per_success']==(s['total_native_actions']/s['successes'] if s['successes'] else None)
    rng=random.Random(p['bootstrap_seed'])
    for control in ('none','online','lookahead'):
        d=[(next(r[2] for r in actual if r[0]==b and r[1]=='discriminate')-next(r[2] for r in actual if r[0]==b and r[1]==control))/8 for b in range(p['blocks'])]
        boot=sorted(sum(rng.choice(d) for _ in d)/len(d) for _ in range(10000))
        assert report['differences'][control]=={'lift':sum(d)/len(d),'lcb95':boot[500]}
    result={'native_reexecution':'PASS','tasks':task_count,'acquisitions':acquisition_count,
            'online_actual_only_learning':'PASS','seeded_config_and_arithmetic':'PASS','report_sha256':sha((OUT/'report.json').read_bytes()),'root':str(root)}
    with (BASE/'r8-independent-verification.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
