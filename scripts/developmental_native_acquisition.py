"""One-shot native selected-feedback prediction experiment, not agency claim.

Freeze:12 training cases143001..12,12 evaluation144001..12,count5..7,flat/
missing/present parent balanced. Fixed effect model from3historical transitions.
Balanced exploration training, then greedy frozen acquisition policy. Actions and
goals are evaluator-supplied probes, NOT learned planning. Arms none/random/arg0/
arg1/learned/all. One native action/case, sensor budget2 (all gets at most one
extra node too). 180s cap; no retries. PASS for BOUNDED_PREDICTION_GAIN only if
learned loss <= half none/random, learned wrong0, all replays GREEN. Strong fixed
arg1 comparison always reported; tying it is NOT general acquisition advantage.
Loss:wrong1,unknown/ambiguous.5,correct0 per original-scope cell. No effect-model
tuning/test learning. Every prediction precedes native action; only selected
observation and actual outcome train acquisition. Models don't see fixture mode.
"""
import copy
import json
import random
import sys
import tempfile
import time
from collections import Counter
from contextlib import closing
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Frame,Action
from packages.action_core.planner import Goal
from packages.shared_world.contextual_rewrite import ContextualRewrite
from packages.shared_world.acquisition_value import AcquisitionValue
from packages.shared_world.contracts import ScopedPartialForecast
from packages.shared_world.relational import _value
from packages.shared_world.runtime import WorldSession,verify_world
from scripts.representation_r3_dev import configuration


def measure(cells, after):
    counts=Counter('unknown' if not v else 'wrong' if _value(after,f,a) not in v else
        'correct' if len(v)==1 else 'ambiguous' for f,a,v in cells)
    return dict(counts=counts,loss=(counts['wrong']+.5*(counts['unknown']+counts['ambiguous']))/sum(counts.values()))


class Probe:
    def __init__(self,action):self.action=action;self.revision=0;self.prediction=None
    def snapshot(self):return {'revision':self.revision}
    def restore(self,s):self.revision=s['revision']
    def choose(self,*args,**kwargs):return self.action,self.prediction,1
    def learn(self,*args):self.revision+=1;return True


def run(output):
    output.mkdir(exist_ok=False);start=time.monotonic();rng=random.Random(143099)
    read=lambda n:json.loads((ROOT/'evidence'/n).read_text())
    seeds=[read('developmental-composition-probe.json')['rows'][0]['native_record']]
    seeds += [r['record'] for r in read('developmental-rewrite-scope.json')['rows'] if r['case'] in ('declared_absent','declared_present')]
    model=ContextualRewrite(seeds);policy=AcquisitionValue();rows=[]
    with tempfile.TemporaryDirectory(prefix='atanor_sense_life_') as temp:
        for phase in ('train','eval'):
            for ordinal in range(12):
                cfg,aliases,ref,payload=configuration(5+ordinal%3,(143001 if phase=='train' else 144001)+ordinal,'detached_absent')
                cfg['operations']=cfg['operations']+[{'id':'rename','arity':2}]
                cfg['paths']=list(cfg['paths']);mode=ordinal%3
                if mode:
                    i=int(aliases[0][1:]);cfg['paths'][i]='envelope/'+cfg['paths'][i]
                    cfg['context_initial']={'envelope':None} if mode==2 else {}
                action=Action('rename',(aliases[1],aliases[0]))
                goal=Goal('probe',kinds=((aliases[1],0),(aliases[0],1)))
                for arm in (('learned',) if phase=='train' else ('none','random','arg0','arg1','learned','all')):
                    if time.monotonic()-start>180:raise TimeoutError('180s cap')
                    name=f'{phase}-{ordinal}-{arm}';body=Sandbox(Path(temp)/name,**cfg)
                    probe=Probe(action);before=body.observe();n=len(before.handles)
                    baseline=model.predict(before,action)
                    selected=( [policy.explore(before,action,rng)] if phase=='train' else
                        [] if arm=='none' else [rng.choice(before.handles)] if arm=='random' else
                        [action.args[0]] if arm=='arg0' else [action.args[1]] if arm=='arg1' else
                        list(before.handles) if arm=='all' else [policy.choose(before,action)] )
                    path=output/(name+'.sqlite')
                    with closing(WorldSession(path,body,probe,config=cfg,total_budget=1,
                            world_id=name,self_id='same-research-self',sensor_budget=2)) as world:
                        sensed=world.sense(selected) if selected else None
                        view=Frame.from_dict(sensed['frame']) if sensed else before
                        cells=[(f,a,v) for f,a,v in model.predict(view,action) if all(i<n for i in a)]
                        probe.prediction=ScopedPartialForecast(before.handles,copy.deepcopy(before.parent),list(before.relations),cells)
                        world.issue_goal(goal,1);outcome=world.run_goal()
                        after=Frame.from_dict(world.state['frame']);sensor_cost=world.state['sensing']
                    result=measure(cells,after);base=measure(baseline,after)
                    replay=verify_world(path,expected_config=cfg,expected_total_budget=1,
                        expected_world_id=name,expected_self_id='same-research-self',expected_goals=[(goal,1)],expected_sensor_budget=2)
                    row=dict(phase=phase,ordinal=ordinal,arm=arm,selected=selected,cost=sensor_cost,
                        result=result,baseline=base,outcome=outcome,replay=replay)
                    rows.append(row)
                    if phase=='train':policy.learn(before,action,selected[0],base['loss']-result['loss'])
    summary={}
    for arm in ('none','random','arg0','arg1','learned','all'):
        samples=[r for r in rows if r['phase']=='eval' and r['arm']==arm]
        summary[arm]=dict(loss=sum(r['result']['loss'] for r in samples)/12,
            wrong=sum(r['result']['counts'].get('wrong',0) for r in samples),
            completed=sum(r['outcome']['completed'] for r in samples),cost=sum(r['cost'] for r in samples))
    good=all(r['replay']['green'] for r in rows)
    passed=good and summary['learned']['wrong']==0 and all(summary['learned']['loss']<=.5*summary[a]['loss'] for a in ('none','random'))
    report=dict(verdict='BOUNDED_PREDICTION_GAIN' if passed else 'NO_PREDICTION_GAIN',
        capability_claim=False,scope=__doc__,summary=summary,all_replays_green=good,rows=rows)
    (output/'report.json').write_text(json.dumps(report,sort_keys=True))
    print(json.dumps({k:v for k,v in report.items() if k not in ('scope','rows')}))


if __name__=='__main__':run(Path(sys.argv[1]))
