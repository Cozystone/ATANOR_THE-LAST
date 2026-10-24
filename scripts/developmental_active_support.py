"""Exposed starting-state support diagnosis. No training on task outcomes."""
import json
import hashlib
import sys
import tempfile
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_task_eval import Adapter
from scripts.developmental_rooted_probe import rooted
from scripts.representation_r3_dev import configuration, make_goal
from packages.action_core.world import Sandbox


def run(source, output):
    raw = source.read_bytes()
    report = json.loads(raw)
    rows = []
    with tempfile.TemporaryDirectory(prefix='atanor_support_') as root:
        for life in report['lives']:
            model = Adapter(life['bootstrap'] + life['acquisition'])
            for task in life['tasks']:
                index = task['task']
                cfg, aliases, _, _ = configuration(3 + index % 2, 97001 + 20 * life['life'] + index)
                body = Sandbox(Path(root) / f"{life['life']}_{life['arm']}_{index}", **cfg)
                frame = body.observe()
                goal = make_goal(body, aliases, index % 4 >= 2)
                required = {('kind', (frame.handles.index(h),)): k for h,k in goal._required_kinds().items()}
                required.update({('size', (frame.handles.index(h),)): s for h,s in goal.sizes})
                required.update({('equal', (frame.handles.index(a),frame.handles.index(b))): 1 for a,b in goal.equal})
                counts = Counter()
                by_operation = {}
                best = -1
                best_actions = []
                for action in body.actions():
                    predicted = {(f,tuple(a)): v for f,a,v in model.predict_cells(frame,action)}
                    supported = 0
                    detail = Counter()
                    for (field,address), wanted in required.items():
                        values = predicted[field,address]
                        key, _ = rooted(frame,action,field,address)
                        category = ('unseen_key' if key not in model.model.rules else
                                    'unsupported_existing_key' if not values else
                                    'multiple' if len(values)>1 else 'singleton')
                        counts[category] += 1
                        by_operation.setdefault(action.op, Counter())[category] += 1
                        detail[category] += 1
                        supported += bool(values) and all(abs(v-wanted)<=1e-12 for v in values)
                    if supported > best:
                        best = supported
                        best_actions = []
                    if supported == best:
                        best_actions.append({'action':action.to_dict(), 'counts':dict(detail)})
                rows.append({'life':life['life'],'arm':life['arm'],'task':index,
                             'task_success':task['success'],'goal_cells':len(required),
                             'all_actions_goal_cell_counts':dict(counts),
                             'by_operation':by_operation,
                             'best_one_step_supported_goal_cells':best,'best_actions':best_actions})
    summary = {}
    for arm in ('none','random','active'):
        counts = Counter()
        for row in rows:
            if row['arm'] == arm:
                counts.update(row['all_actions_goal_cell_counts'])
        summary[arm] = dict(counts)
    result = {'source_sha256':hashlib.sha256(raw).hexdigest(),'summary':summary,'rows':rows,
              'scope':'exposed initial-state support, NOT causal attribution or fresh capability'}
    assert source.read_bytes() == raw
    with output.open('x') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps(summary))


if __name__ == '__main__':
    run(Path(sys.argv[1]),Path(sys.argv[2]))
