"""Single frozen native mission and two causal ablations; no tuning loop."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.episode import digest,encode_config
from packages.action_core.world import Sandbox,Action,Frame
from packages.action_core.planner import Goal
from packages.shared_world.runtime import WorldSession,verify_world
from scripts.persistent_mind_loop import decode_config,completed_count
from scripts.whole_mind_bridge import WholeMindClient

SELF='whole-mind-self-v0';WORLD='whole-mind-workspace-v0'
SCHEMA=[dict(id=x,arity=1) for x in ('mkdir','empty','unlink')]

def worker(folder,expected,limit,preview=False):
    folder=Path(folder);intent=json.loads((folder/'intent.json').read_text())
    if digest(intent)!=expected:raise ValueError('intent changed')
    cfg=decode_config(intent['config']);root=Path(intent['body_root'])
    client=WholeMindClient([],cfg['operations'],intent['arm'],None if preview else folder/'thoughts.jsonl')
    goal=Goal.from_dict(intent['goal'])
    if preview:
        with sqlite3.connect(folder/'world.sqlite') as db:
            state=json.loads(db.execute('SELECT payload FROM state').fetchone()[0])
        client.restore(state['model'])
        body=Sandbox.attach(root,**{k:v for k,v in cfg.items() if k!='initial'})
        reply=client.choose(Frame.from_dict(state['frame']),goal,body.actions(),[])
        return dict(action=reply[0].to_dict(),forecast=reply[1].to_dict(),model_digest=digest(client.snapshot()))
    if root.exists():body=Sandbox.attach(root,**{k:v for k,v in cfg.items() if k!='initial'})
    else:
        if (folder/'world.sqlite').exists():raise ValueError('lost body')
        body=Sandbox(root,**cfg)
    with closing(WorldSession(folder/'world.sqlite',body,client,config=cfg,total_budget=48,world_id=WORLD,self_id=SELF)) as w:
        before=digest(client.snapshot());start=w.state['steps']
        if not w.state['goals']:w.issue_goal(goal,48)
        for _ in range(limit+2):
            if w.state['active'] is None or w.state['steps']-start>=limit:break
            w.step()
            if w.state['halted']:raise RuntimeError(w.state['halted'])
        return dict(pid=os.getpid(),initial_model_digest=before,final_model_digest=digest(client.snapshot()),
                    completed=completed_count(w.state['goals']),steps=w.state['steps'],active=w.state['active'])

def call(folder,limit,preview=False):
    intent=json.loads((folder/'intent.json').read_text())
    p=subprocess.run([sys.executable,__file__,'preview' if preview else 'worker',str(folder),digest(intent),str(limit)],capture_output=True,text=True,timeout=180)
    if p.returncode:raise RuntimeError(p.stderr)
    return json.loads(p.stdout)

def run(out):
    out=Path(out);out.mkdir(exist_ok=False)
    # Retained owned bodies allow inspection/resume after the block; no cleanup.
    base=Path(tempfile.mkdtemp(prefix='atanor_whole_mind_v0_'))
    paths=['workspace_'+str(i) for i in range(8)]+['operator_manifest.txt']
    cfg=dict(paths=paths,initial={p:(b'owned temporary input' if i%2==0 else None) for i,p in enumerate(paths[:-1])},protected=['n8'],operations=SCHEMA)
    cfg['initial'][paths[-1]]=b'Protected operator manifest; never modify.'
    goal=Goal('prepare-workspace',kinds=tuple(('n'+str(i),2 if i%2==0 else 1) for i in range(8)))
    results={}
    for arm in ('full','no_memory','no_planning'):
        folder=out/arm;folder.mkdir()
        intent=dict(arm=arm,config=encode_config(cfg),body_root=str(base/arm),goal=goal.to_dict())
        (folder/'intent.json').write_text(json.dumps(intent,indent=2))
        first=call(folder,6);preview=call(folder,0,True)
        body=Sandbox.attach(base/arm,**{k:v for k,v in cfg.items() if k!='initial'})
        frame=body.observe();target=preview['action']['args'][0];i=frame.handles.index(target)
        op=('empty' if preview['action']['op']=='mkdir' else 'mkdir') if frame.kinds[i]==0 else 'unlink'
        external=Action(op,(target,));assert body.step(external)
        changed=body.observe()
        with sqlite3.connect(folder/'world.sqlite') as db:seq=db.execute('SELECT MAX(seq) FROM events').fetchone()[0]+1
        intervention=dict(observation_seq=seq,action=external.to_dict(),before=frame.to_dict(),after=changed.to_dict(),preview=preview)
        (folder/'intervention.json').write_text(json.dumps(intervention,indent=2))
        last=call(folder,48)
        check=verify_world(folder/'world.sqlite',expected_config=cfg,expected_total_budget=48,
             expected_world_id=WORLD,expected_self_id=SELF,expected_goals=[(goal,48)],expected_external_actions={seq:[external]})
        with sqlite3.connect(folder/'world.sqlite') as db:
            events=[dict(seq=s,kind=k,payload=json.loads(p)) for s,k,p in db.execute('SELECT seq,kind,payload FROM events ORDER BY seq')]
        (folder/'journal.json').write_text(json.dumps(events,indent=2))
        after_plans=[e for e in events if e['seq']>seq and e['kind']=='PREDICT']
        thoughts=[json.loads(s) for s in (folder/'thoughts.jsonl').read_text().splitlines()]
        row=dict(completed=last['completed'],steps=last['steps'],workers=[first,last],native_verification=check,
            continuity=first['final_model_digest']==last['initial_model_digest'],
            distinct_processes=first['pid']!=last['pid'],single_goal=sum(e['kind']=='GOAL' for e in events)==1,
            surprise_observed=any(e['seq']==seq and e['kind']=='OBSERVE' and e['payload']['frame']==changed.to_dict() for e in events),
            plan_revised=bool(after_plans) and after_plans[0]['payload']['action']!=preview['action'],
            experience_used=any(t['derived_memory_edges']>0 and any(q[1] is not None for q in t['retrieved_edges']) for t in thoughts),
            operations_used=sorted({e['payload']['action']['op'] for e in events if e['kind']=='PREDICT'}),
            thought_dispatch_matches=[t['chosen'] for t in thoughts]==[e['payload']['action'] for e in events if e['kind']=='PREDICT'],
            final_evidence=body.evidence(),intent_digest=digest(intent))
        (folder/'receipt.json').write_text(json.dumps(row,indent=2));results[arm]=row
        print(json.dumps(dict(arm=arm,completed=row['completed'],steps=row['steps'],plan_revised=row['plan_revised'])),flush=True)
    full=results['full']
    loss=lambda r:r['completed']<full['completed'] or r['steps']>=full['steps']*1.25
    gates=dict(native=all(r['native_verification']['green'] for r in results.values()),
        continuity=all(r['continuity'] and r['distinct_processes'] and r['single_goal'] for r in results.values()),
        observations=all(r['surprise_observed'] and r['thought_dispatch_matches'] for r in results.values()),
        mission=full['completed']==1 and len(full['operations_used'])>=2,
        surprise_revision=full['plan_revised'],experience=full['experience_used'],
        memory_causal=loss(results['no_memory']),planning_causal=loss(results['no_planning']))
    report=dict(verdict='BOUNDED_INTEGRATION_SUPPORTED' if all(gates.values()) else 'INTEGRATION_PARTIAL',
                gates=gates,results=results,owned_body_root=str(base),
                scope='One authored flat-filesystem mission; H learned-edge BFS under R WorldSession. Not broad digital understanding, all-organ integration, AGI or consciousness.')
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(verdict=report['verdict'],gates=gates)))

if __name__=='__main__':
    if sys.argv[1]=='run':run(sys.argv[2])
    else:print(json.dumps(worker(sys.argv[2],sys.argv[3],int(sys.argv[4]),sys.argv[1]=='preview')))
