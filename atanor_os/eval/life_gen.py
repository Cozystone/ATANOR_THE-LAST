"""A long life in one home, generated from a seed (evaluator side; never imported by agent/).

Every day new files arrive; the person gives 2-3 commands in varied English; some days nobody is there to ask;
rarely the world changes (a tool stops working and a new one with an opaque name appears). Truth stays with the
person (teacher); ATANOR only gets the sentence, its observations and the answers it asks for.
Development uses seed 1; every code version is evaluated once on a fresh seed.
"""
import json
import random
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
EXTS = ['csv', 'log', 'txt', 'json', 'md']
VERBS = {'move': [['move'], ['relocate'], ['shift'], ['transfer'], ['put', 'away'], ['carry']],
         'copy': [['copy'], ['duplicate'], ['clone'], ['make', 'a', 'copy', 'of'], ['back', 'up'], ['replicate']],
         'delete': [['delete'], ['remove'], ['discard'], ['erase'], ['get', 'rid', 'of'], ['throw', 'away']]}
SELECT = {'csv': [['csv', 'files'], ['spreadsheets'], ['comma', 'separated', 'files']],
          'log': [['log', 'files'], ['logs']],
          'txt': [['txt', 'files'], ['text', 'files']],
          'json': [['json', 'files'], ['json', 'documents']],
          'md': [['md', 'files'], ['markdown', 'files']]}
QUANT = [['the'], ['all', 'the'], ['all'], ['every']]
DEST = [['into', 'a', 'folder', 'called', '{d}'], ['to', 'a', 'folder', 'named', '{d}'], ['into', 'a', 'new', 'folder', 'named', '{d}'],
        ['into', 'the', '{d}', 'folder'], ['into', '{d}']]
POLITE = [[], [], ['please'], ['kindly']]
DEST_NAMES = ['acorn', 'basin', 'cellar', 'dune', 'eyrie', 'forge', 'grotto', 'hangar', 'igloo', 'jetty', 'kiosk', 'larder', 'manor',
              'nest', 'oasis', 'pantry', 'quay', 'roost', 'shed', 'tower', 'vault', 'wharf', 'yard', 'zenith', 'annex', 'bunker',
              'cabin', 'depot', 'estate', 'fort', 'garret', 'hut', 'inlet', 'keep', 'lodge', 'mill', 'niche', 'outpost', 'pier',
              'ranch', 'silo', 'turret', 'villa', 'warren', 'bay', 'cove', 'den', 'loft', 'nook', 'attic', 'barn', 'crypt']
CHANGES = ['copy_retired', 'delete_retired', 'move_retired']
FUNCTION = {'into', 'to', 'a', 'folder', 'called', 'named', 'new', 'the', 'please', 'kindly', 'all', 'every'}
NAMES = ['amber', 'birch', 'cobalt', 'dahlia', 'ember', 'fennel', 'garnet', 'heron', 'indigo', 'juniper', 'kestrel', 'lilac',
         'marigold', 'nutmeg', 'olive', 'poppy', 'quill', 'russet', 'saffron', 'thistle', 'umber', 'violet', 'walnut', 'yarrow']


