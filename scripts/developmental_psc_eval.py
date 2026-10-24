"""PSC-v1 one-shot architecture feasibility gate; no old-vocabulary tuning.

Frozen training:192 archived SQLite transitions, raw observed kinds only (the
legacy native state sensor). No equal/schema/context features enter cognition.
Three arms share data and planner: predictive tests / test ablation / exact
transition lookup. Last is a strong control against calling lookup abstraction.
16 new instance seeds152001..152016, alternating n4/n5, prefill1/2; goals exactly
the earlier cohort family (first8 anchor absent/rest free; last8 link a free row).
No evaluation learning. Eight native actions/task, horizon4,4096queries/decision.
Then same learner gets128 random actual transitions at seed153001,n4,prefill2;
repeat the fixed evaluation as a PREDECLARED retention comparison, not a retry.
Frozen before/after checkpoints and restart reconstruction must match.
All native traces replayed independently. Hard wall cap180seconds.

Five gates: dimensions>0; every birth actual conflicting witnessed future with
support>=2; fresh PSC success>=ablation+4 AND>=12/16 AND>=lookup; restored
predictions/plans identical; sequential PSC success set retains EVERY initial
success and previously correct archived whole-state predictions, without any
increase in wrong singletons. Native replay and source immutability mandatory.
Only all GREEN authorizes immediate second-mechanism test. Otherwise preserve
partial result, diagnose this estimator (never declare PSR theory disproved).
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_predictive_state import PredictiveState, token


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(source, output):
    output.mkdir(exist_ok=False)
    training_path = ROOT/'evidence/developmental-fk-schema-tasks.json'
    paths = [source, training_path, Path(__file__),
             ROOT/'scripts/developmental_predictive_state.py']
    hashes = {str(p): digest(p) for p in paths}
    (output/'attempt.json').write_text(token(dict(protocol=__doc__, hashes=hashes)))
    started = time.monotonic()

    def cap():
        if time.monotonic()-started > 180:
            raise TimeoutError('PSC fixed180s cap; do not retry')

    spec = importlib.util.spec_from_file_location('native_psc_sql', source)
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    records = json.loads(training_path.read_text())['training']
    mind = PredictiveState()
    body = native.FKWorld(82001, n=4, prefill=2)
    learning_trace = []
    try:
        for ordinal, r in enumerate(records):
            cap()
            before = list(body.config())
            assert before == r['before']['kinds']
            action = [r['action']['op'], int(r['action']['args'][0][1:])]
            predicted = mind.predict(before, action)
            success = body.do(*action)
            after = list(body.config())
            assert after == r['after']['kinds']
            mind.learn(before, action, after)
            learning_trace.append(dict(before=before, action=action, after=after,
                                       prediction=predicted, success=success,
                                       dimensions=len(mind.tests)))
    finally:
        body.dispose()
    initial = mind.snapshot()
    (output/'initial-mind.json').write_text(token(initial))
    restored = PredictiveState.restore(json.loads((output/'initial-mind.json').read_text()))
    assert token(restored.snapshot()) == token(initial)

    def evaluate(model, phase):
        results = []
        frozen = token(model.snapshot())
        for ordinal in range(16):
            seed, n, prefill = 152001+ordinal, 4+ordinal%2, 1+(ordinal//2)%2
            arms = ['psc', 'ablated', 'lookup']
            if ordinal%2:
                arms.reverse()
            for arm in arms:
                cap()
                body = native.FKWorld(seed, n=n, prefill=prefill)
                initial_obs = list(body.config())
                goal = list(initial_obs)
                if ordinal < 8:
                    goal = [0]+[1]*(n-1)
                else:
                    goal[next(i for i in range(1,n) if goal[i] == 1)] = 2
                actions = [[op, i] for op in native.FK_ACTIONS for i in range(n)]
                mode = dict(ablated=arm=='ablated', tabular=arm=='lookup')
                trace = []
                try:
                    for step in range(8):
                        cap()
                        before = list(body.config())
                        if before == goal:
                            break
                        plan, queries = model.plan(before, actions, goal, **mode)
                        if not plan:
                            trace.append(dict(stop='unsupported', observation=before, queries=queries))
                            break
                        action = plan[0]
                        prediction = model.predict(before, action, **mode)
                        success = body.do(*action)
                        after = list(body.config())
                        trace.append(dict(before=before, action=action, prediction=prediction,
                                          success=success, after=after, queries=queries))
                    solved = list(body.config()) == goal
                finally:
                    body.dispose()
                # Separate real DB replay; forecast never participates in truth.
                replay = native.FKWorld(seed, n=n, prefill=prefill)
                try:
                    assert list(replay.config()) == initial_obs
                    for r in trace:
                        if 'action' not in r:
                            assert list(replay.config()) == r['observation']
                            continue
                        assert list(replay.config()) == r['before']
                        assert replay.do(*r['action']) == r['success']
                        assert list(replay.config()) == r['after']
                    assert (list(replay.config()) == goal) == solved
                finally:
                    replay.dispose()
                results.append(dict(phase=phase, ordinal=ordinal, seed=seed, n=n,
                                    prefill=prefill, arm=arm, goal=goal, success=solved,
                                    trace=trace, native_replay=True))
        assert frozen == token(model.snapshot())
        return results

    before_results = evaluate(restored, 'before')
    # Restart equality at every archived state and schema action, not just digest.
    for r in learning_trace:
        assert mind.state(r['before']) == restored.state(r['before'])
        assert mind.predict(r['before'], r['action']) == restored.predict(r['before'], r['action'])
    continuation = []
    body = native.FKWorld(153001, n=4, prefill=2)
    rng = random.Random(153001)
    try:
        for step in range(128):
            cap()
            before = list(body.config())
            action = [rng.choice(native.FK_ACTIONS), rng.randrange(4)]
            prediction = restored.predict(before, action)
            success = body.do(*action)
            after = list(body.config())
            restored.learn(before, action, after, boundary=step==0)
            continuation.append(dict(before=before, action=action, prediction=prediction,
                                     after=after, success=success))
    finally:
        body.dispose()
    replay = native.FKWorld(153001, n=4, prefill=2)
    try:
        for r in continuation:
            assert list(replay.config()) == r['before']
            assert replay.do(*r['action']) == r['success']
            assert list(replay.config()) == r['after']
    finally:
        replay.dispose()
    final = restored.snapshot()
    (output/'final-mind.json').write_text(token(final))
    assert token(PredictiveState.restore(json.loads(token(final))).snapshot()) == token(final)
    after_results = evaluate(restored, 'after')
    retention = dict(lost_correct=0, wrong_before=0, wrong_after=0)
    for r in learning_trace:
        p = mind.predict(r['before'], r['action'])
        q = restored.predict(r['before'], r['action'])
        retention['lost_correct'] += p == r['after'] and q != r['after']
        retention['wrong_before'] += p is not None and p != r['after']
        retention['wrong_after'] += q is not None and q != r['after']
    all_results = before_results + after_results
    summary = {}
    for phase in ('before', 'after'):
        summary[phase] = {}
        for arm in ('psc', 'ablated', 'lookup'):
            rows = [r for r in all_results if r['phase']==phase and r['arm']==arm]
            summary[phase][arm] = dict(success=sum(r['success'] for r in rows), total=len(rows),
                actions=sum('action' in t for r in rows for t in r['trace']),
                wrong_predictions=sum(t['prediction']!=t['after'] for r in rows for t in r['trace'] if 'action' in t))
    old_successes = {r['ordinal'] for r in before_results if r['arm']=='psc' and r['success']}
    new_successes = {r['ordinal'] for r in after_results if r['arm']=='psc' and r['success']}
    causal = bool(mind.births)
    # Independently reconstruct each pre-birth merged state and observed witness.
    audit = PredictiveState()
    for idx, r in enumerate(learning_trace):
        audit.learn(r['before'], r['action'], r['after'])
        for birth in [b for b in audit.births if b['record']==idx]:
            actions, outcomes = birth['test']
            left, right = birth['witness_rows']
            for start in (left, right):
                window = learning_trace[start:start+len(actions)]
                causal &= [token(t['action']) for t in window] == actions
            causal &= token(learning_trace[left]['before']) == birth['left']
            causal &= token(learning_trace[right]['before']) == birth['right']
            causal &= [token(t['after']) for t in learning_trace[left:left+len(actions)]] == outcomes
            causal &= [token(t['after']) for t in learning_trace[right:right+len(actions)]] != outcomes
    b = summary['before']
    gates = dict(experience_created_dimensions=bool(mind.tests), actual_contradiction=bool(causal),
        ablation_capability_loss=b['psc']['success'] >= b['ablated']['success']+4,
        fresh_capability=b['psc']['success'] >= 12 and b['psc']['success'] >= b['lookup']['success'],
        restart=True, sequential_retention=(old_successes <= new_successes and retention['lost_correct']==0
            and retention['wrong_after'] <= retention['wrong_before']),
        native_replay=True, sources_unchanged=hashes == {str(p):digest(p) for p in paths})
    report = dict(protocol=__doc__, gates=gates, summary=summary, retention=retention,
                  verdict='PSC_FIRST_GATE_GREEN' if all(gates.values()) else 'PSC_FIRST_GATE_NO_GO',
                  dimensions=dict(before=len(mind.tests), after=len(restored.tests)),
                  training=learning_trace, continuation=continuation, results=all_results,
                  source_sha256=hashes, seconds=time.monotonic()-started,
                  caveat='Empirical observation-anchor estimator, not hidden-state PSR or unseen-mechanism transfer.')
    with (output/'report.json').open('x') as stream:
        json.dump(report, stream, sort_keys=True)
    print(json.dumps({k:v for k,v in report.items() if k not in ('protocol','training','continuation','results','source_sha256')}))


if __name__ == '__main__':
    run(Path(sys.argv[1]), Path(sys.argv[2]))
