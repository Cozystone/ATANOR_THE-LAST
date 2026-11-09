"""H_LEARNED_MEMORY_PLAN.md, final check: sealed worlds written by a separate agent (their rules never read here), run once.
A world's module gives  WORLDS  and  data(world, seed) -> {'course': [exp], 'queries': [exp]},
exp = {'tool', 'args', 'before': {id: {attr: value}}, 'after': {...}, 'ok': bool}.
  EMPTY   the symbolic mind from the course alone
  HYBRID  symbolic, then the frozen reader on its unknowns (k examples from the same course, tau, votes: all frozen before)
  READER  the reader alone at tau 0 (reported, not judged)
  PRIOR   the counted priors alone, no learned model (reported, not judged: what the learning adds to)
  python -m atanor_os.memory.final_heldout <worlds.py> <reader.pt> <out_dir> --tau T --votes V [--k 10] [--seeds 1 2 3]
"""
import argparse
import importlib.util
import json
import random
from collections import Counter
from pathlib import Path

import torch

from ..rebuild.bench_predict import judge
from ..rebuild.effects import Effects, outputs
from .episodic import by_tool
from .hybrid import ask, prior_only, reader
from .relational import Scene


def load_module(path):
    spec = importlib.util.spec_from_file_location('sealed_worlds', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def world_run(mod, world, seed, model, device, k, tau, votes):
    d = mod.data(world, seed)
    eff = Effects(slack=1, tiered=True)
    scenes = []
    for t, e in enumerate(d['course']):
        eff.observe({'t': t, 'body': world, 'source': 'program', 'actor': 'teacher', 'action': {'tool': e['tool'], 'args': list(e['args'])},
                     'before': e['before'], 'after': e['after'], 'response': {'ok': bool(e['ok']), 'guard': None}})
        scenes.append(Scene(world, e['tool'], e['args'], e['before'], e['after'], 'ok' if e['ok'] else 'failed'))
    sym, qs = [], []
    for e in d['queries']:
        args = list(e['args'])
        before = [e['before'][a] for a in args]
        after = [e['after'][a] for a in args]
        truth = outputs(before, after, 'ok' if e['ok'] else 'failed')
        m = eff.model(e['tool'], args)
        sym.append('never_seen' if m is None or not m.cases else judge(eff.predict(e['tool'], args, before, reader='BAYES0.99')['outcome'], truth))
        qs.append(Scene(world, e['tool'], args, e['before'], e['after'], 'ok' if e['ok'] else 'failed'))
    pool = by_tool(scenes)
    open_i = [i for i, s in enumerate(sym) if s == 'unknown']
    r = ask(model, pool, [qs[i] for i in open_i], device, k, tau, votes, random.Random(f'{world}-{seed}'))
    hyb = list(sym)
    for i, x in zip(open_i, r):
        hyb[i] = x
    alone = ask(model, pool, qs, device, k, 0.0, 1, random.Random(f'{world}-{seed}-alone'))
    return Counter(sym), Counter(hyb), Counter(alone), Counter(prior_only(pool, qs, k, random.Random(f'{world}-{seed}-prior')))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('worlds')
    ap.add_argument('reader')
    ap.add_argument('out')
    ap.add_argument('--tau', type=float, required=True)
    ap.add_argument('--votes', type=int, required=True)
    ap.add_argument('--k', type=int, default=10)
    ap.add_argument('--seeds', nargs='+', type=int, default=[1, 2, 3])
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'result.json').exists():
        raise SystemExit('already run: the final check is run once')
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = reader(a.reader, device)
    mod = load_module(a.worlds)
    res = {}
    for w in mod.WORLDS:
        tot = {'EMPTY': Counter(), 'HYBRID': Counter(), 'READER': Counter(), 'PRIOR': Counter()}
        for s in a.seeds:
            e, h, r, pr = world_run(mod, w, s, model, device, a.k, a.tau, a.votes)
            tot['EMPTY'].update(e), tot['HYBRID'].update(h), tot['READER'].update(r), tot['PRIOR'].update(pr)
        res[w] = {k: dict(v) for k, v in tot.items()}
        for name, c in tot.items():
            n = sum(c.values())
            print(f"{w} {name:7s} R {c['right'] / n:.3f} W {c['wrong'] / n:.4f} ({c['wrong']}) n={n}", flush=True)
    allc = {k: Counter() for k in ('EMPTY', 'HYBRID', 'READER', 'PRIOR')}
    for w in res:
        for k in allc:
            allc[k].update(res[w][k])
    n = sum(allc['EMPTY'].values())
    rate = lambda c, x: c[x] / n
    gain = rate(allc['HYBRID'], 'right') - rate(allc['EMPTY'], 'right')
    added_wrong = rate(allc['HYBRID'], 'wrong') - rate(allc['EMPTY'], 'wrong')
    worlds_up = sum(res[w]['HYBRID'].get('right', 0) > res[w]['EMPTY'].get('right', 0) for w in res)
    f1, f2 = added_wrong <= 0.01, gain >= 0.03 and worlds_up >= 3
    verdict = 'PASS' if f1 and f2 else ('PARTIAL' if f2 and added_wrong <= 0.03 else 'FAIL')
    summary = {'verdict': verdict, 'gain': round(gain, 4), 'added_wrong': round(added_wrong, 4), 'worlds_up': worlds_up, 'F1': f1, 'F2': f2,
               'tau': a.tau, 'votes': a.votes, 'k': a.k, 'seeds': a.seeds, 'all': {k: dict(v) for k, v in allc.items()}, 'worlds': res}
    (out / 'result.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('verdict', 'gain', 'added_wrong', 'worlds_up', 'F1', 'F2')}))


if __name__ == '__main__':
    main()
