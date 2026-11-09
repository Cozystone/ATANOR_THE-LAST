"""Development probe (GOAL_STATE step B, second of three tries at compounding): the form a past life carries is kept per
KIND of action outcome, and a new body's action is matched to a kind by what its own cases show: one argument or several,
and whether this outcome is the body's answer (one answer seen or several), stayed as it was, took another input's value,
or took some other value. No body's words. Controls as in schema_probe.
Usage: python -m atanor_os.life.schema2_probe one <cache_dir> <target> <seed> <out.json> | sum <dir>
"""
import json
import pickle
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from ..rebuild.bench_predict import judge
from .schema_probe import Schema, predict
from .transfer_probe import BODIES, KS, trained


class Sig(Schema):
    def _key(self, out):
        cs = [c for c in self.m.cases if out in c.y]
        several = len({k[0] for c in self.m.cases for k in c.x if isinstance(k[0], int)}) > 1
        if out == ('r',):
            role = 'answers' if len({c.y[out] for c in cs}) > 1 else 'answer'
        elif all(c.y[out] == c.x.get(out, '-') for c in cs):
            role = 'stay'
        else:
            moved = [c for c in cs if c.y[out] != c.x.get(out, '-')]
            inputs = set.intersection(*[{k for k, v in c.x.items() if v == c.y[out] and k != out} for c in moved])
            role = 'copy' if inputs else 'set'
        return f'{several}:{role}'

    def _entry(self, out):
        return self.q['by'].get(self._key(out))

    def _kind(self, out):
        e = self._entry(out)
        return tuple(e['k']) if e else (0.5, None, 0.5)

    def _size(self, out):
        e = self._entry(out)
        return e['size'] if e else [0.25] * 4


def form_of(eff):
    out = defaultdict(lambda: {'size': Counter(), 'k': Counter()})
    for m in eff.models.values():
        if not m.cases:
            continue
        ba = Sig(m, 0.99, {'by': {}})
        for o in sorted({k for c in m.cases for k in c.y}, key=str):
            hyps = ba._fit(o)[0]
            if not hyps:
                continue
            w, R, tab = max(hyps, key=lambda h: h[0])
            e = out[ba._key(o)]
            e['size'][len(R)] += 1
            for val, const, cop in tab.values():
                tot = const + sum(cop.values())
                e['k']['c'] += const / tot
                for v, p in cop.items():
                    e['k']['s' if v == o else 'o'] += p / tot
    return out


def q_of(forms, rng=None):
    all_keys = {k for f in forms for k in f}
    by = {}
    for key in sorted(all_keys):
        size, kind = Counter(), Counter()
        for f in forms:
            if key in f:
                size.update(f[key]['size'])
                kind.update(f[key]['k'])
        sz = [size[i] + 1 for i in range(4)]
        v = [kind[x] + 1 for x in 'cso']
        by[key] = {'size': [x / sum(sz) for x in sz], 'k': [x / sum(v) for x in v]}
    if rng:
        keys = sorted(by)
        vals = [by[k] for k in keys]
        rng.shuffle(vals)
        by = dict(zip(keys, vals))
    return {'by': by}


def one(d, target, seed, out_f):
    d = Path(d)
    wd = Path(out_f).with_suffix('.w')
    load = lambda b: pickle.loads((d / f'{b}-s{seed}.pkl').read_bytes())
    forms = [form_of(trained(load(b), 0, wd / b)) for b in BODIES if b != target]
    c = load(target)
    qs = {'NONE': {'by': {}}, 'LIFE': q_of(forms), 'SHUF': q_of(forms, random.Random(seed))}
    res = {}
    for k in KS:
        eff = trained(c, k, wd / target)
        for name, q in qs.items():
            r = Counter()
            for w, tool, args, before, truth, _ in c['qs']:
                if not eff.model(tool, args) or not eff.model(tool, args).cases:
                    continue
                r[judge(predict(eff, tool, args, before, q, cls=Sig), truth)] += 1
            res[f'{name}:{k}'] = dict(r)
    res['q'] = qs['LIFE']
    Path(out_f).write_text(json.dumps(res), encoding='utf-8')


def summ(d):
    from .schema_probe import summ as s
    s(d)


if __name__ == '__main__':
    if sys.argv[1] == 'one':
        one(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5])
    else:
        summ(sys.argv[2])
