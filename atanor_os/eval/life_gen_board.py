"""A long life on the third body (a task board), generated from a seed (evaluator side; never imported by agent/).

Every morning new cards arrive (each with a mark); the board persists. The person gives 2-3 commands in English about
cards: put them in a tray, take them out, mark them, raise their level, shred them. Every fourth day nobody is there.
Twice the board's rules change (a tool stops working; a new one with an opaque name appears). None of the file or
screen bodies' words, objects or tools are used.

Expressions come from TRAIN pools. SEALED pools (synonyms and sentence frames never used in a life) are only for the
evaluator's probes (eval/probe_board.py); the teacher of a life never sees them.
"""
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
TRAYS = {'t1': 'amber', 't2': 'teal', 't3': 'plum', 't4': 'slate'}
HUE_TRAY = {h: t for t, h in TRAYS.items()}
MARKS = ('urgent', 'idea', 'defect', 'chore', 'memo')
LEVELS = ('low', 'mid', 'high')

TRAIN = {
    'mark': {'urgent': ['urgent', 'pressing'], 'idea': ['idea', 'suggestion'], 'defect': ['defect', 'bug'],
             'chore': ['chore', 'errand'], 'memo': ['memo', 'reminder']},
    'hue': {'amber': ['amber', 'orange'], 'teal': ['teal', 'green'], 'plum': ['plum', 'purple'], 'slate': ['slate', 'grey']},
    'level': {'high': ['high', 'top'], 'mid': ['mid', 'middle'], 'low': ['low', 'bottom']},
    'by_mark': [['the', '{m}', 'cards'], ['every', '{m}', 'card'], ['all', '{m}', 'cards'], ['all', 'the', '{m}', 'cards']],
    'by_tray': [['the', 'cards', 'in', 'the', '{h}', 'tray'], ['everything', 'in', '{h}'], ['the', 'cards', 'sitting', 'in', '{h}']],
    'verbs': {'lodge': [['stash', '{S}', 'in', 'the', '{H}', 'tray'], ['park', '{S}', 'in', '{H}'], ['tuck', '{S}', 'into', 'the', '{H}', 'bin']],
              'unlodge': [['take', '{S}', 'out'], ['pull', '{S}', 'out', 'of', 'their', 'trays'], ['unpack', '{S}']],
              'stamp': [['label', '{S}', 'as', '{M}'], ['flag', '{S}', 'as', '{M}'], ['mark', '{S}', 'as', '{M}']],
              'lift': [['raise', '{S}', 'to', '{L}'], ['bump', '{S}', 'up', 'to', '{L}'], ['promote', '{S}', 'to', '{L}']],
              'scrap': [['shred', '{S}'], ['scrap', '{S}'], ['toss', '{S}']]},
}
SEALED = {          # never used in a life: for probes of transfer to unseen surface forms
    'mark': {'urgent': ['critical'], 'idea': ['proposal'], 'defect': ['flaw'], 'chore': ['duty'], 'memo': ['jotting']},
    'hue': {'amber': ['honey'], 'teal': ['sea'], 'plum': ['violet'], 'slate': ['ash']},
    'level': {'high': ['peak'], 'mid': ['centre'], 'low': ['base']},
    'by_mark': [['each', '{m}', 'card'], ['those', '{m}', 'cards']],
    'by_tray': [['whatever', 'is', 'in', 'the', '{h}', 'tray']],
    'verbs': {'lodge': [['slip', '{S}', 'into', 'the', '{H}', 'tray']], 'unlodge': [['lift', '{S}', 'out', 'of', 'the', 'trays']],
              'stamp': [['brand', '{S}', 'as', '{M}']], 'lift': [['elevate', '{S}', 'to', '{L}']], 'scrap': [['destroy', '{S}']]},
}
POLITE = [[], [], ['please'], ['kindly']]
FUNCTION = {'the', 'every', 'all', 'in', 'into', 'to', 'up', 'as', 'out', 'of', 'their', 'trays', 'tray', 'bin', 'cards', 'card',
            'everything', 'sitting', 'please', 'kindly', 'each', 'those', 'whatever', 'is'}
