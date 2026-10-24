"""Native reexecution of sealed task traces, no reselection or learning."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.representation_r3_dev import configuration, native_success
from packages.action_core.world import Sandbox, Action


def run(source,output):
    raw=source.read_bytes()
    data=json.loads(raw)
    checked=0
    summary={arm:{'successes':0,'actions':0} for arm in ('before','after')}
    with tempfile.TemporaryDirectory(prefix='atanor_task_audit_') as root:
        for row in data['records']:
            ordinal=row['ordinal']
            cfg,aliases,ref,payload=configuration(3+ordinal%2,data.get('seed_base',72001)+ordinal,
                                                  payload=b'r'*(271+ordinal*23))
            body=Sandbox(Path(root)/f"{ordinal}_{row['arm']}",**cfg)
            for event in row['trace']:
                if 'action' not in event: continue
                assert body.observe().to_dict()==event['before']
                assert body.step(Action.from_dict(event['action']))==event['success']
                assert body.observe().to_dict()==event['after']
                assert body._paths[ref].read_bytes()==payload
                checked+=1
                summary[row['arm']]['actions']+=1
            success=native_success(body,aliases,ref,payload,row['collective'])
            assert success==row['success']
            summary[row['arm']]['successes']+=success
    for arm in summary:
        for key,value in summary[arm].items(): assert value==data['summary'][arm][key]
    assert source.read_bytes()==raw
    result={'native_steps_replayed':checked,'summary':summary,
            'source_sha256':hashlib.sha256(raw).hexdigest(),
            'scope':'same native adapter replay, not independent external judge'}
    with output.open('x') as stream: json.dump(result,stream,sort_keys=True,indent=2)
    print(json.dumps(result))

if __name__=='__main__': run(Path(sys.argv[1]),Path(sys.argv[2]))
