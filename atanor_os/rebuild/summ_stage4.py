"""REBUILD_PLAN.md stage 4: per body and learner, the evaluators' outcomes summed over seeds, and the new learner's own
counts (lab tests, questions, avoided calls). GOOD is success + partial; part-held is reported apart and is not GOOD.
The sixth body (dye, SIXTH_BODY_PLAN.md): a directory holding dye-*-none-s*.json results is summarised for that body
only, the same way as the climate bays (rows, time and the unseen change; the no-grant part apart), with its harm,
irreversible actions without a grant, wrong and command totals, and ORACLE. The seventh body (crumb, the bakery oven
line) is summarised the same way from crumb-*-none-s*.json. Directories without them print what they printed before.
Usage: python -m atanor_os.rebuild.summ_stage4 <dir> [seeds...]
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

GOOD = ('success', 'partial')
NEW = ('dye', 'crumb')                                     # bodies summarised alone, each from its own results


def outcomes(r, body):
    c = Counter(x['outcome'] for x in r.get('rows', []))
    if body in ('clime',) + NEW:
        c.update(x['outcome'] for x in r['time']['rows'])
        for x in r['unseen_change']['rows']:
            c.update(o for o in (x.get('first'), x.get('second')) if o)
    for part in ('unseen_change', 'double_change'):
        if body not in ('clime',) + NEW and isinstance(r.get(part), dict):
            for x in r[part].get('rows', []):
                c.update(o for k, o in x.items() if k in ('first', 'second', 'outcome') and isinstance(o, str))
    return c


def main(d, seeds):
    d = Path(d)
    learners = sorted({p.name.split('-')[1] for p in d.glob('clime-*-none-s*.json')} |
                      {p.name.split('-')[1] for p in d.glob('r2-*-none-s*.json')} |
                      {p.name.split('-')[1] for b in NEW for p in d.glob(f'{b}-*-none-s*.json')})
    newb = next((b for b in NEW if any(d.glob(f'{b}-*-none-s*.json'))), None)
    sixth = newb is not None
    table = defaultdict(lambda: defaultdict(Counter))
    harm = defaultdict(Counter)
    dye = defaultdict(Counter)
    for L in learners:
        for s in seeds:
            files = {'clime': d / f'clime-{L}-none-s{s}.json', 'desk': d / f'r2-{L}-none-s{s}.json'}
            files |= {b: d / f'r2-{L}-three-{b}-s{s}.json' for b in ('board', 'fs', 'view')}
            if sixth:
                files = {newb: d / f'{newb}-{L}-none-s{s}.json'}
            for b, f in files.items():
                if not f.exists():
                    table[b][L]['missing_runs'] += 1
                    continue
                r = json.loads(f.read_text(encoding='utf-8'))
                table[b][L].update(outcomes(r, b))
                if b == 'clime':
                    harm[L].update(r['harm'])
                if b == newb:
                    dye[L].update({'harm': sum(r['harm'].values()), 'irreversible_without_grant': r['irreversible_without_grant'],
                                   'wrong': r['wrong'], 'commands': r['commands'], 'runs': 1})
                    dye[L].update({f'nogrant_{k}': v for k, v in r['nogrant']['outcomes'].items()})
                    for p, v in r['oracle'].items():
                        dye[L].update({f'oracle_{p}_n': v['n'], f'oracle_{p}_good': v['good']})
            for part in ('clime', 'old') + NEW:
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
                keep = ('lab_tests', 'asked_prior', 'avoided_predicted_block', 'left_predicted_no_change', 'avoided_predicted_fail',
                        'acted_as_core_unknown', 'left_as_core_unknown', 'acted_goal_unknown', 'goal_yes', 'goal_not_meant', 'goal_leave',
                        'refused', 'blocked', 'actions')
                out[b][L] = {k: c[k] for k in keep if c[k]}
                continue
            n = sum(v for k, v in c.items() if k != 'missing_runs')
            good = sum(c[k] for k in GOOD)
            out[b][L] = {'n': n, 'good': good, 'good_rate': round(good / n, 3) if n else None, **{k: v for k, v in c.items()}}
    if sixth:
        for L, c in dye.items():
            n, g = sum(c[f'oracle_{p}_n'] for p in ('main', 'unseen', 'time')), sum(c[f'oracle_{p}_good'] for p in ('main', 'unseen', 'time'))
            c = dict(c)
            c['oracle_rate'] = round(g / n, 3) if n else None
            c['wrong_plus_harm_rate'] = round((c['wrong'] + c['harm']) / c['commands'], 4) if c.get('commands') else None
            dye[L] = c
        out[f'{newb}_totals'] = {L: dict(c) for L, c in dye.items()}
        return out
    out['clime_harm'] = {L: dict(c) for L, c in harm.items()}
    return out


if __name__ == '__main__':
    seeds = [int(x) for x in sys.argv[2:]] or [1, 2, 3, 4, 5]
    r = main(sys.argv[1], seeds)
    for b, per in r.items():
        print(b)
        for L, v in per.items():
            print('  ', L, json.dumps(v))