CHANGES = ['lodge_retired', 'stamp_retired']
TOOL_WEIGHTS = ['lodge', 'lodge', 'stamp', 'stamp', 'lift', 'unlodge', 'scrap']


def _sentence(toks):
    s = ' '.join(toks)
    return s[0].upper() + s[1:] + '.'


def make_task(rng, cards, tool, pools=TRAIN):
    """One feasible task on the simulated board `cards` ({id: {'mark','tray','level'}}), or None."""
    by_tray = tool in ('unlodge', 'lift') or (tool in ('stamp', 'scrap') and rng.random() < 0.4)
    if by_tray:
        hues = sorted({c['tray'] for c in cards.values() if c['tray'] != '-'})
        if not hues:
            return None
        hue = rng.choice(hues)
        sel = ('tray', hue)
        frame = rng.choice(pools['by_tray'])
        sel_words = [w for f in frame for w in ([rng.choice(pools['hue'][hue])] if f == '{h}' else [f])]
    else:
        marks = sorted({c['mark'] for c in cards.values()})
        if not marks:
            return None
        m = rng.choice(marks)
        sel = ('mark', m)
        frame = rng.choice(pools['by_mark'])
        sel_words = [w for f in frame for w in ([rng.choice(pools['mark'][m])] if f == '{m}' else [f])]
    truth = sorted(cid for cid, c in cards.items() if c[sel[0]] == sel[1])
    if not truth:
        return None
    second = None
    fill = {'{S}': sel_words}
    if tool == 'lodge':
        hue = rng.choice([h for h in TRAYS.values() if not all(cards[c]['tray'] == h for c in truth)] or [None])
        if hue is None:
            return None
        second, fill['{H}'] = HUE_TRAY[hue], [rng.choice(pools['hue'][hue])]
    elif tool == 'stamp':
        m = rng.choice([x for x in MARKS if not all(cards[c]['mark'] == x for c in truth)])
        second, fill['{M}'] = f'm.{m}', [rng.choice(pools['mark'][m])]
    elif tool == 'lift':
        lv = rng.choice([x for x in LEVELS if not all(cards[c]['level'] == x for c in truth)] or [None])
        if lv is None:
            return None
        second, fill['{L}'] = f'l.{lv}', [rng.choice(pools['level'][lv])]
    elif tool == 'unlodge':
        if all(cards[c]['tray'] == '-' for c in truth):
            return None
    verb = rng.choice(pools['verbs'][tool])
    toks = list(rng.choice(POLITE)) + [w for f in verb for w in fill.get(f, [f])]
    syn = {}
    for kind in ('mark', 'hue', 'level'):
        for canon, words in pools[kind].items():
            for w in words:
                if w in toks and w != canon:
                    syn[w] = canon
    base = pools['verbs'][tool][0][0]
    explain = {w: base for w in verb if not w.startswith('{') and w not in FUNCTION and w != base}
    explain.update(syn)
    explain.update({w: '' for w in toks if w in FUNCTION})
    return {'command': _sentence(toks), 'tool': tool, 'select': list(sel), 'second': second,
            'phrases': {'explain_map': explain}}


def apply_task(cards, task):
    sel = task['select']
    for cid in [c for c, v in cards.items() if v[sel[0]] == sel[1]]:
        t = task['tool']
        if t == 'lodge':
            cards[cid]['tray'] = TRAYS[task['second']]
        elif t == 'unlodge':
            cards[cid]['tray'] = '-'
        elif t == 'stamp':
            cards[cid]['mark'] = task['second'][2:]
        elif t == 'lift':
            cards[cid]['level'] = task['second'][2:]
        elif t == 'scrap':
            del cards[cid]


def inflow(seed, day):
    rng = random.Random(f'board-{seed}-inflow-{day}')
    return {f'q{day:02d}{i}': {'mark': rng.choice(MARKS)} for i in range(5)}


