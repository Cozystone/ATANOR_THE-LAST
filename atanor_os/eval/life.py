"""The living scene: one home workspace and one mind that persist across days; every day is a new process.

New files arrive in the home every day. Each day brings commands. The person (teacher) answers questions when asked
and every answer is counted. The last day has nobody to ask. Conditions run the same days on their own copy:
  LIFE   persistent memory, generalising world model and lexicon
  FRESH  the same mind, but memory wiped at the start of every day (no experience)
  CASE   persistent memory, exact-case world model and exact sentence-shape lexicon (no generalisation)
  FIXED  persistent memory, but a fixed human procedure: always ask to be pointed and shown, never interpret alone
"""
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
OUT = PKG / 'results' / 'life'
WORDS = ['amber', 'birch', 'cobalt', 'dahlia', 'ember', 'fennel', 'garnet', 'heron', 'indigo', 'juniper', 'kestrel', 'lilac',
         'marigold', 'nutmeg', 'olive', 'poppy', 'quill', 'russet', 'saffron', 'thistle', 'umber', 'violet', 'walnut', 'yarrow']
EXTS = ['csv', 'log', 'txt', 'json', 'md']
DAYS = [
    {'day': 1, 'user': True, 'tasks': [
        {'command': 'Move the csv files into a folder called archive.', 'tool': 'move', 'ext': 'csv', 'dest': 'archive'},
        {'command': 'Delete the log files.', 'tool': 'delete', 'ext': 'log', 'dest': None}]},
    {'day': 2, 'user': True, 'tasks': [
        {'command': 'Move the txt files into a folder called papers.', 'tool': 'move', 'ext': 'txt', 'dest': 'papers'},
        {'command': 'Please delete the json files.', 'tool': 'delete', 'ext': 'json', 'dest': None}]},
    {'day': 3, 'user': True, 'tasks': [
        {'command': 'Make a copy of the md files in a folder called backup.', 'tool': 'copy', 'ext': 'md', 'dest': 'backup'},
        {'command': 'Transfer the log files to a folder named vault.', 'tool': 'move', 'ext': 'log', 'dest': 'vault'}]},
    {'day': 4, 'user': True, 'tasks': [
        {'command': 'Make a copy of the csv files in a folder called spare.', 'tool': 'copy', 'ext': 'csv', 'dest': 'spare'},
        {'command': 'Erase the txt files.', 'tool': 'delete', 'ext': 'txt', 'dest': None},
        {'command': 'Move the md files into a folder called shelf.', 'tool': 'move', 'ext': 'md', 'dest': 'shelf'}]},
    {'day': 5, 'user': False, 'tasks': [
        {'command': 'Transfer the json files to a folder named crate.', 'tool': 'move', 'ext': 'json', 'dest': 'crate'},
        {'command': 'Make a copy of the log files in a folder called mirror.', 'tool': 'copy', 'ext': 'log', 'dest': 'mirror'},
        {'command': 'Please delete the csv files.', 'tool': 'delete', 'ext': 'csv', 'dest': None},
        {'command': 'Move the txt files into a folder called drawer.', 'tool': 'move', 'ext': 'txt', 'dest': 'drawer'}]},
]
DAYS_B = [                                   # held-out scenario written after development on DAYS
    {'day': 1, 'user': True, 'tasks': [
        {'command': 'Delete the md files.', 'tool': 'delete', 'ext': 'md', 'dest': None},
        {'command': 'Copy the txt files into a folder called keep.', 'tool': 'copy', 'ext': 'txt', 'dest': 'keep'}]},
    {'day': 2, 'user': True, 'tasks': [
        {'command': 'Move the log files into a folder called stack.', 'tool': 'move', 'ext': 'log', 'dest': 'stack'},
        {'command': 'Discard the csv files.', 'tool': 'delete', 'ext': 'csv', 'dest': None}]},
    {'day': 3, 'user': True, 'tasks': [
        {'command': 'Relocate the json files to a folder named bin.', 'tool': 'move', 'ext': 'json', 'dest': 'bin'},
        {'command': 'Duplicate the md files into a folder called extra.', 'tool': 'copy', 'ext': 'md', 'dest': 'extra'},
        {'command': 'Copy the csv files into a folder called pile.', 'tool': 'copy', 'ext': 'csv', 'dest': 'pile'}]},
    {'day': 4, 'user': False, 'tasks': [
        {'command': 'Discard the log files.', 'tool': 'delete', 'ext': 'log', 'dest': None},
        {'command': 'Move the md files into a folder called crate.', 'tool': 'move', 'ext': 'md', 'dest': 'crate'},
        {'command': 'Relocate the txt files to a folder named slot.', 'tool': 'move', 'ext': 'txt', 'dest': 'slot'},
        {'command': 'Duplicate the json files into a folder called spare.', 'tool': 'copy', 'ext': 'json', 'dest': 'spare'}]},
]
DAYS_C = [                                   # second held-out scenario: the last day recombines known words in new shapes
    {'day': 1, 'user': True, 'tasks': [
        {'command': 'Copy the log files into a folder called keep.', 'tool': 'copy', 'ext': 'log', 'dest': 'keep'},
        {'command': 'Delete the txt files.', 'tool': 'delete', 'ext': 'txt', 'dest': None}]},
    {'day': 2, 'user': True, 'tasks': [
        {'command': 'Move the csv files into a folder called stack.', 'tool': 'move', 'ext': 'csv', 'dest': 'stack'},
        {'command': 'Please discard the json files.', 'tool': 'delete', 'ext': 'json', 'dest': None}]},
    {'day': 3, 'user': True, 'tasks': [
        {'command': 'Relocate the md files to a folder named bin.', 'tool': 'move', 'ext': 'md', 'dest': 'bin'},
        {'command': 'Duplicate the csv files into a folder called extra.', 'tool': 'copy', 'ext': 'csv', 'dest': 'extra'}]},
    {'day': 4, 'user': False, 'tasks': [
        {'command': 'Please copy the md files to a folder named shelf.', 'tool': 'copy', 'ext': 'md', 'dest': 'shelf'},
        {'command': 'Discard the log files, please.', 'tool': 'delete', 'ext': 'log', 'dest': None},
        {'command': 'Relocate the txt files into a folder called tray.', 'tool': 'move', 'ext': 'txt', 'dest': 'tray'},
        {'command': 'Please duplicate the json files to a folder named cabinet.', 'tool': 'copy', 'ext': 'json', 'dest': 'cabinet'},
        {'command': 'Move the log files to a folder named drawer.', 'tool': 'move', 'ext': 'log', 'dest': 'drawer'}]},
]
DAYS_D = [                                   # third held-out scenario; no task removes files a later task of the day needs
    {'day': 1, 'user': True, 'tasks': [
        {'command': 'Move the json files into a folder called store.', 'tool': 'move', 'ext': 'json', 'dest': 'store'},
        {'command': 'Copy the md files into a folder called twin.', 'tool': 'copy', 'ext': 'md', 'dest': 'twin'}]},
    {'day': 2, 'user': True, 'tasks': [
        {'command': 'Delete the csv files.', 'tool': 'delete', 'ext': 'csv', 'dest': None},
        {'command': 'Kindly move the log files to a folder named attic.', 'tool': 'move', 'ext': 'log', 'dest': 'attic'}]},
    {'day': 3, 'user': True, 'tasks': [
        {'command': 'Clone the txt files into a folder called echo.', 'tool': 'copy', 'ext': 'txt', 'dest': 'echo'},
        {'command': 'Remove the md files.', 'tool': 'delete', 'ext': 'md', 'dest': None},
        {'command': 'Shift the csv files to a folder named den.', 'tool': 'move', 'ext': 'csv', 'dest': 'den'}]},
    {'day': 4, 'user': False, 'tasks': [
        {'command': 'Kindly clone the json files to a folder named loft.', 'tool': 'copy', 'ext': 'json', 'dest': 'loft'},
        {'command': 'Shift the md files into a folder called nook.', 'tool': 'move', 'ext': 'md', 'dest': 'nook'},
        {'command': 'Remove the txt files, kindly.', 'tool': 'delete', 'ext': 'txt', 'dest': None},
        {'command': 'Copy the log files to a folder named vault.', 'tool': 'copy', 'ext': 'log', 'dest': 'vault'},
        {'command': 'Move the csv files into a folder called bay.', 'tool': 'move', 'ext': 'csv', 'dest': 'bay'}]},
]
SCENARIOS = {'A': DAYS, 'B': DAYS_B, 'C': DAYS_C, 'D': DAYS_D}
CONDS = ('LIFE', 'FRESH', 'CASE', 'FIXED', 'HAND')


