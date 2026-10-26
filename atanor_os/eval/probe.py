"""Metamorphic probes of a lived mind (evaluator side; never imported by agent/, never written into a life's memory).

After a life, the evaluator copies the mind and the home and asks probe commands whose meaning it knows. Each probe
meaning is posed in variants that must not change the outcome:
  surface : the TRAIN expression (forms the person used in lives) vs a SEALED expression (synonyms and sentence frames
            never used in any life: eval/sealed.py and life_gen_board.SEALED)
  objects : always on newly arrived objects with unseen names
  order   : the same probes in another order (each probe starts from the same copied mind, so order only matters
            through the home state; reported as an invariance check)
Every probe runs once alone (no person) and once with the person (help counted), each on fresh copies, so nothing a
probe teaches reaches the next probe or the life.

Failures are classified automatically from the probe's own log:
  perception | grounding (word-object link) | structure | tool_model | planning | safety_hold | evaluator_env
and a surface-bound signal is raised when a meaning succeeds in its TRAIN form but not in its SEALED form.
"""
import json
import random
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from .sealed import FS_SEALED

CATS = ('perception', 'grounding', 'structure', 'tool_model', 'planning', 'safety_hold', 'evaluator_env')


def classify(row, events):
    """One failed probe -> a failure class, from what the mind logged while it worked on it."""
    if row.get('error'):
        return 'evaluator_env'
    if row.get('truth_empty'):
        return 'evaluator_env'
    ev = [e.get('event') for e in events]
    if row['outcome'] == 'wrong':
        return 'grounding' if row.get('selection_ok') is False else 'structure'
    if 'refuse_unknown' in ev:
        return 'grounding'
    if 'refuse_incomplete' in ev or 'refuse_ambiguous' in ev:
        return 'structure'
    if any(x in ev for x in ('refuse_weak', 'refuse_irreversible')):
        return 'safety_hold'
    if 'plan_budget' in ev:
        return 'planning'
    if any(x in ev for x in ('stuck', 'experiment_budget_spent')) or row.get('achieved') is False:
        return 'tool_model'
    if row.get('missing_objects'):
        return 'perception'
    return 'structure'


# ---------------------------------------------------------------- bodies
class FsProbes:
    BODY = 'fs'
    EXTS = ['csv', 'log', 'txt', 'json', 'md']

    def __init__(self, life_mod):
        self.L = life_mod

    def tasks(self, rng, n):
        """n probe meanings, each as a TRAIN and a SEALED command."""
        out = []
        for i in range(n):
            tool = rng.choice(['copy', 'move', 'delete'])
            ext = rng.choice(self.EXTS)
            dest = None if tool == 'delete' else f'probe{i}box'
            forms = {}
            for form, verbs, sels, dests in (('train', self.L.VERBS, self.L.SELECT, self.L.DEST),
                                             ('sealed', FS_SEALED['verbs'], FS_SEALED['select'], FS_SEALED['dest'])):
                words = rng.choice(verbs[tool]) + ['the'] + rng.choice(sels[ext])
                if dest:
                    words += [w.replace('{d}', dest) for w in rng.choice(dests)]
                s = ' '.join(words)
                forms[form] = s[0].upper() + s[1:] + '.'
            out.append({'tool': tool, 'ext': ext, 'dest': dest, 'forms': forms})
        return out

    def setup(self, life_root, work, i, task):
        shutil.copytree(Path(life_root) / 'home', work / 'home')
        shutil.copytree(Path(life_root) / 'mind', work / 'mind')
        from ..world.fs_world import Workspace
        home = Workspace(work / 'home', create=False)
        for j, ext in enumerate(self.EXTS):                       # newly arrived objects with unseen names
            for k in range(2):
                (home.root / f'zz{i}{j}{k}new.{ext}').write_bytes(f'probe {i} {j} {k}\n'.encode())
        return home

    def teacher(self, home, task, command):
        from ..teach.life_teacher import Teacher
        t = Teacher(home)
        t.begin({'command': command, 'tool': task['tool'], 'ext': task['ext'], 'dest': task['dest'], 'phrases': None})
        return t


class BoardProbes:
    BODY = 'board'

    def __init__(self, gen):
        self.G = gen

    def tasks(self, rng, n):
        out = []
        for i in range(n):
            tool = rng.choice(['lodge', 'stamp', 'lift', 'unlodge', 'scrap'])
            out.append({'tool': tool, 'i': i, 'rng_state': rng.random()})
        return out

    def setup(self, life_root, work, i, task):
        shutil.copytree(Path(life_root) / 'board', work / 'board')
        shutil.copytree(Path(life_root) / 'mind', work / 'mind')
        from ..world.board_world import BoardWorkspace
        home = BoardWorkspace(work / 'board', create=False)
        r = random.Random(f'probe-cards-{i}')
        home.add_cards({f'z{i}{k}': {'mark': r.choice(self.G.MARKS)} for k in range(6)})
        cards = home._read()['cards']
        new = {c: v for c, v in cards.items() if c.startswith(f'z{i}')}
        if task['tool'] in ('unlodge', 'lift'):                     # these need cards in trays: place the new ones first
            for c in new:
                cards[c]['tray'] = r.choice(sorted(self.G.TRAYS))
            home._write({'cards': cards})
        sim = {c: {'mark': v['mark'], 'tray': self.G.TRAYS.get(v['tray'], '-'), 'level': v['level']}
               for c, v in home._read()['cards'].items() if c.startswith(f'z{i}')}
        forms = {}
        for form, pools in (('train', self.G.TRAIN), ('sealed', self.G.SEALED)):
            t = None
            for attempt in range(40):
                t = self.G.make_task(random.Random(f"{task['rng_state']}-{attempt}"), sim, task['tool'], pools)   # same draws: same meaning
                if t:
                    break
            forms[form] = t
        if forms['train'] and forms['sealed']:
            assert (forms['train']['select'], forms['train']['second']) == (forms['sealed']['select'], forms['sealed']['second'])
        task['made'] = forms
        return home

    def teacher(self, home, task, command, form):
        from ..teach.life_teacher import BoardTeacher
        t = BoardTeacher(home)
        t.begin(task['made'][form])
        return t


