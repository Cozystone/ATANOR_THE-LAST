"""Validation instrumentation only. Frozen a890256 cognition owns all choices."""
import json
import os
from pathlib import Path
import sys
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.episode import digest
from packages.action_core.world import Sandbox,Frame
from packages.action_core.planner import Goal
from packages.shared_world.runtime import WorldSession
from scripts.persistent_mind_loop import decode_config,completed_count
from scripts.whole_mind_bridge import WholeMindClient

def preview(client,world,body,goal):
    before=digest(client.snapshot());trace=client.trace
    client.trace=None
    try:
        reply=client.choose(Frame.from_dict(world.state['frame']),goal,body.actions(),[])
    finally:client.trace=trace
    after=digest(client.snapshot())
    if before!=after:raise RuntimeError('preview mutated cognition')
    return dict(canonical_frame=world.state['frame'],observation_seq=world.state['observation_seq'],
                model_digest_before=before,model_digest_after=after,
                memory_digest=digest(sorted((list(k),v) for k,v in client.memory().d.items())),
                action=None if reply is None else reply[0].to_dict(),
                forecast=None if reply is None else reply[1].to_dict())

def run(folder,expected,phase):
    folder=Path(folder);intent=json.loads((folder/'intent.json').read_text())
    if digest(intent)!=expected:raise ValueError('intent binding')
    cfg=decode_config(intent['config']);root=Path(intent['body_root']);cap=intent['cap']
    if root.exists():body=Sandbox.attach(root,**{k:v for k,v in cfg.items() if k!='initial'})
    else:
        if phase!='first' or (folder/'world.sqlite').exists():raise ValueError('lost body')
        body=Sandbox(root,**cfg)
    client=WholeMindClient([],cfg['operations'],intent['arm'],folder/'thoughts.jsonl')
    goal=Goal.from_dict(intent['goal'])
    with closing(WorldSession(folder/'world.sqlite',body,client,config=cfg,total_budget=cap,
                 world_id='whole-mind-world-valid',self_id='whole-mind-self-valid')) as w:
        initial=digest(client.snapshot());start=w.state['steps']
        if not w.state['goals']:w.issue_goal(goal,cap)
        if phase=='resume':
            w.poll(reason='restart_reobservation')
            (folder/'preview_after.json').write_text(json.dumps(preview(client,w,body,goal),indent=2))
        limit=5 if phase=='first' else cap
        for _ in range(cap+4):
            if w.state['active'] is None or w.state['steps']>=limit:break
            w.step()
            if w.state['halted']:raise RuntimeError(w.state['halted'])
        if phase=='first':
            if w.state['steps']!=5:raise RuntimeError('did not reach five actions')
            (folder/'preview_before.json').write_text(json.dumps(preview(client,w,body,goal),indent=2))
            print(json.dumps(dict(ready=True,pid=os.getpid(),steps=5)),flush=True)
            if sys.stdin.readline().strip()!='external-event-done':raise RuntimeError('missing stop authorization')
            # WorldSession already durably committed the fifth result and memory.
            # Do not observe the disturbance until the NEW worker resumes.
        result=dict(pid=os.getpid(),start_steps=start,steps=w.state['steps'],
                    initial_model_digest=initial,final_model_digest=digest(client.snapshot()),
                    completed=completed_count(w.state['goals']),active=w.state['active'],halted=w.state['halted'])
    print(json.dumps(result),flush=True)

if __name__=='__main__':run(sys.argv[1],sys.argv[2],sys.argv[3])
