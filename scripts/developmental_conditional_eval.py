"""One-shot held-out prediction check; no task/agency/generality claim."""
import hashlib
import itertools
import json
from pathlib import Path
import random
import sys
import tempfile
import time
from collections import Counter
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_rooted_probe import rooted, value, cells
from scripts.developmental_continual_probe import score
from scripts.representation_r3_dev import configuration
from packages.shared_world.conditional_support import fit
from packages.shared_world.relational import _value
from packages.action_core.world import Frame, Action, Sandbox


class Model:
    def __init__(self, records, numeric_context=None, key_transform=None):
        self.numeric_context = numeric_context or (lambda frame, nodes: tuple(frame.sizes[i] for i in nodes))
        self.key_transform = key_transform or (lambda key: key)
        self.examples = {}
        self.rules = {}
        self.learn(records)

    def learn(self, records):
        """Refit only touched contexts; same hypotheses as full-history rebuild.

        Records must be real observations supplied by the owning runtime. This
        method does not authenticate provenance or promote predictions to truth.
        """
        touched = set()
        for record in records:
            before, after = (Frame.from_dict(record[k]) for k in ('before', 'after'))
            action = Action.from_dict(record['action'])
            for field, address in cells(before):
                key, nodes = rooted(before, action, field, address)
                key = self.key_transform(key)
                truth = _value(after, field, address)
                expressions = [('keep',), ('constant', truth)]
                expressions += [('copy',)+p for p in itertools.product(range(len(nodes)), repeat=len(address))]
                allowed = frozenset(e for e in expressions if value(e, before, field, address, nodes)==truth)
                self.examples.setdefault(key, []).append((self.numeric_context(before, nodes), allowed))
                touched.add(key)
        for key in touched:
            self.rules[key] = fit(self.examples[key])

    def predict(self, frame, action, conditional):
        result = []
        for field, address in cells(frame):
            key, nodes = rooted(frame, action, field, address)
            key = self.key_transform(key)
            rule = self.rules.get(key)
            symbols = (() if rule is None else rule.query(self.numeric_context(frame, nodes))
                       if conditional else rule.common)
            result.append((field, address, sorted({value(e, frame, field, address, nodes) for e in symbols})))
        return result


def run(source, output):
    raw = source.read_bytes()
    training = json.loads(raw)['records']
    model = Model(training)
    totals = {arm: Counter() for arm in ('baseline', 'conditional')}
    cpu = Counter()
    records = []
    with tempfile.TemporaryDirectory(prefix='atanor_conditional_') as root:
        for episode, count in enumerate((5, 6, 5, 6)):
            seed = 57001 + episode
            rng = random.Random(seed)
            cfg, _, reference, payload = configuration(count, seed, payload=b'z'*(503+episode*211))
            body = Sandbox(Path(root)/str(episode), **cfg)
            for step in range(24):
                before = body.observe()
                action = rng.choice(body.actions())
                predictions = {}
                for arm in totals:
                    start = time.process_time()
                    predictions[arm] = model.predict(before, action, arm=='conditional')
                    cpu[arm] += time.process_time()-start
                success = body.step(action)
                after = body.observe()
                for arm in totals:
                    totals[arm].update(score(predictions[arm], after))
                assert body._paths[reference].read_bytes()==payload
                records.append({'episode': episode, 'step': step, 'before': before.to_dict(),
                                'action': action.to_dict(), 'after': after.to_dict(),
                                'success': success, 'predictions': predictions})
    # Retention check after actual new experience; never feed this back into run.
    updated = Model(training + records)
    retention = {phase: Counter() for phase in ('before', 'after')}
    for record in training:
        before, after = (Frame.from_dict(record[k]) for k in ('before', 'after'))
        action = Action.from_dict(record['action'])
        for phase, learner in (('before', model), ('after', updated)):
            retention[phase].update(score(learner.predict(before, action, True), after))
    b, c = totals['baseline'], totals['conditional']
    passed = (c['wrong']==0 and c['correct_singleton']>b['correct_singleton']
              and c['unknown']<=b['unknown'] and retention['after']['wrong']==0
              and retention['after']['correct_singleton']>=retention['before']['correct_singleton'])
    report = {'verdict': 'PREDICTION_GATE_PASS' if passed else 'PREDICTION_GATE_FAIL',
              'scope': 'new instances and scale, SAME mechanics; no action utility or AGI claim',
              'source_sha256': hashlib.sha256(raw).hexdigest(), 'totals': totals,
              'cpu_seconds': cpu, 'retention': retention, 'records': records}
    assert source.read_bytes()==raw
    with output.open('x') as stream:
        json.dump(report, stream, sort_keys=True, separators=(',', ':'))
    print(json.dumps({k:v for k,v in report.items() if k!='records'}))


if __name__=='__main__':
    run(Path(sys.argv[1]), Path(sys.argv[2]))
