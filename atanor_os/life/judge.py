"""Does life compound? (GOAL_STATE step B, development.) One Self lives through earlier bodies, one after the other, then
meets a body it has never met; the same Self without that past (NONE: the same teacher seed, an empty mind) meets it too.
Measured on the new body after k sessions there, alone, on the body's own evaluator; and what the teaching cost.
  python -m atanor_os.life.judge run <out> --seed N --target dye [--prior b ...] [--prior-sessions S] [--ks 3 6 12]
  python -m atanor_os.life.judge stage <self_dir> <seed> <target> <S> <T> <prior...>   (one stage in this process)
  python -m atanor_os.life.judge sum <out>
"""
import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import host
from .host import BODIES


def blocks(prior, target, S, T):
    """Earlier bodies one after the other, each followed by its practice; then the new body; practice at the very end."""
    out = []
    for b in prior:
        out += [{'kind': 'session', 'body': b, 'i': i} for i in range(S)] + [{'kind': 'practice', 'body': b}]
    return out + [{'kind': 'session', 'body': target, 'i': i} for i in range(T)] + [{'kind': 'practice', 'body': target}]


def stage(a):
    prior = a[5:]
    target, S, T = a[2], int(a[3]), int(a[4])
    host.schedule = lambda bodies, sessions: blocks(prior, target, S, T)
    life = host.Life(a[0], int(a[1]), prior + [target], S)
    done = life.run_stage()
    life.close()
    print('over' if done is None else done)


def evaluate(self_dir, seed, target, out):
    mod = __import__(f'atanor_os.eval.{target}_eval', fromlist=['evaluate'])
    return mod.evaluate(Path(self_dir) / 'worlds' / target, 100 + seed, out)


def teaching(self_dir, target):
    f = Path(self_dir) / 'worlds' / target / 'teacher_log.jsonl'
    c = Counter()
    if f.exists():
        for r in map(json.loads, f.read_text(encoding='utf-8').splitlines()):
            c[r.get('activity', '?')] += 1
            for k in ('questions', 'answers', 'asked', 'demos'):
                if isinstance(r.get(k), int):
                    c[k] += r[k]
    return dict(c)


def run(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    T = max(a.ks)
    for name, prior in (('life', [b for b in a.prior if b != a.target]), ('none', [])):
        self_dir = out / f'{a.target}-{name}-s{a.seed}'
        points = {len(prior) * (a.prior_sessions + 1) + k: f'k{k}' for k in a.ks}
        points[len(prior) * (a.prior_sessions + 1) + T + 1] = 'practice'
        n = 0
        while True:
            cmd = [sys.executable, '-m', 'atanor_os.life.judge', 'stage', str(self_dir), str(a.seed), a.target, str(a.prior_sessions), str(T), *prior]
            p = subprocess.run(cmd, capture_output=True, text=True)
            if p.returncode:
                print(p.stderr[-3000:], file=sys.stderr)
                raise SystemExit(f'{name} stage {n} failed')
            if p.stdout.strip().endswith('over'):
                break
            n += 1
            if n in points:
                f = out / f'r-{name}-s{a.seed}-{points[n]}-{a.target}.json'
                subprocess.run([sys.executable, '-c', 'import sys,json;from atanor_os.life.judge import evaluate,teaching;a=sys.argv;'
                                'evaluate(a[1],int(a[2]),a[3],a[4]);r=json.load(open(a[4],encoding="utf-8"));r["teaching"]=teaching(a[1],a[3]);json.dump(r,open(a[4],"w",encoding="utf-8"))',
                                str(self_dir), str(a.seed), a.target, str(f)], check=True, capture_output=True)
    print('done', a.seed)


def summ(d):
    from ..rebuild.summ_stage4 import GOOD, outcomes
    T = defaultdict(Counter)
    C = defaultdict(Counter)
    for f in sorted(Path(d).glob('r-*.json')):
        _, name, seed, point, target = f.stem.split('-')
        r = json.loads(f.read_text(encoding='utf-8'))
        T[(target, name, point)].update(outcomes(r, target))
        C[(target, name, point)].update(r.get('teaching', {}))
    for k in sorted(T):
        c = T[k]
        n = sum(c.values())
        print(*k, 'n', n, 'good %.3f' % (sum(c[g] for g in GOOD) / n if n else 0), dict(c), 'teaching', dict(C[k]))


if __name__ == '__main__':
    if sys.argv[1] == 'stage':
        stage(sys.argv[2:])
    elif sys.argv[1] == 'sum':
        summ(sys.argv[2])
    else:
        ap = argparse.ArgumentParser()
        ap.add_argument('cmd')
        ap.add_argument('out')
        ap.add_argument('--seed', type=int, required=True)
        ap.add_argument('--target', default='dye')
        ap.add_argument('--prior', nargs='*', default=list(BODIES))
        ap.add_argument('--prior-sessions', type=int, default=6)
        ap.add_argument('--ks', nargs='+', type=int, default=[3, 6, 12])
        a = ap.parse_args()
        if a.seed > 5:
            ap.error('development: seeds 1-5 only')
        run(a)