def life(seed, days=30, compose=False):
    """compose: from day 6, about a third of the commands name two kinds of files at once ('the csv and md files'),
    a combination of known parts never shown together before. Off by default (earlier lives are unchanged)."""
    rng = random.Random(f'life-{seed}')
    dests = DEST_NAMES[:]
    rng.shuffle(dests)
    change_days = sorted(rng.sample(range(8, days), 2))
    changes = rng.sample(CHANGES, 2)
    out, drift, used = [], [], set()
    for day in range(1, days + 1):
        if day in change_days:
            drift = drift + [changes[change_days.index(day)]]
        user = day <= 2 or day % 4 != 0
        tasks = []
        for ext in rng.sample(EXTS, rng.choice([2, 3])):
            form = None
            tool = rng.choice(list(VERBS))
            verb = rng.choice(VERBS[tool])
            sel = rng.choice(SELECT[ext])
            quant = rng.choice(QUANT) if sel != ['spreadsheets'] or True else []
            syn = {w: ext for w in sel if w not in (ext, 'files', 'file')}
            if compose == 'sequence' and day >= 11 and tool in ('copy', 'move') and rng.random() < 0.5:
                tool = 'move'                                  # 'copy ... and then delete them': the end state of a move
                verb = rng.choice(VERBS['copy'])
                tail = rng.choice([['and', 'then', 'delete', 'them'], ['and', 'then', 'remove', 'the', 'originals'],
                                   ['and', 'afterwards', 'erase', 'the', 'originals'], ['then', 'discard', 'them']])
                form = 'sequence'
            elif compose == 'transfer' and day >= 16 and rng.random() < 0.45:
                form = rng.choice(['three', 'repeat', 'plus', 'as well as', 'along with'])
                others = rng.sample([e for e in EXTS if e != ext], 2 if form == 'three' else 1)
                sels = [sel] + [rng.choice(SELECT[e]) for e in others]
                for e, sl in zip(others, sels[1:]):
                    syn.update({w: e for w in sl if w not in (e, 'files', 'file')})
                if quant == ['every']:
                    quant = ['all', 'the']
                if form == 'three':                          # 'the csv, md and txt files' (punctuation is not a token)
                    strip = all(x[-1] == 'files' for x in sels)
                    parts = [x[:-1] if strip and i < 2 else x for i, x in enumerate(sels)]
                    sel = parts[0] + parts[1] + ['and'] + parts[2]
                elif form == 'repeat':                       # 'the csv files and the md files'
                    sel = sels[0] + ['and'] + quant + sels[1]
                else:                                        # joining words never heard before
                    sel = sels[0] + form.split(' ') + sels[1]
                ext = [ext] + others
            elif compose and day >= 6 and rng.random() < 0.35:
                ext2 = rng.choice([e for e in EXTS if e != ext])
                sel2 = rng.choice(SELECT[ext2])
                syn.update({w: ext2 for w in sel2 if w not in (ext2, 'files', 'file')})
                sel = (sel[:-1] if sel[-1] == 'files' and sel2[-1] == 'files' else sel) + ['and'] + sel2
                quant = [q for q in [quant] if q != ['every']][0] if quant != ['every'] else ['all', 'the']
                ext = [ext, ext2]
                form = 'and'
            words = list(rng.choice(POLITE)) + verb + quant + (sel[:-1] + ['file'] if quant == ['every'] and sel[-1] == 'files' else sel)
            d = None
            if tool != 'delete':
                if not dests:                                  # pool used up: further names (seed 1 never reaches this)
                    dests = [f'{a}{b}' for a in ('north', 'south', 'east', 'west') for b in DEST_NAMES if f'{a}{b}' not in used]
                    rng.shuffle(dests)
                d = dests.pop()
                used.add(d)
                words += [w.replace('{d}', d) for w in rng.choice(DEST)]
                if form == 'sequence':
                    words += tail
            sentence = ' '.join(words)
            sentence = sentence[0].upper() + sentence[1:] + '.'
            tasks.append({'command': sentence, 'tool': tool, 'ext': ext, 'dest': d, 'form': form,
                          'phrases': {'verb': verb, 'base': 'copy' if form == 'sequence' else tool,
                                      'explain_map': ({w: ('delete' if w in ('delete', 'remove', 'erase', 'discard') else '') for w in tail}
                                                      if form == 'sequence' else {}), 'selector_synonym': sorted(syn),
                                      'function': sorted(FUNCTION), 'syn_ext': syn}})
        out.append({'day': day, 'user': user, 'drift': list(drift), 'tasks': tasks})
    return out


def inflow(home, day, seed):
    rng = random.Random(f'life-{seed}-inflow-{day}')
    names = rng.sample(NAMES, 10)
    for i, ext in enumerate(EXTS):
        for j in range(2):
            p = home.root / f'{names[2 * i + j]}{day}.{ext}'
            p.write_bytes(f'{p.stem} {rng.random():.6f}\n'.encode())


def run_day(cond, seed, day_no, root, days=30, compose=False):
    from ..agent.life import Mind
    from ..teach.life_teacher import Teacher
    from ..world.fs_world import Workspace
    from .life import hand_do
    root = Path(root)
    day = life(seed, days, compose)[day_no - 1]
    home = Workspace(root / 'home', create=not (root / 'home').exists())
    home.drift = frozenset(day['drift'])
    if cond == 'FRESH' and (root / 'mind').exists():
        shutil.rmtree(root / 'mind')
    inflow(home, day_no, seed)
    teacher = Teacher(home)
    rows = []
    for k, task in enumerate(day['tasks']):
        teacher.begin(task)
        h0, t0 = dict(teacher.help), time.time()
        if cond == 'HAND':
            r, counts = hand_do(home, task['command']), {}
        else:
            mind = Mind(home, root / 'mind', root / 'lab', user=teacher if day['user'] else None, generalize=cond != 'CASE',
                        lexicon_mode='case' if cond == 'CASE' else 'general', seed=day_no * 10 + k)
            r = mind.do(task['command'], f'd{day_no}-t{k}')
            counts = dict(mind.counts)
        ok = teacher.judge()
        helped = {q: teacher.help[q] - h0.get(q, 0) for q in teacher.help if teacher.help[q] - h0.get(q, 0)}
        acted = r.get('achieved') is not None or cond == 'HAND' and r.get('ok')
        rows.append({'day': day_no, 'task': k, 'command': task['command'], 'tool': task['tool'], 'ext': task['ext'],
                     'user': day['user'], 'drift': day['drift'], 'success': ok,
                     'outcome': 'success' if ok else ('wrong' if acted and r.get('achieved') is not False else 'held'),
                     'agent': r, 'help': helped,
                     'help_score': sum({'explain': 1, 'point': 1, 'check': 1, 'demonstrate': 2, 'demonstrate_goal': 3}.get(q, 0) * n
                                       for q, n in helped.items()),
                     'counts': counts, 'seconds': round(time.time() - t0, 2)})
    # before the person leaves, the core brings up what it left unfinished on earlier days
    if cond != 'HAND' and day['user']:
        resume_goals(root, seed, days, day_no, teacher, lambda k: Mind(home, root / 'mind', root / 'lab', user=teacher, generalize=cond != 'CASE',
                     lexicon_mode='case' if cond == 'CASE' else 'general', seed=day_no * 10 + 9 - k), lambda sd, dd: life(sd, dd, compose))
    with open(root / 'days.jsonl', 'a', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + '\n')
    snap = root / 'snap' / f'd{day_no}'                      # end-of-day snapshot (debugging only; never read by the mind)
    for part in ('home', 'mind'):
        if (root / part).exists():
            shutil.copytree(root / part, snap / part, dirs_exist_ok=True)
    return rows


