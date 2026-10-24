"""Frozen same-world online/frozen comparison with session restart, one run.

Body150001,count4;195initial records,no injected directory experience. Three
human goals:directory1->0,0->2,2->1. Same full menu,exploration seed150099,
horizon2/query4096,8actions/goal,24total,180s overall. Both arms journal all actual
events; OFF retains autobiography but effect learner uses initial records only.
New client+WorldSession per goal, same native body/database; exact checkpoint
restoration required. This is session-object restart, NOT OS/process crash test.
PASS: online3completed with>=1action each; strict success lift OR <=75%actions
if frozen also3;old14208retained,both native replays GREEN. No retries/tuning.
Skill reuse is NOT faster learning of a different skill or generality.
"""
import json,sys,tempfile,time
from pathlib import Path
from contextlib import closing
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_directory_acquisition import config
from scripts.developmental_exploring_client import ExploringClient
from scripts.developmental_continual_probe import score
from packages.action_core.world import Sandbox,Frame,Action
from packages.action_core.planner import Goal
from packages.shared_world.runtime import WorldSession,verify_world


def run(output):
    output.mkdir(exist_ok=False);start=time.monotonic()
    read=lambda n:json.loads((ROOT/'evidence'/n).read_text())
    old=read('developmental-continual.json')['records']+read('developmental-online-eval.json')['records']
    initial=old+[read('developmental-composition-probe.json')['rows'][0]['native_record']]
    initial += [r['record'] for r in read('developmental-rewrite-scope.json')['rows'] if r['case'] in ('declared_absent','declared_present')]
    cfg,aliases=config(4,150001)
    goals=[Goal(str(i),kinds=((aliases[s],0),(aliases[d],2))) for i,(s,d) in enumerate(((1,0),(0,2),(2,1)))]
    results={}
    with tempfile.TemporaryDirectory(prefix='atanor_exploring_life_') as temp:
        for arm in ('frozen','online'):
            body=Sandbox(Path(temp)/arm,**cfg);path=output/(arm+'.sqlite')
            checkpoint=None;outcomes=[];resumed=True;cpu=time.process_time()
            for goal in goals:
                client=ExploringClient(initial if checkpoint is None else [],schema=cfg['operations'],
                    exploration_seed=150099,learning=arm=='online',representation='families',
                    planner='cost_ordered',horizon=2,limit=4096)
                with closing(WorldSession(path,body,client,config=cfg,total_budget=24,world_id='w',self_id='s')) as world:
                    if checkpoint is not None: resumed &= client.snapshot()==checkpoint
                    before=world.state['steps'];world.issue_goal(goal,8)
                    while world.state['active'] is not None:
                        if time.monotonic()-start>180:raise TimeoutError('180s cap')
                        outcome=world.step()
                        if world.state['halted']:raise RuntimeError(outcome)
                    outcomes.append(dict(outcome=outcome,actions=world.state['steps']-before))
                    checkpoint=client.snapshot()
            elapsed=time.process_time()-cpu
            replay=verify_world(path,expected_config=cfg,expected_total_budget=24,
                expected_world_id='w',expected_self_id='s',expected_goals=[(g,8) for g in goals])
            retention=Counter()
            for r in old:
                retention.update(score(client.adapter.predict_cells(Frame.from_dict(r['before']),
                    Action.from_dict(r['action'])),Frame.from_dict(r['after'])))
            results[arm]=dict(outcomes=outcomes,completed=sum(r['outcome']['completed'] for r in outcomes),
                actions=sum(r['actions'] for r in outcomes),cpu=elapsed,replay=replay,
                retention=retention,checkpoint_restored=resumed,final_revision=checkpoint['revision'])
    a,b=results['online'],results['frozen']
    verified=all(r['replay']['green'] and r['checkpoint_restored'] and r['retention']=={'correct_singleton':14208} for r in results.values())
    passed=verified and a['completed']==3 and all(r['actions']>=1 for r in a['outcomes']) and (b['completed']<3 or a['actions']<=.75*b['actions'])
    result=dict(verdict='BOUNDED_PERSISTENT_LEARNING_GAIN' if passed else 'NO_PERSISTENT_GAIN',scope=__doc__,verified=verified,results=results)
    (output/'report.json').write_text(json.dumps(result,sort_keys=True))
    print(json.dumps({**{k:v for k,v in result.items() if k not in ('scope','results')},
        'summary':{k:{f:r[f] for f in ('completed','actions','cpu','final_revision')} for k,r in results.items()}}))


if __name__=='__main__':run(Path(sys.argv[1]))
