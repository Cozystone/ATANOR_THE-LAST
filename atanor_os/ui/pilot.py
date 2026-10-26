"""A scripted pilot of the real-person interface (evaluator side). It is NOT a real person and its results are never
reported as such: everything it causes is recorded with source 'pilot'. It answers the same questions a person
answers on the screen (point, contrast, demo, confirm, names), through the same Session and queue, over simulated days,
to find faults in the interface path before real sessions. Its answers come from the evaluator's own meaning table
(teach.tutor.BoardSpec), as the program tutor's do.

Usage: python -m atanor_os.ui.pilot <sandbox_dir> [--seed 7] [--sessions 15]
"""
import argparse
import datetime
import json
import random
import shutil
import time
from pathlib import Path

from ..eval.en_probe import todo
from ..eval.tutor_life import english, targets
from ..teach.tutor import BoardSpec, Tutor, symbols
from .teach_server import Session

DAYS = [0, 0, 1, 2, 2, 3, 5, 6, 6, 8, 9, 11, 13, 14, 16, 18, 20, 21, 23, 25, 27, 28, 30, 32, 33, 35, 37, 38, 40, 42]


class Clock:
    def __init__(self, start):
        self.t = start

    def __call__(self):
        return self.t


def drive(sess, tut, names, timeout=30, noise=0.0, rng=None, pointer=None):
    """Answer the job's questions until it ends. noise: the chance that a pointing includes a card not meant, or that a
    contrast answer is the wrong one (people make such slips); confirmations are always honest."""
    t0 = time.time()
    slips = sess.state.setdefault('pilot_slips', {'point': 0, 'contrast': 0})
    while sess.job.is_alive():
        p = sess.person.pending
        if p is None:
            time.sleep(0.005)
            if time.time() - t0 > timeout:
                raise TimeoutError('job stuck')
            continue
        k = p['kind']
        if k == 'point':
            pts = pointer(tut) if pointer else tut.point()      # a teacher may choose the most informative cards
            others = sorted(set(tut.before) - set(tut.truth) - set(pts))
            others = [o for o in others if tut.before[o].get('kind') in ('card', 'file')]
            if noise and others and rng.random() < noise:
                pts = pts[:1] + [rng.choice(others)]
                slips['point'] += 1
            ans = {'objects': pts}
        elif k == 'contrast':
            yes = tut.contrast(p['object'])
            if noise and rng.random() < noise:
                yes = not yes
                slips['contrast'] += 1
            ans = {'yes': yes}
        elif k == 'demo':
            st = tut.home.observe(tut.home.existing())
            rest = [o for o in tut.truth if not tut.spec.shows(tut.act, o, st)] or tut.truth
            if p.get('error') and len(rest) > 1:           # the last one did not work: show it on another object
                rest = [x for x in rest if x != getattr(tut, '_last_demo', None)] or rest
            o = tut.rng.choice(rest)
            tut._last_demo = o
            tool, args = tut.spec.steps(tut.act, o, getattr(tut.home, 'drift', ()))
            ans = {'tool': tool, 'args': list(args), 'object': o}
        elif k == 'show':                                  # is this what was meant? (honest, like every confirmation)
            ans = {'ok': set(p['objects']) == set(tut.truth)}
        elif k in ('confirm', 'judge'):
            ok = tut.judge()
            acted = set(p.get('acted') or [])
            wrong_cards = bool(acted - set(tut.truth)) or not acted   # acted on cards not meant, or on none of them
            ans = {'ok': ok, 'reason': None if ok else ('cards' if wrong_cards else 'result')}
        elif k == 'name':
            ans = names
        else:
            raise ValueError(k)
        sess.person.answers.put(ans)
        while sess.person.pending is p:
            time.sleep(0.005)
    sess.job.join()


