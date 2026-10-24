"""Exposed causal control: identical acquired action schedule, link denied.

This is not a fresh capability run. It tests whether changed random scheduling
alone explains the apparent gain after adding an actuator.
"""
import json
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.developmental_active_eval import event
from scripts.developmental_task_eval import Adapter
from scripts.representation_r3_dev import configuration,make_goal,native_success
from packages.action_core.world import Sandbox,Action
from packages.shared_world.partial_goal import arbitrate


def run(source,output):
    raw=source.read_bytes();report=json.loads(raw);rows=[]
    with tempfile.TemporaryDirectory(prefix='atanor_link_shadow_') as root:
        for original in (r for r in report['rows'] if r['arm']=='relink'):
            life=original['life'];cfg,_,reference,payload=configuration(3,95001+life)
            body=Sandbox(Path(root)/f'a{life}',**cfg);history=[]
            for old in original['bootstrap']+original['acquisition']:
                action=Action.from_dict(old['action'])
                if action.op=='link':
                    # Explicit native-body permission denial; no state mutation.
                    record={'before':body.observe().to_dict(),'action':action.to_dict(),
                            'after':body.observe().to_dict(),'success':False}
                else:record=event(body,action)
                assert body._paths[reference].read_bytes()==payload
                history.append(record)
            model=Adapter(history);tasks=[]
            for task in range(8):
                cfg,aliases,reference,payload=configuration(3+task%2,101001+20*life+task)
                test=Sandbox(Path(root)/f't{life}_{task}',**cfg);trace=[]
                goal=make_goal(test,aliases,task%4>=2)
                for step in range(2):
                    action,_,_=arbitrate(model,test.observe(),goal,test.actions(),horizon=2,limit=32768)
                    if action is None:break
                    trace.append(event(test,action))
                    assert test._paths[reference].read_bytes()==payload
                    if native_success(test,aliases,reference,payload,task%4>=2):break
                tasks.append({'task':task,'success':native_success(test,aliases,reference,payload,task%4>=2),'trace':trace})
            rows.append({'life':life,'history':history,'tasks':tasks,
                         'success':sum(t['success'] for t in tasks),
                         'original_success':sum(t['success'] for t in original['tasks'])})
    assert source.read_bytes()==raw
    result={'scope':'exposed schedule-matched causal diagnostic; no fresh capability claim',
            'shadow_success':sum(r['success'] for r in rows),
            'original_success':sum(r['original_success'] for r in rows),'rows':rows}
    with output.open('x') as stream:json.dump(result,stream,separators=(',',':'),sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
