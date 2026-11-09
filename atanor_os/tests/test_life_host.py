"""One life (atanor_os/life): the record, body-qualified actions, hard kills, restarts. Dev seed 1 only. No learner scores."""
import json
import os
import random
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import pytest

from atanor_os.life import autobiography
from atanor_os.life.autobiography import Autobiography, ChainBroken
from atanor_os.life.host import Life
from atanor_os.rebuild.effects import Effects
from atanor_os.rebuild.experience import Store, experience
from atanor_os.rebuild.learner import rebuild

ROOT = Path(__file__).resolve().parents[2]
ENV = {**os.environ, 'PYTHONPATH': str(ROOT)}
KILLS = 34
POINTS = ['after:ACTION_INTENT', 'before:ACTION_RESULT', 'after:ACTION_RESULT', 'after:OBSERVATION', 'after:SELF_TRIAL', 'after:TESTIMONY',
          'after:PREDICTION', 'before:HOST']


def host_args(d, sessions, seed=1):
    return [str(d), '--seed', str(seed), '--sessions', str(sessions)]


def one_stage(d, sessions, kill=None, after=None):
    """A process lives the next stage; kill: it ends itself at that record; after: it is killed from outside that many seconds in."""
    base = [sys.executable, '-m', 'atanor_os.tests.life_kill'] if kill else [sys.executable, '-m', 'atanor_os.life.run']
    p = subprocess.Popen(base + host_args(d, sessions) + ['--one-stage'], cwd=ROOT, env={**ENV, 'LIFE_KILL': kill or ''},
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    t0 = time.time()
    while after is not None and p.poll() is None and time.time() - t0 < after:
        time.sleep(0.01)
    if after is not None and p.poll() is None:
        p.kill()                                           # TerminateProcess
    err = p.communicate()[1]
    assert 'Traceback' not in err, err
    return p.returncode


def records(d, kind=None, event=None):
    rows = autobiography.read(Path(d) / 'autobiography.jsonl')
    return [r for r in rows if (kind is None or r['kind'] == kind) and (event is None or r['data'].get('event') == event)]


def verify_life(d, kills):
    """Everything the life must be after any number of kills; -> figures."""
    rows = records(d)                                      # read() checks the whole chain
    me = json.loads((Path(d) / 'self.json').read_text(encoding='utf-8'))['id']
    starts = records(d, 'HOST', 'process_start')
    assert {r['data']['self_id'] for r in starts} == {me}
    intents = {r['seq']: r['data'] for r in rows if r['kind'] == 'ACTION_INTENT'}
    results = Counter(r['data']['intent'] for r in rows if r['kind'] == 'ACTION_RESULT')
    recon = Counter(r['data']['reconciles'] for r in rows if 'reconciles' in r['data'])
    assert all(v == 1 for v in results.values()) and all(v == 1 for v in recon.values())
    assert not (set(results) & set(recon)), 'an action both completed and in doubt'
    assert set(results) | set(recon) == set(intents), 'an intent with neither result nor reconciliation'
    # the journal says an action was made once: the bodies that keep their own log say the same, independently
    made = Counter()
    for b in ('desk', 'clime', 'dye'):
        log = Path(d) / 'worlds' / b / b / 'world_log.jsonl'
        if log.exists():
            for l in log.read_text(encoding='utf-8').splitlines():
                w = json.loads(l)
                if w.get('actor') == 'learner' and w.get('event') in ('act', 'invalid', 'duplicate_prevented'):
                    made[(b, w['tool'], tuple(w['args']))] += 1
    intended = Counter((i['body'], i['tool'], tuple(i['args'])) for i in intents.values())
    completed = Counter((intents[s]['body'], intents[s]['tool'], tuple(intents[s]['args'])) for s in results)
    assert all(made[k] <= intended[k] for k in made), 'the body did something no intent is on record for'
    assert all(k[0] not in ('desk', 'clime', 'dye') or made[k] >= completed[k] for k in completed)
    # an in-doubt action is not made again: the stage it was in is over, so it cannot be in its own stage's later calls
    stage_of, cur = {}, None
    for r in rows:
        if r['data'].get('event') == 'stage_begin':
            cur = r['data']['stage']
        if r['kind'] == 'ACTION_INTENT':
            stage_of[r['seq']] = cur
    for s in recon:
        i = intents[s]
        later = [t for t, j in intents.items() if t > s and (j['body'], j['tool'], j['args']) == (i['body'], i['tool'], i['args']) and stage_of[t] == stage_of[s]]
        assert not later, f'in-doubt action {s} issued again in its own stage'
    # no experience lost for any completed result; a found change is not an effect
    items = Store(Path(d) / 'mind' / 'experiences.jsonl').items
    have = Counter(e.get('intent') for e in items if e.get('intent') is not None)
    assert have == Counter(results.keys()), 'a completed result has no experience (or two)'
    jseq = Counter(e.get('jseq') for e in items if e.get('jseq') is not None)
    carried = [r['seq'] for r in rows if 'experience' in r['data']]
    assert sorted(jseq) == sorted(carried) and all(v == 1 for v in jseq.values())
    assert [e['id'] for e in items] == [f'x{i}' for i in range(len(items))]
    outside = [e for e in items if e.get('actor') == 'outside']
    assert all(e['action'] is None for e in outside) and all(e.get('action') is None for e in items if e.get('source') == 're-observation')
    # stages in order, each once; a restart check on every start
    begun = [r['data']['stage'] for r in records(d, 'HOST', 'stage_begin')]
    assert begun == sorted(set(begun))
    assert len(records(d, 'HOST', 'restart_check')) >= len(starts) - kills   # (a kill can come before that step)
    assert all(r['data']['same'] for r in records(d, 'HOST', 'restart_check'))
    # the models a rebuild from disk gives are the last checkpoint's
    last = records(d, 'HOST', 'checkpoint')[-1]['data']
    eff, goals = rebuild(items)
    if last['experiences'] == len(items):
        assert (eff.digest(), goals.digest()) == (last['effects'], last['goals'])
    changed = sum(1 for r in rows if 'reconciles' in r['data'] and r['data'].get('changed'))
    return {'records': len(rows), 'processes': len(starts), 'stages_begun': len(begun), 'interrupted': len(records(d, 'HOST', 'stage_interrupted')),
            'intents': len(intents), 'results': len(results), 'in_doubt': len(recon), 'in_doubt_found_changed': changed, 'experiences': len(items),
            'outside_found': len(outside), 'final_equal': last['experiences'] == len(items)}


# ---------------------------------------------------------------- the record
def test_chain_detects_alteration_and_survives_a_torn_tail(tmp_path):
    p = tmp_path / 'a.jsonl'
    j = Autobiography(p)
    for k in range(5):
        j.append('OBSERVATION', n=k)
    j.close()
    with open(p, 'ab') as f:                               # a kill in the middle of a line
        f.write(b'{"seq": 5, "kind": "OBS')
    assert len(autobiography.read(p)) == 5
    j = Autobiography(p)
    assert j.append('PREDICTION', n=5) == 5
    j.close()
    assert [r['seq'] for r in autobiography.read(p)] == list(range(6))
    lines = p.read_text(encoding='utf-8').splitlines()
    lines[2] = lines[2].replace('"n": 2', '"n": 9')
    p.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    with pytest.raises(ChainBroken):
        autobiography.read(p)


# ---------------------------------------------------------------- action identity
def test_two_bodies_with_the_same_tool_never_merge():
    eff = Effects()
    def ex(body, t, res, after):
        eff.observe({**experience(body=body, actor='learner', action={'tool': 'seal', 'args': ['x1', 'p1'], 'granted': None},
                                  response={'ok': res == 'ok', 'error': None, 'guard': None},
                                  before={'x1': {'kind': 'k', 's': 'open'}, 'p1': {'kind': 'p', 's': '-'}},
                                  after={'x1': {'kind': 'k', 's': after}, 'p1': {'kind': 'p', 's': '-'}}), 't': t})
    for t in range(4):
        ex('one', t, 'ok', 'shut')
    for t in range(4, 8):
        ex('two', t, 'failed', 'open')
    keys = sorted(eff.models, key=str)
    assert [k[0] for k in keys] == ['one', 'two'] and all(len(m.cases) == 4 for m in eff.models.values())
    assert eff.model('seal', ['x1', 'p1'], body='one') is not eff.model('seal', ['x1', 'p1'], body='two')
    assert all(c.y[('r',)] == 'ok' for c in eff.model('seal', ['x1', 'p1'], body='one').cases)
    assert all(c.y[('r',)] == 'failed' for c in eff.model('seal', ['x1', 'p1'], body='two').cases)
    with pytest.raises(ValueError):
        eff.model('seal', ['x1', 'p1'])                    # two bodies: a query must say which one
    eff.body = 'two'
    assert eff.model('seal', ['x1', 'p1']) is eff.model('seal', ['x1', 'p1'], body='two')


def test_two_bodies_do_not_share_constant_arguments():
    eff = Effects()
    def ex(body, a, t, changes):
        eff.observe({**experience(body=body, actor='learner', action={'tool': 'put', 'args': [a, 'p'], 'granted': None},
                                  response={'ok': True, 'error': None, 'guard': None}, before={a: {'s': 'a'}, 'p': {'s': 'q'}},
                                  after={a: {'s': 'b'}, 'p': {'s': 'r' if changes else 'q'}}), 't': t})
    for t, a in enumerate(('a1', 'a2', 'a3')):
        ex('steady', a, t, False)                          # 'p' never changes here: a constant of this body's action
    for t, a in enumerate(('a1', 'a2')):
        ex('moving', a, 10 + t, True)                      # in the other body the same name changes
    assert eff.constants('steady') == {'p'} and eff.constants('moving') == frozenset()


def test_single_body_runs_need_no_body_named():
    eff = Effects()
    eff.observe({**experience(body='fs', actor='learner', action={'tool': 'stamp', 'args': ['f1'], 'granted': None},
                              response={'ok': True, 'error': None, 'guard': None}, before={'f1': {'s': 'a'}}, after={'f1': {'s': 'b'}}), 't': 0})
    assert eff.model('stamp', ['f1']).key == ('fs', 'stamp', 1, ())


# ---------------------------------------------------------------- one life
def test_a_new_identity_is_never_made_and_the_schedule_does_not_change(tmp_path):
    d = tmp_path / 'self'
    life = Life(d, 1, ['board'], 1)
    life.close()
    me = json.loads((d / 'self.json').read_text(encoding='utf-8'))['id']
    with pytest.raises(ValueError):
        Life(d, 2, ['board'], 1)
    life = Life(d, 1, ['board'], 1)
    assert json.loads((d / 'self.json').read_text(encoding='utf-8'))['id'] == me
    life.close()
    (d / 'self.json').unlink()
    with pytest.raises(ValueError):
        Life(d, 1, ['board'], 1)                           # the autobiography is there; a new identity is not made for it


def test_altered_experiences_are_refused_at_restart(tmp_path):
    d = tmp_path / 'self'
    assert one_stage(d, 1) == 0
    assert one_stage(d, 1) == 0
    p = d / 'mind' / 'experiences.jsonl'
    rows = p.read_text(encoding='utf-8').splitlines()
    assert rows, 'the first stages should have left experiences'
    e = json.loads(rows[0])
    e['after'] = {k: {**v, 'mark': 'altered'} for k, v in e['after'].items()}
    p.write_text('\n'.join([json.dumps(e)] + rows[1:]) + '\n', encoding='utf-8')
    r = subprocess.run([sys.executable, '-m', 'atanor_os.life.run'] + host_args(d, 1) + ['--one-stage'], cwd=ROOT, env=ENV, capture_output=True, text=True)
    assert r.returncode != 0 and 'differ from checkpoint' in r.stderr


def test_hard_kills_at_randomised_points(tmp_path):
    d = tmp_path / 'self'
    rng = random.Random(1)
    sessions = 9                                           # 9 x 6 + 6 practice stages: every kill can close a different stage
    last = sessions * 6 + 5
    kills, at = 0, Counter()
    while kills < KILLS:
        cps = records(d, 'HOST', 'stage_begin')
        assert not cps or cps[-1]['data']['stage'] < last, f'the life ended after {kills} kills'
        if rng.random() < 0.5:                             # at an exact point of the record
            kind = rng.choice(POINTS)
            kill = f'{kind}:{rng.randint(1, 3)}'
            rc = one_stage(d, sessions, kill=kill)
            killed = rc != 0
            at[kind] += killed
        else:                                              # from outside, at a random moment
            rc = one_stage(d, sessions, after=rng.uniform(0.2, 1.8))
            killed = rc != 0
            at['outside'] += killed
        kills += killed
    assert sum(at.values()) >= 30
    while one_stage(d, sessions) == 0 and records(d, 'HOST', 'checkpoint')[-1]['data']['stage'] < last:
        pass
    assert records(d, 'HOST', 'checkpoint')[-1]['data']['stage'] == last
    fig = verify_life(d, kills)
    assert fig['final_equal'] and fig['in_doubt'] >= 5 and 1 <= fig['in_doubt_found_changed'] < fig['in_doubt']
    assert fig['outside_found'] == fig['in_doubt_found_changed']                 # a found change is filed as nothing more
    print('\nKILLS', kills, dict(at), fig)


def test_one_life_through_six_bodies_restarted_every_stage(tmp_path):
    d = tmp_path / 'self'
    r = subprocess.run([sys.executable, '-m', 'atanor_os.life.run'] + host_args(d, 2) + ['--until-stage', '3'], cwd=ROOT, env=ENV, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert [x['data']['stage'] for x in records(d, 'HOST', 'checkpoint')] == [0, 1, 2]
    r = subprocess.run([sys.executable, '-m', 'atanor_os.life.run'] + host_args(d, 2), cwd=ROOT, env=ENV, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    cps = records(d, 'HOST', 'checkpoint')
    assert [x['data']['stage'] for x in cps] == list(range(18))          # 2 x 6 sessions + 6 practices, each exactly once
    assert all(x['data']['live_compared'] for x in cps[:12])              # every session: live models == rebuilt from disk
    assert sorted({x['data']['body'] for x in records(d, 'HOST', 'stage_begin')}) == sorted(['board', 'fs', 'view', 'desk', 'clime', 'dye'])
    pids = [x['data']['pid'] for x in records(d, 'HOST', 'process_start')]
    assert len(set(pids)) >= 19                                           # a new process for every stage
    fig = verify_life(d, 0)
    assert fig['final_equal'] and fig['in_doubt'] == 0 and fig['interrupted'] == 0 and fig['intents'] == fig['results'] > 0
    print('\nE2E', fig, 'processes', len(pids))
