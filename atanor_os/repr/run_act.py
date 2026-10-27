"""GEN3_BUNDLE3_PROTOCOL.md: act or leave, read from case bundles (BUNDLE) or from one result value (SINGLE: the first
case, the current representation; LAST: the latest case, what step E used). Training is a course's world log only;
queries are the meant objects of evaluator-built worlds (no action is run); the labels are evaluator side.
Usage: python -m atanor_os.repr.run_act <body> <seed> <eval_seed> <out.json>
"""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from .bundles import Memory, build, change, controls, read
from .run_bundles import make
from ..eval.tutor_life import DRIFT, body_spec, body_targets
from ..teach.tutor import Tutor

WORK = Path(__file__).resolve().parents[3].parent / 'probe-work'


def worlds(body, root, eval_seed, drift):
    """The evaluator's worlds for this body: the climate bays after 0, 1 and 2 outside changes, the desk's three."""
    if body == 'clime':
        from ..eval.clime_eval import world
        return [lambda k=k: world(root, eval_seed, drift, ticks=k) for k in (0, 1, 2)]
    from ..eval.desk_eval2 import WORLD_DAYS, world
    return [lambda v=v: world(root, eval_seed, drift, variant=v) for v in range(len(WORLD_DAYS))]


def last(mem, pre, tool, consts):
    cases = mem.by_action.get((tool, tuple(consts)), [])
    if not cases:
        return {'answer': None}
    values = dict(change(cases[-1]['pre'], cases[-1]['post']))
    return {'answer': tuple(sorted((k, v) for k, v in values.items() if pre.get(k) != v))}


def decide(ans, pre):
    """The case's resulting values, on this object's own start: nothing left to change is 'leave' (a case matched through
    an attribute allowed to differ may end where this object already is)."""
    if ans['answer'] is None:
        return 'hold'
    return 'act' if any(pre.get(k) != v for k, v in ans['answer']) else 'leave'


def score(body, seed, eval_seed):
    root = WORK / f'act3-{body}-s{seed}'
    log = make(body, seed, root)
    rows = read(log)
    mem = Memory(build(rows, source='T'), controls(rows))
    course = root / f'{body}-s{seed}' / body
    names = json.loads((course / 'names.json').read_text(encoding='utf-8'))
    sels, acts = body_targets(body, names['seed'])
    spec, drift = body_spec(body), [DRIFT[body]]
    pairs = [(s, a) for s in sorted(int(k) for k in names['sel']) for a in sorted(int(k) for k in names['act'])]
    res = {r: Counter() for r in ('BUNDLE', 'SINGLE', 'LAST')}
    examples, needs, held_truth = [], Counter(), Counter()
    for w, mk in enumerate(worlds(body, root / 'eval', eval_seed, drift)):
        for s, a in pairs:
            h = mk()
            t = Tutor(h, spec, f'eval-{eval_seed}')
            t.start(sels[s], acts[a])
            st = h.observe(h.existing())
            for o in sorted(t.truth):
                if o not in st:
                    continue
                truth = 'act' if spec.possible(acts[a], o, t.before) and not spec.shows(acts[a], o, t.before) else 'leave'
                tool, args = spec.steps(acts[a], o, h.drift)
                consts = [x for x in args if x != o]
                b = mem.ask(st[o], tool, consts)
                for name, ans in (('BUNDLE', b), ('SINGLE', mem.single(st[o], tool, consts)), ('LAST', last(mem, st[o], tool, consts))):
                    d = decide(ans, st[o])
                    out = 'held' if d == 'hold' else ('right' if d == truth else 'wrong')
                    res[name][out] += 1
                    if name == 'BUNDLE' and out == 'wrong' and len(examples) < 12:
                        examples.append({'world': w, 'tool': tool, 'consts': consts, 'pre': st[o], 'truth': truth, 'answer': b['answer'],
                                         'used': b.get('used', [])[:5]})
                if b['answer'] is None:
                    needs[b['need'].split(' starting')[0]] += 1
                    held_truth[truth] += 1                 # what a held object needed (reported, not scored)
    shutil.rmtree(root / 'eval', ignore_errors=True)

    def rates(c):
        n = sum(c.values())
        ans = c['right'] + c['wrong']
        return {'n': n, 'right': c['right'], 'wrong': c['wrong'], 'held': c['held'],
                'wrong_rate': round(c['wrong'] / n, 4) if n else None, 'coverage': round(ans / n, 3) if n else None}
    out = {'body': body, 'seed': seed, 'eval_seed': eval_seed, 'train_bundles': len(mem.bundles), **{k: rates(v) for k, v in res.items()},
           'needs': dict(needs.most_common(10)), 'held_truth': dict(held_truth), 'examples': examples}
    b, sg, lt = out['BUNDLE'], out['SINGLE'], out['LAST']
    checks = {'wrong_rate<=0.01': (b['wrong_rate'] or 0) <= 0.01, 'fewer_wrong_than_single': b['wrong'] < sg['wrong'],
              'not_more_wrong_than_last': b['wrong'] <= lt['wrong'], 'coverage>=0.80': (b['coverage'] or 0) >= 0.80}
    out['checks'] = checks
    out['verdict'] = 'PASS' if all(checks.values()) else (
        'PARTIAL' if checks['wrong_rate<=0.01'] and (b['coverage'] or 0) >= 0.60 else 'FAIL')
    return out


if __name__ == '__main__':
    body, seed, eval_seed, out_file = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])
    r = score(body, seed, eval_seed)
    out_file.write_text(json.dumps(r, indent=1, default=str), encoding='utf-8')
    print(json.dumps({k: v for k, v in r.items() if k != 'examples'}, indent=1, default=str))
