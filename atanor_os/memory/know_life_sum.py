"""P_KNOW_LIFE_PLAN.md summary: per body GOOD rate, wrong and harm; own trials = practice trials (every summary file's
practice_* entries) + lab tests at work (lab_tests + lab_tests_other_way, with and without the person).
  python -m atanor_os.memory.know_life_sum <dir> <seed> [<seed> ...]
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from ..rebuild.summ_stage4 import GOOD, outcomes

LEARNERS = ('next_explore', 'next_know')
BODIES = ('board', 'clime', 'desk', 'dye', 'fs', 'view')


def ints(v):
    if isinstance(v, dict):
        return sum(ints(x) for x in v.values())
    return v if isinstance(v, int) else 0


def main(d, seeds):
    d = Path(d)
    out, cost = defaultdict(dict), Counter()
    tab = defaultdict(Counter)
    harm = Counter()
    missing = Counter()
    for L in LEARNERS:
        for s in seeds:
            files = {'clime': d / f'clime-{L}-none-s{s}.json', 'desk': d / f'r2-{L}-none-s{s}.json',
                     'dye': d / f'dye-{L}-none-s{s}.json'}
            files |= {b: d / f'r2-{L}-three-{b}-s{s}.json' for b in ('board', 'fs', 'view')}
            for b, f in files.items():
                if not f.exists():
                    missing[L] += 1
                    continue
                r = json.loads(f.read_text(encoding='utf-8'))
                tab[(b, L)].update(outcomes(r, b))
                if b in ('clime', 'dye'):
                    harm[L] += ints(r.get('harm', {}))
            for f in d.glob(f'*-{L}-summary-s{s}.json'):
                r = json.loads(f.read_text(encoding='utf-8'))
                cost[(L, 'practice')] += sum(ints(v) for k, v in r.items() if k.startswith('practice'))
            for part in ('clime', 'old', 'dye'):
                cf = d / f'counts-{part}-{L}-{s}.jsonl'
                if cf.exists():
                    for line in cf.read_text(encoding='utf-8').splitlines():
                        c = json.loads(line)['counts']
                        cost[(L, 'lab')] += c.get('lab_tests', 0) + c.get('lab_tests_other_way', 0)
                        cost[(L, 'known_by_reader')] += c.get('known_by_reader', 0)
    p1 = True
    rows, bad = Counter(), Counter()
    for b in BODIES:
        line = []
        rate = {}
        for L in LEARNERS:
            c = tab[(b, L)]
            n = sum(c.values())
            rate[L] = sum(c[k] for k in GOOD) / n if n else 0.0
            rows[L] += n
            bad[L] += c['wrong']
            line.append(f'{L} n {n} GOOD {rate[L]:.3f} wrong {c["wrong"]}')
        ok = rate['next_know'] >= rate['next_explore'] - 0.01
        p1 &= ok
        print(f'{b:6s}', ' | '.join(line), '' if ok else '  <-- GOOD lower by more than 1 point')
    for L in LEARNERS:
        bad[L] += harm[L]
    p1 &= bad['next_know'] <= bad['next_explore'] + 0.005 * rows['next_explore']
    own = {L: cost[(L, 'practice')] + cost[(L, 'lab')] for L in LEARNERS}
    p2 = own['next_know'] <= 0.7 * own['next_explore']
    print('wrong + harm', dict(bad), 'rows', dict(rows))
    print('own trials', {L: {'practice': cost[(L, 'practice')], 'lab at work': cost[(L, 'lab')], 'total': own[L]} for L in LEARNERS},
          'known by reader', cost[('next_know', 'known_by_reader')])
    print('missing runs', dict(missing))
    print(json.dumps({'P1': bool(p1), 'P2': bool(p2), 'ratio': round(own['next_know'] / own['next_explore'], 3) if own['next_explore'] else None,
                      'PASS': bool(p1 and p2 and not missing)}))


if __name__ == '__main__':
    main(sys.argv[1], [int(x) for x in sys.argv[2:]])
