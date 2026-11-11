"""Y_CARRY_PLAN.md: does what a Self lived in other bodies carry into a new body through the reader?
For each held-out body B: the reader (reader-all5, trained on other authors' worlds only) is trained further on the course
experiences of the other bodies (the Self's own lived experiences there; no queries, no answers of B), then meets B as the
hybrid does (symbolic first, reader on its unknowns, k=10). BASE is the unchanged reader.
  python -m atanor_os.memory.carry <cache_dir> <out_dir> --seeds 1 2 3 4 5 [--steps 1500] [--lr 1e-4] [--tau 0.95] [--held ...]
"""
import argparse
import json
import random
from collections import Counter
from pathlib import Path

import torch

from . import hybrid, lobo
from .episodic import episodes, task_pool, train as reader_train
from .know import DEFAULT


def mixed_train(model, lived, old, device, steps, lr, mix, k=10, batch=32, seed=0):
    """Every batch: a share `mix` from the lived bodies, the rest replayed from the worlds read before."""
    rng = random.Random(seed)
    pl, po = task_pool(lived), task_pool(old)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps)
    nl = max(1, round(batch * mix))
    for _ in range(steps):
        model.train()
        eps = episodes(lived, rng, k, nl, False, 0.5, pl) + episodes(old, rng, k, batch - nl, False, 0.5, po)
        loss = model.loss(eps, device)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
    return model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cache')
    ap.add_argument('out')
    ap.add_argument('--seeds', nargs='+', type=int, required=True)
    ap.add_argument('--train-seeds', nargs='+', type=int, default=None)
    ap.add_argument('--steps', type=int, default=1500)
    ap.add_argument('--lr', type=float, default=1e-4)
    ap.add_argument('--tau', type=float, default=0.95)
    ap.add_argument('--held', nargs='+', default=list(lobo.BODIES))
    ap.add_argument('--bodies', nargs='+', default=list(lobo.BODIES))
    ap.add_argument('--base', default=DEFAULT)
    ap.add_argument('--mix', type=float, default=0.0, help='share of every batch from the lived bodies (with --replay)')
    ap.add_argument('--replay', type=int, default=0, help='worlds per author family kept beside the lived experiences')
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    lobo.CACHE = hybrid.CACHE = a.cache
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    rows = []
    old = []
    if a.replay:
        from .authors import family, scene
        for au in 'abcde':
            mod = family(au)
            for w in range(a.replay):
                x = mod.world(w)
                old += [scene(f'{au}:{w}', e) for e in x['course'] + x['queries']]
        print('replay scenes', len(old), flush=True)
    for held in a.held:
        scenes = []
        for b in a.bodies:
            if b == held:
                continue
            for s in (a.train_seeds or a.seeds):
                try:
                    scenes += lobo.load(b, s)[1]
                except FileNotFoundError:
                    print('missing', b, s, flush=True)
        model = hybrid.reader(a.base, device).train()
        torch.manual_seed(0)
        if a.mix and old:
            mixed_train(model, scenes, old, device, a.steps, a.lr, a.mix)
        else:
            reader_train(model, scenes + old, device,     steps=a.steps, k=10, batch=32, lr=a.lr, augment=False, biased=0.5, seed=0)
        path = out / f'carry-{held}.pt'
        torch.save(model.state_dict(), path)
        for name, rp in (('BASE', a.base), ('CARRY', str(path))):
            hybrid.run(argparse.Namespace(reader=rp, out=str(out / f'{held}-{name}'), bodies=[held], seeds=a.seeds, ks=[10],
                                          taus=[a.tau], votes=[1], selfcal=None, tau_trusted=[]))
            for r in json.loads((out / f'{held}-{name}' / 'rows.json').read_text(encoding='utf-8')):
                rows.append(dict(r, reader=name, lived=len(scenes)))
        (out / 'rows.json').write_text(json.dumps(rows), encoding='utf-8')
    print('== summary (hybrid)')
    tot = {'BASE': Counter(), 'CARRY': Counter()}
    for r in rows:
        if r['cond'].startswith('HYBRID'):
            n = r['n']
            print(f"{r['body']:6s} {r['reader']:5s} R {r.get('right', 0) / n:.3f} W {r.get('wrong', 0)} n={n} lived={r['lived']}", flush=True)
            tot[r['reader']].update({k: r.get(k, 0) for k in ('right', 'wrong', 'n')})
    for k, c in tot.items():
        print(f"ALL    {k:5s} R {c['right'] / max(1, c['n']):.3f} W {c['wrong']} n={c['n']}", flush=True)


if __name__ == '__main__':
    main()
