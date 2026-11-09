"""G_SURVIVAL_PLAN.md: lineages. A population of Selves, each living one life (earlier bodies, then a body new to the
lineage) under energy and death; the survivors' genomes (six numbers, metabolism.GENOME) are crossed and mutated, and in
the FULL condition the children also inherit their parents' experiences as READ (source 'read'), kept apart from what
they live. Nothing of the core code differs between individuals.
  Conditions: FULL (genes + memories), GENES (genes only), RANDOM (fresh random genes, empty minds, every generation)
  python -m atanor_os.life.lineage run <out> --seed N --target dye --prior board clime --sessions 4 --target-sessions 4
                                          --n 6 --generations 3 --conditions FULL GENES RANDOM [--jobs 8]
  python -m atanor_os.life.lineage stage <self_dir> <seed> <target> <S> <T> <prior...>    (one stage, one process)
  python -m atanor_os.life.lineage sum <out>
Dev seeds only. Fitness = (alive, stages lived, GOOD on the new body / energy spent there, E left).
"""
import argparse
import json
from collections import Counter
import math
import random
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import host
from .judge import blocks, evaluate
from .metabolism import DEFAULT_GENOME, GENOME, Death

BOUNDS = {'tau': (0.90, 0.999), 'lab_tests': (0, 12), 'per_action': (0, 20), 'E_low': (5.0, 80.0), 'E_high': (20.0, 100.0), 'w_epi': (0.1, 5.0),
          'guide': (0, 1)}
INTS = ('lab_tests', 'per_action', 'guide')


# ------------------------------------------------------------ genomes
def clamp(g):
    out = {}
    for k in GENOME:
        lo, hi = BOUNDS[k]
        v = min(max(g[k], lo), hi)
        out[k] = int(round(v)) if k in INTS else round(v, 4)
    if out['E_high'] <= out['E_low']:
        out['E_high'] = round(min(100.0, out['E_low'] + 10.0), 4)
    return out


def random_genome(rng):
    g = {}
    for k in GENOME:
        lo, hi = BOUNDS[k]
        g[k] = rng.uniform(lo, hi) if k != 'tau' else 1 - 10 ** rng.uniform(math.log10(1 - hi), math.log10(1 - lo))
    return clamp(g)


def mutate(g, rng, sigma=0.2):
    out = dict(g)
    for k in GENOME:
        if rng.random() < 0.5:
            continue
        if k == 'tau':
            miss = (1 - g[k]) * math.exp(rng.gauss(0, sigma * 2))
            out[k] = 1 - miss
        elif k == 'guide':
            out[k] = 1 - g[k]
        elif k in INTS:
            out[k] = g[k] + rng.choice((-2, -1, 1, 2))
        else:
            out[k] = g[k] * math.exp(rng.gauss(0, sigma))
    return clamp(out)


def cross(a, b, rng):
    return clamp({k: (a if rng.random() < 0.5 else b)[k] for k in GENOME})


# ------------------------------------------------------------ one life
def stage(a):
    prior = a[5:]
    target, S, T = a[2], int(a[3]), int(a[4])
    host.schedule = lambda bodies, sessions: blocks(prior, target, S, T)
    try:
        life = host.Life(a[0], int(a[1]), prior + [target], S)
    except Death:
        print('dead')
        return
    try:
        done = life.run_stage()
    except Death:
        life.close()
        print('dead')
        return
    life.close()
    print('over' if done is None else done)


def birth(self_dir, seed, bodies, S, genome, parents=()):
    """A new Self with its genome, and (FULL) its parents' experiences as read, never as lived."""
    self_dir = Path(self_dir)
    self_dir.mkdir(parents=True, exist_ok=True)
    (self_dir / 'self.json').write_text(json.dumps({'id': uuid.uuid4().hex, 'seed': seed, 'bodies': bodies, 'sessions': S, 'genome': genome,
                                                     'parents': [str(p) for p in parents]}), encoding='utf-8')
    if parents:
        items, n, seen = [], 0, set()
        for p in parents:
            f = Path(p) / 'mind' / 'experiences.jsonl'
            if not f.exists():
                continue
            for line in f.read_text(encoding='utf-8').splitlines():
                e = json.loads(line)
                if not e.get('action'):
                    continue                           # what was told is not inherited as testimony
                key = json.dumps([e.get('body'), e['action'], e.get('before'), e.get('after'), (e.get('response') or {}).get('ok')], sort_keys=True, default=str)
                if key in seen:
                    continue                           # the same case through two parents, or through a grandparent, once
                seen.add(key)
                depth = int(e.get('inherited_depth', 0)) + 1
                e = {k: v for k, v in e.items() if k not in ('id', 'intent', 'jseq')}
                e.update(id=f'x{n}', t=n, source='read', inherited_from=Path(p).name, inherited_depth=depth)   # a lineage's memory: read, never lived
                items.append(e)
                n += 1
        (self_dir / 'mind').mkdir(exist_ok=True)
        with open(self_dir / 'mind' / 'experiences.jsonl', 'w', encoding='utf-8') as f:
            for e in items:
                f.write(json.dumps(e, ensure_ascii=False, default=str) + '\n')


