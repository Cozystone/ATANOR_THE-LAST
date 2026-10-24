"""Bounded exposed feasibility: can learned old actions explain a new action?

Enumerate all one/two-step programs over opaque learned operation signatures.
Only target argument positions are available; no hand-authored winning program.
Probe native rename as new0, no dispatch-name input to candidate generation.
Actual probe outcomes are never added to the retained old learner.
"""
import hashlib
import itertools
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Action
from scripts.representation_r3_dev import configuration
from scripts.developmental_task_eval import Adapter
from scripts.developmental_active_eval import event
from packages.shared_world.epistemic_lookahead import _query_projection


def programs(schema,arity=2):
    atoms=[(op,args) for op,width in schema.entries
           for args in itertools.permutations(range(arity),width)]
    return [(a,) for a in atoms]+list(itertools.product(atoms,repeat=2))


def forecast(model,before,args,program):
    state=before
    for op,positions in program:
        action=Action(op,tuple(args[i] for i in positions))
        prediction=model.predict(state,[action])[0]
        if prediction is None:return None
        state=prediction[0]
    return _query_projection(state)


def run(output):
    paths=[ROOT/'evidence/developmental-continual.json',ROOT/'evidence/developmental-online-eval.json']
    raws=[p.read_bytes() for p in paths]
    history=sum((json.loads(raw)['records'] for raw in raws),[])
    model=Adapter(history);library=programs(model.schema);rows=[]
    with tempfile.TemporaryDirectory(prefix='atanor_composition_') as root:
        for ordinal,count in enumerate((3,4,3,4)):
            pattern='detached_absent' if ordinal<2 else 'independent_full'
            cfg,aliases,reference,payload=configuration(count,103001+ordinal,pattern)
            cfg={**cfg,'operations':cfg['operations']+[{'id':'rename','arity':2}]}
            body=Sandbox(Path(root)/str(ordinal),**cfg)
            preparation=[]
            if ordinal>=2:preparation.append(event(body,Action('unlink',(aliases[0],))))
            before=body.observe();args=(aliases[1],aliases[0])
            predicted=[forecast(model,before,args,program) for program in library]
            actual=event(body,Action('rename',args))
            assert body._paths[reference].read_bytes()==payload
            statuses=['unsupported' if value is None else
                      'matches' if value.to_dict()==actual['after'] else 'contradicted'
                      for value in predicted]
            rows.append({'ordinal':ordinal,'preparation':preparation,'native_record':actual,
                         'opaque_new_action':{'op':'new0','args':list(args)},
                         'statuses':statuses,'counts':{k:statuses.count(k) for k in ('unsupported','matches','contradicted')}})
    assert all(p.read_bytes()==raw for p,raw in zip(paths,raws))
    compatible=[i for i in range(len(library)) if all(r['statuses'][i]!='contradicted' for r in rows)]
    complete=[i for i in compatible if all(r['statuses'][i]=='matches' for r in rows)]
    result={'programs':library,'rows':rows,'training_events':len(history),
            'compatible_indices':compatible,'complete_indices':complete,
            'source_sha256':[hashlib.sha256(raw).hexdigest() for raw in raws],
            'scope':'four researcher probes, not autonomous experiments/fresh capability; unsupported is not evidence for compatibility'}
    with output.open('x') as stream:json.dump(result,stream,separators=(',',':'),sort_keys=True)
    print(json.dumps({'programs':len(library),'complete':len(complete),'unrefuted':len(compatible),
                      'cases':[r['counts'] for r in rows]}))


if __name__=='__main__':run(Path(sys.argv[1]))
