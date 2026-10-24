import json
from pathlib import Path
import sys
from collections import Counter
ROOT=Path('D:/ATANOR-experiments/2026-09-17/representation-r4')
sys.path.insert(0,str(ROOT))
from packages.shared_world.relational import RelationalLearner,_view,_apply,_context,_leaf,_bindings,_groups,_evaluate
from packages.action_core.world import Frame,Action
from scripts.representation_r1_dev import SCHEMA

records=json.loads((ROOT.parent/'r4-dev-v2/records.json').read_text())
model=RelationalLearner(schema=SCHEMA,partitioned=True)
for i,r in enumerate(records['active']['acquisitions']):
    model.learn(i,Frame.from_dict(r['before']),Action.from_dict(r['action']),Frame.from_dict(r['after']))
model._compile()
task=records['active']['checkpoints']['32']['tasks'][1]
frame=Frame.from_dict(task['trace'][0]['before'])
result={'training_ops':dict(Counter(r['action']['op'] for r in records['active']['acquisitions'])),'actions':[]}
for op in ('empty','unlink'):
    for h in frame.handles:
        if h in task['config']['protected']: continue
        action=Action(op,(h,)); state=model.cache.get(op)
        x=_context(frame,action,(),model.schema); leaf=_leaf(state['tree'],x)
        applicable=[i for i in leaf['counts'] if _apply(state['programs'][i],frame,action,True) is not None]
        anywhere=[i for i in range(len(state['programs'])) if _apply(state['programs'][i],frame,action,True) is not None]
        divergent=0
        for i in applicable:
            binding=_bindings(frame,action); groups=_groups(frame,binding,True)
            for slot,addresses in groups.items():
                outputs={tuple(_evaluate(e,slot[0],a,frame,binding) for a in addresses) for e in state['programs'][i][slot]}
                divergent+=len(outputs)>1
        result['actions'].append({'op':op,'handle':h,'leaf_labels':list(map(int,leaf['counts'])),
            'applicable_in_leaf':applicable,'applicable_anywhere':anywhere,'ambiguous_effect_slots':divergent,
            'prediction':model.predict(frame,[action])[0][0].to_dict()})
output=ROOT.parent/'r4-failure-inspection.json'
output.write_text(json.dumps(result,indent=2))
print(json.dumps({**result,'actions':[{k:v for k,v in r.items() if k!='prediction'} for r in result['actions']]},indent=2))
