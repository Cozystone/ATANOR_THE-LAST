"""Practice after a course (EXPLORE_PLAN.md, next stage): the learner's own experiments in lab copies of a practice world
of its body (explore.py), kept in its experience store like every other call, with actor 'self'. Nothing is told: each
trial is one call's observed before / answer / after. The practice world is the body's world generator at a seed apart
from every evaluator seed (course seed + 300); the world itself is never changed.
"""
import json
import shutil
from pathlib import Path

from .effects import Effects
from .experience import Store, experience
from .explore import explore
from ..life import metabolism

PRACTICE = 300
PER_ACTION = 10


def practice(world_dir, mind_dir, body, seed, selector='CHOOSE', per_action=PER_ACTION):
    """world_dir: the course's world folder (its names.json); mind_dir: the learner's mind. -> number of trials."""
    world_dir, mind_dir = Path(world_dir), Path(mind_dir)
    names = json.loads((world_dir / 'names.json').read_text(encoding='utf-8'))
    store = Store(mind_dir / 'experiences.jsonl')
    eff = Effects()
    eff.body = body                                    # the mind may have lived in other bodies too; this practice is in this one
    for e in store.items:
        if e.get('action'):
            eff.observe(e)

    def keep(e):
        r = e['response']
        x = experience(body=body, source='self', actor='self',
                       action={'tool': e['action']['tool'], 'args': list(e['action']['args']), 'granted': None},
                       executed=not r.get('guard') and r.get('error') != 'invalid',
                       response={'ok': bool(r.get('ok')), 'error': r.get('error'), 'guard': 'blocked' if r.get('guard') else None},
                       before=e['before'], after=e['after'], unobserved=['granted', 'later'])
        x = store.add({**x, 't': len(store.items)})
        eff.observe(x)

    work = mind_dir / f'practice-{body}'
    m = metabolism.CURRENT
    if m is not None:                                   # in a life: the genome's budget, and each trial must be worth its price
        per_action = int(m.g['per_action'])

        def gated(model, tool, args, before, y):
            if y is not None or not m.allow(metabolism.PRICES['SELF_TRIAL'], True):
                return None
            return (0, 0)
        selector = gated
    trials = explore(eff, body, names, seed + PRACTICE, work, per_action=per_action, selector=selector, keep=keep)
    shutil.rmtree(work, ignore_errors=True)
    practice.live = eff                                # the models as learned here (life/host.py checks them against the disk)
    return len(trials)
