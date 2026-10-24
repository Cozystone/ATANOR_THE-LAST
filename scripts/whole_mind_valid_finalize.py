"""Close already-exhausted trials, NEVER rerun or permit one more native action.

Original raw snapshots are preserved. Only the frozen supervisor's normal
OBSERVE/GOAL_END tail is allowed. Evaluation finalization, not a fourth arm.
"""
import json
from pathlib import Path
import shutil
import sqlite3
import sys
from contextlib import closing
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.episode import digest
from packages.action_core.world import Sandbox
from packages.action_core.planner import Goal
from packages.shared_world import runtime
from scripts.whole_mind_bridge import WholeMindClient
from scripts.persistent_mind_loop import decode_config
from scripts.whole_mind_valid_eval import ReplayBody,ExternalFileEvent,hashes,frozen_equal,native_state

def close_exhausted(world):
    before=world.state
    if before['steps']!=world.binding['total_budget']:
        raise ValueError('only an exhausted unfinished terminal tail may close')
    if before['active'] is None:
        assert before['goals'][-1]['result']['reason']=='step_budget_exceeded'
        return dict(native_actions_added=0,model_unchanged=True,steps=before['steps'],terminal=before['goals'][-1]['result'])
    with patch.object(world.body,'step',side_effect=AssertionError('NO EXTRA NATIVE ACTION')):
        with patch.object(world.client,'choose',side_effect=AssertionError('NO EXTRA COGNITION')):
            world.step()
    after=world.state
    assert after['steps']==before['steps'] and after['model']==before['model']
    assert after['active'] is None and after['goals'][-1]['result']['reason'] in ('goal_reached','step_budget_exceeded')
    return dict(native_actions_added=0,model_unchanged=True,steps=after['steps'],terminal=after['goals'][-1]['result'])

def run(out):
    out=Path(out);pre=json.loads((out/'PREFLIGHT.json').read_text())
    assert frozen_equal() and hashes()==pre['frozen_hashes']
    if (out/'FINALIZATION_COMPLETED').exists():raise ValueError('already finalized')
    if not (out/'FINALIZATION_STARTED').exists():
        (out/'FINALIZATION_STARTED').open('x').close()
        shutil.copy2(out/'FINAL_STATUS.json',out/'PRE_FINALIZATION_STATUS.json')
    rows={}
    for arm in ('full','no_memory','no_planning'):
        folder=out/arm;original=folder/'pre_finalization'
        if not original.exists():
            original.mkdir()
            for name in ('receipt.json','journal.json','final_native_state.json'):
                shutil.copy2(folder/name,original/name)
            with sqlite3.connect(folder/'world.sqlite') as src,sqlite3.connect(original/'world.sqlite') as dst:src.backup(dst)
        intent=json.loads((folder/'intent.json').read_text());cfg=decode_config(intent['config'])
        body=Sandbox.attach(Path(intent['body_root']),**{k:v for k,v in cfg.items() if k!='initial'})
        client=WholeMindClient([],cfg['operations'],arm)
        with closing(runtime.WorldSession(folder/'world.sqlite',body,client,config=cfg,total_budget=intent['cap'],
                    world_id='whole-mind-world-valid',self_id='whole-mind-self-valid')) as w:
            tail=close_exhausted(w)
        with sqlite3.connect(folder/'world.sqlite') as db:
            journal=[dict(seq=s,kind=k,payload=json.loads(p)) for s,k,p in db.execute('SELECT seq,kind,payload FROM events ORDER BY seq')]
        old=json.loads((original/'journal.json').read_text())
        assert journal[:len(old)]==old and [e['kind'] for e in journal[len(old):]]==['OBSERVE','OBSERVE','GOAL_END']
        with sqlite3.connect(original/'world.sqlite') as db:
            old_state=json.loads(db.execute('SELECT payload FROM state').fetchone()[0])
        with sqlite3.connect(folder/'world.sqlite') as db:
            new_state=json.loads(db.execute('SELECT payload FROM state').fetchone()[0])
        assert old_state['model']==new_state['model'] and old_state['steps']==new_state['steps']
        (folder/'journal.json').write_text(json.dumps(journal,indent=2))
        intervention=json.loads((folder/'intervention.json').read_text())
        with patch.object(runtime,'Sandbox',ReplayBody):
            verification=runtime.verify_world(folder/'world.sqlite',expected_config=cfg,expected_total_budget=intent['cap'],
                expected_world_id='whole-mind-world-valid',expected_self_id='whole-mind-self-valid',
                expected_goals=[(Goal.from_dict(intent['goal']),intent['cap'])],
                expected_external_actions={intervention['observation_seq']:[ExternalFileEvent()]})
        row=json.loads((original/'receipt.json').read_text());row['verified']=verification;row['finalization']=tail
        assert native_state(body)==row['native_final']
        (folder/'receipt.json').write_text(json.dumps(row,indent=2));rows[arm]=row
    f=rows['full'];valid=all(r['verified']['green'] and r['continuity'] and r['preview_pure'] and
        r['thought_dispatch'] and r['experiences_native_only'] for r in rows.values())
    # This actual Full failed. Finalization cannot manufacture a positive claim.
    assert f['completed']==0
    result=dict(verdict='WHOLE_MIND_V0_VALID_CAPABILITY_FAIL' if valid else 'INVALID_EXPERIMENT_AGAIN',
        source_unchanged=hashes()==pre['frozen_hashes'],hashes_after=hashes(),
        extra_native_actions=0,mission_runs_per_arm=1,finalization_disclosed=True,
        first_decisive_failure='action-selection failure: action5 mkdir(n6), whose goal was FILE, entered an irreversible native directory state before disturbance',
        results={a:dict(completed=r['completed'],steps=r['steps'],noops=r['noops'],
            final_conditions_met=sum(r['native_final']['conditions']),native_replay_green=r['verified']['green'],
            manifest_unchanged=r['native_final']['manifest_unchanged'],n7_recovered=r['native_final']['evidence']['n7']['kind']==2,
            exact_post_reachable=r['exact_post_reachable']) for a,r in rows.items()},
        full_causal_readonly_differences=len(f['causal_readonly_choices']),
        scope='Valid initial mission and safe disturbance; full self-created dead end. No V0 success, no rerun, no cognition repair.')
    (out/'FINAL_STATUS.json').write_text(json.dumps(result,indent=2))
    (out/'FINALIZATION_COMPLETED').open('x').close();print(json.dumps(result))

if __name__=='__main__':run(sys.argv[1])