def life(seed, days=30, drift=True):
    rng = random.Random(f'boardlife-{seed}')
    change_days = sorted(rng.sample(range(8, days), 2)) if drift and days > 10 else []
    changes = rng.sample(CHANGES, 2)
    out, cur, cards = [], [], {}
    for day in range(1, days + 1):
        if day in change_days:
            cur = cur + [changes[change_days.index(day)]]
        for cid, c in inflow(seed, day).items():
            cards[cid] = {'mark': c['mark'], 'tray': '-', 'level': 'low'}
        user = day <= 2 or day % 4 != 0
        tasks, tries = [], 0
        want = rng.choice([2, 3])
        while len(tasks) < want and tries < 60:
            tries += 1
            t = make_task(rng, cards, rng.choice(TOOL_WEIGHTS))
            if t is None:
                continue
            tasks.append(t)
            apply_task(cards, t)
        out.append({'day': day, 'user': user, 'drift': list(cur), 'tasks': tasks})
    return out


def run_day(cond, seed, day_no, root, days=30):
    from ..agent.life import Mind
    from ..teach.life_teacher import BoardTeacher
    from ..world.board_world import BoardWorkspace
    from .life_gen import resume_goals, HELP_SCORE
    root = Path(root)
    day = life(seed, days)[day_no - 1]
    home = BoardWorkspace(root / 'board', create=not (root / 'board').exists())
    home.add_cards(inflow(seed, day_no))
    home.drift = frozenset(day['drift'])
    if cond == 'FRESH' and (root / 'mind').exists():
        shutil.rmtree(root / 'mind')
    teacher = BoardTeacher(home)
    rows = []
    for k, task in enumerate(day['tasks']):
        teacher.begin(task)
        if not teacher.truth:
            rows.append({'day': day_no, 'task': k, 'command': task['command'], 'tool': task['tool'], 'user': day['user'], 'drift': day['drift'],
                         'success': False, 'outcome': 'infeasible', 'agent': {}, 'help': {}, 'help_score': 0, 'counts': {}, 'seconds': 0.0})
            continue
        h0, t0 = dict(teacher.help), time.time()
        mind = Mind(home, root / 'mind', root / 'lab', user=teacher if day['user'] else None, generalize=cond != 'CASE',
                    lexicon_mode='case' if cond == 'CASE' else 'general', seed=day_no * 10 + k)
        r = mind.do(task['command'], f'd{day_no}-t{k}')
        ok = teacher.judge()
        helped = {q: teacher.help[q] - h0.get(q, 0) for q in teacher.help if teacher.help[q] - h0.get(q, 0)}
        acted = r.get('achieved') is not None
        rows.append({'day': day_no, 'task': k, 'command': task['command'], 'tool': task['tool'], 'user': day['user'], 'drift': day['drift'],
                     'success': ok, 'outcome': 'success' if ok else ('wrong' if acted and r.get('achieved') is not False else 'held'),
                     'agent': r, 'help': helped, 'help_score': sum(HELP_SCORE.get(q, 0) * n for q, n in helped.items()),
                     'counts': dict(mind.counts), 'seconds': round(time.time() - t0, 2)})
    if day['user']:      # before the person leaves, the core brings up what it left unfinished on earlier days
        resume_goals(root, seed, days, day_no, teacher, lambda k: Mind(home, root / 'mind', root / 'lab', user=teacher, generalize=cond != 'CASE',
                     lexicon_mode='case' if cond == 'CASE' else 'general', seed=day_no * 10 + 9 - k), life)
    with open(root / 'days.jsonl', 'a', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + '\n')
    snap = root / 'snap' / f'd{day_no}'
    for part in ('board', 'mind'):
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
            subprocess.run([sys.executable, '-c', f'from atanor_os.eval.life_gen_board import run_day; run_day({c!r}, {seed}, {d}, {str(root)!r}, {days})'],
                           cwd=PKG.parent, check=True)
