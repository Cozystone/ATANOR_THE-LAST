"""M_AUTHORS_PLAN.md: world families written by different authors (separate agents, outside the repo, never read here);
train the reader on some authors' worlds, test on an author it never saw.
  python -m atanor_os.memory.authors train <out_reader.pt> --authors a b c d [--init reader.pt] [--worlds 600] [--steps 6000]
  python -m atanor_os.memory.authors test <reader.pt> --author e [--worlds 100] [--tau .95] [--votes 1] [--out f.json]
A family module gives  world(seed) -> {'name', 'course': [exp], 'queries': [exp]}. Training uses seeds 0..worlds-1 of
the training authors; tests use seeds 5000.. of the held-out author (never in any training).
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
from .episodic import Episodic, by_tool, train as reader_train
from .hybrid import ask, reader
from .relational import Scene

FAM = Path('D:/ATANOR-experiments/2026-09-19/families')
TEST0 = 5000


def family(author):
    spec = importlib.util.spec_from_file_location(f'fam_{author}', FAM / f'fam_{author}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def scene(name, e):
    return Scene(name, e['tool'], list(e['args']), e['before'], e['after'], 'ok' if e['ok'] else 'failed')


def train_cmd(a):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    scenes = []
    for au in a.authors:
        mod = family(au)
        for s in range(a.worlds):
            w = mod.world(s)
            name = f'{au}:{s}'
            scenes += [scene(name, e) for e in w['course'] + w['queries']]
    print('training scenes', len(scenes), 'from', a.authors, flush=True)
    model = Episodic()
    if a.init:
        sd = torch.load(a.init, map_location='cpu')
        if sd['bucket.weight'].shape[0] == 1:
            model.load_state_dict(sd)
    torch.manual_seed(0)
    reader_train(model, scenes, device, steps=a.steps, k=10, batch=32, lr=3e-4 if not a.init else 1e-4, augment=False, biased=0.5, seed=0,
                 log=lambda s: print(s, flush=True) if s.startswith(('step 0 ', 'step 2000', 'step 4000')) else None)
    torch.save(model.state_dict(), a.out)
    print('saved', a.out, flush=True)


def test_cmd(a):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = reader(a.reader, device)
    mod = family(a.author)
    tot = {'EMPTY': Counter(), 'HYBRID': Counter(), 'READER': Counter()}
    for s in range(TEST0, TEST0 + a.worlds):
        w = mod.world(s)
        name = f'{a.author}:{s}'
        eff = Effects(slack=1, tiered=True)
        course = []
        for t, e in enumerate(w['course']):
            eff.observe({'t': t, 'body': name, 'source': 'program', 'actor': 'teacher', 'action': {'tool': e['tool'], 'args': list(e['args'])},
                         'before': e['before'], 'after': e['after'], 'response': {'ok': bool(e['ok']), 'guard': None}})
            course.append(scene(name, e))
        sym, qs = [], []
        for e in w['queries']:
            args = list(e['args'])
            before, after = [e['before'][x] for x in args], [e['after'][x] for x in args]
            m = eff.model(e['tool'], args)
            truth = outputs(before, after, 'ok' if e['ok'] else 'failed')
            sym.append('never_seen' if m is None or not m.cases else judge(eff.predict(e['tool'], args, before, reader='BAYES0.99')['outcome'], truth))
            qs.append(scene(name, e))
        pool = by_tool(course)
        open_i = [i for i, x in enumerate(sym) if x == 'unknown']
        r = ask(model, pool, [qs[i] for i in open_i], device, 10, a.tau, a.votes, random.Random(s))
        hyb = list(sym)
        for i, x in zip(open_i, r):
            hyb[i] = x
        tot['EMPTY'].update(sym)
        tot['HYBRID'].update(hyb)
        tot['READER'].update(ask(model, pool, qs, device, 10, 0.0, 1, random.Random(s + 1)))
    res = {}
    for k, c in tot.items():
        n = sum(c.values())
        res[k] = {'R': round(c['right'] / n, 4), 'W': round(c['wrong'] / n, 4), 'n': n, **c}
        print(f"{a.author} {k:7s} R {c['right'] / n:.3f} W {c['wrong'] / n:.4f} ({c['wrong']}) n={n}", flush=True)
    if a.out:
        Path(a.out).write_text(json.dumps({'reader': a.reader, 'author': a.author, 'tau': a.tau, 'votes': a.votes, **res}), encoding='utf-8')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    t = sp.add_parser('train')
    t.add_argument('out')
    t.add_argument('--authors', nargs='+', required=True)
    t.add_argument('--init', default=None)
    t.add_argument('--worlds', type=int, default=600)
    t.add_argument('--steps', type=int, default=6000)
    e = sp.add_parser('test')
    e.add_argument('reader')
    e.add_argument('--author', required=True)
    e.add_argument('--worlds', type=int, default=100)
    e.add_argument('--tau', type=float, default=0.95)
    e.add_argument('--votes', type=int, default=1)
    e.add_argument('--out', default=None)
    a = ap.parse_args()
    train_cmd(a) if a.cmd == 'train' else test_cmd(a)
