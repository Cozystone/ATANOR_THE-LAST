"""One-shot affordance ablation; random acquisition, NOT epistemic agency.

Same six actual bootstrap records, 32 random acquisition actions per arm/life.
Extended body only during acquisition. All tasks use OLD actuators, preventing
new-tool task shortcuts. Models learn native outcomes only, no test learning.
"""
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.developmental_task_eval import Adapter
from scripts.developmental_active_eval import event
from scripts.representation_r3_dev import configuration,make_goal,native_success
from packages.action_core.world import Sandbox,Action
from packages.action_core.relink_body import RelinkBody
from packages.shared_world.partial_goal import arbitrate


def run(source,output):
    raw=source.read_bytes(); report=json.loads(raw)
    output.mkdir(exist_ok=False)
    frozen={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [*sorted((ROOT/'packages').rglob('*.py')),
                       *sorted((ROOT/'scripts').glob('developmental*.py'))]}
    rows=[];start=time.monotonic()
    def cap():
        if time.monotonic()-start>240:raise TimeoutError('relink cap240s; preserve journal, no retry')
    with (output/'journal.jsonl').open('x') as journal, tempfile.TemporaryDirectory(prefix='atanor_relink_') as root:
        for life in range(4):
            bootstrap=next(r['bootstrap'] for r in report['lives'] if r['life']==life)
            for arm in (('base','relink') if life%2==0 else ('relink','base')):
                cap();cfg,_,reference,payload=configuration(3,95001+life)
                if arm=='relink':cfg={**cfg,'operations':cfg['operations']+[{'id':'link','arity':2}]}
                body=(RelinkBody if arm=='relink' else Sandbox)(Path(root)/f'a{life}{arm}',**cfg)
                for old in bootstrap:assert event(body,Action.from_dict(old['action']))==old
                history=list(bootstrap);acquired=[];rng=random.Random(99001+life)
                for step in range(32):
                    cap();record=event(body,rng.choice(body.actions()))
                    assert body._paths[reference].read_bytes()==payload
                    history.append(record);acquired.append(record)
                    journal.write(json.dumps({'life':life,'arm':arm,'stage':'acquisition','step':step,'record':record})+'\n');journal.flush()
                model=Adapter(history);tasks=[]
                for task in range(8):
                    cap();cfg,aliases,reference,payload=configuration(3+task%2,101001+20*life+task)
                    test=Sandbox(Path(root)/f't{life}{arm}{task}',**cfg)
                    collective=task%4>=2;goal=make_goal(test,aliases,collective);trace=[]
                    for step in range(2):
                        action,_,queries=arbitrate(model,test.observe(),goal,test.actions(),horizon=2,limit=32768)
                        if action is None:break
                        record=event(test,action);trace.append(record)
                        assert test._paths[reference].read_bytes()==payload
                        if native_success(test,aliases,reference,payload,collective):break
                    row={'task':task,'success':native_success(test,aliases,reference,payload,collective),'trace':trace}
                    tasks.append(row);journal.write(json.dumps({'life':life,'arm':arm,'stage':'task',**row})+'\n');journal.flush()
                rows.append({'life':life,'arm':arm,'bootstrap':bootstrap,'acquisition':acquired,'tasks':tasks})
    assert source.read_bytes()==raw
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in frozen.items())
    summary={}
    for arm in ('base','relink'):
        selected=[r for r in rows if r['arm']==arm]
        success=sum(t['success'] for r in selected for t in r['tasks'])
        total=sum(len(r['bootstrap'])+len(r['acquisition'])+sum(len(t['trace']) for t in r['tasks']) for r in selected)
        summary[arm]={'success':success,'total_actions':total,'actions_per_success':total/success if success else None,
                      'successful_link_actions':sum(a['action']['op']=='link' and a['success'] for r in selected for a in r['acquisition'])}
    paired={(r['life'],t['task'],r['arm']):t['success'] for r in rows for t in r['tasks']}
    losses=sum(paired[i,t,'base'] and not paired[i,t,'relink'] for i in range(4) for t in range(8))
    lift=summary['relink']['success']>=summary['base']['success']+4 and losses==0
    result={'verdict':'AFFORDANCE_LEARNING_GAIN' if lift else 'NO_AFFORDANCE_GAIN','paired_losses':losses,
            'summary':summary,'source_sha256':hashlib.sha256(raw).hexdigest(),'source_digests':frozen,
            'rows':rows,'scope':'new task instances, known mechanics; random acquisition, not self-chosen experiments'}
    with (output/'report.json').open('x') as stream:json.dump(result,stream,separators=(',',':'),sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','source_digests')}))


if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
