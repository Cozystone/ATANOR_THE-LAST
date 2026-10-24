"""Post-run diagnosis ONLY: native oracle is never exposed to the PSC learner.

Do not repair/retry frozen PSC-v1. Compare empirical-root support to actual native
reachability under the identical four-action planning horizon. Oracle uses SQLite
execution+generic BFS, not authored SQL solution rules. Hard120s/4096queries/case.
"""
from collections import Counter, deque
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_predictive_state import PredictiveState, token


def run(source, directory):
    output = directory/'diagnosis.json'
    if output.exists():
        raise FileExistsError(output)
    paths = [directory/'report.json', directory/'initial-mind.json', directory/'final-mind.json',
             ROOT/'scripts/developmental_predictive_state.py', source]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    report = json.loads(paths[0].read_text())
    minds = {phase:PredictiveState.restore(json.loads((directory/name).read_text()))
             for phase,name in [('before','initial-mind.json'),('after','final-mind.json')]}
    spec = importlib.util.spec_from_file_location('psc_diagnostic_native', source)
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    started = time.monotonic()
    cases = []
    for r in report['results']:
        if r['phase'] != 'before' or r['arm'] != 'psc':
            continue
        actions = [[op,i] for op in native.FK_ACTIONS for i in range(r['n'])]
        body = native.FKWorld(r['seed'],n=r['n'],prefill=r['prefill'])
        initial = list(body.config())
        body.dispose()
        support = {}
        for phase,mind in minds.items():
            counter = Counter()
            for action in actions:
                examples = mind.edges.get((token(initial),token(action)),{})
                counter['root_actions_observed_once'] += sum(examples.values()) >= 1
                counter['root_actions_observed_twice'] += sum(examples.values()) >= 2
                p = mind.predict(initial, action)
                q = mind.predict(initial, action, tabular=True)
                counter['psc_singleton'] += p is not None
                counter['lookup_singleton'] += q is not None
                counter['psc_changes_state'] += p is not None and p != initial
            counter['goal_seen_as_outcome'] = any(token(r['goal']) in c for c in mind.edges.values())
            support[phase] = counter
        queue = deque([(initial,[])])
        seen = {token(initial)}
        found = None
        queries = 0
        while queue:
            state, path = queue.popleft()
            if state == r['goal']:
                found = path
                break
            if len(path) >= 4:
                continue
            for action in actions:
                if time.monotonic()-started > 120 or queries >= 4096:
                    raise TimeoutError('native diagnostic cap; no retry')
                queries += 1
                body = native.FKWorld(r['seed'],n=r['n'],prefill=r['prefill'])
                try:
                    for previous in path:
                        body.do(*previous)
                    assert list(body.config()) == state
                    body.do(*action)
                    after = list(body.config())
                finally:
                    body.dispose()
                key = token(after)
                if key not in seen:
                    seen.add(key)
                    queue.append((after,path+[action]))
        cases.append(dict(ordinal=r['ordinal'], n=r['n'], initial=initial, goal=r['goal'],
                          native_plan=found, native_queries=queries, root_support=support))
    assert hashes == {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    summary = dict(cases=len(cases), native_reachable=sum(c['native_plan'] is not None for c in cases),
                   shortest_lengths=[len(c['native_plan']) if c['native_plan'] is not None else None for c in cases],
                   no_changing_root_before=sum(c['root_support']['before']['psc_changes_state']==0 for c in cases),
                   no_changing_root_after=sum(c['root_support']['after']['psc_changes_state']==0 for c in cases),
                   observed_once_before=sum(c['root_support']['before']['root_actions_observed_once'] for c in cases),
                   observed_twice_before=sum(c['root_support']['before']['root_actions_observed_twice'] for c in cases),
                   goals_seen_before=sum(c['root_support']['before']['goal_seen_as_outcome'] for c in cases),
                   goals_seen_after=sum(c['root_support']['after']['goal_seen_as_outcome'] for c in cases))
    with output.open('x') as stream:
        json.dump(dict(protocol=__doc__, summary=summary, cases=cases, source_sha256=hashes,
                       seconds=time.monotonic()-started), stream, sort_keys=True)
    print(json.dumps(summary))


if __name__ == '__main__':
    run(Path(sys.argv[1]), Path(sys.argv[2]))
