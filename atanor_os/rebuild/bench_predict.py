"""REBUILD_PLAN.md stage 2: predict, before acting, what an action will do. Every reader gets the same experiences (one
course's body log) and answers the same queries: in the evaluator's worlds, every object x every action the teacher
uses in this body, called as the body's steps for it. The truth is what the call does in a lab copy of that world
(nothing in the world itself is run). Scored on the whole outcome (the body's answer and every argument's attributes).
Queries are split by how new their start is: an identical start was seen (seen), every start value was seen but not in
this combination (new_combination), or some start value was never seen with this action (new_value).
Usage: python -m atanor_os.rebuild.bench_predict <body> <course_dir> <eval_seed> <out.json>
"""
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .effects import Effects, flat
from .experience import load_course
from ..eval.tutor_life import DRIFT, body_spec, body_targets
from ..repr.run_act6 import worlds

READERS = ('NEW', 'BAYES0.95', 'BAYES0.99', 'EXACT', 'LAST', 'CORE')


def grants(h):
    return {c: True for c in set(getattr(h, 'CAPABILITY', {}).values())}


def run_lab(h, root, tool, args):
    lab = h.lab_copy(root, h.existing())
    if hasattr(h, 'drift'):
        lab.drift = h.drift
    try:
        res = lab.execute(tool, tuple(args), grants(h))
    except ValueError:
        res = {'ok': False, 'error': 'invalid'}
    after = lab.observe(lab.existing())
    shutil.rmtree(root, ignore_errors=True)
    return res, after


def novelty(m, x):
    if m is None:
        return 'new_action'
    if any(c.x == x for c in m.cases):
        return 'seen'
    vals = defaultdict(set)
    for c in m.cases:
        for k, v in c.x.items():
            vals[k].add(v)
    return 'new_combination' if all(v in vals[k] for k, v in x.items()) else 'new_value'


def queries(body, course_dir, eval_seed, work):
    """[(world index, tool, args, before, truth)] for every evaluator world, action and object; truth from a lab copy."""
    names = json.loads((Path(course_dir) / body / 'names.json').read_text(encoding='utf-8'))
    _, acts = body_targets(body, names['seed'])
    spec, drift = body_spec(body), [DRIFT[body]]
    out = []
    for w, mk in enumerate(worlds(body, Path(work) / 'eval', eval_seed, drift)):
        h = mk()
        for a in sorted(int(k) for k in names['act']):
            for o in sorted(h.existing()):
                try:
                    tool, args = spec.steps(acts[a], o, h.drift)
                except Exception:
                    continue
                if len(set(args)) != len(args):
                    continue
                st = h.observe(h.existing())                # as the course logs observe: the existing world, and
                blank = {k: '-' for k in next(iter(st.values()), {})} | {'kind': 'absent'}   # 'no value' for what is not there
                before = [st.get(x, blank) for x in args]
                r, after_obs = run_lab(h, Path(work) / 'lab', tool, args)
                resp = 'blocked' if r.get('blocked') else ('ok' if r.get('ok') else 'failed')
                after = [after_obs.get(x, blank) for x in args]
                truth = {('r',): resp}
                for i, (b, af) in enumerate(zip(before, after)):
                    for k in sorted(set(b or {}) | set(af or {})):
                        truth[(i, k)] = (af or {}).get(k, '-')
                out.append((w, tool, list(args), before, truth, after))
    shutil.rmtree(Path(work), ignore_errors=True)
    return out


def judge(y, truth):
    if y is None:
        return 'unknown'
    return 'right' if all(y.get(k, '-') == v for k, v in truth.items()) else 'wrong'


def train(body, course_dir, **kw):
    exps = load_course(course_dir, body)
    eff = Effects(**kw)
    for e in exps:
        eff.observe(e)
    return eff, exps


def score(body, course_dir, eval_seed, work):
    models, exps = {}, None
    models['NEW'], exps = train(body, course_dir, slack=1, tiered=True)
    eff = models['NEW']
    res = {r: defaultdict(Counter) for r in READERS}
    examples = []
    for w, tool, args, before, truth, _ in queries(body, course_dir, eval_seed, work):
        resp = truth[('r',)]
        m = eff.model(tool, args)
        nov = novelty(m, flat(before))
        for rd in READERS:
            p = eff.predict(tool, args, before, reader=rd)
            y = p['outcome']
            out = judge(y, truth)
            for part in ('all', nov) + (('blocked',) if resp == 'blocked' else ()):
                res[rd][part][out] += 1
            if rd == 'BAYES0.99' and out == 'wrong' and len(examples) < 10:
                examples.append({'tool': tool, 'args': args, 'before': before, 'truth': {str(k): v for k, v in truth.items()},
                                 'pred': {str(k): v for k, v in y.items()}, 'novelty': nov})
    shutil.rmtree(Path(work), ignore_errors=True)

    def rates(c):
        n = sum(c.values())
        ans = c['right'] + c['wrong']
        return {'n': n, 'right': c['right'], 'wrong': c['wrong'], 'unknown': c['unknown'],
                'coverage': round(ans / n, 3) if n else None, 'acc_answered': round(c['right'] / ans, 3) if ans else None,
                'right_rate': round(c['right'] / n, 3) if n else None}
    return {'body': body, 'course': str(course_dir), 'eval_seed': eval_seed, 'experiences': len(exps),
            'actions': len(eff.models), 'readers': {rd: {part: rates(c) for part, c in parts.items()} for rd, parts in res.items()},
            'examples_wrong_new': examples}


if __name__ == '__main__':
    body, course_dir, eval_seed, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), Path(sys.argv[4])
    r = score(body, course_dir, eval_seed, Path(out).with_suffix('.work'))
    out.write_text(json.dumps(r, indent=1, default=str), encoding='utf-8')
    print(json.dumps({rd: v['all'] for rd, v in r['readers'].items()}, indent=1))
