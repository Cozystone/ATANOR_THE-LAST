"""GEN3_BUNDLE6_PROTOCOL.md: act or leave, read from case bundles, on all five bodies. The three older bodies keep no
world log, so inside this process only their execute is wrapped to observe the whole world before and after each call
(the bodies, the learner and the teacher are unchanged and never see this log). Actions with a case whose effect lands
on an object outside the call's arguments are reported apart. Reader G: agreeing cases decide (BUNDLE), else the latest
value (LAST), the shape of the current learner.
Usage: python -m atanor_os.repr.run_act6 <body> <seed> <eval_seed> <out.json>
"""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from .bundles import Memory, build, controls, read
from .run_act import WORK, decide, last, worlds as worlds_new
from ..eval.tutor_life import DRIFT, body_spec, body_targets
from ..teach.tutor import Tutor

OLD = ('board', 'fs', 'view')
LOG = {'path': None}


def _wrap(cls):
    """Observe the whole world before and after a call; log the arguments' attributes and what else changed."""
    inner = cls.execute

    def execute(self, tool, args, capabilities, *a, **kw):
        before = self.observe(self.existing())
        res = inner(self, tool, args, capabilities, *a, **kw)
        if LOG['path'] is not None:
            after = self.observe(self.existing())
            seen = [x for x in args]
            elsewhere = sorted(o for o in set(before) | set(after) if o not in seen and before.get(o) != after.get(o))
            blank = {k: '-' for k in next(iter(before.values()), {})} | {'kind': 'absent'}
            row = {'event': 'act', 'tool': tool, 'args': list(args), 'ok': bool(res.get('ok')), 'error': res.get('error'),
                   'obs_before': {o: before.get(o, blank) for o in seen}, 'obs_after': {o: after.get(o, blank) for o in seen},
                   'elsewhere': elsewhere}
            with open(LOG['path'], 'a', encoding='utf-8') as f:
                f.write(json.dumps(row, sort_keys=True) + '\n')
        return res
    cls.execute = execute


def _install():
    from ..world.board_world import BoardWorkspace
    from ..world.fs_world import Workspace
    from ..world.view_world import ViewWorkspace
    for cls in (BoardWorkspace, Workspace, ViewWorkspace):
        _wrap(cls)


def course(body, seed, root):
    from ..teach.teacher_policy import Teacher
    base = Path(root) / f'{body}-s{seed}'
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    if body in OLD:
        LOG['path'] = base / 'obs_log.jsonl'
    Teacher(base / body, seed=seed, drift_from=10, body=body, mind=base / 'mind').run(25)
    LOG['path'] = None
    return (base / 'obs_log.jsonl') if body in OLD else (base / body / body / 'world_log.jsonl'), base / body


def worlds(body, root, eval_seed, drift):
    if body not in OLD:
        return worlds_new(body, root, eval_seed, drift)
    from ..eval.teacher_eval import world
    return [lambda: world(root, eval_seed, drift, body)]


