"""Single frozen developmental comparison. See preregistration; never retry."""
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import time
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_plastic_world import PlasticWorld
from packages.shared_world.sql_schema_sensor import schema_observation


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame(body):
    kinds = list(body.config())
    edges = [[0]*body.n for _ in kinds]
    for k, ref in body.con.execute('SELECT k, ref FROM row_ ORDER BY k'):
        if ref is not None:
            edges[k][ref] = 1
    schema = schema_observation(body.con, ['anchor']+['row_']*(body.n-1))
    return dict(kinds=kinds, scalars=schema['scalars'], edges=[edges, schema['references']])


def run(source, output):
    output.mkdir(exist_ok=False)
    paths = [source, Path(__file__), ROOT/'scripts/developmental_plastic_world.py',
             ROOT/'packages/shared_world/sql_schema_sensor.py',
             ROOT/'docs/ATANOR_PLASTIC_LIFE_V1_PREREGISTRATION.md']
    hashes = {str(p): sha(p) for p in paths}
    (output/'attempt.json').write_text(json.dumps(dict(hashes=hashes)), encoding='utf-8')
    spec = importlib.util.spec_from_file_location('native_plastic', source)
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    started, cpu_started = time.monotonic(), time.process_time()
    results, life_stats = [], []
    native_steps_verified = 0

    def cap():
        if time.monotonic()-started > 1800:
            raise TimeoutError('30 minute hard cap; preserve attempt, no retry')

    def actions(n):
        return [[op, i] for op in range(4) for i in range(n)]

    def replay(seed, n, prefill, trace):
        nonlocal native_steps_verified
        body = native.FKWorld(seed, n=n, prefill=prefill)
        try:
            for event in trace:
                assert frame(body) == event['before']
                op, target = event['action']
                assert bool(body.do(native.FK_ACTIONS[op], target)) == event['native_accept']
                assert frame(body) == event['after']
                native_steps_verified += 1
        finally:
            body.dispose()

    def evaluate(checkpoints, life, age):
        # Same held-out tasks across ages: measurement only, never canonical updates.
        # Includes all outcomes, including accidentally already-satisfied starts.
        for task in range(4):
            seed, n, prefill = 720000+life*100+task, 5+task%2, 1+task//2
            goal = list(native.fk_goal(seed+30000, n=n))
            order = ['fresh', 'passive', 'developing']
            order = order[(life+task+age//256)%3:]+order[:(life+task+age//256)%3]
            for arm in order:
                cap()
                state = checkpoints[arm]
                model = PlasticWorld.restore(state)
                model.enter_body(n)
                rng = random.Random(seed+91000)
                body = native.FKWorld(seed, n=n, prefill=prefill)
                trace = []
                queries, updates = model.model_queries, model.updates
                cpu = time.process_time()
                try:
                    before = frame(body)
                    while before['kinds'] != goal and len(trace) < 32:
                        cap()
                        allowed = actions(n)
                        action = model.choose_task(before, allowed, goal, rng)
                        prediction, _ = model.forecasts(before, [action])
                        accepted = bool(body.do(native.FK_ACTIONS[action[0]], action[1]))
                        after = frame(body)
                        model.learn(before, action, after)
                        trace.append(dict(before=before, action=action,
                                          predicted_kinds=prediction[0].tolist(),
                                          native_accept=accepted, after=after))
                        before = after
                    success = before['kinds'] == goal
                finally:
                    body.dispose()
                row = dict(life=life, age=age, arm=arm, task=task, seed=seed, n=n,
                           prefill=prefill, goal=goal, success=success, actions=len(trace),
                           penalized_actions=len(trace) if success else 33,
                           queries=model.model_queries-queries, updates=model.updates-updates,
                           cpu_seconds=time.process_time()-cpu, trace=trace)
                replay(seed, n, prefill, trace)
                with (output/'tasks.jsonl').open('a', encoding='utf-8') as f:
                    f.write(json.dumps(row, separators=(',', ':'))+'\n')
                results.append({k:v for k,v in row.items() if k != 'trace'})

    for life in range(4):
        seed = 610000+life
        fresh = PlasticWorld(seed)
        fresh.enter_body(4)
        frozen = fresh.checkpoint()
        models = {arm:PlasticWorld.restore(frozen) for arm in ('passive', 'developing')}
        bodies = {arm:native.FKWorld(seed, n=4, prefill=2) for arm in models}
        rngs = {arm:random.Random(seed+100) for arm in models}
        traces = {arm:[] for arm in models}
        cpus = {arm:0. for arm in models}
        try:
            evaluate(dict(fresh=frozen, **{a:m.checkpoint() for a,m in models.items()}), life, 0)
            for age in range(1, 1025):
                cap()
                for arm, model in models.items():
                    body = bodies[arm]
                    cpu = time.process_time()
                    before = frame(body)
                    action = model.choose_experience(before, actions(4), rngs[arm], arm=='developing')
                    accepted = bool(body.do(native.FK_ACTIONS[action[0]], action[1]))
                    after = frame(body)
                    model.learn(before, action, after)
                    cpus[arm] += time.process_time()-cpu
                    traces[arm].append(dict(before=before, action=action, native_accept=accepted, after=after))
                if age in (256, 1024):
                    checkpoints = dict(fresh=frozen)
                    for arm, model in models.items():
                        state = model.checkpoint()
                        path = output/f'life-{life}-{arm}-{age}.pt'
                        torch.save(state, path)
                        restored = PlasticWorld.restore(torch.load(path, weights_only=True))
                        obs, allowed = frame(bodies[arm]), actions(4)
                        a, _ = model.forecasts(obs, allowed)
                        b, _ = restored.forecasts(obs, allowed)
                        assert torch.equal(a, b)
                        checkpoints[arm] = state
                        life_stats.append(dict(life=life, arm=arm, age=age,
                                               queries=state['model_queries'], updates=state['updates'],
                                               cpu_seconds=cpus[arm], checkpoint_sha256=sha(path)))
                    evaluate(checkpoints, life, age)
            for arm, trace in traces.items():
                replay(seed, 4, 2, trace)
                (output/f'life-{life}-{arm}.json').write_text(json.dumps(trace, separators=(',', ':')), encoding='utf-8')
        finally:
            for body in bodies.values():
                body.dispose()
        print(json.dumps(dict(completed_life=life, wall_seconds=time.monotonic()-started)), flush=True)

    def rows(arm, age):
        return [r for r in results if r['arm']==arm and r['age']==age]

    def cost(arm, age, life=None):
        r = [r for r in rows(arm, age) if life is None or r['life']==life]
        return sum(x['penalized_actions'] for x in r)/len(r)

    totals = {f'{arm}-{age}':dict(success=sum(r['success'] for r in rows(arm,age)), count=16,
               mean_penalized_actions=cost(arm,age), actual_actions=sum(r['actions'] for r in rows(arm,age)),
               cpu_seconds=sum(r['cpu_seconds'] for r in rows(arm,age)))
               for arm in ('fresh','passive','developing') for age in (0,256,1024)}
    success_set = lambda arm,age: {(r['life'],r['task']) for r in rows(arm,age) if r['success']}
    lost = sorted(success_set('developing',256)-success_set('developing',1024))
    gates = dict(native_reexecution=True, restart_forecasts=True,
                 source_unchanged=all(sha(Path(p))==h for p,h in hashes.items()),
                 fresh_cost_lift=cost('developing',1024)<=0.8*cost('fresh',1024),
                 passive_cost_lift=cost('developing',1024)<=0.8*cost('passive',1024),
                 all_lives_beat_fresh=all(cost('developing',1024,i)<cost('fresh',1024,i) for i in range(4)),
                 all_lives_beat_passive=all(cost('developing',1024,i)<cost('passive',1024,i) for i in range(4)),
                 success_not_lower=all(len(success_set('developing',1024))>=len(success_set(a,1024)) for a in ('fresh','passive')),
                 age_gain=cost('developing',1024)<=0.9*cost('developing',256),
                 nonvacuous_retention=len(success_set('developing',256))>=4 and not lost)
    report = dict(verdict='BOUNDED_DEVELOPMENTAL_PASS' if all(gates.values()) else 'NO_GO',
                  scope='known SQLite mechanics, new n5/n6 instances; not new-law transfer or AGI',
                  gates=gates, totals=totals, lost_successes=lost, life_stats=life_stats,
                  native_steps_verified=native_steps_verified, task_results=results,
                  wall_seconds=time.monotonic()-started, cpu_seconds=time.process_time()-cpu_started,
                  hashes=hashes)
    (output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('verdict','gates','totals','wall_seconds')}), flush=True)


if __name__ == '__main__':
    run(Path(sys.argv[1]), Path(sys.argv[2]))
