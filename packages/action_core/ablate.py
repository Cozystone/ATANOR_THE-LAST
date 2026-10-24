"""Exposed DEV planning ablations. No candidate/benchmark capability claim."""
from __future__ import annotations

import os
for _key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[_key] = '1'

import argparse
import copy
import json
from pathlib import Path
import tempfile
import time

from .dev import make_case, source_hashes
from .model import Learner
from .planner import choose
from .retrieval import Retrieval
from .world import Frame, Action, Sandbox


class NoDisagreement:
    def __init__(self, model):
        self.model = model

    def predict(self, *args):
        return [(f, 0.) for f, _ in self.model.predict(*args)]

    def learn(self, *args):
        return self.model.learn(*args)


def retrieval_from(path):
    result = Retrieval()
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        result.learn(r['id'], Frame.from_dict(r['before']), Action.from_dict(r['action']),
                     Frame.from_dict(r['after']), [(Frame.from_dict(f), Action.from_dict(a)) for f, a in r['history']])
    return result


def run(source, output):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    hashes = source_hashes()
    snapshot = json.loads((source / 'model.json').read_text(encoding='utf-8'))
    retrieval = retrieval_from(source / 'training.jsonl')
    conditions = [('neural', h, u) for h in (1, 3) for u in (False, True)] + [('retrieval', h, False) for h in (1, 3)]
    rows = []
    with tempfile.TemporaryDirectory(prefix='atanor-action-ablation-') as temp:
        for case in range(8):
            config, goal = make_case(30000 + case)
            order = conditions[case % 6:] + conditions[:case % 6]
            for arm, horizon, uncertainty in order:
                label = f'{arm}-h{horizon}-u{int(uncertainty)}'
                model = Learner.restore(snapshot) if arm == 'neural' else copy.deepcopy(retrieval)
                if not uncertainty:
                    model = NoDisagreement(model)
                body = Sandbox(Path(temp) / f'{case}-{label}', **config)
                events, history = [], []
                cpu = time.process_time()
                for step in range(8):
                    if goal.holds(body.evidence()):
                        break
                    before = body.observe()
                    action, forecast, nodes = choose(model, before, goal, body.actions(), history,
                                                    horizon=horizon, width=2, limit=160)
                    success = body.step(action)
                    after = body.observe()
                    model.learn(f'probe-{case}-{step}', before, action, after, history)
                    events.append({'action': action.to_dict(), 'before': before.to_dict(), 'after': after.to_dict(),
                        'evidence': body.evidence(), 'forecast': forecast.to_dict(), 'operation_success': success,
                        'no_change': before == after, 'nodes': nodes})
                    history = (history + [(before, action)])[-3:]
                end_cpu = time.process_time() - cpu
                success = goal.holds(body.evidence())
                replay = Sandbox(Path(temp) / f'replay-{case}-{label}', **config)
                verified = True
                for event in events:
                    verified &= replay.observe().to_dict() == event['before']
                    verified &= replay.step(Action.from_dict(event['action'])) == event['operation_success']
                    verified &= replay.observe().to_dict() == event['after'] and replay.evidence() == event['evidence']
                verified &= goal.holds(replay.evidence()) == success
                rows.append({'case': case, 'arm': label, 'success': success, 'charged_steps': len(events) if success else 8,
                    'no_change': sum(e['no_change'] for e in events), 'failed_actions': sum(not e['operation_success'] for e in events),
                    'repeated_actions': sum(events[i]['action'] == events[i-1]['action'] for i in range(1, len(events))),
                    'replay': bool(verified), 'cpu_seconds': end_cpu, 'events': events})
            print(f'planning DEV {case + 1}/8', flush=True)
    totals = {}
    for arm in sorted({r['arm'] for r in rows}):
        selected = [r for r in rows if r['arm'] == arm]
        totals[arm] = {k: sum(r[k] for r in selected) for k in ('success', 'charged_steps', 'no_change', 'failed_actions', 'repeated_actions', 'cpu_seconds')}
    result = {'status': 'DEV_DIAGNOSTIC', 'capability_claim': False, 'totals': totals, 'rows': rows,
              'replays_verified': sum(r['replay'] for r in rows), 'sources_before': hashes, 'sources_after': source_hashes()}
    if hashes != result['sources_after']:
        result['status'] = 'INVALID_SOURCE_CHANGED'
    (output / 'report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'totals': totals, 'replays_verified': result['replays_verified'], 'status': result['status']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.source, args.output)
