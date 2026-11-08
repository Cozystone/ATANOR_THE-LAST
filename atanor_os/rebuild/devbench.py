"""Development bench for the effect readers (dev seeds only): every query of a course, cached once (truth from lab
copies, as bench_predict), then any reader scored in seconds.
  python -m atanor_os.rebuild.devbench cache <body> <course_dir> <eval_seed> <cache.pkl>
  python -m atanor_os.rebuild.devbench score <cache_dir> <reader> [<reader> ...]
"""
import json
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .bench_predict import judge, novelty, queries, train
from .effects import flat


def cache(body, course_dir, eval_seed, out):
    qs = queries(body, course_dir, eval_seed, Path(out).with_suffix('.work'))
    Path(out).write_bytes(pickle.dumps({'body': body, 'course': str(course_dir), 'eval_seed': eval_seed, 'qs': qs}))


PRACTICE = 300                                          # dev practice worlds: course seed + 300 (evaluator: + 100)


def _eff(c, rd):
    """'BAYES0.99' or 'BAYES0.99+X3' (after 3 chosen trials per action) / '+R3' (3 random trials per action)."""
    eff, _ = train(c['body'], c['course'], slack=1, tiered=True)
    if '+' in rd:
        from .explore import explore
        names = json.loads((Path(c['course']) / c['body'] / 'names.json').read_text(encoding='utf-8'))
        spec = rd.split('+')[1]
        ps, wd = c['eval_seed'] - 100 + PRACTICE, Path(c['course']).parent / f'xw-{c["body"]}-{c["eval_seed"]}-{spec}'
        counts = None
        if spec.startswith('RM'):                          # random, as many trials per action as CHOOSE made
            explore(train(c['body'], c['course'], slack=1, tiered=True)[0], c['body'], names, ps, wd, per_action=int(spec[2:]))
            counts = dict(explore.counts)
        tr = explore(eff, c['body'], names, ps, wd, per_action=int(spec.lstrip('XRM')),
                     selector='CHOOSE' if spec[0] == 'X' else 'RANDOM', counts=counts)
        eff._trials = len(tr)
    return eff


def run(c, readers):
    base = _eff(c, 'BAYES')
    effs = {rd: _eff(c, rd) if '+' in rd else base for rd in readers}
    res = {r: defaultdict(Counter) for r in readers}
    wrong = defaultdict(list)
    for w, tool, args, before, truth, _ in c['qs']:
        m = base.model(tool, args)
        if m is None or not m.cases:
            continue
        nov = novelty(m, flat(before))
        for rd in readers:
            out = judge(effs[rd].predict(tool, args, before, reader=rd.split('+')[0])['outcome'], truth)
            res[rd]['all'][out] += 1
            res[rd][nov][out] += 1
            if out == 'wrong':
                wrong[rd].append((tool, list(args), nov))
    run.effs = effs
    return res, wrong


def score(d, readers):
    tot = {r: defaultdict(Counter) for r in readers}
    lines = []
    for f in sorted(Path(d).glob('*.pkl')):
        c = pickle.loads(f.read_bytes())
        res, wrong = run(c, readers)
        for r in readers:
            for p, cnt in res[r].items():
                tot[r][(c['body'], p)] += cnt
            if '+' in r:
                lines.append(f'{f.stem} {r} trials {getattr(run.effs[r], "_trials", 0)}')
            if wrong[r]:
                lines.append(f'{f.stem} {r} wrong {Counter(map(str, wrong[r])).most_common(3)}')
    print('\n'.join(lines))
    bodies = sorted({b for r in readers for b, _ in tot[r]})
    for b in bodies:
        for p in ('all', 'seen', 'new_combination', 'new_value'):
            row = []
            for r in readers:
                c = tot[r].get((b, p))
                if not c:
                    continue
                n = sum(c.values())
                row.append(f'{r}: R {c["right"] / n:.3f} W {c["wrong"]}/{n}')
            if row:
                print(f'{b:6} {p:16}', ' | '.join(row))


if __name__ == '__main__':
    if sys.argv[1] == 'cache':
        cache(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5])
    else:
        score(sys.argv[2], sys.argv[3:])
