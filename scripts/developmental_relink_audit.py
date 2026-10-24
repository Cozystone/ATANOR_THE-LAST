"""Replay sealed native actions and independently recount, never select again."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Action
from packages.action_core.relink_body import RelinkBody
from scripts.developmental_active_eval import event
from scripts.representation_r3_dev import configuration,native_success


def run(source,output):
    raw=source.read_bytes();report=json.loads(raw);count=0;rows=[]
    with tempfile.TemporaryDirectory(prefix='atanor_relink_replay_') as root:
        for row in report['rows']:
            life,arm=row['life'],row['arm']
            cfg,_,reference,payload=configuration(3,95001+life)
            if arm=='relink':cfg={**cfg,'operations':cfg['operations']+[{'id':'link','arity':2}]}
            body=(RelinkBody if arm=='relink' else Sandbox)(Path(root)/f'a{life}{arm}',**cfg)
            for record in row['bootstrap']+row['acquisition']:
                assert event(body,Action.from_dict(record['action']))==record
                assert body._paths[reference].read_bytes()==payload
                count+=1
            for task in row['tasks']:
                cfg,aliases,reference,payload=configuration(3+task['task']%2,101001+20*life+task['task'])
                test=Sandbox(Path(root)/f"t{life}{arm}{task['task']}",**cfg)
                for record in task['trace']:
                    assert record['action']['op']!='link'
                    assert event(test,Action.from_dict(record['action']))==record
                    assert test._paths[reference].read_bytes()==payload
                    count+=1
                assert native_success(test,aliases,reference,payload,task['task']%4>=2)==task['success']
            rows.append({'life':life,'arm':arm,'success':sum(t['success'] for t in row['tasks']),
                         'total_actions':len(row['bootstrap'])+len(row['acquisition'])+sum(len(t['trace']) for t in row['tasks'])})
    for arm,summary in report['summary'].items():
        selected=[r for r in rows if r['arm']==arm]
        successes=sum(r['success'] for r in selected);actions=sum(r['total_actions'] for r in selected)
        assert successes==summary['success'] and actions==summary['total_actions']
        assert actions/successes==summary['actions_per_success']
    assert source.read_bytes()==raw
    result={'native_transitions_verified':count,'rows':rows,'source_sha256':hashlib.sha256(raw).hexdigest(),
            'scope':'same native adapter replay, not external judge; four independent life seeds, not32 independent lives'}
    with output.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result))


if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
