"""Exposed action-selection audit, NOT a new capability evaluation.

Reuse twelve actual historical transitions. Compare original scope with recorded
pre-action expanded scope using the unchanged generic partial-goal selector.
Enumerate all distinct ordered pairs of original handles for the observed
operation, not a supplied winning action. Off-record choices have no measured
outcome: never score them against the one historical action's outcome.
"""
import hashlib
import itertools
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.action_core.world import Frame, Action
from packages.action_core.planner import Goal
from packages.shared_world.contextual_rewrite import ContextualRewrite
from packages.shared_world.partial_goal import select
from scripts.developmental_acquisition_ablation import project


def run(output):
    paths = [ROOT/'evidence'/name for name in (
        'developmental-composition-probe.json', 'developmental-rewrite-scope.json',
        'developmental-contextual-v1/report.json')]
    data = [json.loads(p.read_text()) for p in paths]
    training = [data[0]['rows'][0]['native_record']]
    training += [r['record'] for r in data[1]['rows']
                 if r['case'] in ('declared_absent', 'declared_present')]
    model = ContextualRewrite(training)
    adapter = SimpleNamespace(predict_cells=model.predict)
    rows = []
    for row in data[2]['rows']:
        record = row['record']; n = 6 + row['ordinal'] % 3
        full = Frame.from_dict(record['before'])
        base = project(full, list(range(n)))
        actual = Frame.from_dict(record['after'])
        recorded_action = Action.from_dict(record['action'])
        goal = Goal('historical-probe', kinds=((recorded_action.args[0], 0),
                                             (recorded_action.args[1], 1)))
        actions = [Action(recorded_action.op, args)
                   for args in itertools.permutations(base.handles, 2)]
        result = dict(ordinal=row['ordinal'], recorded_action=recorded_action.to_dict(),
                      recorded_goal_success=all(actual.kinds[actual.handles.index(h)] == k
                                                for h, k in goal.kinds))
        for arm, view in (('base', base), ('expanded', full)):
            chosen = select(adapter, view, goal, actions)
            action = chosen[0] if chosen else None
            result[arm] = dict(action=action.to_dict() if action else None,
                              score=chosen[1].score if chosen else None,
                              outcome_known=action == recorded_action)
        rows.append(result)
    summary = {arm: dict(
        abstentions=sum(r[arm]['action'] is None for r in rows),
        recorded_success_selected=sum(r[arm]['outcome_known'] and r['recorded_goal_success'] for r in rows),
        recorded_failure_selected=sum(r[arm]['outcome_known'] and not r['recorded_goal_success'] for r in rows),
        off_record_selected=sum(r[arm]['action'] is not None and not r[arm]['outcome_known'] for r in rows)
    ) for arm in ('base', 'expanded')}
    report = dict(scope=__doc__, capability_claim=False, summary=summary, rows=rows,
                  source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    with output.open('x') as stream:
        json.dump(report, stream, sort_keys=True)
    print(json.dumps(summary))


if __name__ == '__main__':
    run(Path(sys.argv[1]))