def score(body, seed, eval_seed):
    root = WORK / f'act6-{body}-s{seed}'
    log, course_dir = course(body, seed, root)
    rows = read(log)
    mem = Memory(build(rows, source='T'), controls(rows))
    elsewhere = sorted({(r['tool'], tuple(a for a in r['args'][1:])) for r in rows if r.get('event') == 'act' and r.get('elsewhere')})
    away = {t for t, _ in elsewhere}                       # tools seen to change objects outside their arguments
    names = json.loads((course_dir / 'names.json').read_text(encoding='utf-8'))
    sels, acts = body_targets(body, names['seed'])
    spec, drift = body_spec(body), [DRIFT[body]]
    possible = getattr(spec, 'possible', lambda act, o, state: True)
    pairs = [(s, a) for s in sorted(int(k) for k in names['sel']) for a in sorted(int(k) for k in names['act'])]
    readers = ('BUNDLE', 'G', 'LEAVE', 'SINGLE', 'LAST')
    res = {r: Counter() for r in readers}
    apart = {r: Counter() for r in readers}
    hit = Counter()
    examples = []
    for w, mk in enumerate(worlds(body, root / 'eval', eval_seed, drift)):
        for s, a in pairs:
            h = mk()
            t = Tutor(h, spec, f'eval-{eval_seed}')
            t.start(sels[s], acts[a])
            st = h.observe(h.existing())
            blank = {k: '-' for k in next(iter(st.values()), {})} | {'kind': 'absent'}
            for o in sorted(t.truth):
                if o not in st:
                    continue
                truth = 'act' if possible(acts[a], o, t.before) and not spec.shows(acts[a], o, t.before) else 'leave'
                tool, args = spec.steps(acts[a], o, h.drift)
                known = {c for (tl, cs) in mem.by_action for c in cs if tl == tool}
                consts = [x for x in args if x in known]   # as bundles.build: constants never change; the case is about the
                obj = next((x for x in args if x not in known), o)   # first argument that does (a copy's new path, say)
                pre = st.get(obj) or blank
                b = mem.ask(pre, tool, consts)
                lt = last(mem, pre, tool, consts)
                for name, ans in (('BUNDLE', b), ('G', b if b['answer'] is not None else lt), ('LEAVE', b),
                                  ('SINGLE', mem.single(pre, tool, consts)), ('LAST', lt)):
                    d = decide(ans, pre)
                    if name == 'LEAVE' and d == 'hold':
                        d = 'leave'
                    out = 'held' if d == 'hold' else ('right' if d == truth else 'wrong')
                    (apart if tool in away else res)[name][out] += 1
                    if name == 'G' and truth == 'act' and tool not in away:
                        hit['n'] += 1
                        hit['acted'] += d == 'act'
                    if name == 'BUNDLE' and out == 'wrong' and tool not in away and len(examples) < 12:
                        examples.append({'world': w, 'tool': tool, 'consts': consts, 'object': obj, 'pre': pre, 'truth': truth, 'answer': b['answer']})
    shutil.rmtree(root / 'eval', ignore_errors=True)

    def rates(c):
        n = sum(c.values())
        ans = c['right'] + c['wrong']
        return {'n': n, 'right': c['right'], 'wrong': c['wrong'], 'held': c['held'],
                'wrong_rate': round(c['wrong'] / n, 4) if n else None, 'coverage': round(ans / n, 3) if n else None}
    out = {'body': body, 'seed': seed, 'eval_seed': eval_seed, 'train_bundles': len(mem.bundles),
           **{k: rates(v) for k, v in res.items()}, 'apart_tools': sorted(away), 'apart': {k: rates(v) for k, v in apart.items()},
           'g_act_hit': {'n': hit['n'], 'acted': hit['acted'], 'rate': round(hit['acted'] / hit['n'], 3) if hit['n'] else None},
           'examples': examples}
    b, g, sg, lt = out['BUNDLE'], out['G'], out['SINGLE'], out['LAST']
    rate = out['g_act_hit']['rate'] or 0
    out['checks'] = {'bundle_wrong_rate<=0.01': (b['wrong_rate'] or 0) <= 0.01, 'g_not_more_wrong_than_single_or_last':
                     g['wrong'] <= min(sg['wrong'], lt['wrong']), 'g_act_hit>=0.90': rate >= 0.90}
    out['verdict'] = 'PASS' if all(out['checks'].values()) else ('PARTIAL' if out['checks']['bundle_wrong_rate<=0.01'] else 'FAIL')
    return out


if __name__ == '__main__':
    _install()
    body, seed, eval_seed, out_file = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])
    r = score(body, seed, eval_seed)
    out_file.write_text(json.dumps(r, indent=1, default=str), encoding='utf-8')
    print(json.dumps({k: v for k, v in r.items() if k != 'examples'}, indent=1, default=str))
