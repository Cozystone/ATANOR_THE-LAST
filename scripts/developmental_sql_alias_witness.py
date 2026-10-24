"""Native observation-alias witness, not candidate tuning or capability trial."""
import importlib.util,json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_fk_tasks import encode,context
from scripts.developmental_rooted_probe import rooted
from packages.action_core.world import Action

def run(source,output):
    raw=source.read_bytes(); spec=importlib.util.spec_from_file_location('fk',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    rows=[]
    for target in (0,1):
        body=module.FKWorld(85001,n=4,prefill=0)
        try:
            for i in range(4): assert body.do('insert',i)
            before=encode(body);action=Action('link',(f'n{target}',))
            key,nodes=rooted(before,action,'kind',(target,))
            features=context(before,nodes)
            ok=body.do('link',target);after=encode(body)
            rows.append({'target':target,'before':before.to_dict(),'key':repr(key),
                         'features':features,'success':ok,'after':after.to_dict(),
                         'actual_target_state':after.kinds[target]})
        finally:body.dispose()
    assert rows[0]['before']==rows[1]['before']
    assert rows[0]['key']==rows[1]['key'] and rows[0]['features']==rows[1]['features']
    assert rows[0]['actual_target_state']!=rows[1]['actual_target_state']
    result={'verdict':'OBSERVATION_ALIAS_CONFIRMED','source_sha256':hashlib.sha256(raw).hexdigest(),
            'scope':'existing codec omits native table membership; no learner repair tested','rows':rows}
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,indent=2)
    print(json.dumps({'verdict':result['verdict'],'actual_targets':[r['actual_target_state'] for r in rows]}))

if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
