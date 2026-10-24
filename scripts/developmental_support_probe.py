"""Frozen-history diagnostic, not a learner or experimental policy."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.action_core.world import Sandbox, Action
from packages.shared_world.relational import RelationalLearner, _apply, _groups, _bindings
from packages.shared_world.effect_hypotheses import inspect_effects
from scripts.representation_r3_dev import configuration


def run(source, output):
    raw = source.read_bytes()
    data = json.loads(raw)
    model = RelationalLearner.restore(data['snapshot'])
    snapshot = model.snapshot()
    cfg, _, reference, payload = configuration(3, 119031)
    results = []
    with tempfile.TemporaryDirectory(prefix='atanor_support_') as root:
        body = Sandbox(Path(root) / 'native', **cfg)
        for record in data['records']:
            assert body.observe().to_dict() == record['before']
            assert body.step(Action.from_dict(record['action'])) == record['success']
            assert body.observe().to_dict() == record['after']
        frame = body.observe()
        for action in body.actions():
            receipt = inspect_effects(model, frame, action)
            programs = model.cache.get(action.op, {}).get('programs', [])
            keys = set(_groups(frame, _bindings(frame, action), model.partitioned))
            applicable = [i for i, p in enumerate(programs)
                          if _apply(p, frame, action, model.partitioned) is not None]
            unsupported = receipt['status'] == 'NO_APPLICABLE_ROUTED_BRANCH'
            category = ('A_ROUTING' if applicable else 'B_NO_PROGRAM_SUPPORT') if unsupported else 'SUPPORTED'
            results.append({'action': action.to_dict(), 'status': receipt['status'],
                            'category': category, 'all_applicable': applicable,
                            'routed': receipt.get('routed_labels'),
                            'slot_deltas': [{'missing': sorted(map(repr, keys-set(p))),
                                             'extra': sorted(map(repr, set(p)-keys))}
                                            for p in programs]})
        assert body._paths[reference].read_bytes() == payload
    assert model.snapshot() == snapshot
    assert source.read_bytes() == raw
    counts = {k: sum(r['category'] == k for r in results)
              for k in ('A_ROUTING', 'B_NO_PROGRAM_SUPPORT', 'SUPPORTED')}
    report = {'source_sha256': hashlib.sha256(raw).hexdigest(), 'counts': counts,
              'snapshot_unchanged': True, 'capability_claim': False, 'actions': results}
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
    print(json.dumps(counts))


if __name__ == '__main__':
    run(Path(sys.argv[1]), Path(sys.argv[2]))