def live(self_dir, seed, target, S, T, prior, log):
    """Every stage in a process of its own until the life is over or dead."""
    with open(log, 'a', encoding='utf-8') as lf:
        while True:
            p = subprocess.run([sys.executable, '-m', 'atanor_os.life.lineage', 'stage', str(self_dir), str(seed), target, str(S), str(T), *prior],
                               capture_output=True, text=True, env=None)
            lf.write(p.stdout + p.stderr)
            out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ''
            if p.returncode:
                lf.write(f'\nFAILED rc={p.returncode}\n')
                return 'failed'
            if out in ('over', 'dead'):
                return out


def measure(self_dir, seed, target, out):
    rows = host.Autobiography(Path(self_dir) / 'autobiography.jsonl').rows() if (Path(self_dir) / 'autobiography.jsonl').exists() else []
    dead = (Path(self_dir) / '.dead').exists()
    stages = sum(1 for r in rows if r['kind'] == 'HOST' and r['data'].get('event') == 'stage_begin')
    E = next((r['data']['E'] for r in reversed(rows) if r['kind'] == 'INTEROCEPTION'), None)
    spent, in_target, preds = 0.0, False, 0
    for r in rows:
        if r['kind'] == 'HOST' and r['data'].get('event') == 'stage_begin':
            in_target = r['data'].get('body') == target
        if in_target and r['kind'] == 'INTEROCEPTION' and r['data']['delta'] < 0:
            spent -= r['data']['delta']
        if in_target and r['kind'] == 'PREDICTION':
            preds += 1
    lived = read = 0
    f = Path(self_dir) / 'mind' / 'experiences.jsonl'
    if f.exists():
        for line in f.read_text(encoding='utf-8').splitlines():
            e = json.loads(line)
            if e.get('action'):
                if e.get('source') == 'read':
                    read += 1
                else:
                    lived += 1
    good = None
    if (Path(self_dir) / 'worlds' / target / 'names.json').exists():
        try:
            from ..rebuild.summ_stage4 import GOOD, outcomes
            evaluate(self_dir, seed, target, out)
            c = outcomes(json.loads(Path(out).read_text(encoding='utf-8')), target)
            n = sum(c.values())
            good = sum(c[g] for g in GOOD) / n if n else None
        except Exception as ex:                            # a dead Self may leave a world no evaluator can read
            good = None
            Path(out).with_suffix('.error.txt').write_text(repr(ex), encoding='utf-8')
    cmd = Counter()                                        # the person's own scoring of the Self's work in the new body, every body alike
    tl = Path(self_dir) / 'worlds' / target / 'teacher_log.jsonl'
    if tl.exists():
        for line in tl.read_text(encoding='utf-8').splitlines():
            r = json.loads(line)
            if r.get('activity') == 'command':
                cmd[r.get('outcome')] += 1
    n_cmd = sum(cmd.values())
    good_t = (cmd['success'] + cmd['partial']) / n_cmd if n_cmd else None
    fit = (0 if dead else 1, E or 0.0)                     # setting 5: what nature ranks by, nothing of mine (alive, then what is left)
    return {'dead': dead, 'stages': stages, 'E': E, 'spent_target': round(spent, 3), 'predictions_target': preds, 'good': good,
            'good_teacher': good_t, 'commands_target': n_cmd, 'wrong_target': cmd['wrong'], 'lived': lived, 'read': read, 'fitness': fit}