def run(root, seed=7, n_sessions=15, noise=0.0, drift_from=None, source='pilot'):
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    clock = Clock(datetime.datetime(2026, 11, 1, 10, 0))
    sess = Session(root, seed=seed, source=source, clock=clock)
    sels, acts = targets(seed)
    sym = symbols(seed)
    rng = random.Random(f'pilot-{seed}')
    nrng = random.Random(f'pilot-noise-{seed}')
    tut = Tutor(sess.home, BoardSpec, f'pilot-{seed}')
    taught, sym_named, en_named = [], set(), set()

    def feasible(s, a):
        tut.start(sels[s], acts[a])
        return bool(todo(BoardSpec, sess.home, tut, acts[a]))

    def lesson(s, a):
        tut.start(sels[s], acts[a])
        sess.start('teach')
        drive(sess, tut, {'selection': sym[s], 'action': sym[20 + a]}, noise=noise, rng=nrng)
        last = json.loads((root / 'log.jsonl').read_text(encoding='utf-8').splitlines()[-1])
        if last.get('event') == 'lesson' and last.get('named'):   # the pilot uses only names it actually gave
            taught.append((s, a))
            sym_named.update({('s', s), ('a', a)})

    def command(s, a, lang, alone):
        tut.start(sels[s], acts[a])
        words = [sym[20 + a], sym[s]] if lang == 'sym' else english('act', acts[a])[:1] + english('sel', sels[s]) + english('act', acts[a])[1:]
        sess.start('command', text=' '.join(words), alone=alone)
        drive(sess, tut, {}, noise=noise, rng=nrng)
        last = json.loads((root / 'log.jsonl').read_text(encoding='utf-8').splitlines()[-1])
        if not alone and last.get('why') == 'needs recheck' and feasible(s, a):
            lesson(s, a)                                   # asked to teach again, the person does
        return sess  # outcome is in the log

    for i in range(n_sessions):
        clock.t = datetime.datetime(2026, 11, 1, 10, 0) + datetime.timedelta(days=DAYS[i], minutes=i)
        if i:
            sess.new_session()
        if drift_from is not None and i >= drift_from:
            sess.home.drift = frozenset(['lodge_retired'])     # the world changes: one tool stops working
        pairs = [(s, a) for s in range(len(sels)) for a in range(len(acts))]
        rng.shuffle(pairs)
        if i < 3:                                          # first sessions: lessons with symbols
            for s, a in [p for p in pairs if feasible(*p)][:2]:
                lesson(s, a)
            continue
        if i in (7, 9):                                    # later: English phrases for things already shared
            for s, a in [p for p in taught if ('en', p) not in en_named][:2]:
                if feasible(s, a):
                    tut.start(sels[s], acts[a])
                    sess.start('name', part='selection', phrase=' '.join(english('sel', sels[s])))
                    drive(sess, tut, {}, noise=noise, rng=nrng)
                    tut.start(sels[s], acts[a])
                    sess.start('name', part='action', phrase=' '.join(english('act', acts[a])))
                    drive(sess, tut, {}, noise=noise, rng=nrng)
                    en_named.add(('en', (s, a)))
        named_s = {x for k, x in sym_named if k == 's'}
        named_a = {x for k, x in sym_named if k == 'a'}
        cands = [p for p in pairs if p[0] in named_s and p[1] in named_a and feasible(*p)]
        en_pairs = [p for p in cands if any(('en', q) in en_named and q[0] == p[0] for q in taught)
                    and any(('en', q) in en_named and q[1] == p[1] for q in taught)]
        for j, (s, a) in enumerate(cands[:4]):
            lang = 'en' if en_pairs and j % 2 and i > 9 else 'sym'
            if lang == 'en':
                s, a = en_pairs[j % len(en_pairs)]
                if not feasible(s, a):
                    continue
            command(s, a, lang, alone=(j % 2 == 0))
    write_names(root, seed, {('s', x) for k, x in sym_named if k == 's'} | {('a', x) for k, x in sym_named if k == 'a'},
                {q for _, q in en_named}, sym)
    return sess


def write_names(root, seed, named, en_pairs, sym, body='board'):
    """What the teaching side meant by each name it gave (read only by the evaluator, never by the learner)."""
    out = {'seed': seed, 'body': body, 'sel': {str(x): sym[x] for k, x in named if k == 's'}, 'act': {str(x): sym[20 + x] for k, x in named if k == 'a'},
           'en_sel': sorted({s for s, _ in en_pairs}), 'en_act': sorted({a for _, a in en_pairs})}
    (Path(root) / 'names.json').write_text(json.dumps(out, indent=1), encoding='utf-8')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--sessions', type=int, default=15)
    ap.add_argument('--noise', type=float, default=0.0)
    ap.add_argument('--drift-from', type=int, default=None)
    a = ap.parse_args()
    sess = run(a.root, a.seed, a.sessions, a.noise, a.drift_from)
    sess.save()
    print('slips', sess.state.get('pilot_slips'))
    print('done', a.root)
