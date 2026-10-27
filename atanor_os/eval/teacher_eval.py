"""Evaluation after a course of teaching (evaluator side; never seen by the teacher).

Takes the mind a course left (by the synthetic teacher, or by a fixed curriculum for comparison) and, on a COPY of it,
gives commands with nobody there, on a world of new cards from another seed, some days after the course:
  taught   a selection and an action that were taught together
  combo    a named selection with a named action never taught together
  english  sealed English forms (from a file outside the repository) for things that got English phrases
  unseen change  the stamp tool stops working (the course never had this); the same command twice on one mind copy:
           the first should fail without a wrong act, the second should change course (hold) rather than fail again
Every command runs on a fresh copy of the mind and the board, so one test cannot teach the next. What each name
means comes from names.json, the teaching side's own record of what it meant. Holding is not success.
Usage: python -m atanor_os.eval.teacher_eval <course_dir> <eval_seed> <out.json> [sealed:<path>]
"""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from .en_probe import DEV_FORMS, todo, words_of
from .tutor_life import DRIFT as BODY_DRIFT, FS_FOLDERS, body_spec, body_targets, day_inflow
from ..teach.tutor import Tutor

UNSEEN = {'board': ('stamp', 'stamp_retired'), 'fs': ('move', 'move_retired'), 'view': ('filter', 'filter_retired'),
          'desk': ('tag', 'tag_retired')}   # never in the course


def world(root, eval_seed, drift, body='board'):
    if root.exists():
        shutil.rmtree(root)
    if body == 'board':
        from ..world.board_world import BoardWorkspace
        home = BoardWorkspace(root)
        for d in range(40, 48):
            home.add_cards({f'e{d}{k}': c for k, c in day_inflow(eval_seed, d).items()})
    elif body == 'view':
        from .tutor_life import make_home
        home = make_home('view', root, eval_seed, 40)
    elif body == 'desk':
        from ..world.desk_world import DeskWorkspace
        from .tutor_life import desk_inflow
        home = DeskWorkspace(root, seed=eval_seed)
        for d in range(40, 45):
            home.add_items(desk_inflow(eval_seed, d))
        home.tick()                                        # some outside changes before the day starts
    else:
        from ..world.fs_world import Workspace
        from .life_gen import inflow as file_inflow
        home = Workspace(root)
        for d in FS_FOLDERS:
            (home.root / d).mkdir()
        for d in (40, 41, 42):
            file_inflow(home, d, eval_seed)
    home.drift = frozenset(drift)
    return home


def part_held(t, res):
    """GEN2_H3_PROTOCOL.md: the learner withheld some meant objects and was right on all it did (not wrong, not success)."""
    return bool(res.get('withheld')) and t.judge(ignore=res['withheld'])


