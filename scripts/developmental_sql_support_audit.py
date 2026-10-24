"""Read-only audit of sealed initial task states; no new native execution."""
import hashlib,json,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_task_eval import Adapter
from scripts.developmental_fk_tasks import context
from scripts.developmental_rooted_probe import rooted
from packages.action_core.world import Frame,Action
from packages.action_core.planner import Goal
from packages.shared_world.epistemic_lookahead import _query_projection

def run(source,output):
    raw=source.read_bytes(); data=json.loads(raw)
    ops=list(dict.fromkeys(r['action']['op'] for r in data['training']))
    schema=[{'id':op,'arity':1} for op in ops]
    models={arm:Adapter(data['training'],schema=schema,numeric_context=context if arm=='relational' else None)
            for arm in ('local','relational')}
    rows=[]; totals=Counter(); reasons=Counter()
    for record in data['records']:
        frame=Frame.from_dict(record['trace'][0]['before'])
        goal=Goal('audit',kinds=tuple((f'n{i}',s) for i,s in enumerate(record['target'])))
        model=models[record['arm']]
        actions=[]
        for op in ops:
            for handle in frame.handles:
                action=Action(op,(handle,))
                cells=model.model.predict(frame,action,True)
                unresolved=Counter(field for field,_,values in cells if len(values)!=1)
                for field,address,values in cells:
                    if len(values)==1: continue
                    key,_=rooted(frame,action,field,address)
                    rule=model.model.rules.get(key)
                    reason=('unseen_context' if rule is None else
                            'unresolved_conflict' if not rule.common and not rule.alternatives else
                            'surviving_disagreement')
                    reasons[record['arm']+':'+field+':'+reason]+=1
                forecast=model.predict(frame,[action])[0]
                changed=False; goal_match=False
                if forecast is not None:
                    projected=_query_projection(forecast[0])
                    changed=projected.to_dict()!=frame.to_dict()
                    goal_match=bool(goal.probability(forecast[0]))
                category='unsupported' if forecast is None else 'supported_change' if changed else 'supported_nochange'
                totals[record['arm']+':'+category]+=1
                actions.append({'action':action.to_dict(),'category':category,'unresolved':dict(unresolved),
                                'one_step_goal_match':goal_match})
        rows.append({'ordinal':record['ordinal'],'arm':record['arm'],'actions':actions})
    report={'source_sha256':hashlib.sha256(raw).hexdigest(),'totals':dict(totals),'reasons':dict(reasons),'rows':rows,
            'scope':'exposed root support audit only, not replanned task performance'}
    assert source.read_bytes()==raw
    with output.open('x') as stream:json.dump(report,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps(report['totals']))

if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
