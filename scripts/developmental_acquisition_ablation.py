"""EXPOSED observation-masking feasibility, not new native agency/capability.

Reuse twelve previously observed full native transitions. Censor appended sensor
nodes for the base view and reveal selected ancestors from the same PRE-action
observation. Never invent historical hidden values. All sensor alternatives are
available offline: training is full-information, NOT autonomous experience.
First six train credit, last six exposed holdout; frozen effect model, no tuning.
"""
import json
import random
import sys
from pathlib import Path
from collections import Counter
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from packages.action_core.world import Frame,Action
from packages.shared_world.contextual_rewrite import ContextualRewrite
from packages.shared_world.acquisition_value import AcquisitionValue
from packages.shared_world.relational import _value


def project(frame, indices):
    matrix=lambda m:[[m[i][j] for j in indices] for i in indices]
    return Frame([frame.kinds[i] for i in indices], [frame.sizes[i] for i in indices],
        matrix(frame.equal), matrix(frame.parent), tuple(frame.handles[i] for i in indices),
        {k:matrix(m) for k,m in frame.relations.items()})


def run(output, selected_only=False, balanced=False):
    # Fixed one-shot DEV credit ablation, not a fresh/native capability trial.
    # Six uniform selections, seed142001, then six greedy choices. No seed sweep.
    rng=random.Random(142001)
    read=lambda n:json.loads((ROOT/'evidence'/n).read_text())
    seeds=[read('developmental-composition-probe.json')['rows'][0]['native_record']]
    seeds += [r['record'] for r in read('developmental-rewrite-scope.json')['rows'] if r['case'] in ('declared_absent','declared_present')]
    model=ContextualRewrite(seeds); policy=AcquisitionValue(); results=[]
    for row in read('developmental-contextual-v1/report.json')['rows']:
        ordinal=row['ordinal']; record=row['record']; count=6+ordinal%3
        full=Frame.from_dict(record['before']); after=Frame.from_dict(record['after'])
        action=Action.from_dict(record['action']); base=project(full,list(range(count)))
        def assess(view):
            counts=Counter(); loss=0.
            for field,address,values in model.predict(view,action):
                if any(i>=count for i in address):continue
                truth=_value(after,field,address)
                status='unknown' if not values else 'wrong' if truth not in values else 'correct' if len(values)==1 else 'ambiguous'
                counts[status]+=1
                loss += 1. if status=='wrong' else .5 if status in ('unknown','ambiguous') else 0.
            return dict(counts=counts,loss=loss/sum(counts.values()))
        baseline=assess(base); candidates={}
        for i,h in enumerate(base.handles):
            selected=set(range(count)); frontier=[i]
            while frontier:
                child=frontier.pop()
                for j in range(len(full.handles)):
                    if full.parent[j][child] and j not in selected:
                        selected.add(j);frontier.append(j)
            candidates[h]=assess(project(full,sorted(selected)))
        chosen=(policy.explore(base,action,rng) if balanced else rng.choice(base.handles)) if selected_only and ordinal<6 else policy.choose(base,action)
        results.append(dict(ordinal=ordinal,training=ordinal<6,baseline=baseline,
            chosen=chosen,learned=candidates[chosen],fixed=candidates[base.handles[0]],
            fixed_arg0=candidates[action.args[0]],fixed_arg1=candidates[action.args[1]],
            random_expected_loss=sum(v['loss'] for v in candidates.values())/len(candidates),
            all_observed=assess(full),candidates=candidates))
        if ordinal<6:
            credited=[chosen] if selected_only else list(candidates)
            for h in credited:policy.learn(base,action,h,baseline['loss']-candidates[h]['loss'])
    held=results[6:]
    summary={arm:sum(r[arm]['loss'] for r in held)/len(held) for arm in ('baseline','learned','fixed','fixed_arg0','fixed_arg1','all_observed')}
    summary['random_expected']=sum(r['random_expected_loss'] for r in held)/len(held)
    with output.open('x') as f:json.dump(dict(scope=__doc__,selected_only=selected_only,balanced=balanced,
        credit_scope='only chosen simulated observations' if selected_only else 'all offline alternatives',
        summary=summary,rows=results),f,sort_keys=True)
    print(json.dumps(summary))


if __name__=='__main__':run(Path(sys.argv[1]),'--selected-only' in sys.argv[2:], '--balanced' in sys.argv[2:])
