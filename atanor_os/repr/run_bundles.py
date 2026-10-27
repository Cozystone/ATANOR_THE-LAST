"""GEN3_BUNDLE_PROTOCOL.md runner.
  make   run the program-teacher course (the frozen generation-2 core, unchanged) on a body and seed, keeping its log
  score  read training logs and query logs only, and score BUNDLE, SINGLE and ORACLE on the queries
The scorer alone knows which later changes are an act's delayed effect (evaluator side): on the desk, a draft left
queued by a send; nothing else in these two bodies.
Usage: python -m atanor_os.repr.run_bundles make <body> <seed> <root>
       python -m atanor_os.repr.run_bundles score <body> <out.json> <train logs ...> -- <query logs ...>
"""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from .bundles import Memory, build, change, controls, read


def make(body, seed, root):
    from ..teach.teacher_policy import Teacher
    base = Path(root) / f'{body}-s{seed}'
    if base.exists():
        shutil.rmtree(base)
    Teacher(base / body, seed=seed, drift_from=10, body=body, mind=base / 'mind').run(25)
    return base / body / body / 'world_log.jsonl'


def truth_who(body, b):
    return 'action' if body == 'desk' and b['post'].get('status') == 'queued' else 'outside'


def score(body, train_logs, query_logs):
    train_rows = [r for p in train_logs for r in read(p)]
    train = [b for i, p in enumerate(train_logs) for b in build(read(p), source=f'T{i}')]
    ctrl = Counter()
    for p in train_logs:
        ctrl.update(controls(read(p)))
    mem = Memory(train, ctrl)
    queries = [b for i, p in enumerate(query_logs) for b in build(read(p), source=f'Q{i}')]
    conditional = {k for k, cases in mem.by_action.items() if len({change(c['pre'], c['post']) for c in cases}) > 1}
    res = {'BUNDLE': Counter(), 'SINGLE': Counter(), 'BUNDLE_cond': Counter(), 'SINGLE_cond': Counter(),
           'later': Counter(), 'later_who': Counter()}
    examples = {'held': [], 'wrong': []}
    for q in queries:
        truth = change(q['pre'], q['post'])
        key = (q['tool'], tuple(q['consts']))
        cond = key in conditional
        for name, ans in (('BUNDLE', mem.ask(q['pre'], q['tool'], q['consts'])), ('SINGLE', mem.single(q['pre'], q['tool'], q['consts']))):
            if ans['answer'] is None:
                outcome = 'held'
            else:
                outcome = 'right' if ans['answer'] == truth else 'wrong'
            res[name][outcome] += 1
            if cond:
                res[name + '_cond'][outcome] += 1
            if name == 'BUNDLE' and outcome in examples and len(examples[outcome]) < 8:
                examples[outcome].append({'query': q['id'], 'tool': q['tool'], 'cond': cond, 'answer': ans.get('answer'), 'truth': truth,
                                          'need': ans.get('need'), 'used': ans.get('used', [])[:5]})
        if q['later'] is not None:
            lt = change(q['post'], q['later'])
            a = mem.ask_later(q['post'], q['tool'], q['consts'])
            if a['answer'] is None:
                res['later']['held'] += 1
            else:
                res['later']['right' if a['answer'] == lt else 'wrong'] += 1
                if lt:
                    res['later_who']['right' if a['who'] == truth_who(body, q) else 'wrong'] += 1
    def rates(c):
        n = sum(c.values())
        ans = c['right'] + c['wrong']
        return {'n': n, 'right': c['right'], 'wrong': c['wrong'], 'held': c['held'],
                'precision': round(c['right'] / ans, 3) if ans else None, 'coverage': round(ans / n, 3) if n else None,
                'wrong_rate': round(c['wrong'] / n, 4) if n else None}
    out = {'body': body, 'train_bundles': len(train), 'queries': len(queries), 'conditional_actions': sorted(map(str, conditional)),
           **{k: rates(v) for k, v in res.items() if k != 'later_who'},
           'later_who': {'right': res['later_who']['right'], 'wrong': res['later_who']['wrong'],
                         'accuracy': round(res['later_who']['right'] / max(1, sum(res['later_who'].values())), 3)},
           'oracle': {'precision': 1.0, 'coverage': 1.0}, 'examples': examples}
    b, bc, sc = out['BUNDLE'], out['BUNDLE_cond'], out['SINGLE_cond']
    checks = {'cond_precision>=0.95': (bc['precision'] or 0) >= 0.95, 'cond_coverage>=0.60': (bc['coverage'] or 0) >= 0.60,
              'wrong_rate<=0.02': (b['wrong_rate'] or 0) <= 0.02,
              'cond_precision>single': (bc['precision'] or 0) > (sc['precision'] or 0),
              'later_who>=0.90': out['later_who']['accuracy'] >= 0.90}
    four = [checks['cond_precision>=0.95'] and checks['cond_coverage>=0.60'], checks['wrong_rate<=0.02'],
            checks['cond_precision>single'], checks['later_who>=0.90']]
    out['checks'] = checks
    out['verdict'] = 'PASS' if all(four) else ('PARTIAL' if (b['wrong_rate'] or 0) <= 0.05 and sum(four) >= 2 else 'FAIL')
    return out


if __name__ == '__main__':
    if sys.argv[1] == 'make':
        print(make(sys.argv[2], int(sys.argv[3]), sys.argv[4]))
    else:
        body, out_file = sys.argv[2], Path(sys.argv[3])
        rest = sys.argv[4:]
        cut = rest.index('--')
        r = score(body, rest[:cut], rest[cut + 1:])
        out_file.write_text(json.dumps(r, indent=1, default=str), encoding='utf-8')
        print(json.dumps({k: v for k, v in r.items() if k != 'examples'}, indent=1, default=str))
