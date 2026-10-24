"""Native upper bound for the sealed42-program composition grammar."""
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event
from packages.action_core.world import Sandbox,Action


def run(source,output):
    raw=source.read_bytes();original=json.loads(raw);rows=[];steps=0
    with tempfile.TemporaryDirectory(prefix='atanor_native_composition_') as root:
        for case in original['rows']:
            ordinal=case['ordinal'];count=3+ordinal%2
            cfg,aliases,ref,payload=configuration(count,103001+ordinal,
                              'detached_absent' if ordinal<2 else 'independent_full')
            matches=[]
            for index,program in enumerate(original['programs']):
                body=Sandbox(Path(root)/f'{ordinal}_{index}',**cfg)
                for record in case['preparation']:
                    assert event(body,Action.from_dict(record['action']))==record
                    steps+=1
                assert body.observe().to_dict()==case['native_record']['before']
                args=(aliases[1],aliases[0]);trace=[]
                for op,positions in program:
                    trace.append(event(body,Action(op,tuple(args[i] for i in positions))));steps+=1
                assert body._paths[ref].read_bytes()==payload
                matched=body.observe().to_dict()==case['native_record']['after']
                if matched:matches.append(index)
                rows.append({'case':ordinal,'program':index,'matched':matched,'trace':trace})
    assert source.read_bytes()==raw
    summary=[{'case':i,'matches':[r['program'] for r in rows if r['case']==i and r['matched']]} for i in range(4)]
    result={'summary':summary,'native_actions_including_preparation':steps,'rows':rows,
            'scope':'exposed native grammar ceiling, not learned capability'}
    with output.open('x') as stream:json.dump(result,stream,separators=(',',':'),sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
