"""A long life on the screen body, generated from a seed (evaluator side; never imported by agent/).

Every morning the screen restarts in a standard layout (two list panels, unfiltered, sorted by name) over a data
folder that keeps receiving files; the person gives 2-3 commands in varied English about panels (filter, sort,
group, open, close); every fourth day nobody is there to ask. Tasks are generated to be feasible from the
intended state sequence; if ATANOR left the screen in another state, the teacher reports a task as infeasible
and it is skipped. The mind's memory persists across days exactly as in the file life.
"""
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
PANELS = ('p1', 'p2', 'p3')
EXT_WORDS = {'csv': [['csv'], ['csv', 'files'], ['spreadsheets']], 'md': [['md'], ['markdown'], ['md', 'files']],
             'txt': [['txt'], ['text', 'files']], 'log': [['log'], ['logs'], ['log', 'files']], 'json': [['json'], ['json', 'files']],
             'all': [['all'], ['everything'], ['all', 'files']]}
KEY_WORDS = {'size': [['size']], 'name': [['name']], 'ext': [['ext'], ['extension']]}
GRP_WORDS = {'ext': [['ext'], ['extension']], 'none': [['none'], ['nothing']]}
VERBS = {'filter': [['filter', '{p}', 'to', '{v}'], ['show', 'only', '{v}', 'in', '{p}'], ['restrict', '{p}', 'to', '{v}'], ['narrow', '{p}', 'down', 'to', '{v}']],
         'sort': [['sort', '{p}', 'by', '{v}'], ['order', '{p}', 'by', '{v}'], ['arrange', '{p}', 'by', '{v}']],
         'group': [['group', '{p}', 'by', '{v}'], ['bunch', '{p}', 'by', '{v}'], ['cluster', '{p}', 'by', '{v}']],
         'open': [['open', '{p}'], ['bring', 'up', '{p}'], ['show', '{p}']],
         'close': [['close', '{p}'], ['dismiss', '{p}'], ['hide', '{p}']]}
POLITE = [[], [], ['please'], ['kindly']]
FUNCTION = {'to', 'by', 'in', 'only', 'up', 'down', 'please', 'kindly'}
START = {'p1': {'kind': 'panel', 'filter': 'all', 'sort': 'name', 'group': 'none'},
         'p2': {'kind': 'panel', 'filter': 'all', 'sort': 'name', 'group': 'none'}}


def _feasible(spec, tool, p, val):
    s = spec.get(p)
    if tool == 'open':
        return s is None
    if s is None or s['kind'] != 'panel':
        return False
    if tool == 'group' and val != 'none' and s['filter'] != 'all':
        return False
    if tool == 'filter':
        return s['filter'] != val
    if tool == 'sort':
        return s['sort'] != val
    if tool == 'group':
        return s['group'] != val
    return True


def _apply(spec, tool, p, val):
    if tool == 'open':
        spec[p] = {'kind': 'panel', 'filter': 'all', 'sort': 'name', 'group': 'none'}
    elif tool == 'close':
        spec.pop(p, None)
    else:
        spec[p][tool] = val


CHANGES = ['filter_retired', 'sort_retired']


def life(seed, days=30, drift=True):
    rng = random.Random(f'viewlife-{seed}')
    change_days = sorted(rng.sample(range(8, days), 2)) if drift and days > 10 else []
    changes = rng.sample(CHANGES, 2)
    out, cur = [], []
    for day in range(1, days + 1):
        if day in change_days:
            cur = cur + [changes[change_days.index(day)]]
        user = day <= 2 or day % 4 != 0
        spec = json.loads(json.dumps(START))
        tasks = []
        tries = 0
        while len(tasks) < rng.choice([2, 3]) and tries < 50:
            tries += 1
            tool = rng.choice(['filter', 'filter', 'sort', 'sort', 'group', 'open', 'close'])
            p = rng.choice(PANELS)
            if tool == 'filter':
                val, words = rng.choice([(e, w) for e in EXT_WORDS for w in EXT_WORDS[e]])
                vobj = f'ext:{val}'
            elif tool == 'sort':
                val, words = rng.choice([(k, w) for k in KEY_WORDS for w in KEY_WORDS[k]])
                vobj = f'key:{val}'
            elif tool == 'group':
                val, words = rng.choice([(g, w) for g in GRP_WORDS for w in GRP_WORDS[g]])
                vobj = f'grp:{val}'
            else:
                val, words, vobj = None, [], None
            if not _feasible(spec, tool, p, val):
                continue
            verb = rng.choice(VERBS[tool])
            toks = list(rng.choice(POLITE))
            for w in verb:
                if w == '{p}':
                    toks.append(p)
                elif w == '{v}':
                    toks += words
                else:
                    toks.append(w)
            sentence = ' '.join(toks)
            sentence = sentence[0].upper() + sentence[1:] + '.'
            tasks.append({'command': sentence, 'tool': tool, 'panel': p, 'value': vobj,
                          'phrases': {'verb': [w for w in verb if not w.startswith('{')], 'base': tool,
                                      'selector_synonym': [w for w in words if w not in (val, 'files')], 'function': sorted(FUNCTION)}})
            _apply(spec, tool, p, val)
        out.append({'day': day, 'user': user, 'drift': list(cur), 'tasks': tasks})
    return out