def hand_do(home, command):
    """HAND: a fixed procedure a developer wrote (keyword parser + hard-coded steps); it never asks and never learns."""
    import re
    toks = re.findall(r'[a-z0-9]+', command.lower())
    tool = next((t for t in toks if t in ('copy', 'move', 'delete')), None)
    ext = next((t for t in toks if t in EXTS), None)
    dest = next((toks[i + 1] for i, t in enumerate(toks[:-1]) if t in ('called', 'named')), None)
    if tool is None or ext is None or (tool != 'delete' and dest is None):
        return {'ok': False, 'reason': 'not understood'}
    files = [p for p in home.existing() if '/' not in p and p.endswith('.' + ext) and home.kind(p) == 'file']
    if tool != 'delete':
        home.execute('mkdir', (dest,), {'destroy': True})
    for f in files:
        home.execute(tool, (f, f'{dest}/{f}') if dest and tool != 'delete' else (f,), {'destroy': True})
    return {'ok': True}
HELP_WEIGHT = {'explain': 1, 'point': 1, 'check': 1, 'demonstrate': 2, 'demonstrate_goal': 3}


def inflow(home, day):
    """New files arrive at the top of the home folder (same for every condition)."""
    rng = random.Random(f'life-inflow-{day}')
    names = rng.sample(WORDS, 10)
    for i, ext in enumerate(EXTS):
        for j in range(2):
            p = home.root / f'{names[2 * i + j]}{day}.{ext}'
            p.write_bytes(f'{p.stem} {rng.random():.6f}\n'.encode())


