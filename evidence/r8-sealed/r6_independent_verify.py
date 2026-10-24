"""Independent stdlib native execution. No imports from ATANOR candidate."""
import json
import os
from pathlib import Path
import random
import shutil
import tempfile
from r3_independent_verify import observe,sha

BASE=Path('D:/ATANOR-experiments/2026-09-17')
ROOT=BASE/'representation-r6';OUT=BASE/'r6-fresh-v1'
PATTERNS=('coupled_full','coupled_empty','detached_absent','detached_empty','independent_full','independent_mixed')
OPS=[{'id':'empty','arity':1},{'id':'unlink','arity':1},{'id':'copy','arity':2}]

def config(count,seed,spec,pattern='coupled_full',payload=None):
    rng=random.Random(seed);names=[f'{rng.getrandbits(72):018x}' for _ in range(count+1)]
    payload=payload if payload is not None else rng.randbytes(rng.randint(53,199))
    initial={names[-1]:payload.hex()};links={}
    if pattern in ('coupled_full','coupled_empty'):
        initial[names[0]]=payload.hex() if pattern=='coupled_full' else ''
        links={name:names[0] for name in names[1:-1]}
    elif pattern in ('detached_absent','detached_empty'):
        initial[names[1]]=payload.hex();links={name:names[1] for name in names[2:-1]}
        if pattern=='detached_empty':initial[names[0]]=''
    else:
        initial.update({name:payload.hex() for name in names[:-1]})
        if pattern=='independent_mixed':initial[names[0]]=''
    paths=list(names);rng.shuffle(paths)
    handles={name:f'n{paths.index(name)}' for name in names}
    cfg={'paths':paths,'initial':initial,'initial_links':links,'protected':[handles[names[-1]]],
         'operations':OPS,'relation_spec':spec}
    return cfg,[handles[name] for name in names[:-1]],handles[names[-1]],payload

def construct(root,cfg):
    root.mkdir(parents=True)
    for name,value in cfg['initial'].items():(root/name).write_bytes(bytes.fromhex(value))
    for name,source in cfg['initial_links'].items():os.link(root/source,root/name)
    return [root/name for name in cfg['paths']]

def execute(paths,action,protected):
    assert set(action)=={'op','args'}
    args=[int(h[1:]) for h in action['args']]
    assert all(0<=i<len(paths) for i in args) and action['args'][-1] not in protected
    try:
        if action['op']=='empty':
            assert len(args)==1;paths[args[0]].write_bytes(b'')
        elif action['op']=='unlink':
            assert len(args)==1;paths[args[0]].unlink()
        else:
            assert action['op']=='copy' and len(args)==2 and args[0]!=args[1]
            shutil.copyfile(paths[args[0]],paths[args[1]])
        return True
    except OSError:return False

