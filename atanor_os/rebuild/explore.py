"""Self-directed experiments (after the course): ATANOR tries, in lab copies of a practice world of its own body, the
calls whose result it cannot yet predict, and learns from what happens. Nothing is told: a trial is one call and its
observed before / answer / after, the same experience a course call gives. The practice world is the body's own world
generator at a seed apart from every evaluator seed; the world itself is never changed (lab copies only).

Which calls (CHOOSE): every action the course used x every object of the practice world, called as the body's steps
for it; candidates are those whose BAYES prediction is unknown. One trial per round per action, the candidate whose
start differs most from every case of that action (most attributes whose value the action never met), so the first
trials cover the most new values; after each trial the model is refitted. RANDOM (ablation): the same budget, any call,
uniformly. RANDOM with `counts` (matched ablation): per action, as many random trials as CHOOSE made.
Budget: `per_action` trials per action at most; CHOOSE stops earlier when nothing it can call is unknown.
RETEST (selector 'RETEST'): as CHOOSE, and when nothing is unknown, the call whose prediction is confident but whose
start holds values the action never met (most of them first): a confident guess about a new value is tested too.
SUPPORT (selector 'SUPPORT'): as CHOOSE, and when nothing is unknown, the call whose confident prediction rests on no
case of its own answer holding this start's values ('ok' predicted, but no 'ok' case ever had this value), most first.
"""
import random
from pathlib import Path

from .bench_predict import run_lab
from .effects import flat
from ..eval.tutor_life import DRIFT, body_spec, body_targets
from ..repr.run_act6 import worlds

READER = 'BAYES0.99'


def _calls(body, names, h):
    _, acts = body_targets(body, names['seed'])
    spec = body_spec(body)
    out = []
    for a in sorted(int(k) for k in names['act']):
        for o in sorted(h.existing()):
            try:
                tool, args = spec.steps(acts[a], o, h.drift)
            except Exception:
                continue
            if len(set(args)) == len(args):
                out.append((a, tool, list(args)))
    return out


def _newness(m, x):
    seen = {}
    for c in m.cases:
        for k, v in c.x.items():
            seen.setdefault(k, set()).add(v)
    return sum(v not in seen.get(k, ()) for k, v in x.items())


def _unsupported(m, x, y, never_varied=False):
    """How many of this start's values no case with the predicted answer ever held (never_varied: only on attributes
    that had one value in every such case; an attribute already seen to vary under this answer says little)."""
    seen = {}
    for c in m.cases:
        if c.y.get(('r',)) == y.get(('r',)):
            for k, v in c.x.items():
                seen.setdefault(k, set()).add(v)
    return sum(v not in seen.get(k, ()) and (not never_varied or len(seen.get(k, ())) == 1) for k, v in x.items())


def explore(eff, body, names, practice_seed, work, per_action=3, selector='CHOOSE', t0=10 ** 6, counts=None, keep=None):
    """Adds trials to eff (actor 'self'); returns the list of trials (tool, args, before, response, after).
    keep(e): how a trial is learned (default eff.observe; the learner also stores it, practice.py)."""
    work = Path(work)
    drift = [DRIFT[body]]
    trials, t = [], t0
    rng = random.Random(f'explore-{body}-{practice_seed}')
    mks = worlds(body, work / 'practice', practice_seed, drift)
    budget = {}
    for w, mk in enumerate(mks):
        h = mk()
        calls = _calls(body, names, h)
        acts = sorted({a for a, _, _ in calls})
        for _round in range(per_action):
            for a in acts:
                if budget.get(a, 0) >= (per_action if counts is None else counts.get(a, 0)):
                    continue
                cands = []
                for a2, tool, args in calls:
                    if a2 != a:
                        continue
                    m = eff.model(tool, args)
                    if m is None or not m.cases:
                        continue
                    st = h.observe(h.existing())
                    blank = {k: '-' for k in next(iter(st.values()), {})} | {'kind': 'absent'}
                    before = [st.get(x, blank) for x in args]
                    if selector in ('CHOOSE', 'RETEST', 'SUPPORT', 'VARIED'):
                        nw = _newness(m, flat(before))
                        y = eff.predict(tool, args, before, reader=READER)['outcome']
                        if y is None:
                            cands.append((0, -nw, len(cands), tool, args, st))
                        elif selector == 'RETEST' and nw:                  # confident, but about values never met
                            cands.append((1, -nw, len(cands), tool, args, st))
                        elif selector == 'SUPPORT' and _unsupported(m, flat(before), y):   # no case of this answer held them
                            cands.append((1, -_unsupported(m, flat(before), y), len(cands), tool, args, st))
                        elif selector == 'VARIED' and _unsupported(m, flat(before), y, True):   # ... on an attribute that never varied under it
                            cands.append((1, -_unsupported(m, flat(before), y, True), len(cands), tool, args, st))
                    else:
                        cands.append((0, 0, len(cands), tool, args, st))
                if not cands:
                    continue
                if selector in ('CHOOSE', 'RETEST', 'SUPPORT', 'VARIED'):
                    _, _, _, tool, args, st = min(cands)
                else:
                    _, _, _, tool, args, st = rng.choice(cands)
                r, after_obs = run_lab(h, work / 'lab', tool, args)
                if r.get('blocked'):                       # the lab answers blocked as 'blocked'; experiences mark it 'guard'
                    r = dict(r, guard=True)
                t += 1
                blank = {k: '-' for k in next(iter(st.values()), {})} | {'kind': 'absent'}   # as the queries observe
                e = {'t': t, 'actor': 'self', 'action': {'tool': tool, 'args': list(args)},
                     'before': {x: st.get(x, blank) for x in args}, 'after': {x: after_obs.get(x, blank) for x in args},
                     'response': r}
                (keep or eff.observe)(e)
                trials.append((tool, list(args), [st.get(x, blank) for x in args], r, [after_obs.get(x, blank) for x in args]))
                budget[a] = budget.get(a, 0) + 1
    explore.counts = budget
    return trials
