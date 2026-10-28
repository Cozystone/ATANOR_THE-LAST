"""REBUILD_PLAN.md stage 3: choosing checks that settle what the learner does not know.

After one course (the same experiences for every policy), the learner meets the evaluator's worlds. For each world, the
queries it cannot predict are open questions. With a budget of K checks per world, a policy picks which to settle:
  CHOOSE   the lab test (a call on a lab copy: cost 1, no risk to the world) on an open question whose untried
           condition (its start values never seen with the action) the most open questions share
  RANDOM   a lab test on a random open question
  ASK      asks the person to show the call on that object (the person acts in the world: cost 1 question, the world
           changes); the learner observes it as a demonstration. Same information as a lab test, other cost
  HOLD     no check; open questions stay open (recorded with what would settle them)
  ORACLE   is told every true outcome (the teacher handing over answers; not a learner policy)
After the checks: right / wrong / unknown on every query of that world, then on the next eval seed's worlds with the
experience gained (later solo: no more checks). Costs: lab tests, questions, world changes made by checks.
Usage: python -m atanor_os.rebuild.bench_inquiry <body> <course_dir> <eval_seed> <next_eval_seed> <out.json> [K]
"""
import copy
import json
import random
import sys
from collections import Counter
from pathlib import Path

from .bench_predict import judge, queries, train
from .effects import flat

POLICIES = ('CHOOSE', 'RANDOM', 'ASK', 'HOLD', 'ORACLE')


READER = 'BAYES0.99'


def untried(eff, tool, args, before):
    """What makes this start new for its action: (action key, the start values never seen with it)."""
    m = eff.model(tool, args)
    if m is None:
        return ('new action', tool)
    x = flat(before)
    seen = {}
    for c in m.cases:
        for k, v in c.x.items():
            seen.setdefault(k, set()).add(v)
    return (m.key, tuple(sorted(((k, v) for k, v in x.items() if v not in seen.get(k, ())), key=str)))


def case_of(tool, args, before, after, resp, t, actor):
    return {'t': t, 'actor': actor, 'action': {'tool': tool, 'args': list(args), 'granted': None}, 'executed': resp != 'blocked',
            'response': {'ok': resp == 'ok', 'guard': 'harm' if resp == 'blocked' else None},
            'before': dict(zip(args, before)), 'after': dict(zip(args, after if resp != 'blocked' else before)), 'unobserved': []}


def run_world(eff, qs, policy, K, rng, t0):
    """Settle up to K open questions in one world. Returns counts and the clock."""
    cost = Counter()
    t = t0
    if policy == 'ORACLE':                                 # told every outcome it could not predict, all at once
        for w, tool, args, before, truth, after in [q for q in qs if eff.predict(q[1], q[2], q[3], reader=READER)['outcome'] is None]:
            t += 1
            cost['told'] += 1
            eff.observe(case_of(tool, args, before, after, truth[('r',)], t, 'teacher-told'))
        return Counter(judge(eff.predict(q[1], q[2], q[3], reader=READER)['outcome'], q[4]) for q in qs), cost, t
    for _ in range(K):
        open_q = [q for q in qs if eff.predict(q[1], q[2], q[3], reader=READER)['outcome'] is None]
        if not open_q or policy == 'HOLD':
            break
        if policy in ('CHOOSE',):                       # test the untried condition the most open questions share
            sig = {id(q): untried(eff, q[1], q[2], q[3]) for q in open_q}
            size = Counter(sig.values())
            pick = max(open_q, key=lambda q: (size[sig[id(q)]], -open_q.index(q)))
        else:
            pick = rng.choice(open_q) if policy in ('RANDOM', 'ASK') else open_q[0]
        w, tool, args, before, truth, after = pick
        t += 1
        if policy == 'ORACLE':
            cost['told'] += 1
            actor = 'teacher-told'
        elif policy == 'ASK':
            cost['questions'] += 1
            cost['world_changes'] += truth[('r',)] == 'ok' and any(b != a for b, a in zip(before, after))
            actor = 'person'
        else:
            cost['lab_tests'] += 1
            actor = 'learner-lab'
        eff.observe(case_of(tool, args, before, after, truth[('r',)], t, actor))
    out = Counter(judge(eff.predict(q[1], q[2], q[3], reader=READER)['outcome'], q[4]) for q in qs)
    return out, cost, t


def score(body, course_dir, eval_seed, next_seed, K, work):
    base, exps = train(body, course_dir)
    t0 = max((e['t'] for e in exps), default=0) + 1
    qs_all = queries(body, course_dir, eval_seed, Path(work) / 'a')
    nxt = queries(body, course_dir, next_seed, Path(work) / 'b')
    worlds = sorted({q[0] for q in qs_all})
    res = {}
    for pol in POLICIES:
        eff = copy.deepcopy(base)
        rng = random.Random(f'{body}-{eval_seed}-{pol}')
        tot, cost, t = Counter(), Counter(), t0
        for w in worlds:
            out, c, t = run_world(eff, [q for q in qs_all if q[0] == w], pol, K, rng, t)
            tot.update(out)
            cost.update(c)
        later = Counter(judge(eff.predict(q[1], q[2], q[3], reader=READER)['outcome'], q[4]) for q in nxt)
        n, ln = sum(tot.values()), sum(later.values())
        res[pol] = {'here': dict(tot), 'here_right_rate': round(tot['right'] / n, 3) if n else None, 'cost': dict(cost),
                    'later': dict(later), 'later_right_rate': round(later['right'] / ln, 3) if ln else None}
    before_any = Counter(judge(base.predict(q[1], q[2], q[3], reader=READER)['outcome'], q[4]) for q in qs_all)
    return {'body': body, 'course': str(course_dir), 'eval_seed': eval_seed, 'next_seed': next_seed, 'K': K,
            'no_checks': dict(before_any), 'policies': res}


if __name__ == '__main__':
    body, cd, es, ns, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), Path(sys.argv[5])
    K = int(sys.argv[6]) if len(sys.argv) > 6 else 10
    r = score(body, cd, es, ns, K, out.with_suffix('.work'))
    out.write_text(json.dumps(r, indent=1, default=str), encoding='utf-8')
    print(json.dumps({p: (v['here_right_rate'], v['later_right_rate'], v['cost'], v['here'].get('wrong', 0)) for p, v in r['policies'].items()}))
