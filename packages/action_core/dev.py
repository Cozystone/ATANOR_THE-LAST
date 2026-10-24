"""Reusable development probe. NEVER a sealed fresh capability evaluation.

Real filesystem episodes, same exposed history/experience for warm neural and
retrieval controls; cold is secondary. Public tool schemas, parent relations,
file-content equality and protected reference are given, not learned perception.
"""
from __future__ import annotations

import os
for _key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[_key] = '1'

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import tempfile
import time

from .episode import Episode, verify_episode
from .model import Learner
from .planner import Goal, choose
from .retrieval import Retrieval
from .worker import Client
from .world import Sandbox


def make_case(seed, *, training=False):
    rng = random.Random(seed)
    names = [f'x{rng.getrandbits(32):08x}' for _ in range(6)]
    ref, parent, child = names[:3]
    paths = [ref, parent, parent + '/' + child] + names[3:3 + rng.randrange(1, 3)]
    rng.shuffle(paths)
    initial = {ref: rng.randbytes(rng.randrange(3, 25))}
    if rng.random() < .5:
        initial[parent] = None
        if rng.random() < .5:
            initial[parent + '/' + child] = b'wrong bytes'
    if training:
        for p in names[3:]:
            if p in paths and rng.random() < .5:
                initial[p] = rng.choice((None, b'', b'distractor'))
    source = f'n{paths.index(ref)}'
    target = f'n{paths.index(parent + "/" + child)}'
    return {'paths': paths, 'initial': initial, 'protected': {source}}, Goal(f'g-{seed}', ((target, 1),), ((source, target),))


def source_hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob('*.py'))}


