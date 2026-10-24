"""Frozen task utility gate. Supplied goals, learned effects, no supplied plans."""
import hashlib,json,os,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Action
from packages.action_core.planner import Goal
from packages.shared_world.index_rewrite import IndexRewrite
from packages.shared_world.planning import choose
from packages.shared_world.partial_goal import arbitrate
from scripts.developmental_task_eval import Adapter
from scripts.developmental_active_eval import event
from scripts.representation_r3_dev import configuration,make_goal,native_success


class Combined:
    def __init__(self,base,examples):self.base=base;self.rewrite=IndexRewrite(examples)
    def predict(self,frame,action,conditional=True):
        cells=self.rewrite.predict(frame,action)
        return cells if all(len(v)==1 for _,_,v in cells) else self.base.predict(frame,action,conditional)


def digests():
    paths=list((ROOT/'packages').rglob('*.py'))+[Path(__file__),
        ROOT/'scripts/developmental_task_eval.py',ROOT/'scripts/developmental_conditional_eval.py',
        ROOT/'evidence/developmental-composition-probe.json',
        ROOT/'evidence/developmental-continual.json',ROOT/'evidence/developmental-online-eval.json']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def run(output):
    output.mkdir(exist_ok=False);frozen=digests();start=time.monotonic();rows=[]
    old=[]
    for name in ('developmental-continual.json','developmental-online-eval.json'):
        old+=json.loads((ROOT/'evidence'/name).read_text())['records']
    examples=[json.loads((ROOT/'evidence/developmental-composition-probe.json').read_text())['rows'][0]['native_record']]
    with tempfile.TemporaryDirectory(prefix='atanor_rewrite_tasks_') as root:
        for ordinal in range(24):
            new=ordinal<16;linked=ordinal%2==0
            cfg,aliases,ref,payload=configuration(5+ordinal%3 if new else 3+ordinal%2,
                109001+ordinal,'detached_absent' if new and linked else 'independent_full' if new else 'coupled_full')
            cfg={**cfg,'operations':cfg['operations']+[{'id':'rename','arity':2}]}
            for arm in ('baseline','candidate') if ordinal%2==0 else ('candidate','baseline'):
                if time.monotonic()-start>300:raise TimeoutError('registered 300s hard cap')
                body=Sandbox(Path(root)/f'{ordinal}_{arm}',**cfg);prep=[]
                if new and not linked:prep.append(event(body,Action('unlink',(aliases[0],))))
                model=Adapter(old+examples,schema=cfg['operations'])
                if arm=='candidate':model.model=Combined(model.model,examples)
                if new:
                    channel=next(iter(body.observe().relations))
                    desired=[(channel,aliases[0],h,int(linked)) for h in aliases[2:]]
                    goal=Goal('supplied-outcome',kinds=((aliases[1],0),),
                        equal=tuple((h,ref) for h in [aliases[0]]+aliases[2:]),relations=tuple(desired))
                    def success():
                        p=body._paths
                        return (not p[aliases[1]].exists() and p[ref].read_bytes()==payload and
                            all(p[h].is_file() and p[h].read_bytes()==payload for h in [aliases[0]]+aliases[2:]) and
                            all(os.path.samefile(p[aliases[0]],p[h])==linked for h in aliases[2:]))
                else:
                    collective=ordinal%4>=2;goal=make_goal(body,aliases,collective)
                    def success():return native_success(body,aliases,ref,payload,collective)
                trace=[];cpu=time.process_time()
                for step in range(1 if new else 2):
                    if new:
                        action,prediction,queries=choose(model,body.observe(),goal,body.actions(),
                            horizon=1,limit=32768,allow_partial=True,complete_only=True)
                    else:
                        action,prediction,queries=arbitrate(model,body.observe(),goal,body.actions(),horizon=2,limit=32768)
                    if action is None:
                        trace.append({'stop':'unsupported','queries':queries});break
                    trace.append({**event(body,action),'prediction':prediction.to_dict(),'queries':queries})
                    assert body._paths[ref].read_bytes()==payload
                    if success():break
                rows.append({'ordinal':ordinal,'arm':arm,'new':new,'linked':linked,'goal':goal.to_dict(),
                    'success':success(),'trace':trace,'preparation':prep,'cpu_seconds':time.process_time()-cpu})
    summary={arm:{str(new):{'successes':sum(r['success'] for r in rows if r['arm']==arm and r['new']==new),
        'actions':sum('action' in t for r in rows if r['arm']==arm and r['new']==new for t in r['trace']),
        'queries':sum(t['queries'] for r in rows if r['arm']==arm and r['new']==new for t in r['trace'])}
        for new in (True,False)} for arm in ('baseline','candidate')}
    paired_loss=sum(next(r for r in rows if r['ordinal']==i and r['arm']=='baseline')['success'] and
                    not next(r for r in rows if r['ordinal']==i and r['arm']=='candidate')['success'] for i in range(24))
    unchanged=frozen==digests()
    passed=(unchanged and not paired_loss and summary['candidate']['True']['successes']>=summary['baseline']['True']['successes']+4
            and summary['candidate']['False']['successes']==summary['baseline']['False']['successes']==8)
    result={'verdict':'BOUNDED_TASK_LIFT' if passed else 'TASK_LIFT_NOT_CONFIRMED','summary':summary,
        'paired_losses':paired_loss,'source_unchanged':unchanged,'source_sha256':frozen,'rows':rows,
        'scope':'operator-supplied goals and one example; no autonomous concepts, curriculum, or cross-mechanism transfer'}
    (output/'report.json').write_text(json.dumps(result,sort_keys=True,separators=(',',':')))
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','source_sha256')}))


if __name__=='__main__':run(Path(sys.argv[1]))
