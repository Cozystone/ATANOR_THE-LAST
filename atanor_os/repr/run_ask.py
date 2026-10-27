"""GEN4_B1_PROTOCOL.md: objects without agreeing cases settled by one contrast question each, the answer kept for that
action and start (reader ASK), against G and LEAVE, on the five bodies with experiment 6's data. The answers are the
evaluator's labels (the program teacher answers as the person means), so this measures questions spent and reused.
Usage: python -m atanor_os.repr.run_ask <body> <seed> <eval_seed> <out.json>
"""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from .bundles import Memory, _freeze, build, controls, read
from .run_act import WORK, decide, last
from .run_act6 import _install, course, worlds
from ..eval.tutor_life import DRIFT, body_spec, body_targets
from ..teach.tutor import Tutor

BUDGET = 6                                                 # the learner's QUESTION_BUDGET per command


def score(body, seed, eval_seed):
    root = WORK / f'ask-{body}-s{seed}'
    log, course_dir = course(body, seed, root)
    rows = read(log)
    mem = Memory(build(rows, source='T'), controls(rows))
    names = json.loads((course_dir / 'names.json').read_text(encoding='utf-8'))
    sels, acts = body_targets(body, names['seed'])
    spec, drift = body_spec(body), [DRIFT[body]]
    possible = getattr(spec, 'possible', lambda act, o, state: True)
    pairs = [(s, a) for s in sorted(int(k) for k in names['sel']) for a in sorted(int(k) for k in names['act'])]
    res = {r: Counter() for r in ('ASK', 'G', 'LEAVE')}
    hit, answers, asked = Counter(), {}, Counter()        # answers: (tool, consts, start) -> 'act' / 'leave'
    commands = 0
    for w, mk in enumerate(worlds(body, root / 'eval', eval_seed, drift)):
        for s, a in pairs:
            h = mk()
            t = Tutor(h, spec, f'eval-{eval_seed}')
            t.start(sels[s], acts[a])
            st = h.observe(h.existing())
            blank = {k: '-' for k in next(iter(st.values()), {})} | {'kind': 'absent'}
            commands += 1
            spent = 0
            for o in sorted(t.truth):
                if o not in st:
                    continue
                truth = 'act' if possible(acts[a], o, t.before) and not spec.shows(acts[a], o, t.before) else 'leave'
                tool, args = spec.steps(acts[a], o, h.drift)
                known = {c for (tl, cs) in mem.by_action for c in cs if tl == tool}
                consts = [x for x in args if x in known]
                obj = next((x for x in args if x not in known), o)
                pre = st.get(obj) or blank
                b = mem.ask(pre, tool, consts)
                lt = last(mem, pre, tool, consts)
                key = (tool, tuple(consts), _freeze(pre))
                if b['answer'] is not None:
                    ask = decide(b, pre)
                elif key in answers:
                    ask = answers[key]                     # the person's earlier answer from this start
                    asked['reused'] += 1
                elif spent < BUDGET:
                    ask = answers[key] = truth             # "this one too?" answered as the person means
                    spent += 1
                    asked['asked'] += 1
                else:
                    ask = decide(lt, pre)
                    asked['over_budget'] += 1
                for name, d in (('ASK', ask), ('G', decide(b if b['answer'] is not None else lt, pre)),
                                ('LEAVE', 'leave' if b['answer'] is None else decide(b, pre))):
                    res[name]['right' if d == truth else 'wrong'] += 1
                if truth == 'act':
                    hit['n'] += 1
                    hit['acted'] += ask == 'act'
    shutil.rmtree(root / 'eval', ignore_errors=True)

    def rates(c):
        n = sum(c.values())
        return {'n': n, 'right': c['right'], 'wrong': c['wrong'], 'wrong_rate': round(c['wrong'] / n, 4) if n else None}
    out = {'body': body, 'seed': seed, 'eval_seed': eval_seed, 'commands': commands, **{k: rates(v) for k, v in res.items()},
           'questions': dict(asked), 'questions_per_command': round(asked['asked'] / commands, 3) if commands else None,
           'act_hit': {'n': hit['n'], 'acted': hit['acted'], 'rate': round(hit['acted'] / hit['n'], 3) if hit['n'] else None}}
    k, g, lv = out['ASK'], out['G'], out['LEAVE']
    rate = out['act_hit']['rate'] or 0
    out['checks'] = {'wrong_rate<=0.01': (k['wrong_rate'] or 0) <= 0.01, 'not_more_wrong_than_g_or_leave': k['wrong'] <= min(g['wrong'], lv['wrong']),
                     'act_hit>=0.90': rate >= 0.90, 'questions_per_command<=2': (out['questions_per_command'] or 0) <= 2}
    first3 = [out['checks'][c] for c in ('wrong_rate<=0.01', 'not_more_wrong_than_g_or_leave', 'act_hit>=0.90')]
    out['verdict'] = 'PASS' if all(out['checks'].values()) else ('PARTIAL' if all(first3) else 'FAIL')
    return out


if __name__ == '__main__':
    _install()
    body, seed, eval_seed, out_file = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])
    r = score(body, seed, eval_seed)
    out_file.write_text(json.dumps(r, indent=1, default=str), encoding='utf-8')
    print(json.dumps(r, indent=1, default=str))
