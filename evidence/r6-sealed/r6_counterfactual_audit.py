"""Post-seal diagnosis of known feasible plans; NOT a new capability attempt."""
import json
from pathlib import Path
import sys
import tempfile
from collections import Counter
ROOT=Path('D:/ATANOR-experiments/2026-09-17/representation-r6');sys.path.insert(0,str(ROOT))
from packages.action_core.world import Action,Sandbox
from packages.shared_world.relational import RelationalLearner,_leaf,_context,_apply

rows=[json.loads(x) for x in (ROOT.parent/'r6-fresh-v1/rows.jsonl').read_text().splitlines()]
root=Path(tempfile.mkdtemp(prefix='atanor_r6_diagnostic_'));records=[];counts=Counter()
for row in rows:
    if row['arm']!='lookahead':continue
    model=RelationalLearner.restore(row['learner_snapshot']);model._compile()
    for ti,task in enumerate(row['tasks']):
        if task['collective'] or task['success']:continue
        cfg=json.loads(json.dumps(task['config']));cfg['initial']={k:bytes.fromhex(v) for k,v in cfg['initial'].items()}
        reference=cfg['paths'][int(cfg['protected'][0][1:])]
        target=next(k for k in cfg['initial'] if k!=reference);handle=f'n{cfg["paths"].index(target)}'
        body=Sandbox(root/f'{row["block"]}_{ti}',**cfg)
        for op in ('unlink','empty'):
            before=body.observe();action=Action(op,(handle,));state=model.cache[op]
            leaf=_leaf(state['tree'],_context(before,action,(),model.schema))
            applicable=[int(i) for i in leaf['counts'] if _apply(state['programs'][i],before,action,True) is not None]
            anywhere=[i for i,p in enumerate(state['programs']) if _apply(p,before,action,True) is not None]
            predicted,u=model.predict(before,[action])[0];body.step(action);after=body.observe()
            exact=all(s.sizes==after.sizes and s.equal==after.equal and s.relations==after.relations and
                      [k.index(1) for k in s.kinds]==after.kinds for w,s in predicted.outcomes)
            category='exact' if exact else ('no_program' if not anywhere else ('routed_away' if not applicable else 'wrong_program'))
            counts[(op,category)]+=1
            records.append({'block':row['block'],'task':ti,'op':op,'category':category,'uncertainty':u,
                            'leaf_labels':list(map(int,leaf['counts'])),'applicable':applicable,'anywhere':anywhere})
        assert body._paths[handle].read_bytes()==b''
        assert all(body._paths[f'n{i}'].read_bytes()==cfg['initial'][reference] for i in range(len(cfg['paths'])) if f'n{i}'!=handle)
result={'scope':'Known feasible unlink->empty diagnostic on 24 failed selective tasks, fresh temporary roots; candidate unchanged and original RED untouched.',
        'counts':{str(k):v for k,v in counts.items()},'records':records}
(ROOT.parent/'r6-counterfactual-audit.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'counts':result['counts'],'example':records[:2]},indent=2))
