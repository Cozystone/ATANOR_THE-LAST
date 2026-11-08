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

PRACTICE = 300
PER_ACTION = 10


def practice(world_dir, mind_dir, body, seed, selector='CHOOSE', per_action=PER_ACTION):
    """world_dir: the course's world folder (its names.json); mind_dir: the learner's mind. -> number of trials."""
    world_dir, mind_dir = Path(world_dir), Path(mind_dir)
    names = json.loads((world_dir / 'names.json').read_text(encoding='utf-8'))
    store = Store(mind_dir / 'experiences.jsonl')
    eff = Effects()
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
    trials = explore(eff, body, names, seed + PRACTICE, work, per_action=per_action, selector=selector, keep=keep)
    shutil.rmtree(work, ignore_errors=True)
    return len(trials)
