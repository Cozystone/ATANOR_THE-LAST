"""One-shot new-instance comparison, not unseen mechanics/autonomous curriculum.

Freeze four instances145001..145004,count3/4 alternating occupied file and
directory source. Before=195previous observations; after=those+occupied,
missing_source,directory_source historical actual observations (no rejected
same-argument row). Both frozen during evaluation, same full permitted action
menu, cost-order horizon2/query4096,4actions/goal,180s overall. Alternate arm
execution order. PASS only if after solves all4, strict paired success gain,
no paired loss,old14208correct retained,and all native replays GREEN. Otherwise
NO_TASK_GAIN (or verification failure). Do not retry or change thresholds.
"""
import json
import sys
import tempfile
import time
from collections import Counter
from contextlib import closing
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.developmental_persistent_client import PersistentClient
from scripts.representation_r3_dev import configuration
from scripts.developmental_continual_probe import score
from packages.action_core.world import Sandbox,Frame,Action
from packages.action_core.planner import Goal
from packages.shared_world.runtime import WorldSession,verify_world


def run(output):
    output.mkdir(exist_ok=False); start=time.monotonic()
    read=lambda n:json.loads((ROOT/'evidence'/n).read_text())
    old=read('developmental-continual.json')['records']+read('developmental-online-eval.json')['records']
    scope=read('developmental-rewrite-scope.json')['rows']
    initial=old+[read('developmental-composition-probe.json')['rows'][0]['native_record']]
    initial += [r['record'] for r in scope if r['case'] in ('declared_absent','declared_present')]
    extra=[next(r['record'] for r in scope if r['case']==case)
           for case in ('occupied','missing_source','directory_source')]
    rows=[]
    with tempfile.TemporaryDirectory(prefix='atanor_observable_tasks_') as temp:
        for ordinal in range(4):
            cfg,aliases,ref,payload=configuration(3+ordinal%2,145001+ordinal,'detached_absent')
            cfg['operations']=cfg['operations']+[{'id':'rename','arity':2}]
            dest,source=(cfg['paths'][int(h[1:])] for h in aliases[:2])
            directory=bool(ordinal%2)
            if directory:
                cfg['initial_links']={};cfg['initial'][source]=None
            else:cfg['initial'][dest]=b'occupied payload'
            goal=Goal('move',kinds=((aliases[1],0),(aliases[0],2 if directory else 1)))
            for arm in (('before','after') if ordinal%2==0 else ('after','before')):
                name=f'{ordinal}-{arm}';body=Sandbox(Path(temp)/name,**cfg)
                client=PersistentClient(initial+(extra if arm=='after' else []),schema=cfg['operations'],
                    horizon=2,limit=4096,learning=False,planner='cost_ordered',representation='families')
                path=output/(name+'.sqlite');cpu=time.process_time()
                with closing(WorldSession(path,body,client,config=cfg,total_budget=4,world_id=name,self_id='research-self')) as world:
                    world.issue_goal(goal,4)
                    while world.state['active'] is not None:
                        if time.monotonic()-start>180:raise TimeoutError('180s cap')
                        outcome=world.step()
                        if world.state['halted']:raise RuntimeError(outcome)
                    actions=world.state['steps']
                elapsed=time.process_time()-cpu
                replay=verify_world(path,expected_config=cfg,expected_total_budget=4,
                    expected_world_id=name,expected_self_id='research-self',expected_goals=[(goal,4)])
                retained=Counter()
                for record in old:
                    retained.update(score(client.adapter.predict_cells(Frame.from_dict(record['before']),
                        Action.from_dict(record['action'])),Frame.from_dict(record['after'])))
                rows.append(dict(ordinal=ordinal,arm=arm,directory=directory,outcome=outcome,
                    actions=actions,cpu=elapsed,replay=replay,retention=retained))
    summary={arm:dict(completed=sum(r['outcome']['completed'] for r in rows if r['arm']==arm),
        actions=sum(r['actions'] for r in rows if r['arm']==arm)) for arm in ('before','after')}
    verified=all(r['replay']['green'] and r['retention']=={'correct_singleton':14208} for r in rows)
    passed=verified and summary['after']['completed']==4 and summary['before']['completed']<4
    result=dict(verdict='BOUNDED_TASK_GAIN' if passed else 'NO_TASK_GAIN' if verified else 'VERIFICATION_FAILED',
                scope=__doc__,summary=summary,verified=verified,rows=rows)
    (output/'report.json').write_text(json.dumps(result,sort_keys=True))
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','scope')}))


if __name__=='__main__':run(Path(sys.argv[1]))
