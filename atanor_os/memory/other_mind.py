"""V_TWO_SELVES_PLAN.md V3: a model of another Self's mind, apart from one's own (a false-belief task on the bodies).
A and B live the same course. At the body's world change (a tool stops, a new one appears) A leaves; B stays and sees
the changed world. B was not always watching A: it saw A witness only a share of the earlier experiences.
For every call after the change B is asked: what does A expect of this call? Truth: A's actual model (everything A
witnessed before leaving). TOM: B answers from a separate model built only from what B saw A witness. EGO: B answers
from its own model (what B itself believes). False-belief items: A's expectation is confident and wrong about the world.
  python -m atanor_os.memory.other_mind <cache_dir> <out.json> --bodies ... --seeds ... [--seen 0.7]
"""
import argparse
import json
import random
from collections import Counter
from pathlib import Path

from . import lobo
from ..rebuild.bench_predict import judge
from ..rebuild.effects import Effects, outputs

READER = 'BAYES0.99'


def mind(exps):
    eff = Effects(slack=1, tiered=True)
    for e in exps:
        eff.observe(e)
    return eff


def expect(eff, e):
    args = e['action']['args']
    m = eff.model(e['action']['tool'], args)
    if m is None or not m.cases:
        return None
    return eff.predict(e['action']['tool'], args, [e['before'].get(a) for a in args], reader=READER)['outcome']


def same(p, q):
    if p is None or q is None:
        return p is None and q is None
    return all(p.get(k) == v for k, v in q.items()) and all(q.get(k) == v for k, v in p.items())


def change_at(exps):
    first = {}
    for i, e in enumerate(exps):
        first.setdefault(e['action']['tool'], i)
    late = [i for t, i in first.items() if i > 0.2 * len(exps)]
    return min(late) if late else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cache')
    ap.add_argument('out')
    ap.add_argument('--bodies', nargs='+', required=True)
    ap.add_argument('--seeds', nargs='+', type=int, required=True)
    ap.add_argument('--seen', type=float, default=0.7)
    a = ap.parse_args()
    lobo.CACHE = a.cache
    rows, tot = [], Counter()
    for body in a.bodies:
        c = Counter()
        for seed in a.seeds:
            if not (Path(a.cache) / f'{body}-s{seed}.pkl').exists():
                continue
            exps = lobo.load(body, seed)[0]
            cut = change_at(exps)
            if cut is None:
                c['no_change'] += 1
                continue
            rng = random.Random(f'tom-{body}-{seed}')
            before = exps[:cut]
            a_mind = mind(before)                                           # what A really knows
            tom = mind([e for e in before if rng.random() < a.seen])          # B's model of A: what B saw A witness
            ego = mind(exps)                                                # B's own mind
            for e in exps[cut:]:
                args = e['action']['args']
                r = e.get('response')
                if r is None:
                    continue
                resp = 'blocked' if r.get('guard') else ('ok' if r.get('ok') else 'failed')
                truth = outputs([e['before'].get(x) for x in args], [e['after'].get(x) for x in args], resp)
                pa, pt, pe = expect(a_mind, e), expect(tom, e), expect(ego, e)
                kind = 'ignorant' if pa is None else ('false_belief' if judge(pa, truth) == 'wrong' else 'true_belief')
                c[f'{kind}:n'] += 1
                c[f'{kind}:TOM'] += same(pt, pa)
                c[f'{kind}:EGO'] += same(pe, pa)
        rows.append({'body': body, **c})
        tot.update(c)
        print(body, dict(c), flush=True)
    for kind in ('false_belief', 'ignorant', 'true_belief'):
        n = tot[f'{kind}:n']
        if n:
            print(f"ALL {kind:13s} n {n:5d}  TOM {tot[f'{kind}:TOM'] / n:.3f}  EGO {tot[f'{kind}:EGO'] / n:.3f}")
    Path(a.out).write_text(json.dumps(rows), encoding='utf-8')


if __name__ == '__main__':
    main()
