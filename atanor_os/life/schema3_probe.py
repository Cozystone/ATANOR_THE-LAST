"""Development probe (GOAL_STATE step B, third of three tries at compounding): a past life carries whole forms of ACTIONS.
A new action's own cases give its pattern (which outcomes stay, copy, are set, how the body answers). Actions of the same
pattern in other bodies say which inputs mattered, by role only (the argument's own attribute or another's, a value or
whether it has one): those explanations get that much more weight. Falls back to the outcome's kind, then to the flat
prior. Controls as in schema_probe. Usage: python -m atanor_os.life.schema3_probe one <cache> <target> <seed> <out> | sum <dir>
"""
import json
import pickle
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from ..rebuild.bench_predict import judge
from .schema2_probe import Sig
from .schema_probe import predict
from .transfer_probe import BODIES, KS, trained


def roles(R, o):
    own = o[0] if o != ('r',) else None
    return json.dumps(sorted(('own' if r[0] == own else 'other') if isinstance(r[0], int) else ('has-own' if r[1] == own else 'has-other') for r in R))


class Whole(Sig):
    def _pattern(self):
        if not hasattr(self, '_pat'):
            outs = sorted({k for c in self.m.cases for k in c.y}, key=str)
            self._pat = '+'.join(sorted(r for r in (Sig._key(self, o) for o in outs) if not r.endswith('stay')))
        return self._pat

    def _entry(self, out):
        by = self.q['by']
        return by.get(self._pattern() + '|' + Sig._key(self, out)) or by.get(Sig._key(self, out))

    def _fit(self, out):
        fresh = out not in self._cache
        res = super()._fit(out)
        e = self._entry(out)
        if fresh and e and e.get('roles'):
            c, m = e['roles'], len(e['roles']) + 1
            N = sum(c.values())
            res[0][:] = [(w * (c.get(roles(R, out), 0) + 0.5) / (N + 0.5 * m) * m, R, tab) for w, R, tab in res[0]]
        return res


def form_of(eff):
    out = defaultdict(lambda: {'size': Counter(), 'k': Counter(), 'roles': Counter()})
    for m in eff.models.values():
        if not m.cases:
            continue
        ba = Whole(m, 0.99, {'by': {}})
        for o in sorted({k for c in m.cases for k in c.y}, key=str):
            hyps = ba._fit(o)[0]
            if not hyps:
                continue
            w, R, tab = max(hyps, key=lambda h: h[0])
            for key in (ba._pattern() + '|' + Sig._key(ba, o), Sig._key(ba, o)):
                e = out[key]
                e['size'][len(R)] += 1
                e['roles'][roles(R, o)] += 1
                for val, const, cop in tab.values():
                    tot = const + sum(cop.values())
                    e['k']['c'] += const / tot
                    for v, p in cop.items():
                        e['k']['s' if v == o else 'o'] += p / tot
    return out


def q_of(forms, rng=None):
    by = {}
    for key in sorted({k for f in forms for k in f}):
        size, kind, rl = Counter(), Counter(), Counter()
        for f in forms:
            if key in f:
                size.update(f[key]['size'])
                kind.update(f[key]['k'])
                rl.update(f[key]['roles'])
        sz = [size[i] + 1 for i in range(4)]
        v = [kind[x] + 1 for x in 'cso']
        by[key] = {'size': [x / sum(sz) for x in sz], 'k': [x / sum(v) for x in v], 'roles': dict(rl)}
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
    forms = [form_of(trained(load(b), 10, wd / b)) for b in BODIES if b != target]    # a life: its practice included
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
                r[judge(predict(eff, tool, args, before, q, cls=Whole), truth)] += 1
            res[f'{name}:{k}'] = dict(r)
    Path(out_f).write_text(json.dumps(res), encoding='utf-8')


if __name__ == '__main__':
    if sys.argv[1] == 'one':
        one(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5])
    else:
        from .schema_probe import summ
        summ(sys.argv[2])