# ------------------------------------------------------------ generations
def run(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(f'lineage-{a.seed}')
    S, T = a.sessions, a.target_sessions
    pops = {c: [random_genome(rng) for _ in range(a.n)] for c in a.conditions}
    parents = {c: [() for _ in range(a.n)] for c in a.conditions}
    for gen in range(a.generations):
        if a.rotate:                                    # each generation meets a body no ancestor lived: the real new body
            prior, target = [a.rotate[gen]], a.rotate[gen + 1]
        else:
            prior, target = a.prior, a.target
        bodies = prior + [target]
        jobs = []
        for c in a.conditions:
            for i, g in enumerate(pops[c]):
                d = out / c / f'g{gen}' / f'i{i}'
                birth(d, a.seed, bodies, S, g, parents[c][i] if c == 'FULL' else ())
                jobs.append((c, i, d))

        def one(job):
            c, i, d = job
            end = live(d, a.seed, target, S, T, prior, d / 'life.log')
            m = measure(d, a.seed, target, d / f'eval-{c}-g{gen}-i{i}.json')   # a name of its own: the evaluator works under it
            m.update(condition=c, gen=gen, i=i, end=end, genome=pops[c][i], target=target, prior=prior)
            (d / 'measure.json').write_text(json.dumps(m), encoding='utf-8')
            return m
        with ThreadPoolExecutor(a.jobs) as ex:
            ms = list(ex.map(one, jobs))
        (out / f'gen{gen}.json').write_text(json.dumps(ms), encoding='utf-8')
        for c in a.conditions:
            res = sorted((m for m in ms if m['condition'] == c), key=lambda m: m['fitness'], reverse=True)
            print(gen, c, 'alive', sum(not m['dead'] for m in res), '/', len(res), 'best', res[0]['fitness'], flush=True)
            if c == 'RANDOM':
                pops[c] = [random_genome(rng) for _ in range(a.n)]
                continue
            top = res[:max(2, len(res) // 2)]
            kids, kin = [], []
            for _ in range(a.n):
                pa, pb = rng.sample(top, 2)
                kids.append(mutate(cross(pa['genome'], pb['genome'], rng), rng))
                kin.append((out / c / f'g{gen}' / f"i{pa['i']}", out / c / f'g{gen}' / f"i{pb['i']}"))
            pops[c], parents[c] = kids, kin
    summ(out)


def summ(out):
    out = Path(out)
    for f in sorted(out.glob('gen*.json')):
        ms = json.loads(f.read_text(encoding='utf-8'))
        for c in sorted({m['condition'] for m in ms}):
            r = [m for m in ms if m['condition'] == c]
            alive = [m for m in r if not m['dead']]
            good = [m['good'] for m in r if m['good'] is not None]
            gt = [m['good_teacher'] for m in r if m.get('good_teacher') is not None]
            E = [m['E'] or 0 for m in r]
            print(f.stem, r[0].get('target', ''), c, f"alive {len(alive)}/{len(r)}", f"E {sum(E) / len(E):.1f}",
                  f"teacherGOOD {sum(gt) / len(gt):.3f}" if gt else 'teacherGOOD -', f"evalGOOD {sum(good) / len(good):.3f}" if good else 'evalGOOD -',
                  f"spent {sum(m['spent_target'] for m in r) / len(r):.1f}", f"wrong {sum(m.get('wrong_target', 0) for m in r)}",
                  f"guide {sum(m['genome'].get('guide', 0) for m in r)}/{len(r)}",
                  f"read {sum(m['read'] for m in r) / len(r):.0f} lived {sum(m['lived'] for m in r) / len(r):.0f}")


if __name__ == '__main__':
    if sys.argv[1] == 'stage':
        stage(sys.argv[2:])
        sys.exit(0)
    if sys.argv[1] == 'sum':
        summ(sys.argv[2])
        sys.exit(0)
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd')
    ap.add_argument('out')
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--target', default='dye')
    ap.add_argument('--prior', nargs='*', default=['board', 'clime'])
    ap.add_argument('--sessions', type=int, default=4)
    ap.add_argument('--target-sessions', type=int, default=4)
    ap.add_argument('--n', type=int, default=6)
    ap.add_argument('--generations', type=int, default=3)
    ap.add_argument('--conditions', nargs='+', default=['FULL', 'GENES', 'RANDOM'])
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--rotate', nargs='*', default=None, help='bodies in order; generation k lives rotate[k] then meets rotate[k+1]')
    a = ap.parse_args()
    if a.seed not in range(1, 6):
        ap.error('development: seeds 1-5 only')
    run(a)
