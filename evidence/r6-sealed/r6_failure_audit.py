"""Post-result model diagnosis ONLY, never rerun or tune the fresh trial."""
import json
from pathlib import Path
import sys
from collections import Counter
ROOT=Path('D:/ATANOR-experiments/2026-09-17/representation-r6');sys.path.insert(0,str(ROOT))
from packages.action_core.world import Frame,Action
from packages.shared_world.relational import RelationalLearner,_leaf,_context,_apply,_bindings,_groups,_evaluate

rows=[json.loads(x) for x in (ROOT.parent/'r6-fresh-v1/rows.jsonl').read_text().splitlines()]
records=[];counts=Counter()
for row in rows:
    if row['arm']!='lookahead':continue
    model=RelationalLearner.restore(row['learner_snapshot']);model._compile()
    for ordinal,task in enumerate(row['tasks']):
        if task['success']:continue
        for step,event in enumerate(task['trace']):
            before=Frame.from_dict(event['before']);action=Action.from_dict(event['action']);after=Frame.from_dict(event['after'])
            state=model.cache.get(action.op)
            leaf=_leaf(state['tree'],_context(before,action,(),model.schema)) if state else {'counts':{}}
            applicable=[i for i in leaf['counts'] if _apply(state['programs'][i],before,action,True) is not None]
            anywhere=[i for i in range(len(state['programs'])) if _apply(state['programs'][i],before,action,True) is not None] if state else []
            ambiguity=[]
            for label in applicable:
                binding=_bindings(before,action);groups=_groups(before,binding,True)
                for slot,addresses in groups.items():
                    outcomes={tuple(_evaluate(e,slot[0],a,before,binding) for a in addresses) for e in state['programs'][label][slot]}
                    if len(outcomes)>1:ambiguity.append({'slot':slot,'expressions':state['programs'][label][slot],'values':list(outcomes)})
            forecast=model.predict(before,[action])[0][0]
            exact=all(s.sizes==after.sizes and s.equal==after.equal and s.relations==after.relations and
                      [k.index(1) for k in s.kinds]==after.kinds for w,s in forecast.outcomes)
            category='exact_step_but_failed_plan' if exact else ('no_program' if not anywhere else ('routed_away' if not applicable else 'wrong_applicable_program'))
            counts[category]+=1
            records.append({'block':row['block'],'task':ordinal,'step':step,'collective':task['collective'],'action':event['action'],
                'category':category,'leaf_labels':list(map(int,leaf['counts'])),'applicable':applicable,'anywhere':anywhere,'ambiguous_slots':ambiguity})
output={'scope':'All chosen steps in failed lookahead tasks, post-result diagnosis. No repair/no rerun. Exactness is whole state, not goal probability.',
        'counts':dict(counts),'records':records}
(ROOT.parent/'r6-failure-audit.json').write_text(json.dumps(output,indent=2))
print(json.dumps({'counts':dict(counts),'ambiguous_wrong_steps':sum(r['category']=='wrong_applicable_program' and bool(r['ambiguous_slots']) for r in records),'first_wrong':next((r for r in records if r['category']=='wrong_applicable_program'),None)},indent=2))
