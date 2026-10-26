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


def run(root, seed=1, per_body=15, shared=True, policy='t2'):
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    teachers = {b: Teacher(root / b, seed, drift_from=9, policy=policy, body=b,
                           mind=(root / 'mind') if shared else (root / b / 'mind')) for b in BODIES}
    for i in range(per_body):
        for j, b in enumerate(BODIES):
            teachers[b].session(i, day=i * len(BODIES) + j)      # one session a day, bodies in turn
    for t in teachers.values():
        t.finish()
    return teachers


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--per-body', type=int, default=15)
    ap.add_argument('--separate', action='store_true')
    a = ap.parse_args()
    run(a.root, a.seed, a.per_body, shared=not a.separate)
    print('done', a.root)