# ---------------------------------------------------------------- running probes
def run_probes(body, life_root, out_file, seed, n=24, drift=()):
    """drift: the world rules in force at the end of the life (the probes live in the same world)."""
    from ..agent.life import Mind
    rng = random.Random(f'probe-{body}-{seed}')
    if body == 'fs':
        from . import life_gen
        P = FsProbes(life_gen)
    else:
        from . import life_gen_board
        P = BoardProbes(life_gen_board)
    rows = []
    tasks = P.tasks(rng, n)
    order = list(range(n))
    rng.shuffle(order)                                              # 'order' variant: probes posed in a shuffled order
    for i in order:
        task = tasks[i]
        for form in ('train', 'sealed'):
            for with_person in (False, True):
                work = Path(tempfile.mkdtemp(prefix='probe'))
                row = {'probe': i, 'form': form, 'person': with_person, 'tool': task['tool']}
                try:
                    home = P.setup(life_root, work, i, task)
                    home.drift = frozenset(drift)
                    if body == 'fs':
                        command = task['forms'][form]
                        teacher = P.teacher(home, task, command)
                    else:
                        made = task['made'][form]
                        if made is None:
                            row.update(truth_empty=True, outcome='skipped', success=False)
                            rows.append(row)
                            continue
                        command = made['command']
                        teacher = P.teacher(home, task, command, form)
                    row['command'] = command
                    if not teacher.truth:
                        row.update(truth_empty=True, outcome='skipped', success=False)
                        rows.append(row)
                        continue
                    h0 = dict(teacher.help)
                    mind = Mind(home, work / 'mind', work / 'lab', user=teacher if with_person else None)
                    n0 = sum(1 for _ in open(work / 'mind' / 'log.jsonl', encoding='utf-8')) if (work / 'mind' / 'log.jsonl').exists() else 0
                    r = mind.do(command, f'probe-{i}-{form}')
                    ok = teacher.judge()
                    lines = (work / 'mind' / 'log.jsonl').read_text(encoding='utf-8').splitlines()[n0:] if (work / 'mind' / 'log.jsonl').exists() else []
                    events = [json.loads(l) for l in lines]
                    t_json = json.loads((work / 'mind' / 'task.json').read_text(encoding='utf-8')) if (work / 'mind' / 'task.json').exists() else {}
                    sel = sorted((t_json.get('interp') or {}).get('selected', []))
                    acted = r.get('achieved') is not None
                    row.update(success=ok, achieved=r.get('achieved'),
                               outcome='success' if ok else ('wrong' if acted and r.get('achieved') is not False else 'held'),
                               help={q: teacher.help[q] - h0.get(q, 0) for q in teacher.help if teacher.help[q] - h0.get(q, 0)},
                               selection_ok=(sel == teacher.truth) if sel else None)
                    if not ok:
                        row['failure'] = classify(row, events)
                except Exception as exc:                            # an evaluator or environment defect, never hidden
                    row.update(outcome='error', success=False, error=repr(exc)[:300], failure='evaluator_env')
                finally:
                    shutil.rmtree(work, ignore_errors=True)
                rows.append(row)
    Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + '\n')
    return summarize(rows)


def summarize(rows):
    s = {}
    for form in ('train', 'sealed'):
        alone = [r for r in rows if r['form'] == form and not r['person'] and r['outcome'] != 'skipped']
        pers = [r for r in rows if r['form'] == form and r['person'] and r['outcome'] != 'skipped']
        s[form] = {'alone_success': f"{sum(r['success'] for r in alone)}/{len(alone)}",
                   'alone_wrong': sum(r['outcome'] == 'wrong' for r in alone),
                   'alone_held': sum(r['outcome'] == 'held' for r in alone),
                   'person_success': f"{sum(r['success'] for r in pers)}/{len(pers)}",
                   'person_help': sum(sum(v for k, v in r.get('help', {}).items() if k != 'confirm') for r in pers),
                   'failures': dict(Counter(r.get('failure') for r in alone if not r['success']))}
    by = defaultdict(dict)
    for r in rows:
        if not r['person'] and r['outcome'] != 'skipped':
            by[r['probe']][r['form']] = r['success']
    s['surface_bound'] = sum(1 for v in by.values() if v.get('train') and v.get('sealed') is False)
    s['sealed_only'] = sum(1 for v in by.values() if v.get('sealed') and v.get('train') is False)
    s['pairs'] = sum(1 for v in by.values() if 'train' in v and 'sealed' in v)
    return s