def run_day(cond, day_no, root, scenario='A'):
    """One day in one process (a restart): load the mind from disk, live the day, save."""
    from ..agent.life import Mind
    from ..teach.life_teacher import Teacher
    from ..world.fs_world import Workspace
    root = Path(root)
    day = next(d for d in SCENARIOS[scenario] if d['day'] == day_no)
    home = Workspace(root / 'home', create=not (root / 'home').exists())
    if cond == 'FRESH' and (root / 'mind').exists():
        shutil.rmtree(root / 'mind')
    inflow(home, day_no)
    teacher = Teacher(home)
    user = teacher if day['user'] else None
    rows = []
    for k, task in enumerate(day['tasks']):
        if cond == 'HAND':
            teacher.begin(task)
            t0 = time.time()
            r = hand_do(home, task['command'])
            rows.append({'day': day_no, 'task': k, 'command': task['command'], 'success': teacher.judge(), 'agent': r, 'help': {},
                         'help_score': 0, 'counts': {}, 'seconds': round(time.time() - t0, 2), 'episodes': 0})
            continue
        mind = Mind(home, root / 'mind', root / 'lab', user=user, generalize=cond != 'CASE',
                    lexicon_mode='case' if cond == 'CASE' else 'general', seed=day_no * 10 + k, fixed=cond == 'FIXED')
        teacher.begin(task)
        h0 = dict(teacher.help)
        t0 = time.time()
        r = mind.do(task['command'], f'd{day_no}-t{k}')
        helped = {q: teacher.help[q] - h0.get(q, 0) for q in teacher.help if teacher.help[q] - h0.get(q, 0)}
        rows.append({'day': day_no, 'task': k, 'command': task['command'], 'success': teacher.judge(), 'agent': r,
                     'help': helped, 'help_score': sum(HELP_WEIGHT.get(q, 0) * n for q, n in helped.items()),
                     'counts': dict(mind.counts), 'seconds': round(time.time() - t0, 2), 'episodes': len(mind.episodes)})
    with open(root / 'days.jsonl', 'a', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + '\n')
    return rows


def run(out=OUT, conds=CONDS, scenario='A'):
    out = Path(out)
    for c in conds:
        root = out / c
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        for d in SCENARIOS[scenario]:
            subprocess.run([sys.executable, '-c', f'from atanor_os.eval.life import run_day; run_day({c!r}, {d["day"]}, {str(root)!r}, {scenario!r})'],
                           cwd=PKG.parent, check=True)
    return summary(out, conds, scenario)


def summary(out=OUT, conds=CONDS, scenario='A'):
    DAYS = SCENARIOS[scenario]
    out = Path(out)
    s = {}
    for c in conds:
        rows = [json.loads(l) for l in (out / c / 'days.jsonl').read_text(encoding='utf-8').splitlines()]
        s[c] = {d['day']: {'success': f"{sum(r['success'] for r in rows if r['day'] == d['day'])}/{len(d['tasks'])}",
                           'help': sum(r['help_score'] for r in rows if r['day'] == d['day']),
                           'lab': sum(r['counts'].get('lab_actions', 0) for r in rows if r['day'] == d['day']),
                           'surprises': sum(r['counts'].get('surprises', 0) for r in rows if r['day'] == d['day']),
                           'seconds': round(sum(r['seconds'] for r in rows if r['day'] == d['day']), 1)} for d in DAYS}
    (out / 'summary.json').write_text(json.dumps(s, indent=1), encoding='utf-8')
    return s
