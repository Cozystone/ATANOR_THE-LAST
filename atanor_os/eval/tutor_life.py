"""A taught life on the board without sentences first (evaluator side). Each day is a new process (memory persists only
through the mind directory, as in every life). The person decides each day, on the board as it is, what makes sense to
teach or ask (a lesson or a command is only posed if there are objects it applies to and the action can be done).
Phases:
  A  lessons, no words: point at a few objects meant, ATANOR asks contrast questions, one demonstration, ATANOR does the
     rest, the person confirms; then the person NAMES the selection and the action with arbitrary per-seed symbols.
  B  symbol commands for a selection and an action that were taught together.
  C  new combinations: a taught selection with a taught action never shown together.
  -  from day 9 a world change (one tool stops working, a new one appears): a counter-example to action claims.
  D  English: the person attaches English phrases to concepts already shared (pointing / demonstrating while saying the
     phrase), then gives English commands, including new combinations.
Every fourth day nobody is there. Conditions: FULL, ONTO (claims and graph kept, past raw events unreadable), RAW (only
raw events kept; concepts re-derived from them), NONE (memory wiped every day), PASSIVE (FULL memory, no contrast questions).
"""
import itertools
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

from .life_gen_board import MARKS, TRAYS, inflow as card_inflow

PKG = Path(__file__).resolve().parents[1]
HUE_TRAY = {h: t for t, h in TRAYS.items()}


def targets(seed):
    rng = random.Random(f'tutor-targets-{seed}')
    sels = [{'kind': 'card', 'mark': m} for m in sorted(MARKS)] + [{'kind': 'card', 'tray': h} for h in rng.sample(sorted(HUE_TRAY), 2)] +            [{'kind': 'card', 'mark': m, 'tray': h} for m, h in zip(rng.sample(sorted(MARKS), 2), rng.sample(sorted(HUE_TRAY), 2))]   # conjunctions
    acts = [{'tool': 'lodge', 'second': t} for t in rng.sample(sorted(TRAYS), 2)] + \
           [{'tool': 'stamp', 'second': f'm.{m}'} for m in rng.sample(sorted(MARKS), 1)] + [{'tool': 'lift', 'second': 'l.high'}, {'tool': 'unlodge'}, {'tool': 'scrap'}]
    return sels, acts


def english(kind, spec):
    """English names for already shared concepts (the TRAIN pools' canonical words), as (head, tail) around a selection.
    Evaluator side only: the learner never sees this table, only the person saying the phrase while pointing or showing."""
    if kind == 'sel':
        if spec['kind'] == 'file':
            return ['the', spec['ext'], 'files']
        if spec['kind'] == 'panel':
            if 'sort' in spec:
                return ['the', 'panels', 'sorted', 'by', spec['sort']]
            if 'group' in spec:
                return ['the', 'ungrouped', 'panels']
            return ['the', 'unfiltered', 'panels'] if spec['filter'] == 'all' else ['the', 'panels', 'showing', spec['filter']]
        if 'mark' in spec and 'tray' in spec:
            return ['the', spec['mark'], 'cards', 'in', spec['tray']]
        return ['the', spec['mark'], 'cards'] if 'mark' in spec else ['the', 'cards', 'in', spec['tray']]
    t, v = spec['tool'], spec.get('second')
    if t in ('copy', 'move'):
        return [t, 'into', v]
    if t == 'delete':
        return ['delete']
    if t == 'filter':
        return ['show', 'only', v.split(':', 1)[1]]
    if t in ('sort', 'group'):
        return [t, 'by', v.split(':', 1)[1]]
    if t == 'lodge':
        return ['stash', 'in', TRAYS[v]]
    if t == 'stamp':
        return ['label', 'as', v[2:]]
    if t == 'lift':
        return ['raise', 'to', v[2:]]
    return {'unlodge': ['take', 'out'], 'scrap': ['shred']}[t]


FS_EXTS = ['csv', 'log', 'txt', 'json', 'md']
FS_FOLDERS = ['archive', 'inbox', 'vault', 'attic']
VIEW_PANELS = ('p1', 'p2', 'p3')


