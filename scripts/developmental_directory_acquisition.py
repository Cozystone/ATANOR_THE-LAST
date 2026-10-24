"""Frozen DEV feasibility, no new exploration algorithm or autonomous curriculum.

Existing max(unknown,disagreement) heuristic vs random vs no acquisition. One
operator-supplied mixed file/directory body seed146001,count4,8continuous actions,
no reset/no goal during acquisition. Seed146099 for ties/random. Same195initial
records; no injected directory example. Fresh task instances147001/2,count3/4,
empty-directory move goals. Frozen task learners,full menu,horizon2,4096queries,
4actions each,180s total. PASS only missing2/2 and strict gain over random/none,
all replay/old14208retention pass. Otherwise NO_ACQUISITION_ADVANTAGE. One run;
no retries/tuning. Prior missing-support failure remains valid; new question is
whether accessible experience plus complementary effect model changes it.
"""
import json,random,sys,tempfile,time
from pathlib import Path
from contextlib import closing
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event
from scripts.developmental_persistent_client import PersistentClient
from scripts.developmental_effect_families import EffectFamilies
from scripts.developmental_continual_probe import score
from packages.action_core.world import Sandbox,Frame,Action
from packages.action_core.planner import Goal
from packages.shared_world.runtime import WorldSession,verify_world


def config(count,seed):
    cfg,aliases,ref,payload=configuration(count,seed,'detached_absent')
    cfg['operations']=cfg['operations']+[{'id':'rename','arity':2}]
    cfg['initial_links']={}
    cfg['initial'][cfg['paths'][int(aliases[1][1:])]]=None
    return cfg,aliases


def run(output, *, acquisition_seed=146001, task_seed=147001, choice_seed=146099,
        reverse_actions=False):
    output.mkdir(exist_ok=False);start=time.monotonic()
    read=lambda n:json.loads((ROOT/'evidence'/n).read_text())
    old=read('developmental-continual.json')['records']+read('developmental-online-eval.json')['records']
    initial=old+[read('developmental-composition-probe.json')['rows'][0]['native_record']]
    initial += [r['record'] for r in read('developmental-rewrite-scope.json')['rows'] if r['case'] in ('declared_absent','declared_present')]
    rows=[]
    with tempfile.TemporaryDirectory(prefix='atanor_directory_acq_') as temp:
        for arm in ('none','random','missing'):
            cfg,_=config(4,acquisition_seed);body=Sandbox(Path(temp)/arm,**cfg)
            model=EffectFamilies(initial);trace=[];rng=random.Random(choice_seed)
            for step in range(0 if arm=='none' else 8):
                if time.monotonic()-start>180:raise TimeoutError('180s cap')
                before=body.observe();actions=body.actions()
                if reverse_actions: actions.reverse()
                ranks=[]
                for action in actions:
                    cells=model.predict(before,action)
                    ranks.append((sum(not v for _,_,v in cells),sum(len(v)>1 for _,_,v in cells)))
                ranks=ranks if arm=='missing' else [(0,0)]*len(actions)
                best=max(ranks);index=rng.choice([i for i,r in enumerate(ranks) if r==best])
                record=event(body,actions[index]);trace.append(record);model.learn([record])
            # Independent native reexecution from external fixture, not forecast.
            replay=Sandbox(Path(temp)/(arm+'-replay'),**cfg)
            replay_ok=all(event(replay,Action.from_dict(r['action']))==r for r in trace)
            tasks=[]
            for ordinal in range(2):
                if time.monotonic()-start>180:raise TimeoutError('180s cap')
                tc,aliases=config(3+ordinal,task_seed+ordinal);name=f'{arm}-{ordinal}'
                target=Sandbox(Path(temp)/name,**tc)
                goal=Goal('directory-move',kinds=((aliases[1],0),(aliases[0],2)))
                client=PersistentClient(initial+trace,schema=tc['operations'],horizon=2,limit=4096,
                    learning=False,planner='cost_ordered',representation='families')
                path=output/(name+'.sqlite')
                with closing(WorldSession(path,target,client,config=tc,total_budget=4,world_id=name,self_id='research-self')) as world:
                    world.issue_goal(goal,4);outcome=world.run_goal();steps=world.state['steps']
                verified=verify_world(path,expected_config=tc,expected_total_budget=4,
                    expected_world_id=name,expected_self_id='research-self',expected_goals=[(goal,4)])
                tasks.append(dict(outcome=outcome,actions=steps,replay=verified))
            retention=Counter()
            for r in old:
                retention.update(score(model.predict(Frame.from_dict(r['before']),Action.from_dict(r['action'])),Frame.from_dict(r['after'])))
            rows.append(dict(arm=arm,trace=trace,acquisition_replay=replay_ok,tasks=tasks,retention=retention))
    summary={r['arm']:sum(t['outcome']['completed'] for t in r['tasks']) for r in rows}
    verified=all(r['acquisition_replay'] and r['retention']=={'correct_singleton':14208}
        and all(t['replay']['green'] for t in r['tasks']) for r in rows)
    passed=verified and summary['missing']==2 and all(summary[a]<2 for a in ('none','random'))
    result=dict(verdict='BOUNDED_ACQUISITION_ADVANTAGE' if passed else 'NO_ACQUISITION_ADVANTAGE',
        scope=__doc__,parameters=dict(acquisition_seed=acquisition_seed, task_seed=task_seed,
            choice_seed=choice_seed,reverse_actions=reverse_actions),
        summary=summary,verified=verified,rows=rows)
    (output/'report.json').write_text(json.dumps(result,sort_keys=True))
    print(json.dumps({k:v for k,v in result.items() if k not in ('scope','rows')}))
    return result


if __name__=='__main__':run(Path(sys.argv[1]))
