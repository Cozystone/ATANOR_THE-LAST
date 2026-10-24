"""Read-only source diagnosis of first sealed persistent-v1 abstention.

No retraining on diagnostic actions, no capability rerun. Reconstruct preceding
native events in a new temporary body. Compare fixed depth3/4 beam and depth4
cost-ordered searches at4096queries each. Execute cost-ordered witness if found.
This is exposed failure analysis, never fresh capability evidence.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_task_eval import Adapter
from scripts.representation_r3_dev import configuration
from packages.action_core.world import Sandbox, Action
from packages.action_core.planner import Goal
from packages.shared_world.partial_goal import arbitrate
from packages.shared_world.cost_ordered_search import search


def run(output):
    if output.exists(): raise FileExistsError(output)
    source = ROOT / 'evidence/developmental-persistent-v1/online.sqlite'
    db = sqlite3.connect('file:' + source.as_posix() + '?mode=ro&immutable=1', uri=True)
    try:
        rows = [(kind, json.loads(text)) for kind, text in db.execute(
            'SELECT kind,payload FROM events ORDER BY seq')]
    finally:
        db.close()
    old = []
    for name in ('developmental-continual.json', 'developmental-online-eval.json'):
        old += json.loads((ROOT / 'evidence' / name).read_text())['records']
    model = Adapter(old); previous = []; probes = {}
    cfg, _, reference, payload = configuration(5, 138001)
    with tempfile.TemporaryDirectory(prefix='atanor_abstention_') as root:
        body = Sandbox(Path(root) / 'body', **cfg)
        for kind, row in rows:
            if kind == 'GOAL' and row['goal']['id'] == '2':
                goal = Goal.from_dict(row['goal']); break
            if kind == 'PREDICT':
                action = Action.from_dict(row['action'])
            elif kind == 'DISPATCH':
                before = body.observe(); success = body.step(action)
            elif kind == 'RESULT':
                after = body.observe()
                assert after.to_dict() == row['frame'] and body.evidence() == row['evidence']
                assert success == row['succeeded']
                event = dict(before=before.to_dict(), action=action.to_dict(), after=after.to_dict())
                previous.append(event); model.model.learn([event])
        else:
            raise ValueError('expected failed goal missing')
        frame = body.observe(); actions = body.actions(); coverage = Counter()
        for action in actions:
            cells = model.predict_cells(frame, action)
            coverage['actions'] += 1
            coverage['complete_actions'] += all(len(v) == 1 for _, _, v in cells)
            for _, _, values in cells:
                coverage['unknown' if not values else 'singleton' if len(values) == 1 else 'ambiguous'] += 1
        for horizon in (3, 4):
            start = time.process_time()
            action, prediction, used = arbitrate(model, frame, goal, actions,
                horizon=horizon, width=8, limit=4096)
            probes[str(horizon)] = dict(action=None if action is None else action.to_dict(),
                queries=used, cpu=time.process_time()-start)
        start = time.process_time()
        plan, expected, used = search(model, frame, goal, [(a,) for a in actions], budget=4, limit=4096)
        probes['cost_ordered4'] = dict(plan=[a.to_dict() for a in plan], queries=used,
            cpu=time.process_time()-start)
        witness = []
        for action, predicted in zip(plan, expected):
            before = body.observe(); success = body.step(action); after = body.observe()
            witness.append(dict(before=before.to_dict(), action=action.to_dict(), success=success,
                prediction=predicted.to_dict(), after=after.to_dict(), exact=predicted.to_dict()==after.to_dict()))
        native = bool(plan) and all(body._paths[h].is_file() and
            len(body._paths[h].read_bytes()) == (0 if size == 0 else len(payload)) for h, size in goal.sizes)
        assert body._paths[reference].read_bytes() == payload
    result = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        preceding_native_steps=len(previous), goal=goal.to_dict(), coverage=coverage,
        probes=probes, witness=witness, native_goal_reached=native)
    with output.open('x') as stream: json.dump(result, stream, sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k != 'witness'}))


if __name__ == '__main__': run(Path(sys.argv[1]))