def body_targets(body, seed):
    rng = random.Random(f'tutor-targets-{body}-{seed}')
    if body == 'board':
        return targets(seed)
    if body == 'fs':
        sels = [{'kind': 'file', 'ext': e} for e in FS_EXTS]
        acts = [{'tool': 'copy', 'second': d} for d in rng.sample(FS_FOLDERS, 2)] +                [{'tool': 'move', 'second': d} for d in rng.sample(FS_FOLDERS, 2)] + [{'tool': 'delete'}]
        return sels, acts
    sels = [{'kind': 'panel', 'filter': 'all'}, {'kind': 'panel', 'sort': 'name'}, {'kind': 'panel', 'group': 'none'},
            {'kind': 'panel', 'filter': 'csv'}, {'kind': 'panel', 'sort': 'size'}]
    acts = [{'tool': 'filter', 'second': 'ext:md'}, {'tool': 'sort', 'second': 'key:ext'}, {'tool': 'group', 'second': 'grp:ext'},
            {'tool': 'filter', 'second': 'ext:log'}]
    return sels, acts


def make_home(body, root, seed, day_no):
    """The day's world: it persists; new things arrive (board cards, files) or others change it (screen panels)."""
    root = Path(root)
    if body == 'board':
        from ..world.board_world import BoardWorkspace
        home = BoardWorkspace(root / 'board', create=not (root / 'board').exists())
        home.add_cards(day_inflow(seed, day_no))
        return home
    if body == 'fs':
        from ..world.fs_world import Workspace
        from .life_gen import inflow as file_inflow
        new = not (root / 'home').exists()
        home = Workspace(root / 'home', create=new)
        if new:
            for d in FS_FOLDERS:
                (home.root / d).mkdir()
        file_inflow(home, day_no, seed)
        return home
    from ..world.fs_world import Workspace
    from ..world.view_world import ViewWorkspace
    data = Workspace(root / 'data', create=not (root / 'data').exists())
    rng = random.Random(f'tutor-view-{seed}-{day_no}')
    for i, ext in enumerate(FS_EXTS):
        (data.root / f'd{day_no}_{i}.{ext}').write_bytes(f'{day_no} {i}\n'.encode())
    spec = {p: {'kind': 'panel', 'filter': rng.choice(['all', 'all', 'csv', 'txt']), 'sort': rng.choice(['name', 'name', 'size']),
                'group': 'none'} for p in VIEW_PANELS}
    if (root / 'view').exists():
        shutil.rmtree(root / 'view')
    return ViewWorkspace(root / 'view', data, spec=spec)


def body_spec(body):
    from ..teach.tutor import BoardSpec, FsSpec, ViewSpec
    return {'board': BoardSpec, 'fs': FsSpec, 'view': ViewSpec}[body]


DRIFT = {'board': 'lodge_retired', 'fs': 'copy_retired', 'view': 'sort_retired'}


def plan(seed, days=24, body='board'):
    """Which kinds of events each day has (the concrete objects are chosen by the person on the day's board)."""
    rng = random.Random(f'tutor-plan-{seed}')
    out = []
    for d in range(1, days + 1):
        user = d <= 2 or d % 4 != 0
        ev = []
        if d <= 4 and user:
            ev += [['lesson'], ['lesson']]
        if d in (11, 13) and user:
            ev += [['english'], ['english'], ['english']]
        for _ in range(3 if d >= 2 else 0):
            kind = 'C' if d >= 5 and rng.random() < 0.5 else 'B'
            lang = 'en' if d >= 12 and rng.random() < 0.5 else 'sym'
            ev.append(['test', kind, lang])
        out.append({'day': d, 'user': user, 'drift': [DRIFT[body]] if d >= 9 else [], 'events': ev})
    return out


def day_inflow(seed, day):
    """New cards arrive; some were already put in a tray by others."""
    rng = random.Random(f'tutor-inflow-{seed}-{day}')
    cards = card_inflow(seed, day)
    for cid in sorted(cards)[:2]:
        cards[cid]['tray'] = rng.choice(sorted(TRAYS))
    return cards


