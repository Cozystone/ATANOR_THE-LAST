"""Frozen DEV continuous replanning: frozen vs learning from every own event.

Same192 prior, same native seed131001,count4, no resets;16 supplied outcome goals
(eight-goal empty/restore schedule repeated). No procedure library. Existing
complete-first partial-goal arbitration, horizon3,width8. Per episode6actions,
8192model calls including explicit selected-action prediction,120s total cap.
Every arm replans after each actual observation. Only online rebuilds model using
all own actual events (failures included), never imagined states. No retries.
Capability gain ONLY >=2more successes with no increase in actions, or equal
success with >=20% lower total CPU and no increase in actions. Forecast error
reduction alone is diagnostic, not capability. Retained prior cells must not
regress. All induction CPU counted. Goals/operator curriculum are not agency.
"""
import json,sys,time,tempfile
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Frame,Action
from packages.action_core.planner import Goal
from packages.shared_world.partial_goal import arbitrate
from scripts.developmental_task_eval import Adapter
from scripts.developmental_continual_probe import score
from scripts.developmental_active_eval import event
from scripts.representation_r3_dev import configuration


def run(output):
    if output.exists():raise FileExistsError(output)
    old=[]
    for name in ('developmental-continual.json','developmental-online-eval.json'):
        old+=json.loads((ROOT/'evidence'/name).read_text())['records']
    models={a:Adapter(old) for a in ('frozen','online')};histories={a:[] for a in models}
    rows=[];start=time.monotonic();cfg,aliases,ref,payload=configuration(4,131001)
    targets=({0},set(),{1},set(),{2,3},set(),{0,1},set())*2
    with tempfile.TemporaryDirectory(prefix='atanor_revision_life_') as root:
        bodies={a:Sandbox(Path(root)/a,**cfg) for a in models}
        initial=bodies['online'].observe();full=initial.sizes[initial.handles.index(ref)]
        for n,empty in enumerate(targets):
            for arm in (('frozen','online') if n%2==0 else ('online','frozen')):
                body=bodies[arm];goal=Goal('supplied-outcome',sizes=tuple((h,0. if i in empty else full) for i,h in enumerate(aliases)))
                trace=[];queries=0;cpu=time.process_time();stop='action_budget'
                def actual_success():
                    return all(body._paths[h].is_file() and body._paths[h].read_bytes()==(b'' if i in empty else payload) for i,h in enumerate(aliases))
                for step in range(6):
                    if time.monotonic()-start>120:raise TimeoutError('120s cap')
                    if actual_success():stop='goal_reached';break
                    actions=body.actions();remaining=8192-queries
                    if remaining<=len(actions)+1:stop='query_budget';break
                    view=body.observe()
                    action,prediction,used=arbitrate(models[arm],view,goal,actions,horizon=3,width=8,limit=remaining-1)
                    queries+=used
                    if action is None:stop='unsupported';break
                    cells=models[arm].predict_cells(view,action);queries+=1
                    record=event(body,action);histories[arm].append(record)
                    trace.append({**record,'predictions':cells,'decision':prediction.to_dict(),
                        'prediction_score':dict(score(cells,Frame.from_dict(record['after'])))})
                    if arm=='online':models[arm]=Adapter(old+histories[arm])
                assert body._paths[ref].read_bytes()==payload and queries<=8192
                rows.append(dict(ordinal=n,arm=arm,goal=goal.to_dict(),trace=trace,queries=queries,
                    cpu=time.process_time()-cpu,success=actual_success(),stop=stop))
    summary={}
    for arm,model in models.items():
        errors=Counter();retention=Counter()
        for r in rows:
            if r['arm']==arm:
                for s in r['trace']:errors.update(s['prediction_score'])
        for r in old:retention.update(score(model.predict_cells(Frame.from_dict(r['before']),Action.from_dict(r['action'])),Frame.from_dict(r['after'])))
        summary[arm]=dict(successes=sum(r['success'] for r in rows if r['arm']==arm),
            actions=len(histories[arm]),queries=sum(r['queries'] for r in rows if r['arm']==arm),
            cpu=sum(r['cpu'] for r in rows if r['arm']==arm),predictions=errors,retention=retention)
    a,b=summary['online'],summary['frozen']
    gain=a['actions']<=b['actions'] and (a['successes']>=b['successes']+2 or
        (a['successes']==b['successes'] and a['cpu']<=.8*b['cpu'])) and a['retention']==b['retention']
    result=dict(verdict='DEV_REVISION_CAPABILITY_GAIN' if gain else 'NO_DEV_REVISION_CAPABILITY_GAIN',summary=summary,rows=rows)
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':run(Path(sys.argv[1]))