def run(output, train_episodes=40, test_episodes=8, change_balanced=False, latest_update=False, uncertainty_weight=0.5, cover_root=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)  # Never overwrite another attempt.
    sources = source_hashes()
    wall, cpu = time.perf_counter(), time.process_time()
    model, retrieval = Learner(seed=2101, change_balanced=change_balanced, latest_update=latest_update), Retrieval()
    parameters = sum(p.numel() for p in model.members.parameters())
    trace = output / 'training.jsonl'
    with tempfile.TemporaryDirectory(prefix='atanor-action-dev-') as temp, trace.open('x', encoding='utf-8') as raw:
        for episode in range(train_episodes):
            config, _ = make_case(10000 + episode, training=True)
            body = Sandbox(Path(temp) / f'train-{episode}', **config)
            rng, history = random.Random(20000 + episode), []
            for step in range(12):
                before, action = body.observe(), rng.choice(body.actions())
                success = body.step(action)
                after = body.observe()
                event_id = f'dev-train-{episode}-{step}'
                args = (event_id, before, action, after, history)
                model.learn(*args)
                retrieval.learn(*args)
                raw.write(json.dumps({'id': event_id, 'before': before.to_dict(), 'action': action.to_dict(),
                    'success': success, 'after': after.to_dict(),
                    'history': [[f.to_dict(), a.to_dict()] for f, a in history]}) + '\n')
                history = (history + [(before, action)])[-3:]
            if (episode + 1) % 10 == 0:
                print(f'DEV training {episode + 1}/{train_episodes}', flush=True)
        snapshot = model.snapshot()
        (output / 'model.json').write_text(json.dumps(snapshot), encoding='utf-8')
        results = []
        for episode in range(test_episodes):
            config, goal = make_case(30000 + episode)
            order = ['neural', 'retrieval', 'cold'] if episode % 2 == 0 else ['cold', 'retrieval', 'neural']
            for arm in order:
                active = Learner.restore(snapshot) if arm == 'neural' else Learner(seed=2101, change_balanced=change_balanced, latest_update=latest_update) if arm == 'cold' else copy.deepcopy(retrieval)
                body = Sandbox(Path(temp) / f'test-{episode}-{arm}', **config)
                start_cpu, start_wall = time.process_time(), time.perf_counter()
                history, events = [], []
                for step in range(8):
                    if goal.holds(body.evidence()):
                        break
                    before = body.observe()
                    action, forecast, nodes = choose(active, before, goal, body.actions(), history,
                        horizon=2 if cover_root else 3, width=2, limit=1024 if cover_root else 160,
                        uncertainty_weight=uncertainty_weight, cover_root=cover_root)
                    success = body.step(action)
                    after = body.observe()
                    active.learn(f'test-{episode}-{step}', before, action, after, history)
                    events.append({'action': action.to_dict(), 'forecast': forecast.to_dict(),
                        'operation_success': success, 'after': after.to_dict(), 'evidence': body.evidence(), 'nodes': nodes})
                    history = (history + [(before, action)])[-3:]
                complete = goal.holds(body.evidence())
                results.append({'episode': episode, 'arm': arm, 'success': complete,
                    'steps': len(events), 'charged_steps': len(events) if complete else 8,
                    'cpu_seconds': time.process_time() - start_cpu,
                    'wall_seconds': time.perf_counter() - start_wall, 'events': events})
            print(f'DEV comparison {episode + 1}/{test_episodes}', flush=True)
        # One preselected full learner-process episode, not selected for success.
        config, goal = make_case(30000)
        body = Sandbox(Path(temp) / 'process-trace', **config)
        with Client(seed=2101, horizon=2 if cover_root else 3, width=2, limit=1024 if cover_root else 160,
                    uncertainty_weight=uncertainty_weight, cover_root=cover_root) as client:
            client.restore(snapshot)
            episode = Episode(output / 'episode.sqlite', body, goal, client, config=config, budget=8)
            try:
                stop = episode.run()
            finally:
                episode.close()
        verified = verify_episode(output / 'episode.sqlite', expected_config=config,
                                   expected_goal=goal, expected_budget=8)
    totals = {arm: {'successes': sum(r['success'] for r in results if r['arm'] == arm),
                   'episodes': test_episodes,
                   'charged_steps': sum(r['charged_steps'] for r in results if r['arm'] == arm),
                   'cpu_seconds': sum(r['cpu_seconds'] for r in results if r['arm'] == arm)}
              for arm in ('neural', 'retrieval', 'cold')}
    report = {'status': 'DEV_ONLY', 'capability_claim': False, 'sources_before': sources,
              'sources_after': source_hashes(), 'train_episodes': train_episodes,
              'training_transitions': train_episodes * 12, 'parameters': parameters, 'change_balanced': change_balanced,
              'latest_update': latest_update, 'uncertainty_weight': uncertainty_weight, 'cover_root': cover_root,
              'totals': totals, 'rows': results, 'process_episode': stop, 'independent_replay': verified,
              'wall_seconds': time.perf_counter() - wall, 'parent_cpu_seconds': time.process_time() - cpu,
              'limitations': ['same mechanics, new DEV configurations only', 'fully observed public structured state',
                  '8 exposed DEV cases, no inference or fresh claim', 'partial restart per test, not lifetime transfer',
                  'CPU totals exclude learner subprocess and startup; not efficiency proof',
                  'neural and retrieval get same records, not equal training algorithms',
                  'no biology-derived topology or pretrained weights',
                  'neural uncertainty is ensemble disagreement; retrieval disagreement zero; see selected weight',
                  'independent replay covers one preselected process episode, not all comparison rows']}
    if report['sources_before'] != report['sources_after']:
        report['status'] = 'INVALID_SOURCE_CHANGED'
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('status', 'parameters', 'totals', 'process_episode', 'independent_replay', 'wall_seconds')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--train-episodes', type=int, default=40)
    parser.add_argument('--test-episodes', type=int, default=8)
    parser.add_argument('--change-balanced', action='store_true')
    parser.add_argument('--latest-update', action='store_true')
    parser.add_argument('--uncertainty-weight', type=float, default=0.5)
    parser.add_argument('--cover-root', action='store_true')
    args = parser.parse_args()
    run(args.output, args.train_episodes, args.test_episodes, args.change_balanced, args.latest_update,
        args.uncertainty_weight, args.cover_root)
