"""Frozen one-shot native conditional-effect retention/generalization gate.

Train same3 exposed actual events: original example + declared absent/present
parent scope records. Compare intersection vs all consistent conditional splits.
12 fresh prediction cases: flat/missing/present parent x4, counts5..7, new names,
new payloads, balanced linked/independent. No test learning. In8 solvable cases,
let existing one-step full-support planner select from ALL permitted actions.
PASS requires zero candidate wrong cells,12/12 complete predictions,8/8 actual
tasks,>=4 task lift, no paired loss. Missing-parent4 are not task-success cases;
their prediction must be correct. Closure observes ancestors, not success.
New seeds113001..113012.120s cap. No rerun or threshold changes after outcomes.
"""
import json,sys,tempfile,time,hashlib,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Action,Frame
from packages.action_core.planner import Goal
from packages.action_core.observation_scope import ancestor_closed_paths
from packages.shared_world.index_rewrite import IndexRewrite
from packages.shared_world.contextual_rewrite import ContextualRewrite
from packages.shared_world.planning import choose
from scripts.representation_r3_dev import configuration
from scripts.developmental_continual_probe import score
from scripts.developmental_active_eval import event
from scripts.developmental_task_eval import Adapter
from scripts.developmental_rewrite_tasks import Combined


def run(output):
    output.mkdir(exist_ok=False);start=time.monotonic();rows=[];tasks=[]
    sources=[ROOT/'evidence/developmental-composition-probe.json',ROOT/'evidence/developmental-rewrite-scope.json']
    raws=[p.read_bytes() for p in sources]
    examples=[json.loads(raws[0])['rows'][0]['native_record']]+[r['record'] for r in json.loads(raws[1])['rows'] if r['case'] in ('declared_absent','declared_present')]
    old=[]
    for name in ('developmental-continual.json','developmental-online-eval.json'):
        old+=json.loads((ROOT/'evidence'/name).read_text())['records']
    models={'intersection':IndexRewrite(examples),'conditional':ContextualRewrite(examples)}
    with tempfile.TemporaryDirectory(prefix='atanor_context_gate_') as root:
        for ordinal in range(12):
            if time.monotonic()-start>120:raise TimeoutError('registered120s cap')
            mode=ordinal%3;linked=ordinal%2==0
            cfg,aliases,ref,payload=configuration(5+ordinal%3,113001+ordinal,
                'detached_absent' if linked else 'independent_full')
            cfg={**cfg,'paths':list(cfg['paths']),'initial':dict(cfg['initial']),
                'operations':cfg['operations']+[{'id':'rename','arity':2}]}
            if not linked:cfg['initial'].pop(cfg['paths'][int(aliases[0][1:])])
            if mode:
                cfg['paths'][int(aliases[0][1:])]='envelope/'+cfg['paths'][int(aliases[0][1:])]
                cfg['paths']=ancestor_closed_paths(cfg['paths'])
                if mode==2:cfg['initial']['envelope']=None
            body=Sandbox(Path(root)/f'predict{ordinal}',**cfg)
            before=body.observe();action=Action('rename',(aliases[1],aliases[0]))
            predictions={arm:model.predict(before,action) for arm,model in models.items()}
            record=event(body,action)
            counts={arm:score(p,Frame.from_dict(record['after'])) for arm,p in predictions.items()}
            rows.append({'ordinal':ordinal,'mode':mode,'record':record,'predictions':predictions,'counts':counts})
            if mode==1:continue
            for arm in ('intersection','conditional') if ordinal%2==0 else ('conditional','intersection'):
                task=Sandbox(Path(root)/f'task{ordinal}{arm}',**cfg);model=Adapter(old+examples,schema=cfg['operations'])
                model.model=Combined(model.model,examples);model.model.rewrite=models[arm]
                channel=next(iter(task.observe().relations))
                goal=Goal('given-outcome',kinds=((aliases[1],0),),equal=tuple((h,ref) for h in [aliases[0]]+aliases[2:]),
                    relations=tuple((channel,aliases[0],h,int(linked)) for h in aliases[2:]))
                selected,prediction,queries=choose(model,task.observe(),goal,task.actions(),horizon=1,limit=32768,allow_partial=True,complete_only=True)
                trace=[] if selected is None else [event(task,selected)]
                p=task._paths
                success=(not p[aliases[1]].exists() and all(p[h].is_file() and p[h].read_bytes()==payload for h in [aliases[0]]+aliases[2:])
                    and all(os.path.samefile(p[aliases[0]],p[h])==linked for h in aliases[2:]) and p[ref].read_bytes()==payload)
                tasks.append({'ordinal':ordinal,'arm':arm,'success':success,'goal':goal.to_dict(),'trace':trace,'queries':queries})
    summary={arm:{'wrong':sum(r['counts'][arm].get('wrong',0) for r in rows),
        'complete':sum(r['counts'][arm].get('correct_singleton',0)==len(r['predictions'][arm]) for r in rows),
        'tasks':sum(t['success'] for t in tasks if t['arm']==arm)} for arm in models}
    passed=(summary['conditional']['wrong']==0 and summary['conditional']['complete']==12 and summary['conditional']['tasks']==8
        and summary['conditional']['tasks']>=summary['intersection']['tasks']+4)
    assert [p.read_bytes() for p in sources]==raws
    result={'verdict':'BOUNDED_CONDITIONAL_GAIN' if passed else 'NOT_CONFIRMED','summary':summary,'rows':rows,'tasks':tasks,
        'source_sha256':[hashlib.sha256(raw).hexdigest() for raw in raws],
        'scope':'supplied three experiences/goals/ancestor sensor; not autonomous representation, agency or complete host model'}
    (output/'report.json').write_text(json.dumps(result,sort_keys=True,separators=(',',':')))
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','tasks')}))


if __name__=='__main__':run(Path(sys.argv[1]))
