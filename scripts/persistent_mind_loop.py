"""Opt-in lifecycle bridge for EXISTING WorldSession and learned planner.

An operator-authorized persistent agenda, not autonomous goal invention or
consciousness. No main-runtime changes. Thought traces are diagnostics, never
authority/evidence. Real filesystem effects remain in existing Sandbox.
"""
import json
import os
from pathlib import Path
import random
import sqlite3
import sys
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_exploring_client import ExploringClient
from packages.action_core.world import Sandbox
from packages.action_core.planner import Goal
from packages.action_core.episode import digest
from packages.shared_world.runtime import WorldSession
from packages.shared_world.contracts import ScopedPartialForecast


def decode_config(c):
    c=dict(c)
    for field in ('initial','context_initial'):
        if field in c:c[field]={k:None if v is None else bytes.fromhex(v) for k,v in c[field].items()}
    return c


def completed_count(goals):
    return sum(bool((g.get('result') or {}).get('completed')) for g in goals)


class ObservedClient(ExploringClient):
    def _decision(self,*args,**kwargs):
        reply=super()._decision(*args,**kwargs)
        self.decision_mode='model_supported' if reply[0] is not None else 'unknown_exploration'
        return reply

    def emit(self,row):
        with self.trace.open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')

    def choose(self,frame,goal,actions,history,*,failed_attempts=()):
        candidates=[dict(action=a.to_dict(),cells=self.adapter.predict_cells(frame,a)) for a in actions]
        if self.no_prediction and actions:
            self.decision_mode='prediction_disabled'
            i=random.Random(self.exploration_seed+self.state['revision']).randrange(len(actions))
            cells=[(field,address,[]) for field,address,_ in candidates[i]['cells']]
            reply=(actions[i],ScopedPartialForecast(frame.handles,frame.parent,list(frame.relations),cells),len(actions))
        else:reply=super().choose(frame,goal,actions,history,failed_attempts=failed_attempts)
        self.emit(dict(kind='THINK',revision=self.state['revision'],goal=goal.to_dict(),before=frame.to_dict(),
                       alternatives=candidates,chosen=None if reply is None else reply[0].to_dict(),
                       prediction=None if reply is None else reply[1].to_dict(),
                       query_nodes=0 if reply is None else reply[2],instrumentation_queries=len(actions),
                       decision_mode=getattr(self,'decision_mode','abstained'),
                       authority=False))
        return reply

    def learn(self,event_id,before,action,after,history):
        p0=self.adapter.predict_cells(before,action)
        answer=super().learn(event_id,before,action,after,history)
        p1=self.adapter.predict_cells(before,action)
        self.emit(dict(kind='REVISE',event_id=event_id,revision=self.state['revision'],
                       previous=p0,revised=p1,changed=p0!=p1,authority=False))
        return answer


def worker(folder,expected_digest,max_actions):
    folder=Path(folder);intent=json.loads((folder/'intent.json').read_text())
    if digest(intent)!=expected_digest:raise ValueError('authorized intent mismatch')
    cfg=decode_config(intent['config']);root=Path(intent['body_root'])
    # Never reconstruct an existing body's files from initial fixtures.
    if root.exists():body=Sandbox.attach(root,**{k:v for k,v in cfg.items() if k!='initial'})
    else:
        if (folder/'world.sqlite').exists():raise ValueError('journal exists but native body missing')
        body=Sandbox(root,**cfg)
    total_budget=intent.get('total_budget',24);goal_budget=intent.get('goal_budget',8)
    if any(type(v) is not int or not 1<=v<=64 for v in (total_budget,goal_budget)):
        raise ValueError('bounded operator budgets required')
    client=ObservedClient(intent['initial_records'],schema=cfg['operations'],
        exploration_seed=150099,learning=intent['arm']!='frozen',representation='families',
        planner='cost_ordered',horizon=2,limit=4096)
    client.trace=folder/'thoughts.jsonl';client.no_prediction=intent['arm']=='no_prediction'
    goals=[Goal.from_dict(g) for g in intent['goals']]
    with closing(WorldSession(folder/'world.sqlite',body,client,config=cfg,total_budget=total_budget,
                              world_id='persistent-world',self_id='persistent-self')) as world:
        start=world.state['steps'];initial=digest(client.snapshot());ticks=0
        while ticks<128 and world.state['steps']-start<max_actions:
            state=world.state
            if state['halted']:raise RuntimeError(state['halted'])
            if state['active'] is None:
                if len(state['goals'])==len(goals):break
                world.issue_goal(goals[len(state['goals'])],goal_budget)
            world.step();ticks+=1
        result=dict(pid=os.getpid(),start_steps=start,steps=world.state['steps'],
                    initial_model_digest=initial,final_model_digest=digest(client.snapshot()),
                    revision=client.state['revision'],active=world.state['active'],
                    completed=completed_count(world.state['goals']),
                    exhausted=len(world.state['goals'])==len(goals) and world.state['active'] is None)
    print(json.dumps(result))

if __name__=='__main__':worker(sys.argv[1],sys.argv[2],int(sys.argv[3]))
