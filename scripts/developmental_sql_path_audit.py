"""Researcher witness paths, never training or autonomous task credit."""
import hashlib,importlib.util,json,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_fk_schema_tasks import schema_encode
from scripts.developmental_fk_tasks import context
from scripts.developmental_task_eval import Adapter
from packages.action_core.world import Action
from packages.shared_world.epistemic_lookahead import _query_projection

def run(source,evidence,output):
    raws=[p.read_bytes() for p in (source,evidence)]
    spec=importlib.util.spec_from_file_location('fk_native',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    data=json.loads(raws[1]); model=Adapter(data['training'],
        schema=[{'id':op,'arity':1} for op in module.FK_ACTIONS],numeric_context=context)
    rows=[]; totals=Counter()
    for ordinal in range(8):
        body=module.FKWorld(86001+ordinal,n=4+ordinal%2,prefill=1+(ordinal//2)%2)
        try:
            # Diagnostic recipe supplied externally, not counted as cognition.
            path=[Action('unlink',(f'n{i}',)) for i,s in enumerate(body.config()) if s==2]
            path.append(Action('delete',('n0',)))
            trace=[]
            for action in path:
                before=schema_encode(body)
                cells=model.model.predict(before,action,True)
                unresolved=Counter(field for field,_,v in cells if len(v)!=1)
                forecast=model.predict(before,[action])[0]
                assert body.do(action.op,int(action.args[0][1:]))
                after=schema_encode(body)
                status='unsupported' if forecast is None else 'correct' if _query_projection(forecast[0]).to_dict()==after.to_dict() else 'wrong'
                totals[status]+=1
                trace.append({'before':before.to_dict(),'action':action.to_dict(),
                    'after':after.to_dict(),'status':status,'unresolved':dict(unresolved)})
            assert list(body.config())==[0]+[1]*(body.n-1)
            rows.append({'ordinal':ordinal,'trace':trace})
        finally:body.dispose()
    result={'source_sha256':[hashlib.sha256(r).hexdigest() for r in raws],
            'scope':'manual native witness, no evaluation retry/learning','totals':dict(totals),'rows':rows}
    assert [p.read_bytes() for p in (source,evidence)]==raws
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps(result['totals']))

if __name__=='__main__':run(*(Path(p) for p in sys.argv[1:]))