def run_day(cond, seed, day_no, root, days=30):
    from ..agent.life import Mind
    from ..teach.life_teacher import ViewTeacher
    from ..world.fs_world import Workspace
    from ..world.view_world import ViewWorkspace
    root = Path(root)
    day = life(seed, days)[day_no - 1]
    data = Workspace(root / 'data', create=not (root / 'data').exists())
    rng = random.Random(f'viewlife-{seed}-inflow-{day_no}')
    for i, ext in enumerate(('csv', 'md', 'txt', 'log', 'json')):
        (data.root / f'd{day_no}_{i}.{ext}').write_bytes(f'{day_no} {rng.random():.4f}\n'.encode())
    if (root / 'view').exists():
        shutil.rmtree(root / 'view')
    home = ViewWorkspace(root / 'view', data, spec=json.loads(json.dumps(START)))        # the screen restarts each morning
    home.drift = frozenset(day['drift'])
    if cond == 'FRESH' and (root / 'mind').exists():
        shutil.rmtree(root / 'mind')
    teacher = ViewTeacher(home)
    rows = []
    for k, task in enumerate(day['tasks']):
        spec = home._read()
        if not _feasible(spec, task['tool'], task['panel'], task['value'].split(':', 1)[1] if task['value'] else None):
            rows.append({'day': day_no, 'task': k, 'command': task['command'], 'tool': task['tool'], 'user': day['user'], 'drift': day['drift'],
                         'success': False, 'outcome': 'infeasible', 'agent': {}, 'help': {}, 'help_score': 0, 'counts': {}, 'seconds': 0.0})
            continue
        teacher.begin(task)
        h0, t0 = dict(teacher.help), time.time()
        mind = Mind(home, root / 'mind', root / 'lab', user=teacher if day['user'] else None, generalize=cond != 'CASE',
                    lexicon_mode='case' if cond == 'CASE' else 'general', seed=day_no * 10 + k)
        r = mind.do(task['command'], f'd{day_no}-t{k}')
        ok = teacher.judge()
        helped = {q: teacher.help[q] - h0.get(q, 0) for q in teacher.help if teacher.help[q] - h0.get(q, 0)}
        acted = r.get('achieved') is not None
        rows.append({'day': day_no, 'task': k, 'command': task['command'], 'tool': task['tool'], 'user': day['user'], 'drift': day['drift'],
                     'success': ok, 'outcome': 'success' if ok else ('wrong' if acted and r.get('achieved') is not False else 'held'),
                     'agent': r, 'help': helped,
                     'help_score': sum({'explain': 1, 'point': 1, 'check': 1, 'demonstrate': 2, 'demonstrate_goal': 3}.get(q, 0) * n
                                       for q, n in helped.items()),
                     'counts': dict(mind.counts), 'seconds': round(time.time() - t0, 2)})
    with open(root / 'days.jsonl', 'a', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + '\n')
    snap = root / 'snap' / f'd{day_no}'
    for part in ('view', 'mind'):
        if (root / part).exists():
            shutil.copytree(root / part, snap / part, dirs_exist_ok=True)
    return rows


def run(seed, out, conds=('LIFE', 'FRESH', 'CASE'), days=30):
    out = Path(out)
    for c in conds:
        root = out / c
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        for d in range(1, days + 1):
            subprocess.run([sys.executable, '-c', f'from atanor_os.eval.life_gen_view import run_day; run_day({c!r}, {seed}, {d}, {str(root)!r}, {days})'],
                           cwd=PKG.parent, check=True)
    return out
