"""Development probe (GOAL_STATE step B, fourth try at compounding, a different place): a past life does not touch the
predictor. It changes only WHAT IS TRIED FIRST in a new body. Each action lived in an earlier body leaves a role
coordinate, with no body's words: its pattern (which outcomes stay, copy, are set; how the body answers) and, per
outcome, the input roles that decided it (the argument's own attribute, another argument's, a value's presence). In a
new body an action's own first cases give its pattern; the earlier actions of that pattern say which roles mattered,
weighted by how many distinct bodies showed it (one body: a rumour; several: a schema). Experiments that vary those
roles into never-met values come first. The predictor stays the empty mind's, so wrong cannot rise through the prior.
Measured as learning cost: right rate after k own trials, and the k at which right first reaches 0.95 of what the empty
mind reaches at k=10.  NONE today's chooser  LIFE role-guided  SHUF roles permuted across patterns (control)
Usage: python -m atanor_os.life.role_space_probe one <cache_dir> <target> <seed> <out.json> | sum <dir>
"""
import json
import pickle
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from ..rebuild.bench_predict import judge, train
from ..rebuild.devbench import PRACTICE
from ..rebuild.effects import flat
from ..rebuild.explore import explore
from .schema2_probe import Sig
from .schema3_probe import roles as role_of
from .transfer_probe import BODIES, trained

KS = (0, 1, 2, 3, 5, 10)


def pattern_of(ba, outs):
    return '+'.join(sorted(r for r in (ba._key(o) for o in outs) if not r.endswith('stay')))


def coordinates(eff):
    """-> {pattern: {outcome kind: Counter(roles)}} for every action this mind has cases of."""
    out = defaultdict(lambda: defaultdict(Counter))
    for m in eff.models.values():
        if not m.cases:
            continue
        ba = Sig(m, 0.99, {'by': {}})
        outs = sorted({k for c in m.cases for k in c.y}, key=str)
        pattern = pattern_of(ba, outs)
        for o in outs:
            hyps = ba._fit(o)[0]
            if not hyps:
                continue
            w, R, tab = max(hyps, key=lambda h: h[0])
            out[pattern][ba._key(o)][role_of(R, o)] += 1
    return out


def space(effs):
    """Role space of a life: how many distinct bodies showed each (pattern, outcome kind, roles)."""
    sp = defaultdict(lambda: defaultdict(Counter))
    for eff in effs:
        for pat, by in coordinates(eff).items():
            for kind, rl in by.items():
                for r in rl:
                    sp[pat][kind][r] += 1                   # once per body
    return sp


def shuffled(sp, rng):
    pats = sorted(sp)
    vals = [sp[p] for p in pats]
    rng.shuffle(vals)
    return dict(zip(pats, vals))


def guided(sp):
    """A chooser: unknown predictions first (as today), among them the start that puts a never-met value on a role the
    life says decides this kind of outcome; then confident predictions that do the same (the life asks to test them)."""
    def pick(m, tool, args, before, y):
        ba = Sig(m, 0.99, {'by': {}})
        outs = sorted({k for c in m.cases for k in c.y}, key=str)
        hints = sp.get(pattern_of(ba, outs))
        x = flat(before)
        seen = defaultdict(set)
        for c in m.cases:
            for k, v in c.x.items():
                seen[k].add(v)
        score = 0.0
        if hints:
            for o in outs:
                for rl, nb in hints.get(ba._key(o), {}).items():
                    want = json.loads(rl)
                    own = o[0] if o != ('r',) else None
                    for k, v in x.items():
                        if v in seen[k]:
                            continue
                        r = 'own' if k[0] == own else 'other'
                        if r in want or ('has-' + r) in want:
                            score += nb                        # bodies that agreed
        if y is None:
            return (0, -score)
        return (1, -score) if score > 0 else None
    return pick


def one(d, target, seed, out_f):
    d = Path(d)
    wd = Path(out_f).with_suffix('.w')
    load = lambda b: pickle.loads((d / f'{b}-s{seed}.pkl').read_bytes())
    sp = space(trained(load(b), 10, wd / b) for b in BODIES if b != target)
    c = load(target)
    names = json.loads((Path(c['course']) / c['body'] / 'names.json').read_text(encoding='utf-8'))
    ps = c['eval_seed'] - 100 + PRACTICE
    res = {}
    for name, s in (('NONE', None), ('LIFE', sp), ('SHUF', shuffled(sp, random.Random(seed)))):
        for k in KS:
            eff, _ = train(c['body'], c['course'], slack=1, tiered=True)
            if k:
                explore(eff, c['body'], names, ps, wd / f'{target}-{name}', per_action=k,
                        selector='CHOOSE' if s is None else guided(s))
            r = Counter()
            for w, tool, args, before, truth, _ in c['qs']:
                m = eff.model(tool, args)
                if not m or not m.cases:
                    continue
                r[judge(eff.predict(tool, args, before, reader='BAYES0.99')['outcome'], truth)] += 1
            res[f'{name}:{k}'] = dict(r)
            res[f'{name}:{k}:trials'] = sum(explore.counts.values()) if k else 0
    res['space'] = {p: {k: dict(v) for k, v in by.items()} for p, by in sp.items()}
    Path(out_f).write_text(json.dumps(res), encoding='utf-8')


def summ(d):
    T, N = defaultdict(Counter), defaultdict(int)
    for f in sorted(Path(d).glob('*.json')):
        b = f.stem.split('-')[0]
        for k, v in json.loads(f.read_text(encoding='utf-8')).items():
            if k.endswith(':trials'):
                N[(b, k)] += v
            elif ':' in k:
                T[(b, k)].update(v)
    for b in BODIES:
        print(b)
        for k in KS:
            row = []
            for name in ('NONE', 'LIFE', 'SHUF'):
                c = T[(b, f'{name}:{k}')]
                n = sum(c.values()) or 1
                row.append(f'{name} R {c["right"] / n:.3f} W {c["wrong"] / n:.3f} T {N[(b, f"{name}:{k}:trials")]}')
            print('  k', k, ' | '.join(row))
        c10 = T[(b, 'NONE:10')]
        goal = 0.95 * c10['right'] / (sum(c10.values()) or 1)
        reach = {}
        for name in ('NONE', 'LIFE', 'SHUF'):
            reach[name] = next((k for k in KS if T[(b, f'{name}:{k}')]['right'] / (sum(T[(b, f'{name}:{k}')].values()) or 1) >= goal), None)
        print('  first k reaching', f'{goal:.3f}:', reach)


if __name__ == '__main__':
    if sys.argv[1] == 'one':
        one(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5])
    else:
        summ(sys.argv[2])