def evaluate(course, eval_seed, out_file, sealed=None):
    from ..agent.learners import make as Grounder         # the current learner, or the frozen copy (ATANOR_LEARNER)
    course, out_file = Path(course), Path(out_file)
    names = json.loads((course / 'names.json').read_text(encoding='utf-8'))
    body = names.get('body', 'board')
    mind_dir = Path(names['mind']) if names.get('mind') else course / 'mind'
    sels, acts = body_targets(body, names['seed'])         # the meanings the teaching side gave its names
    spec, drift = body_spec(body), [BODY_DRIFT[body]]
    unseen_tool, unseen_drift = UNSEEN[body]
    log = [json.loads(l) for l in (course / 'log.jsonl').read_text(encoding='utf-8').splitlines()]
    tlog = course / 'teacher_log.jsonl'
    pairs_taught = set()
    if tlog.exists():
        for r in map(json.loads, tlog.read_text(encoding='utf-8').splitlines()):
            if r['activity'] == 'lesson' and r.get('outcome') == 'success':
                pairs_taught.add((sels.index(r['sel']), acts.index(r['act'])))
    else:
        for r in log:
            if r['event'] == 'lesson' and r.get('named'):
                sym_s, sym_a = r['named'].get('selection'), r['named'].get('action')
                s = next((int(k) for k, v in names['sel'].items() if v == sym_s), None)
                a = next((int(k) for k, v in names['act'].items() if v == sym_a), None)
                if s is not None and a is not None:
                    pairs_taught.add((s, a))
    work = Path(__file__).resolve().parents[3].parent / 'probe-work' / out_file.stem
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    forms = json.loads(Path(sealed).read_text(encoding='utf-8'))['forms'] if sealed else DEV_FORMS   # dev forms only in development
    rows = []
    for s in sorted(int(k) for k in names['sel']):
        for a in sorted(int(k) for k in names['act']):
            base = world(work / 'b', eval_seed, drift, body)
            t0 = Tutor(base, spec, f'eval-{eval_seed}')
            t0.start(sels[s], acts[a])
            if not todo(spec, base, t0, acts[a]):
                continue
            tests = [('taught' if (s, a) in pairs_taught else 'combo', [names['act'][str(a)], names['sel'][str(s)]])]
            if s in names['en_sel'] and a in names['en_act']:
                tests += [(f'english:{f}', words_of(form, sels[s], acts[a])) for f, form in forms.items()]
            for kind, words in tests:
                h = world(work / 'b', eval_seed, drift, body)
                if (work / 'm').exists():
                    shutil.rmtree(work / 'm')
                shutil.copytree(mind_dir, work / 'm')
                t = Tutor(h, spec, f'eval-{eval_seed}')
                t.start(sels[s], acts[a])
                res = Grounder(h, work / 'm', person=None, source='evaluator', caps={c: True for c in set(getattr(h, 'CAPABILITY', {}).values())}).obey(words)
                ok = t.judge()
                rows.append({'sel': s, 'act': a, 'kind': kind, 'why': res.get('why'),
                             'outcome': 'success' if ok and res.get('ok') else ('part-held' if part_held(t, res) else
                                                                               ('wrong' if res.get('acted') else
                                                                                ('missed' if res.get('ok') else 'held')))})
    revision = []                                          # a world change the course never had: one tool stops
    for s in sorted(int(k) for k in names['sel']):
        for a in sorted(int(k) for k in names['act']):
            if acts[a]['tool'] != unseen_tool:
                continue
            h = world(work / 'b', eval_seed, list(drift) + [unseen_drift], body)
            t = Tutor(h, spec, f'eval-{eval_seed}')
            t.start(sels[s], acts[a])
            if not todo(spec, h, t, acts[a]):
                continue
            if (work / 'm').exists():
                shutil.rmtree(work / 'm')
            shutil.copytree(mind_dir, work / 'm')
            seq = []
            for _ in range(2):                             # the same mind twice: does the failure change what it does next?
                t.start(sels[s], acts[a])
                res = Grounder(h, work / 'm', person=None, source='evaluator', caps={c: True for c in set(getattr(h, 'CAPABILITY', {}).values())}).obey([names['act'][str(a)], names['sel'][str(s)]])
                ok = t.judge()
                seq.append('success' if ok and res.get('ok') else ('tool_failed' if res.get('failed') else
                                                                   ('part-held' if part_held(t, res) else
                                                                    ('wrong' if res.get('acted') else ('missed' if res.get('ok') else 'held:' + str(res.get('why')))))))
            revision.append({'sel': s, 'act': a, 'first': seq[0], 'second': seq[1]})
    oracle = []                                            # knows the answer: the right tool calls, done directly
    for s in sorted(int(k) for k in names['sel']):
        for a in sorted(int(k) for k in names['act']):
            h = world(work / 'b', eval_seed, drift, body)
            t = Tutor(h, spec, f'eval-{eval_seed}')
            t.start(sels[s], acts[a])
            rest = todo(spec, h, t, acts[a])
            if not rest:
                continue
            for o in rest:
                tool, args = spec.steps(acts[a], o, h.drift)
                try:
                    h.execute(tool, args, {c: True for c in set(getattr(h, 'CAPABILITY', {}).values())})
                except ValueError:
                    pass
            oracle.append({'sel': s, 'act': a, 'outcome': 'success' if t.judge() else 'fail'})
    delayed = []                                           # desk only: the outcome of send comes later
    if body == 'desk':
        for s in sorted(int(k) for k in names['sel']):
            for a in sorted(int(k) for k in names['act']):
                if acts[a]['tool'] != 'send':
                    continue
                h = world(work / 'b', eval_seed, drift, body)
                t = Tutor(h, spec, f'eval-{eval_seed}')
                t.start(sels[s], acts[a])
                if not todo(spec, h, t, acts[a]):
                    continue
                if (work / 'm').exists():
                    shutil.rmtree(work / 'm')
                shutil.copytree(mind_dir, work / 'm')
                words = [names['act'][str(a)], names['sel'][str(s)]]
                truth = list(t.truth)
                Grounder(h, work / 'm', person=None, source='evaluator', caps={c: True for c in set(getattr(h, 'CAPABILITY', {}).values())}).obey(words)
                h.tick()
                st = h.observe(h.existing())
                carried = all((st.get(o) or {}).get('status') in ('queued', 'sent', 'failed') for o in truth)
                n0 = sum(1 for _ in open(h.root / 'world_log.jsonl', encoding='utf-8'))
                Grounder(h, work / 'm', person=None, source='evaluator', caps={c: True for c in set(getattr(h, 'CAPABILITY', {}).values())}).obey(words)       # the same command again
                again = [json.loads(l) for l in open(h.root / 'world_log.jsonl', encoding='utf-8')][n0:]
                resend = sum(1 for r in again if r.get('event') == 'act' and r.get('tool') == 'send' and r['args'][0] in truth)
                delayed.append({'sel': s, 'act': a, 'carried_out': carried, 'resend_attempts': resend})
    double = []                                            # file body only: two tools the course never saw stop at once
    if body == 'fs':
        two = ['move_retired', 'delete_retired']
        if (work / 'm').exists():
            shutil.rmtree(work / 'm')
        shutil.copytree(mind_dir, work / 'm')              # one mind for the whole sequence, as a day alone
        for s in sorted(int(k) for k in names['sel']):
            for a in sorted(int(k) for k in names['act']):
                if acts[a]['tool'] not in ('move', 'delete'):
                    continue
                h = world(work / 'b', eval_seed, list(drift) + two, body)
                t = Tutor(h, spec, f'eval-{eval_seed}')
                t.start(sels[s], acts[a])
                if not todo(spec, h, t, acts[a]):
                    continue
                res = Grounder(h, work / 'm', person=None, source='evaluator', caps={c: True for c in set(getattr(h, 'CAPABILITY', {}).values())}).obey([names['act'][str(a)], names['sel'][str(s)]])
                ok = t.judge()
                double.append({'sel': s, 'act': a, 'tool': acts[a]['tool'], 'outcome': 'success' if ok and res.get('ok') else
                               ('tool_failed' if res.get('failed') else ('wrong' if res.get('acted') else ('missed' if res.get('ok') else 'held:' + str(res.get('why')))))})
    shutil.rmtree(work)
    summ = {}
    for r in rows:
        k = r['kind'].split(':')[0]
        summ.setdefault(k, Counter())[r['outcome']] += 1
    out = {'course': str(course), 'eval_seed': eval_seed, 'summary': {k: dict(v) for k, v in summ.items()},
           'held_why': dict(Counter(r['why'] for r in rows if r['outcome'] == 'held')), 'rows': rows,
           'unseen_change': {'n': len(revision), 'first': dict(Counter(r['first'] for r in revision)),
                             'second': dict(Counter(r['second'] for r in revision)), 'rows': revision},
           'double_change': {'n': len(double), 'outcomes': dict(Counter(r['outcome'] for r in double)), 'rows': double},
           'oracle': {'n': len(oracle), 'success': sum(r['outcome'] == 'success' for r in oracle), 'rows': oracle},
           'delayed': {'n': len(delayed), 'carried_out': sum(r['carried_out'] for r in delayed),
                       'resend_attempts': sum(r['resend_attempts'] for r in delayed), 'rows': delayed}}
    out_file.write_text(json.dumps(out, indent=1), encoding='utf-8')
    return out


if __name__ == '__main__':
    sealed = next((a[7:] for a in sys.argv[4:] if a.startswith('sealed:')), None)
    r = evaluate(sys.argv[1], int(sys.argv[2]), sys.argv[3], sealed)
    print(json.dumps({k: r[k] for k in ('summary', 'held_why')} | {'unseen_change': {k: v for k, v in r['unseen_change'].items() if k != 'rows'}}, indent=1))