def main():
    p=json.loads((ROOT/'docs/R6_PREREG_V1.json').read_text());report=json.loads((OUT/'report.json').read_text())
    rows=[json.loads(x) for x in (OUT/'rows.jsonl').read_text().splitlines()]
    assert len(rows)==p['blocks']*4 and sha((OUT/'rows.jsonl').read_bytes())==report['rows_sha256']
    for name,digest in p['source_hashes'].items():assert sha((ROOT/name).read_bytes())==digest
    assert sha((ROOT/'evidence/r2-discovery/receipt.json').read_bytes())==p['projection_sha256']
    spec=json.loads((ROOT/'evidence/r2-discovery/receipt.json').read_text())['projection']
    root=Path(tempfile.mkdtemp(prefix='atanor_r6_independent_'));rng=random.Random(p['seed'])
    actual=[];ordinal=0;acquisition_count=task_count=0
    for block in range(p['blocks']):
        seed=rng.getrandbits(30);arms=list(p['arms']);rng.shuffle(arms)
        allowed=[config(n,seed+n*101+i,spec,pattern,b'x'*23)[0] for n in (2,3) for i,pattern in enumerate(PATTERNS)]
        for arm in arms:
            row=rows[ordinal];assert (row['block'],row['seed'],row['arm'])==(block,seed,arm)
            acquisitions=row['acquisitions'];assert len(acquisitions)<=32
            model=row['learner_snapshot'];assert model['revision']==len(acquisitions)==len(model['rows'])
            assert set(model['seen'])==set(range(len(acquisitions)))
            seen=set()
            for i,event in enumerate(acquisitions):
                cfg=event['config'];assert cfg in allowed
                key=json.dumps([cfg,event['action']],sort_keys=True);assert key not in seen;seen.add(key)
                paths=construct(root/str(ordinal)/'acquire'/str(i),cfg)
                assert observe(paths,spec)[0]==event['before']
                assert execute(paths,event['action'],cfg['protected'])==event['succeeded']
                assert observe(paths,spec)[0]==event['after']
                assert observe([Path(event['native_root'])/name for name in cfg['paths']],spec)==observe(paths,spec)
                learned=model['rows'][i]
                assert learned['history']==[]
                assert all(learned[k]==event[k] for k in ('before','action','after'))
                acquisition_count+=1
            successes=actions=0;assert len(row['tasks'])==8
            for t,task in enumerate(row['tasks']):
                j=t//2;collective=bool(t%2)
                cfg,aliases,reference,payload=config(4+j%2,seed+39007+j*191,spec)
                assert task['config']==cfg and task['collective']==collective
                paths=construct(root/str(ordinal)/'task'/str(t),cfg)
                expected={h:b'' if collective or i==0 else payload for i,h in enumerate(aliases)};expected[reference]=payload
                def success():return all(paths[int(h[1:])].is_file() and paths[int(h[1:])].read_bytes()==v for h,v in expected.items())
                assert len(task['trace'])<=2
                for event in task['trace']:
                    assert not success()
                    assert observe(paths,spec)[0]==event['before']
                    assert execute(paths,event['action'],cfg['protected'])==event['succeeded']
                    assert observe(paths,spec)[0]==event['after'];actions+=1
                assert success()==task['success'];successes+=success();task_count+=1
                assert observe([Path(task['native_root'])/name for name in cfg['paths']],spec)==observe(paths,spec)
            assert successes==row['successes'] and actions==row['task_actions']
            assert len(acquisitions)==row['acquisition_actions']
            assert actions+len(acquisitions)==row['total_native_actions']
            actual.append((block,arm,successes,actions,len(acquisitions)));ordinal+=1
    for arm in p['arms']:
        part=[r for r in actual if r[1]==arm];s=report['scores'][arm]
        assert s['successes']==sum(r[2] for r in part) and s['n']==8*len(part)
        assert s['task_actions']==sum(r[3] for r in part) and s['acquisition_actions']==sum(r[4] for r in part)
        assert s['total_native_actions']==s['task_actions']+s['acquisition_actions']
        assert s['actions_per_success']==(s['total_native_actions']/s['successes'] if s['successes'] else None)
    rng=random.Random(p['bootstrap_seed'])
    for control in ('none','random','active'):
        deltas=[(next(r[2] for r in actual if r[0]==b and r[1]=='lookahead')-next(r[2] for r in actual if r[0]==b and r[1]==control))/8 for b in range(p['blocks'])]
        boot=sorted(sum(rng.choice(deltas) for _ in deltas)/len(deltas) for _ in range(10000))
        assert report['differences'][control]=={'lift':sum(deltas)/len(deltas),'lcb95':boot[500]}
    result={'native_reexecution':'PASS','tasks':task_count,'acquisitions':acquisition_count,
            'actual_only_training':'PASS','seeded_config_and_arithmetic':'PASS','report_sha256':sha((OUT/'report.json').read_bytes()),'root':str(root)}
    with (BASE/'r6-independent-verification.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
