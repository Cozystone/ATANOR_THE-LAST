"""Fresh frozen trace-procedure planning gate. One execution, no test learning.

12paired native bodies seeds125001..125012,count4..6. First8 empty2/3 aliases
preserving others (4/6primitive action allowance); last4 prior empty-one/all
goals(2action allowance). Three arms SAME learned model/search: primitives,
learned2-step procedures, reversed learned sequences as same-size sham library.
4096cached primitive-model queries/case,width16, same native budget,240s overall.
Pass: learned12/12, all native intermediate predictions faithful, no paired loss;
against BOTH controls either >=2more tasks or <=80% queries at equal success.
CPU reported separately. Reversed is a causal ordering control, not neutral random
policy. Prior induction/action experience costs are sunk, not claimed free.
No AGI/agency/new-mechanics claim. Source/training digest guard pre/post.
"""
import hashlib,json,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox
from packages.action_core.planner import Goal
from packages.shared_world.trace_procedures import mine,instantiate
from scripts.developmental_procedure_probe import search
from scripts.developmental_task_eval import Adapter
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event


def fingerprints():
    paths=list((ROOT/'packages').rglob('*.py'))+[Path(__file__),ROOT/'scripts/developmental_procedure_probe.py',
        ROOT/'scripts/developmental_task_eval.py',ROOT/'scripts/developmental_conditional_eval.py']
    paths += [ROOT/'evidence'/name for name in ('developmental-arbitration-v1/file.json','developmental-continual.json','developmental-online-eval.json')]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def run(output):
    output.mkdir(exist_ok=False);bound=fingerprints();start=time.monotonic();rows=[]
    raw=json.loads((ROOT/'evidence/developmental-arbitration-v1/file.json').read_text())
    cpu=time.process_time();library=mine([r['trace'] for r in raw['records'] if r['arm']=='after' and r['success']]);induction_cpu=time.process_time()-cpu
    reverse=[(tuple(reversed(template)),count) for template,count in library]
    old=[]
    for name in ('developmental-continual.json','developmental-online-eval.json'):
        old+=json.loads((ROOT/'evidence'/name).read_text())['records']
    model=Adapter(old)
    with tempfile.TemporaryDirectory(prefix='atanor_procedure_gate_') as root:
        for n in range(12):
            count=4+n%3;targets=(2+n%2) if n<8 else (1 if n%2==0 else count)
            budget=2*targets if n<8 else 2
            cfg,aliases,ref,payload=configuration(count,125001+n)
            arms=('primitive','learned','reversed');arms=arms[n%3:]+arms[:n%3]
            for arm in arms:
                if time.monotonic()-start>240:raise TimeoutError('registered240s cap')
                body=Sandbox(Path(root)/f'{n}_{arm}',**cfg);view=body.observe()
                goal=Goal('given-outcome',sizes=tuple((h,0. if i<targets else view.sizes[view.handles.index(h)]) for i,h in enumerate(aliases)))
                options=[(a,) for a in body.actions()]
                if arm!='primitive':options=instantiate(library if arm=='learned' else reverse,view.handles,body.actions())+options
                cpu=time.process_time();plan,predictions,queries=search(model,view,goal,options,budget=budget,limit=4096,width=16)
                planning_cpu=time.process_time()-cpu;trace=[];faithful=True
                assert len(plan)<=budget and queries<=4096
                for action,prediction in zip(plan,predictions):
                    record=event(body,action);trace.append({**record,'prediction':prediction.to_dict()})
                    faithful &= record['after']==prediction.to_dict()
                    if not faithful:break
                success=all(body._paths[h].is_file() and body._paths[h].read_bytes()==(b'' if i<targets else payload) for i,h in enumerate(aliases))
                assert body._paths[ref].read_bytes()==payload
                rows.append({'ordinal':n,'arm':arm,'targets':targets,'budget':budget,'goal':goal.to_dict(),'queries':queries,
                    'planning_cpu':planning_cpu,'trace':trace,'faithful':faithful,'success':success})
    summary={arm:{'successes':sum(r['success'] for r in rows if r['arm']==arm),'queries':sum(r['queries'] for r in rows if r['arm']==arm),
        'actions':sum(len(r['trace']) for r in rows if r['arm']==arm),'cpu':sum(r['planning_cpu'] for r in rows if r['arm']==arm)} for arm in ('primitive','learned','reversed')}
    a=summary['learned'];unchanged=fingerprints()==bound
    gain=all(a['successes']>=b['successes']+2 or (a['successes']==b['successes'] and a['queries']<=.8*b['queries']) for arm,b in summary.items() if arm!='learned')
    passed=unchanged and a['successes']==12 and all(r['faithful'] for r in rows) and gain
    result={'verdict':'BOUNDED_PROCEDURE_GAIN' if passed else 'NO_PROCEDURE_GAIN','summary':summary,'rows':rows,'library':library,
        'induction_cpu':induction_cpu,'source_unchanged':unchanged,'source_sha256':bound,
        'scope':'planning efficiency via learned parameterized traces, same physics, human goals; not agency or generality'}
    (output/'report.json').write_text(json.dumps(result,sort_keys=True,separators=(',',':')))
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','source_sha256')}))


if __name__=='__main__':run(Path(sys.argv[1]))
