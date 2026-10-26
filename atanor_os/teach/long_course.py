"""A long course across three bodies (evaluator side): one synthetic teacher per body, sessions in turn (board, file,
screen), one simulated day each. With shared=True a single ATANOR mind lives in all three bodies (its claims stay
scoped by body); with shared=False each body has its own mind (the comparison). The teacher chooses what to teach
in each session exactly as in a single-body course (policy t2), through the person's interface only.

Usage: python -m atanor_os.teach.long_course <root> [--seed 1] [--per-body 15] [--separate]
Then evaluate each body with eval/teacher_eval.py on <root>/<body>.
"""
import argparse
import shutil
from pathlib import Path

from .teacher_policy import Teacher

BODIES = ('board', 'fs', 'view')


CHANGE_FROM = {'board': 6, 'fs': 12, 'view': 18}          # each body's tool stops working on a different day


def run(root, seed=1, per_body=15, shared=True, policy='t2', change_from=None, noise=0.0, budget=3, bodies=BODIES):
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    change_from = change_from or {b: 9 for b in bodies}
    teachers = {b: Teacher(root / b, seed, drift_from=change_from[b], policy=policy, body=b, noise=noise, per_session=budget,
                           mind=(root / 'mind') if shared else (root / b / 'mind')) for b in bodies}
    for i in range(per_body):
        for j, b in enumerate(bodies):
            teachers[b].session(i, day=i * len(bodies) + j)      # one session a day, bodies in turn
    for t in teachers.values():
        t.finish()
    return teachers


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--per-body', type=int, default=15)
    ap.add_argument('--separate', action='store_true')
    ap.add_argument('--staggered', action='store_true', help='tool changes on different days per body')
    ap.add_argument('--noise', type=float, default=0.0, help='chance of a human-like slip in pointing or a contrast answer')
    ap.add_argument('--policy', default='t2')
    ap.add_argument('--budget', type=int, default=3, help='teacher activities per session')
    a = ap.parse_args()
    run(a.root, a.seed, a.per_body, shared=not a.separate, change_from=CHANGE_FROM if a.staggered else None, noise=a.noise, policy=a.policy, budget=a.budget)
    print('done', a.root)


def curves(body_dir, block=5):
    """Per body, in blocks of sessions: questions the person answered (lesson + command help, confirmations left out),
    and how many commands given with nobody there succeeded."""
    import json
    rows = [json.loads(l) for l in (Path(body_dir) / 'log.jsonl').read_text(encoding='utf-8').splitlines()]
    out = []
    last = max(r['session'] for r in rows)
    for lo in range(1, last + 1, block):
        b = [r for r in rows if lo <= r['session'] < lo + block]
        q = sum(v for r in b if r['event'] in ('lesson', 'command', 'name') for k, v in (r.get('help') or {}).items() if k != 'confirm')
        alone = [r for r in b if r['event'] == 'command' and r.get('alone') and not r.get('recalled')]
        out.append({'sessions': f'{lo}-{min(lo + block - 1, last)}', 'questions': q, 'lessons': sum(r['event'] == 'lesson' for r in b),
                    'alone': f"{sum(r['outcome'] == 'success' for r in alone)}/{len(alone)}"})
    return out