def run_day(cond, seed, day_no, root, days=24, body='board'):
    from ..agent.grounding import Grounder
    from ..teach.tutor import Tutor, symbols
    root = Path(root)
    sels, acts = body_targets(body, seed)
    day = plan(seed, days, body)[day_no - 1]
    home = make_home(body, root, seed, day_no)
    home.drift = frozenset(day['drift'])
    BoardSpec = body_spec(body)
    if cond == 'NONE' and (root / 'mind').exists():
        shutil.rmtree(root / 'mind')
    sp = root / 'tutor_state.json'                     # the person's own memory of what was taught (evaluator side)
    S = json.loads(sp.read_text(encoding='utf-8')) if sp.exists() else {'taught': [], 'sym_sel': [], 'sym_act': [], 'en_sel': [], 'en_act': []}
    if cond == 'NONE':                                 # the person knows ATANOR forgets nothing it was told... it does forget here
        pass
    sym = symbols(seed)
    sym_sel = {j: sym[j] for j in range(len(sels))}
    sym_act = {j: sym[20 + j] for j in range(len(acts))}
    tut = Tutor(home, BoardSpec, f'{seed}-{day_no}')
    mode = {'FULL': 'FULL', 'ONTO': 'ONTO', 'RAW': 'RAW', 'NONE': 'FULL', 'PASSIVE': 'FULL'}[cond]
    g = Grounder(home, root / 'mind', person=tut if day['user'] else None, mode=mode, passive=cond == 'PASSIVE')
    rng = random.Random(f'tutor-choice-{seed}-{day_no}')
    rows = []

    def feasible(s, a):
        tut.start(sels[s], acts[a])
        st = home.observe(home.existing())
        todo = [o for o in tut.truth if not BoardSpec.shows(acts[a], o, st)]
        if body == 'board' and acts[a]['tool'] in ('lift', 'unlodge') and any(st[o]['tray'] == '-' for o in todo):
            return False                               # the person knows these need cards in a tray
        if body == 'view' and acts[a]['tool'] == 'group' and any(st[o]['filter'] != 'all' for o in todo):
            return False                               # grouping needs the unfiltered list
        return bool(todo)

    def pick(cands, prefer=None):
        cands = list(cands)
        rng.shuffle(cands)
        if prefer:
            cands.sort(key=prefer)
        return next(((s, a) for s, a in cands if feasible(s, a)), None)

    def teach(s, a, row, names=('sym',)):
        """A lesson: point, contrast questions, one demonstration, ATANOR does the rest, confirm; then the names."""
        tut.start(sels[s], acts[a])
        lid = f'L{s}.{a}-d{day_no}'
        sc = g.learn_selection(lid)
        row['criterion_ok'] = bool(sc) and g.extension(sc['content']['atoms'], g.feats()) == tut.truth
        ac = g.learn_action(lid)
        acted, failed = g.apply(sc['content'], ac['content'], lid) if sc else ([], [])
        ok = tut.confirm()
        g.reply(ok)
        row.update(reproduced=ok, acted=len(acted), failed=len(failed))
        for lang in names:
            if lang == 'sym':
                if sc:
                    g.bind(sym_sel[s], sc['content']['concept'], lid, replace=True)
                g.bind(sym_act[a], ac['content']['action'], lid, replace=True)
            else:
                if sc:
                    g.name_phrase(english('sel', sels[s]), sc['content']['concept'], lid)
                g.name_phrase(english('act', acts[a]), ac['content']['action'], lid)
        if [s, a] not in S['taught']:
            S['taught'].append([s, a])
        for key, j in (('sym_sel', s), ('sym_act', a)) if 'sym' in names else ():
            if j not in S[key]:
                S[key].append(j)

    for k, e in enumerate(day['events']):
        h0 = dict(tut.help)
        row = {'day': day_no, 'k': k, 'user': day['user'], 'event': e[0], 'drift': day['drift']}
        if e[0] == 'lesson':
            ts = {x for x, _ in S['taught']}
            ta = {y for _, y in S['taught']}
            c = pick(itertools.product(range(len(sels)), range(len(acts))), prefer=lambda p: (p[0] in ts) + (p[1] in ta))
            if c is None:
                row['outcome'] = 'nothing to teach'
            else:
                row.update(sel=c[0], act=c[1])
                teach(c[0], c[1], row)
        elif e[0] == 'english':
            c = pick([tuple(p) for p in S['taught']], prefer=lambda p: (p[0] in S['en_sel']) + (p[1] in S['en_act']))
            if c is None:
                row['outcome'] = 'nothing to name'
            else:
                s, a = c
                row.update(sel=s, act=a)
                tut.start(sels[s], acts[a])
                sc = g.known_concept(f'E{s}-d{day_no}', english('sel', sels[s]))   # the person points while saying the phrase; contrast if unclear
                row['english_sel_known'] = bool(sc)
                sc = sc or g.learn_selection(f'E{s}-d{day_no}')
                cands = [sc] if sc else []
                if sc:
                    g.name_phrase(english('sel', sels[s]), sc['content']['concept'], f'E{s}-d{day_no}')
                    S['en_sel'].append(s)
                ac = g.learn_action(f'E{a}-d{day_no}')    # demonstrate while saying the action phrase
                same = ac.get('v', 1) > 1                 # learn_action reuses an action only when the whole call matches
                node = ac['content']['action']
                g.name_phrase(english('act', acts[a]), node, f'E{a}-d{day_no}')
                S['en_act'].append(a)
                row['english_act_matched_existing'] = bool(same)
                if cands:
                    g.apply(cands[0]['content'], ac['content'], f'E{s}-d{day_no}')
                row['reproduced'] = tut.confirm()
        else:
            _, kind, lang = e
            named_s = S['sym_sel'] if lang == 'sym' else S['en_sel']
            named_a = S['sym_act'] if lang == 'sym' else S['en_act']
            taught = [tuple(p) for p in S['taught']]
            if kind == 'B':
                cands = [p for p in taught if p[0] in named_s and p[1] in named_a]
            else:
                cands = [(s, a) for s in set(named_s) for a in set(named_a) if (s, a) not in taught]
            c = pick(cands)
            row.update(kind=kind, lang=lang)
            if c is None:
                row['outcome'] = 'infeasible'
                rows.append(row)
                continue
            s, a = c
            row.update(sel=s, act=a)
            tut.start(sels[s], acts[a])
            if lang == 'sym':
                words = [sym_act[a], sym_sel[s]]
                random.Random(f'{seed}-{day_no}-{k}').shuffle(words)
            else:
                ea = english('act', acts[a])
                words = ea[:1] + english('sel', sels[s]) + ea[1:]
            row['words'] = words
            look = g.lookup(sym_sel[s]) if lang == 'sym' else None
            if look and look['kind'] == 'selects':
                ext = g.extension(look['claim']['content']['atoms'], g.feats())
                row['retrieval_ok'] = ext == tut.truth
            res = g.obey(words, task=f'd{day_no}-k{k}')
            row['used_claims'] = res.get('used')
            if not res.get('ok') and day['user'] and res.get('why') == 'unresolved':
                teach(s, a, row, names=(lang,))       # the person re-teaches (counted as help)
                row['retaught'] = True
            elif not res.get('ok') and day['user'] and res.get('failed'):
                ac = g.learn_action(f'R{a}-d{day_no}')   # the tool did not do what was remembered: shown again
                if lang == 'sym':
                    g.bind(sym_act[a], ac['content']['action'], f'R{a}-d{day_no}', replace=True)
                else:
                    g.name_phrase(english('act', acts[a]), ac['content']['action'], f'R{a}-d{day_no}')
                sc = g.lookup(sym_sel[s]) if lang == 'sym' else None
                if sc:
                    g.apply(sc['claim']['content'], ac['content'], f'R{a}-d{day_no}')
                row['redemonstrated'] = True
            ok = tut.judge()
            acted = bool(res.get('acted'))
            row.update(outcome='success' if ok else ('wrong' if acted else 'held'), first_try=res.get('ok', False) and ok,
                       why=res.get('why'), retrieved_as=res.get('retrieved_as'))
        row['help'] = {q: tut.help[q] - h0.get(q, 0) for q in tut.help if tut.help[q] - h0.get(q, 0)}
        rows.append(row)
    sp.write_text(json.dumps(S), encoding='utf-8')
    counts = dict(g.counts)
    with open(root / 'days.jsonl', 'a', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps({**r, 'counts': counts}, default=str) + '\n')
    return rows


def _content(g, words):
    """English: a word that has been bound to exactly one internal node stands for it; the others say nothing."""
    out = []
    for w in words:
        if g.mode == 'RAW':
            nodes = {e['node'] for e in g.mem.events.all() if e['kind'] == 'name' and e.get('symbol') == w}
        else:
            nodes = {c['content']['refers'] for c in g.mem.claims.claims('denotes') if c['content']['symbol'] == w}
        if len(nodes) == 1:
            out.append(w)
    return out


def run(seed, out, conds=('FULL', 'ONTO', 'RAW', 'NONE', 'PASSIVE'), days=24, body='board'):
    out = Path(out)
    for c in conds:
        root = out / c
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        for d in range(1, days + 1):
            subprocess.run([sys.executable, '-c', f'from atanor_os.eval.tutor_life import run_day; run_day({c!r}, {seed}, {d}, {str(root)!r}, {days}, {body!r})'],
                           cwd=PKG.parent, check=True)
