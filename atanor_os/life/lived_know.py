"""T_LIVED_PLAN.md: one Self per condition lives the prior bodies and then the target body, with energy and one death
(default genome, the program teacher). KNOW: practice skips calls the reader (other authors' worlds, self-check gate)
is sure of (ATANOR_PRACTICE_KNOW=1); NONE: today's practice. Measured in the target body: GOOD, energy spent, trials.
  python -m atanor_os.life.lived_know <out> --seeds 1 2 3 --prior board clime --target dye [--S 4 --T 4]
"""
import argparse
import json
import os
from pathlib import Path

from .lineage import birth, live, measure
from .metabolism import DEFAULT_GENOME


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--seeds', nargs='+', type=int, required=True)
    ap.add_argument('--prior', nargs='+', default=['board', 'clime'])
    ap.add_argument('--target', default='dye')
    ap.add_argument('--S', type=int, default=4)
    ap.add_argument('--T', type=int, default=4)
    ap.add_argument('--cond', choices=['NONE', 'KNOW'], required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    os.environ['ATANOR_PRACTICE_KNOW'] = '1' if a.cond == 'KNOW' else '0'
    os.environ.setdefault('ATANOR_LEARNER', 'next_explore')
    os.environ.setdefault('ATANOR_KNOW_TAU', '0.9')          # R_GATE_PLAN.md setting
    os.environ.setdefault('ATANOR_KNOW_GATE', '0.8')
    res = {}
    for s in a.seeds:
        d = out / f'{a.cond}-s{s}'
        birth(d, s, a.prior + [a.target], a.S, dict(DEFAULT_GENOME))
        res[s] = {'end': live(d, s, a.target, a.S, a.T, a.prior, out / f'{a.cond}-s{s}.log'),
                  **measure(d, s, a.target, out / f'{a.cond}-s{s}-eval.json')}
        trials = 0
        f = d / 'autobiography.jsonl'
        for line in f.read_text(encoding='utf-8').splitlines():
            r = json.loads(line)
            trials += r.get('kind') == 'SELF_TRIAL'
        res[s]['self_trials_all'] = trials
        print(a.cond, s, json.dumps(res[s]), flush=True)
    (out / f'{a.cond}.json').write_text(json.dumps(res, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
