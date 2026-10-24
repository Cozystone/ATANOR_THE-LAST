"""Frozen DEV: learn experienced procedure endpoints, no hand-written effects.

Train12 actual after-arm arbitration traces; same old192 primitive model.
Eight native cases: count3/5 x coupled_full,independent_full,independent_mixed,
detached_absent; seeds135001..8. Execute first mined permitted sequence bound to
first alias; all choices diagnostic, not agency. Compare one composite forecast
with constituent forecasts. Repeat pure prediction50times for timing (NOT native
retry). GO: no new wrong cells, at least baseline full coverage, composite CPU
<=80%primitive CPU. No evaluation learning, no task/capability claim.
"""
import json,sys,tempfile,time
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Action,Frame
from packages.shared_world.trace_procedures import mine
from packages.shared_world.procedure_effects import symbol,endpoints
from packages.shared_world.epistemic_lookahead import _query_projection
from scripts.developmental_task_eval import Adapter
from scripts.developmental_active_eval import event
from scripts.developmental_continual_probe import score
from scripts.representation_r3_dev import configuration


def run(output):
    if output.exists():raise FileExistsError(output)
    raw=json.loads((ROOT/'evidence/developmental-arbitration-v1/file.json').read_text())
    traces=[r['trace'] for r in raw['records'] if r['arm']=='after' and r['success']]
    library=mine(traces);derived=endpoints(traces,library);cpu=time.process_time();compressed=Adapter(derived);fit_cpu=time.process_time()-cpu
    old=[]
    for name in ('developmental-continual.json','developmental-online-eval.json'):old+=json.loads((ROOT/'evidence'/name).read_text())['records']
    primitive=Adapter(old);rows=[];timing=Counter();totals={'primitive':Counter(),'compressed':Counter()}
    with tempfile.TemporaryDirectory(prefix='atanor_effect_probe_') as root:
        n=0
        for count in (3,5):
            for pattern in ('coupled_full','independent_full','independent_mixed','detached_absent'):
                cfg,aliases,ref,payload=configuration(count,135001+n,pattern)
                body=Sandbox(Path(root)/str(n),**cfg);before=body.observe()
                template=library[0][0];binding=(aliases[0],)
                sequence=tuple(Action(op,tuple(binding[i] for i in args)) for op,args in template)
                assert all(a in body.actions() for a in sequence)
                predictions={}
                for arm in totals:
                    started=time.process_time()
                    for _ in range(50):
                        if arm=='compressed':pred=compressed.predict(before,[symbol(sequence)])[0]
                        else:
                            current=before;pred=None
                            for action in sequence:
                                pred=primitive.predict(current,[action])[0]
                                if pred is None:break
                                current=_query_projection(pred[0])
                    timing[arm]+=time.process_time()-started
                    predictions[arm]=None if pred is None else _query_projection(pred[0]).to_dict()
                trace=[event(body,a) for a in sequence];actual=body.observe().to_dict()
                for arm,pred in predictions.items():
                    totals[arm]['full_correct' if pred==actual else 'unknown' if pred is None else 'wrong']+=1
                assert body._paths[ref].read_bytes()==payload
                rows.append(dict(ordinal=n,count=count,pattern=pattern,trace=trace,predictions=predictions));n+=1
    a,b=totals['compressed'],totals['primitive']
    passed=a['wrong']==0 and a['full_correct']>=b['full_correct'] and timing['compressed']<=.8*timing['primitive']
    result=dict(verdict='DEV_COMPRESSED_EFFECT_SIGNAL' if passed else 'NO_DEV_COMPRESSED_EFFECT_SIGNAL',totals=totals,cpu_50_queries=timing,fit_cpu=fit_cpu,derived=derived,rows=rows)
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','derived')}))


if __name__=='__main__':run(Path(sys.argv[1]))
