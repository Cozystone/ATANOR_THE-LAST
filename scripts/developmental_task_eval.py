"""Fixed goal utility comparison; bodies/goals operator supplied, not agency."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.developmental_conditional_eval import Model
from scripts.representation_r1_dev import SCHEMA
from scripts.representation_r3_dev import configuration, make_goal, native_success
from packages.action_core.schema import bind_schema
from packages.action_core.world import Sandbox, Frame
from packages.shared_world.relational import _view
from packages.shared_world.epistemic_lookahead import _query_projection
from packages.shared_world.planning import choose


class Adapter:
    def __init__(self, records, schema=SCHEMA, numeric_context=None):
        self.model=Model(records, numeric_context=numeric_context)
        self.schema=bind_schema(schema)

    def predict_cells(self, frame, action):
        return self.model.predict(frame, action, True)

    def predict(self, state, actions, history=()):
        frame=state if type(state) is Frame else _query_projection(state)
        if frame is None:
            return [None for _ in actions]
        result=[]
        for action in actions:
            cells=self.model.predict(frame,action,True)
            if any(len(values)!=1 for _,_,values in cells):
                result.append(None)
                continue
            output=copy.deepcopy(frame)
            for field,address,values in cells:
                v=values[0]
                if field=='kind': output.kinds[address[0]]=int(v)
                elif field=='size': output.sizes[address[0]]=v
                else:
                    matrix=output.equal if field=='equal' else output.relations[field]
                    matrix[address[0]][address[1]]=v
            result.append((_view(output),0.))
        return result


def run(initial, experience, output,policy_comparison=False,seed_base=72001,arbitration=False):
    raws=[p.read_bytes() for p in (initial,experience)]
    old,new=[json.loads(raw)['records'] for raw in raws]
    models={'before':Adapter(old+new if policy_comparison else old),'after':Adapter(old+new)}
    records=[]
    with tempfile.TemporaryDirectory(prefix='atanor_task_') as root:
        for ordinal in range(24):
            collective=ordinal%4>=2
            cfg,aliases,reference,payload=configuration(3+ordinal%2,seed_base+ordinal,
                                                        payload=b'r'*(271+ordinal*23))
            for arm in ('before','after') if ordinal%2==0 else ('after','before'):
                body=Sandbox(Path(root)/f'{ordinal}_{arm}',**cfg)
                goal=make_goal(body,aliases,collective)
                trace=[]
                start=time.process_time()
                for step in range(2):
                    before=body.observe()
                    actions=body.actions(); progress=None; preliminary=0
                    if policy_comparison and arm=='after':
                        from packages.shared_world.partial_goal import select,arbitrate
                        if arbitration:
                            progress=arbitrate(models[arm],before,goal,actions,horizon=2,limit=32768)
                        else:
                            progress=select(models[arm],before,goal,actions)
                            preliminary=len(actions)
                    if progress is not None:
                        action,predicted,queries=progress
                    else:
                        action,predicted,queries=choose(models[arm],before,goal,actions,
                            horizon=2,limit=32768-preliminary,allow_partial=True)
                        queries+=preliminary
                    if action is None:
                        trace.append({'stop':'unsupported','queries':queries})
                        break
                    ok=body.step(action)
                    trace.append({'before':before.to_dict(),'action':action.to_dict(),
                                  'prediction':predicted.to_dict(),'after':body.observe().to_dict(),
                                  'success':ok,'queries':queries})
                    assert body._paths[reference].read_bytes()==payload
                    if native_success(body,aliases,reference,payload,collective): break
                records.append({'ordinal':ordinal,'arm':arm,'collective':collective,
                    'success':native_success(body,aliases,reference,payload,collective),
                    'cpu_seconds':time.process_time()-start,'trace':trace})
    summary={}
    for arm in models:
        rows=[r for r in records if r['arm']==arm]
        summary[arm]={'successes':sum(r['success'] for r in rows),
                      'actions':sum('action' in t for r in rows for t in r['trace']),
                      'cpu_seconds':sum(r['cpu_seconds'] for r in rows)}
    lift=summary['after']['successes']-summary['before']['successes']
    verdict=('RETENTION_PASS' if summary['after']['successes']==summary['before']['successes']==24
             and summary['after']['actions']<=summary['before']['actions'] else 'RETENTION_FAIL') if policy_comparison else (
             'TASK_LIFT_PASS' if lift>=4 else 'TASK_LIFT_NOT_CONFIRMED')
    result={'verdict':verdict,
            'source_sha256':[hashlib.sha256(r).hexdigest() for r in raws],
            'incremental_acquisition_actions':0 if policy_comparison else len(new),'summary':summary,'records':records,
            'policy_comparison':policy_comparison,'seed_base':seed_base,
            'scope':'24 paired same-mechanics tasks, not generality; economy separate'}
    with output.open('x') as stream: json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))


if __name__=='__main__': run(*(Path(p) for p in sys.argv[1:]))
