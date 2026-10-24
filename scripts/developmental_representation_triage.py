"""Exposed-data diagnostic, not a new capability attempt or grammar tuning.

Enumerate all recorded action operators/handles at unique archived before states.
Compare frozen base versus dependency decoder for complete planner support and
kind goal inputs. No outcomes are claimed for unexecuted counterfactual actions.
Check exact observed-state/action outcome aliasing separately. Hard cap 120s.
No learner changes, native mutation, or new concept claims.
"""
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.action_core.world import Action, Frame
from scripts.developmental_conditional_eval import Model
from scripts.developmental_fk_tasks import context
from scripts.developmental_observation_dependencies import Dependencies


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def run(output):
    paths = [ROOT/'evidence/developmental-fk-schema-tasks.json',
             ROOT/'evidence/developmental-dependency-forecast-v1/report.json']
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    training = json.loads(paths[0].read_text())['training']
    prior = json.loads(paths[1].read_text())
    rows = training + [r for episode in prior['episodes'] for r in episode['trace']]
    model = Model(training, numeric_context=context)
    dependency = Dependencies()
    for row in training[:48]:
        for key in ('before', 'after'):
            dependency.learn(Frame.from_dict(row[key]))
    states = {canonical(r['before']): r['before'] for r in rows}
    operators = sorted({r['action']['op'] for r in training})
    aliases = defaultdict(set)
    for row in rows:
        aliases[canonical([row['before'], row['action']])].add(canonical(row['after']))
    counts = Counter()
    changes = []
    start = time.monotonic()
    for encoded, state in sorted(states.items()):
        frame = Frame.from_dict(state)
        for op in operators:
            for handle in frame.handles:
                if time.monotonic() - start > 120:
                    raise TimeoutError('120-second diagnostic cap')
                action = Action(op, (handle,))
                p = model.predict(frame, action, True)
                q = dependency.forecast(p)
                assert [x[:2] for x in p] == [x[:2] for x in q]
                complete = [all(len(x[2]) == 1 for x in arm) for arm in (p, q)]
                changed = [a[0] for a, b in zip(p, q) if a[2] != b[2]]
                counts['action_queries'] += 1
                counts['baseline_complete'] += complete[0]
                counts['factored_complete'] += complete[1]
                counts['new_complete'] += not complete[0] and complete[1]
                counts['lost_complete'] += complete[0] and not complete[1]
                counts['changed_complete_successor'] += all(complete) and bool(changed)
                counts['kind_changed_queries'] += 'kind' in changed
                counts['changed_queries'] += bool(changed)
                if changed:
                    changes.append(dict(state_sha256=hashlib.sha256(encoded.encode()).hexdigest(),
                                        action=action.to_dict(), fields=sorted(set(changed)),
                                        complete=complete))
    assert hashes == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    report = dict(protocol=__doc__, source_sha256=hashes, unique_states=len(states),
                  observed_transitions=len(rows), counts=counts, changes=changes,
                  exact_observation_action_keys=len(aliases),
                  conflicting_observation_action_keys=sum(len(v) > 1 for v in aliases.values()),
                  limitation='No alias found does not prove observability; no unseen mechanics or task run.',
                  seconds=time.monotonic()-start)
    with output.open('x') as stream:
        json.dump(report, stream, sort_keys=True)
    print(json.dumps({k:v for k,v in report.items() if k not in ('protocol','changes','source_sha256')}))


if __name__ == '__main__':
    run(Path(sys.argv[1]))