HELP_SCORE = {'explain': 1, 'point': 1, 'check': 1, 'recall': 1, 'demonstrate': 2, 'demonstrate_goal': 3}


def resume_goals(root, seed, days, day_no, teacher, make_mind, life_fn, feasible=None):
    """The person is here: the core brings up the goals it left unfinished. Their rows go to resumed.jsonl, apart from
    the day's tasks (a held task stays held in days.jsonl)."""
    L = life_fn(seed, days)
    out = []
    for k, g in enumerate(make_mind(0).pending_goals()):
        d0, t0_ = (int(x[1:]) for x in g['id'].split('-'))
        task = L[d0 - 1]['tasks'][t0_]
        mind = make_mind(k)
        if feasible is not None and not feasible(task):
            mind._set_pending([x for x in mind.pending_goals() if x['id'] != g['id']])
            out.append({'day': day_no, 'goal': g['id'], 'delay': day_no - d0, 'why': g['why'], 'tool': task['tool'], 'outcome': 'infeasible',
                        'success': False, 'help': {}, 'help_score': 0})
            continue
        teacher.begin(task)
        h0, t0 = dict(teacher.help), time.time()
        r = mind.resume(g)
        ok = r is not None and teacher.judge()
        helped = {q: teacher.help[q] - h0.get(q, 0) for q in teacher.help if teacher.help[q] - h0.get(q, 0)}
        outcome = 'no longer wanted' if r is None else 'success' if ok else (
            'wrong' if r.get('achieved') is not None and r.get('achieved') is not False else 'held')
        out.append({'day': day_no, 'goal': g['id'], 'delay': day_no - d0, 'why': g['why'], 'command': g['command'], 'tool': task['tool'],
                    'outcome': outcome, 'success': ok, 'agent': r, 'help': helped,
                    'help_score': sum(HELP_SCORE.get(q, 0) * n for q, n in helped.items()), 'counts': dict(mind.counts),
                    'seconds': round(time.time() - t0, 2)})
    if out:
        with open(Path(root) / 'resumed.jsonl', 'a', encoding='utf-8') as f:
            for r in out:
                f.write(json.dumps(r, default=str) + '\n')
    return out


def run(seed, out, conds=('LIFE', 'FRESH', 'CASE', 'HAND'), days=30, compose=False):
    out = Path(out)
    for c in conds:
        root = out / c
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        for d in range(1, days + 1):
            subprocess.run([sys.executable, '-c', f'from atanor_os.eval.life_gen import run_day; run_day({c!r}, {seed}, {d}, {str(root)!r}, {days}, {compose!r})'],
                           cwd=PKG.parent, check=True)
    return curves(out, conds)


def curves(out, conds=('LIFE', 'FRESH', 'CASE', 'HAND')):
    out = Path(out)
    res = {}
    for c in conds:
        rows = [json.loads(l) for l in (out / c / 'days.jsonl').read_text(encoding='utf-8').splitlines()]
        weeks = {}
        for r in rows:
            w = (r['day'] - 1) // 7 + 1
            x = weeks.setdefault(w, Counter())
            x['tasks'] += 1
            x[r['outcome']] += 1
            x['help'] += r['help_score']
            x['lab'] += r['counts'].get('lab_actions', 0)
            x['no_user_tasks'] += int(not r['user'])
            x['no_user_success'] += int(not r['user'] and r['success'])
        res[c] = {w: dict(v) for w, v in sorted(weeks.items())}
    (out / 'curves.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    return res
