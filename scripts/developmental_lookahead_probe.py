"""DEV go/no-go for learned-preparation search, not a capability claim.

R10 had six bootstrap observations and no applicable preparatory model. Here use
retained192 actual events plus3 contextual rewrite examples, same finite search
bounds (length3,width32,queries2048). No prepared experiment menu or target state.
Four fixed initial bodies, seeds115001..115004,count3/4,linked/independent.
Score is disagreeing output cells / actual sequence length; unknown is NOT
disagreement. Search all permitted actions, only full-singleton preparation.
GO requires some selected multi-step proposal, faithful native preparation and
reduced disagreement at its actually observed final query after real learning.
Otherwise do not build a larger lookahead subsystem.120s overall cap, once.
"""
import json,sys,tempfile,time,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Frame,Action
from packages.shared_world.contextual_rewrite import ContextualRewrite
from scripts.developmental_task_eval import Adapter
from scripts.developmental_rewrite_tasks import Combined
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event
from scripts.developmental_continual_probe import score


def adapter(old,examples,schema):
    model=Adapter(old+examples,schema=schema)
    model.model=Combined(model.model,examples);model.model.rewrite=ContextualRewrite(examples)
    return model


def materialize(frame,cells):
    if any(len(v)!=1 for _,_,v in cells):return None
    output=copy.deepcopy(frame)
    for field,address,values in cells:
        if field=='kind':output.kinds[address[0]]=int(values[0])
        elif field=='size':output.sizes[address[0]]=values[0]
        else:(output.equal if field=='equal' else output.relations[field])[address[0]][address[1]]=values[0]
    # Query-only algebraic view; never journalled as an observation or learned.
    return output


def search(model,frame,actions):
    frontier=[(frame,())];seen={repr(frame.to_dict())};best=None;queries=0;immediate=0;skipped=0
    for depth in range(1,4):
        successors=[]
        for state,prefix in frontier:
            for action in actions:
                if queries>=2048:return best,queries,immediate,skipped
                cells=model.predict_cells(state,action);queries+=1
                disagreement=sum(len(v)>1 for _,_,v in cells)
                if depth==1:immediate=max(immediate,disagreement)
                utility=disagreement/depth
                if disagreement and (best is None or utility>best[0]):best=(utility,prefix+(action,))
                if depth==3:continue
                future=materialize(state,cells)
                if future is None:skipped+=1;continue
                key=repr(future.to_dict())
                if key not in seen:seen.add(key);successors.append((future,prefix+(action,)))
        frontier=successors[:32]
        if not frontier:break
    return best,queries,immediate,skipped


def run(output):
    old=[]
    for name in ('developmental-continual.json','developmental-online-eval.json'):
        old+=json.loads((ROOT/'evidence'/name).read_text())['records']
    examples=[json.loads((ROOT/'evidence/developmental-composition-probe.json').read_text())['rows'][0]['native_record']]
    examples += [r['record'] for r in json.loads((ROOT/'evidence/developmental-rewrite-scope.json').read_text())['rows'] if r['case'] in ('declared_absent','declared_present')]
    rows=[];start=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='atanor_lookahead_dev_') as root:
        for i in range(4):
            if time.monotonic()-start>120:raise TimeoutError('registered120s cap')
            cfg,aliases,ref,payload=configuration(3+i%2,115001+i,'coupled_full' if i<2 else 'independent_full')
            cfg={**cfg,'operations':cfg['operations']+[{'id':'rename','arity':2}]}
            body=Sandbox(Path(root)/str(i),**cfg);model=adapter(old,examples,cfg['operations'])
            best,queries,immediate,skipped=search(model,body.observe(),body.actions())
            records=[];faithful=True;before_disagreement=after_disagreement=None
            if best:
                for n,action in enumerate(best[1]):
                    before=body.observe();prediction=model.predict_cells(before,action)
                    record=event(body,action);records.append(record)
                    actual=Frame.from_dict(record['after'])
                    assert body._paths[ref].read_bytes()==payload
                    if n<len(best[1])-1:
                        measured=score(prediction,actual)
                        faithful &= measured.get('correct_singleton',0)==len(prediction)
                        if not faithful:break
                    else:
                        before_disagreement=sum(len(v)>1 for _,_,v in prediction)
                        updated=adapter(old,examples+records,cfg['operations'])
                        after_disagreement=sum(len(v)>1 for _,_,v in updated.predict_cells(before,action))
            rows.append({'ordinal':i,'queries':queries,'immediate_disagreement':immediate,'unsupported_preparations':skipped,
                'utility':None if best is None else best[0],'sequence':[] if best is None else [a.to_dict() for a in best[1]],
                'faithful_preparation':faithful,'before_disagreement':before_disagreement,'after_disagreement':after_disagreement,'records':records})
    go=any(len(r['sequence'])>1 and r['faithful_preparation'] and r['after_disagreement'] is not None
           and r['after_disagreement']<r['before_disagreement'] for r in rows)
    result={'verdict':'MULTISTEP_FEASIBLE' if go else 'NO_MULTISTEP_JUSTIFICATION','rows':rows,
        'scope':'four exposed DEV worlds, supplied score and prior experience, not capability/economy/agency proof'}
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({'verdict':result['verdict'],'rows':[{k:v for k,v in r.items() if k!='records'} for r in rows]}))


if __name__=='__main__':run(Path(sys.argv[1]))
