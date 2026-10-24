"""Frozen fresh pair-context gate; no forced-use task to manufacture a gain.

Both models retain192 old events +3context examples +2exposed equal-degree witness
events. Old histogram implementation pinned at a4d7020; new adds argument pairs.
8fresh native two-cluster worlds, seeds121001..121008,groups(3,3),(2,4),(4,2),(3,4),
balanced within/across-cluster rename prediction. Then same goal remove one alias
and preserve all others/content/relations; ALL actions available, one action
budget and existing complete-first/partial-goal planner, no action prescribed.
Prediction gate: candidate8/8 complete,0wrong. Capability gate:>=2more native tasks,
zero paired losses. If only prediction improves, do NOT label capability lift or
expand this branch. No test learning, no retries,120s cap.
"""
import json,sys,tempfile,subprocess,types,hashlib,time,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Frame,Action
from packages.action_core.planner import Goal
from packages.shared_world.contextual_rewrite import ContextualRewrite
from packages.shared_world.partial_goal import arbitrate
from scripts.developmental_rewrite_tasks import Combined
from scripts.developmental_task_eval import Adapter
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event
from scripts.developmental_continual_probe import score


def run(output):
    output.mkdir(exist_ok=False);start=time.monotonic()
    source=subprocess.check_output(['git','show','a4d7020:packages/shared_world/contextual_rewrite.py'],cwd=ROOT).decode()
    legacy=types.ModuleType('packages.shared_world.frozen_histogram');legacy.__package__='packages.shared_world'
    exec(compile(source,'a4d7020:contextual_rewrite.py','exec'),legacy.__dict__)
    old=[]
    for name in ('developmental-continual.json','developmental-online-eval.json'):
        old+=json.loads((ROOT/'evidence'/name).read_text())['records']
    examples=[json.loads((ROOT/'evidence/developmental-composition-probe.json').read_text())['rows'][0]['native_record']]
    examples += [r['record'] for r in json.loads((ROOT/'evidence/developmental-rewrite-scope.json').read_text())['rows'] if r['case'] in ('declared_absent','declared_present')]
    examples += json.loads((ROOT/'evidence/developmental-context-alias.json').read_text())['records']
    effects={'histogram':legacy.ContextualRewrite(examples),'pair':ContextualRewrite(examples)};rows=[];tasks=[]
    with tempfile.TemporaryDirectory(prefix='atanor_pair_gate_') as root:
        for n in range(8):
            if time.monotonic()-start>120:raise TimeoutError('registered120s cap')
            left,right=((3,3),(2,4),(4,2),(3,4))[n//2]
            cfg,aliases,ref,payload=configuration(left+right,121001+n)
            names=[cfg['paths'][int(h[1:])] for h in aliases]
            cfg={**cfg,'initial':{**cfg['initial'],names[left]:payload},
                'initial_links':{name:names[0 if i<left else left] for i,name in enumerate(names) if i not in (0,left)},
                'operations':cfg['operations']+[{'id':'rename','arity':2}]}
            body=Sandbox(Path(root)/f'predict{n}',**cfg);before=body.observe()
            action=Action('rename',(aliases[0],aliases[1 if n%2==0 else left]))
            predictions={arm:m.predict(before,action) for arm,m in effects.items()}
            record=event(body,action)
            rows.append({'ordinal':n,'config_groups':[left,right],'record':record,'predictions':predictions,
                'counts':{arm:score(p,Frame.from_dict(record['after'])) for arm,p in predictions.items()}})
            for arm in ('histogram','pair') if n%2==0 else ('pair','histogram'):
                body=Sandbox(Path(root)/f'task{n}{arm}',**cfg);view=body.observe();channel=next(iter(view.relations))
                remaining=aliases[1:]
                relations=tuple((channel,a,b,int(view.relations[channel][view.handles.index(a)][view.handles.index(b)]))
                    for a in remaining for b in remaining)
                goal=Goal('remove-preserve',kinds=((aliases[0],0),),equal=tuple((h,ref) for h in remaining),relations=relations)
                model=Adapter(old+examples,schema=cfg['operations']);model.model=Combined(model.model,examples);model.model.rewrite=effects[arm]
                selected,prediction,queries=arbitrate(model,view,goal,body.actions(),horizon=1,limit=32768)
                trace=[] if selected is None else [event(body,selected)]
                paths=body._paths
                success=(not paths[aliases[0]].exists() and all(paths[h].is_file() and paths[h].read_bytes()==payload for h in remaining)
                    and all(paths[a].exists() and paths[b].exists() and int(os.path.samefile(paths[a],paths[b]))==v for _,a,b,v in relations)
                    and paths[ref].read_bytes()==payload)
                tasks.append({'ordinal':n,'arm':arm,'goal':goal.to_dict(),'trace':trace,'queries':queries,'success':success})
    summary={arm:{'complete':sum(r['counts'][arm].get('correct_singleton',0)==len(r['predictions'][arm]) for r in rows),
        'wrong':sum(r['counts'][arm].get('wrong',0) for r in rows),
        'tasks':sum(t['success'] for t in tasks if t['arm']==arm)} for arm in effects}
    prediction_pass=summary['pair']['complete']==8 and summary['pair']['wrong']==0
    loss=any(next(t for t in tasks if t['ordinal']==n and t['arm']=='histogram')['success'] and
        not next(t for t in tasks if t['ordinal']==n and t['arm']=='pair')['success'] for n in range(8))
    capability=prediction_pass and not loss and summary['pair']['tasks']>=summary['histogram']['tasks']+2
    result={'verdict':'CAPABILITY_GAIN' if capability else 'PREDICTION_ONLY' if prediction_pass else 'NOT_CONFIRMED',
        'summary':summary,'paired_loss':loss,'legacy_sha256':hashlib.sha256(source.encode()).hexdigest(),'rows':rows,'tasks':tasks,
        'scope':'fresh instances of exposed file mechanics; no generality, agency, or cross-mechanism transfer'}
    (output/'report.json').write_text(json.dumps(result,sort_keys=True,separators=(',',':')))
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','tasks')}))


if __name__=='__main__':run(Path(sys.argv[1]))
