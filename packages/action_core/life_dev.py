"""Exposed continuity DEV and one preselected real-worker restart comparison."""
from __future__ import annotations

import os
for _variable in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[_variable] = '1'

import argparse
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import zipfile

from .dev import make_case, source_hashes
from .episode import canonical, digest
from .life import Life
from .model import Learner
from .planner import choose
from .storage import require_space
from .worker import Client


PLANNING = {'horizon': 2, 'width': 2, 'limit': 4096,
            'cover_root': True, 'uncertainty_weight': 0}


def load_base(path):
    """Normalize only the documented legacy neural dispatch tag, as fresh_eval does.

    DEV4 predates the algorithm tag. Its weights/RNG/replay are not changed, and
    an explicit different algorithm is rejected rather than overwritten.
    """
    base = json.loads(Path(path).read_text(encoding='utf-8'))
    if 'algorithm' not in base:
        base['algorithm'] = 'neural'
    if base['algorithm'] != 'neural':
        raise ValueError('continuity DEV requires the neural base checkpoint')
    return base


class LocalClient:
    """Same research Client API, in process for cheap DEV; no isolation claim."""
    def restore(self, checkpoint):
        self.model = Learner.restore(checkpoint)

    def snapshot(self):
        return self.model.snapshot()

    def choose(self, frame, goal, actions, history):
        return choose(self.model, frame, goal, actions, history, **PLANNING)

    def learn(self, *args):
        return self.model.learn(*args)


def episode_rows(summary):
    rows = []
    for entry in summary['episodes']:
        assert entry['phase'] == 'done'
        stop = entry['stop']
        rows.append({'index': entry['index'], 'success': stop['completed'],
                     'charged_steps': stop['steps'] if stop['completed'] else 8,
                     'actual_steps': stop['steps'], 'checkpoint_digest': entry['checkpoint_digest']})
    return rows


def trace(path):
    db = sqlite3.connect('file:' + Path(path).resolve().as_posix() + '?mode=ro', uri=True)
    events = [(k, json.loads(p)) for k, p in db.execute('SELECT kind,payload FROM events ORDER BY seq')]
    state = json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
    db.close()
    # Episode UUID/event identities differ between independent runs; native
    # observations, action choices and pre-result forecasts must still agree.
    comparable = [(k, p) for k, p in events if k in ('FORECAST', 'DISPATCH', 'RESULT', 'STOP')]
    return comparable, state


def restart_comparison(output, body_parent, base):
    config, goal = make_case(30000)
    agenda = [{'config': config, 'goal': goal, 'budget': 8}]
    summaries, traces, states = {}, {}, {}
    for label in ('uninterrupted', 'restarted'):
        root, body_root = output / label, body_parent / label
        client = Client(seed=2101, **PLANNING)
        life = Life(root, body_root, agenda, client, initial_checkpoint=base, overall_budget=8)
        try:
            if label == 'restarted':
                first = life.step()
                assert first['steps_used'] == 1 and first['status'] == 'RUNNING'
                previous_pid = client.process.pid
                life.close()
                client.close()
                client = Client(seed=2101, **PLANNING)
                assert client.process.pid != previous_pid
                life = Life(root, body_root, agenda, client, initial_checkpoint=base, overall_budget=8)
            summaries[label] = life.run()
            assert summaries[label]['status'] == 'COMPLETE'
        finally:
            life.close()
            client.close()
        traces[label], states[label] = trace(summaries[label]['episodes'][0]['db_path'])
    assert traces['uninterrupted'] == traces['restarted']
    for field in ('weights', 'revision', 'rng', 'replay'):
        assert states['uninterrupted']['model'][field] == states['restarted']['model'][field]
    return {'mechanism': 'GREEN', 'same_native_actions_observations_forecasts': True,
            'same_weights_revision_rng_replay': True,
            'real_worker_replaced_after_actions': 1, 'summaries': summaries}


