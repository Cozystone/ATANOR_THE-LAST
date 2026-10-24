"""Native reexecution of sealed traces; no policy rerun or outcome selection."""
import hashlib,json,os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.representation_r3_dev import configuration,native_success
from scripts.developmental_active_eval import event
from packages.action_core.world import Sandbox,Action


def run(source,output):
    raw=source.read_bytes();data=json.loads(raw);steps=0;verified=0
    with tempfile.TemporaryDirectory(prefix='atanor_rewrite_audit_') as root:
        for i,row in enumerate(data['rows']):
            n=row['ordinal'];new=n<16;linked=n%2==0
            cfg,aliases,ref,payload=configuration(5+n%3 if new else 3+n%2,109001+n,
                'detached_absent' if new and linked else 'independent_full' if new else 'coupled_full')
            cfg={**cfg,'operations':cfg['operations']+[{'id':'rename','arity':2}]}
            body=Sandbox(Path(root)/str(i),**cfg)
            for recorded in row['preparation']+row['trace']:
                if 'action' not in recorded:continue
                actual=event(body,Action.from_dict(recorded['action']))
                assert actual=={k:recorded[k] for k in actual}
                steps+=1
            if new:
                # Check the explicit goal directly, independently of Goal.probability.
                paths=body._paths;goal=row['goal'];success=True
                for h,kind in goal['kinds']:
                    actual=1 if paths[h].is_file() else 2 if paths[h].is_dir() else 0
                    success &= actual==kind
                for a,b in goal['equal']:
                    success &= paths[a].is_file() and paths[b].is_file() and paths[a].read_bytes()==paths[b].read_bytes()
                for channel,a,b,wanted in goal['relations']:
                    assert cfg['relation_spec']['channels'][channel]['operator']=='eq'
                    assert cfg['relation_spec']['fields'][cfg['relation_spec']['channels'][channel]['column']]=='st_ino'
                    success &= paths[a].exists() and paths[b].exists() and int(os.path.samefile(paths[a],paths[b]))==wanted
                success &= paths[ref].read_bytes()==payload
            else:success=native_success(body,aliases,ref,payload,n%4>=2)
            assert bool(success)==row['success'];verified+=1
    assert source.read_bytes()==raw
    result={'verdict':'NATIVE_REPLAY_VERIFIED','rows':verified,'native_steps':steps,
        'source_sha256':hashlib.sha256(raw).hexdigest(),'scope':'same body adapter; not external independent judge'}
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True)
    print(json.dumps(result))


if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
