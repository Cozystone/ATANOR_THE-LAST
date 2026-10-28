"""REBUILD_PLAN.md stage 4: per body and learner, the evaluators' outcomes summed over seeds, and the new learner's own
counts (lab tests, questions, avoided calls). GOOD is success + partial; part-held is reported apart and is not GOOD.
Usage: python -m atanor_os.rebuild.summ_stage4 <dir> [seeds...]
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

GOOD = ('success', 'partial')


def outcomes(r, body):
    c = Counter(x['outcome'] for x in r.get('rows', []))
    if body == 'clime':
        c.update(x['outcome'] for x in r['time']['rows'])
        for x in r['unseen_change']['rows']:
            c.update(o for o in (x.get('first'), x.get('second')) if o)
    for part in ('unseen_change', 'double_change'):
        if body != 'clime' and isinstance(r.get(part), dict):
            for x in r[part].get('rows', []):
                c.update(o for k, o in x.items() if k in ('first', 'second', 'outcome') and isinstance(o, str))
    return c


def main(d, seeds):
    d = Path(d)
    learners = sorted({p.name.split('-')[1] for p in d.glob('clime-*-none-s*.json')} |
                      {p.name.split('-')[1] for p in d.glob('r2-*-none-s*.json')})
    table = defaultdict(lambda: defaultdict(Counter))
    harm = defaultdict(Counter)
    for L in learners:
        for s in seeds:
            files = {'clime': d / f'clime-{L}-none-s{s}.json', 'desk': d / f'r2-{L}-none-s{s}.json'}
            files |= {b: d / f'r2-{L}-three-{b}-s{s}.json' for b in ('board', 'fs', 'view')}
            for b, f in files.items():
                if not f.exists():
                    table[b][L]['missing_runs'] += 1
                    continue
                r = json.loads(f.read_text(encoding='utf-8'))
                table[b][L].update(outcomes(r, b))
                if b == 'clime':
                    harm[L].update(r['harm'])
            for part in ('clime', 'old'):
                cf = d / f'counts-{part}-{L}-{s}.jsonl'
                if cf.exists():
                    for line in cf.read_text(encoding='utf-8').splitlines():
                        row = json.loads(line)
                        table['_cost_' + ('with_person' if row['person'] else 'alone')][L].update(row['counts'])
    out = {}
    for b, per in sorted(table.items()):
        out[b] = {}
        for L, c in sorted(per.items()):
            if b.startswith('_cost'):
                keep = ('lab_tests', 'asked_prior', 'avoided_predicted_block', 'left_predicted_no_change', 'predicted_fail',
                        'acted_as_core_unknown', 'left_as_core_unknown', 'acted_goal_unknown', 'goal_yes', 'goal_not_meant', 'goal_leave',
                        'refused', 'blocked', 'actions')
                out[b][L] = {k: c[k] for k in keep if c[k]}
                continue
            n = sum(v for k, v in c.items() if k != 'missing_runs')
            good = sum(c[k] for k in GOOD)
            out[b][L] = {'n': n, 'good': good, 'good_rate': round(good / n, 3) if n else None, **{k: v for k, v in c.items()}}
    out['clime_harm'] = {L: dict(c) for L, c in harm.items()}
    return out


if __name__ == '__main__':
    seeds = [int(x) for x in sys.argv[2:]] or [1, 2, 3, 4, 5]
    r = main(sys.argv[1], seeds)
    for b, per in r.items():
        print(b)
        for L, v in per.items():
            print('  ', L, json.dumps(v))
