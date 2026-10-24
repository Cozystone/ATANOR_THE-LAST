"""Native counterexample to histogram-only action context; not a task solver."""
import json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Action,Frame
from packages.shared_world.contextual_rewrite import context
from packages.shared_world.index_rewrite import signature
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event


def run(output):
    cfg,aliases,ref,payload=configuration(4,119001)
    names=[cfg['paths'][int(h[1:])] for h in aliases]
    cfg={**cfg,'initial':{**cfg['initial'],names[2]:payload},
         'initial_links':{names[1]:names[0],names[3]:names[2]},
         'operations':cfg['operations']+[{'id':'rename','arity':2}]}
    records=[];features=[];pairs=[]
    with tempfile.TemporaryDirectory(prefix='atanor_context_alias_') as root:
        for i,dest in enumerate((aliases[1],aliases[2])):
            body=Sandbox(Path(root)/str(i),**cfg);action=Action('rename',(aliases[0],dest));before=body.observe()
            _,args=signature(before,action);features.append(context(before,args))
            pairs.append({name:matrix[args[0]][args[1]] for name,matrix in before.relations.items()})
            records.append(event(body,action));assert body._paths[ref].read_bytes()==payload
    result={'feature_collision':features[0]==features[1],
            'native_successes':[r['success'] for r in records],
            'observable_argument_relations':pairs,'records':records,
            'scope':'body sensor distinguishes pair relation; histogram projection aliases it. Diagnostic not acquisition.'}
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))


if __name__=='__main__':run(Path(sys.argv[1]))
