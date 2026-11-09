"""BIRTH_PLAN.md final check: run once. Validity of the held-out formats, the run, and the verdict by the plan's rule.
  python -m atanor_os.eval.birth_final check <cache_dir> <formats_file>
  python -m atanor_os.eval.birth_final judge <out_dir>
"""
import glob
import importlib.util
import json
import pickle
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

BODIES = ('board', 'clime', 'desk', 'dye', 'fs', 'view')


def check(cache, file):
    """Every format, on every object of every query: one line, the name and each value verbatim. Prints counts only."""
    spec = importlib.util.spec_from_file_location('held_out_formats', file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    bad, n = Counter(), 0
    rng = random.Random(0)
    files = sorted(glob.glob(f'{cache}/*.pkl'))
    for f in files:
        c = pickle.loads(Path(f).read_bytes())
        for w, tool, args, before, truth, after in c['qs']:
            for name, obs in list(zip(args, before)) + list(zip(args, after)):
                if obs is None:
                    continue
                for fmt in mod.FORMATS:
                    n += 1
                    t = mod.line(fmt, name, obs, rng)
                    if '\n' in t or name not in t or any(str(v) not in t for v in obs.values() if v not in ('-', None)):
                        bad[fmt] += 1
    print('files', len(files), 'lines', n, 'formats', len(mod.FORMATS), 'bad', {f: bad[f] for f in mod.FORMATS})
    return not any(bad.values())


def judge(out):
    rows = json.loads((Path(out) / 'rows.json').read_text())
    pool = defaultdict(Counter)
    for b, _, fmt, m, t in rows:
        pool[(b, fmt, m)].update(t)
    rate = lambda c: c['right'] / max(1, sum(c.values()))
    base = {b: pool[(b, '-', 'ADAPTER')] for b in BODIES}
    allbase = sum(base.values(), Counter())
    fmts = sorted({f for _, f, m in pool if m == 'BIRTH'})
    res, passed = {}, 0
    for f in fmts:
        tot = sum((pool[(b, f, 'BIRTH')] for b in BODIES), Counter())
        pos = sum((pool[(b, f, 'POS')] for b in BODIES), Counter())
        per = {b: (round(rate(pool[(b, f, 'BIRTH')]), 3), round(rate(base[b]), 3), pool[(b, f, 'BIRTH')]['wrong']) for b in BODIES}
        ok_bodies = sum(rate(pool[(b, f, 'BIRTH')]) >= 0.85 * rate(base[b]) for b in BODIES)
        wrong = tot['wrong'] / max(1, sum(tot.values()))
        h1 = rate(tot) >= 0.90 * rate(allbase) and ok_bodies >= 5
        h2 = wrong <= 0.01
        passed += h1 and h2
        res[f] = {'right': round(rate(tot), 4), 'adapter_right': round(rate(allbase), 4), 'wrong_rate': round(wrong, 4), 'bodies_ok': ok_bodies,
                  'POS_right': round(rate(pos), 4), 'H1': h1, 'H2': h2, 'per_body(birth,adapter,wrong)': per}
    verdict = 'PASS' if passed == len(fmts) else 'PARTIAL' if passed * 2 >= len(fmts) else 'FAIL'
    print(json.dumps({'verdict': verdict, 'passed_formats': passed, 'of': len(fmts), 'formats': res}, indent=1))


if __name__ == '__main__':
    if sys.argv[1] == 'check':
        sys.exit(0 if check(sys.argv[2], sys.argv[3]) else 1)
    judge(sys.argv[2])