def run(source, output):
    source, output = Path(source), Path(output)
    storage = require_space(output)
    output.mkdir(parents=True, exist_ok=False)
    before = source_hashes()
    base = load_base(source / 'model.json')
    indices = list(range(8)) + list(reversed(range(8)))
    agenda = []
    for index in indices:
        config, goal = make_case(30000 + index)
        agenda.append({'config': config, 'goal': goal, 'budget': 8})
    with (output / 'prerun.json').open('x') as out:
        out.write(canonical({'status': 'EXPOSED_DEV', 'indices': indices, 'modes': ['carry', 'reset', 'frozen'],
            'base_digest': digest(base), 'sources': before, 'budget': PLANNING,
            'overall_budget_per_mode': 128, 'storage': storage}))
    modes = {}
    with tempfile.TemporaryDirectory(prefix='atanor-life-dev-') as temp:
        body_parent = Path(temp)
        for mode in ('carry', 'reset', 'frozen'):
            require_space(output, minimum_bytes=4 * 1024**3)
            cpu, wall = time.process_time(), time.perf_counter()
            client = LocalClient()
            root, body_root = output / mode, body_parent / mode
            with Life(root, body_root, agenda, client, initial_checkpoint=base,
                      overall_budget=128, mode=mode) as life:
                halfway = life.run(max_episodes=8)
                assert halfway['status'] == 'PAUSED', canonical(halfway)
                checkpoint_at_pause = digest(life.checkpoint())
            client = LocalClient()  # New runner/client, same persisted life and actual bodies.
            with Life(root, body_root, agenda, client, initial_checkpoint=base,
                      overall_budget=128, mode=mode) as life:
                assert digest(life.checkpoint()) == checkpoint_at_pause
                final = life.run()
                assert final['status'] == 'COMPLETE', canonical(final)
                checkpoint = life.checkpoint()
            rows = episode_rows(final)
            modes[mode] = {'successes': sum(r['success'] for r in rows),
                'charged_steps': sum(r['charged_steps'] for r in rows), 'rows': rows,
                'first_half_successes': sum(r['success'] for r in rows[:8]),
                'second_half_successes': sum(r['success'] for r in rows[8:]),
                'cpu_seconds': time.process_time() - cpu, 'wall_seconds': time.perf_counter() - wall,
                'model_revision': checkpoint['revision'], 'replay_records': len(checkpoint['replay']),
                'summary': final}
            print(f'continuity DEV {mode} complete', flush=True)
        restart = restart_comparison(output, body_parent, base)
    after = source_hashes()
    assert before == after
    carry, reset = modes['carry'], modes['reset']
    regression = (reset['successes'] - carry['successes'] > 1 or
                  carry['charged_steps'] > 1.25 * reset['charged_steps'])
    report = {'status': 'DEV_REGRESSION' if regression else 'DEV_NO_REGRESSION',
        'capability_claim': False, 'modes': modes, 'restart': restart,
        'sources_before': before, 'sources_after': after,
        'limitations': ['reused DEV cases, same mechanics and single pretrained checkpoint',
            'agenda externally fixed, not self-generated goals',
            'model knowledge carried; body identities remain explicit separate contexts',
            'in-process comparison CPU includes ledger/checkpoint/replay overhead',
            'no-regression is not evidence of positive persistence benefit or general Self']}
    with (output / 'report.json').open('x') as out:
        json.dump(report, out, indent=2)
    with zipfile.ZipFile(output / 'source.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(Path(__file__).parent.rglob('*.py')):
            archive.write(path, path.relative_to(Path(__file__).resolve().parents[2]))
    print(json.dumps({'status': report['status'], 'capability_claim': False,
                      'modes': {k: {f: v[f] for f in ('successes', 'charged_steps', 'cpu_seconds',
                                  'first_half_successes', 'second_half_successes')} for k, v in modes.items()},
                      'restart_mechanism': restart['mechanism']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    arguments = parser.parse_args()
    run(arguments.source, arguments.output)
