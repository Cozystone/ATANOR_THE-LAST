"""P9 harness (evaluator side): English commands -> ATANOR's interpretation over frozen R1 -> action -> judged by truth.

Training (teacher on) and evaluation (teacher and every model off: import guard + socket audit) run in separate
processes. Sealed sentence files live outside the repository; only their sha256 is published before the run.
"""
import hashlib
import json
import random
import sys
import time
from pathlib import Path

from ..agent.concepts import ConceptModel, Representation
from ..agent.language import Lexicon, goal_from_interpretation, object_atoms, tokens
from ..agent.loop import run_episode
from ..core.journal import Journal
from ..world.fs_world import Workspace, name_ext
from ..world.raw_obs import raw_attrs
from .generator import WORDS_TEST, WORDS_TRAIN

PKG = Path(__file__).resolve().parents[1]
OUT = PKG / 'results' / 'p9'
R1_PATH = PKG / 'results' / 'p8b' / 'reps' / 'R1_KEEP' / 'stable_fs.json'
SEALED = Path('D:/ATANOR-experiments/2026-09-19/sealed')
SEALED_SHA = {'immediate': '882942f8f464678f632c578e9b3d2c7dfc00be02fd24f6b38f471d5a48b361e6',
              'delayed': '3386e118204511e6e3f8cc360f3642a3aaee8a95df61cd465828a026d4682e78'}
EXTS = {'train': ['txt', 'csv', 'md'], 'eval': ['txt', 'csv', 'md', 'log', 'json']}
SEEN_EXT = {'txt', 'csv', 'md', 'any'}
CONDS = ('CONCEPT', 'FLAT', 'NONE', 'ORACLE')
DELAY_HOURS = 72


# ---------------- scenes and truth ----------------
def scene(index, split, root, ext):
    """Fresh workspace: 4-6 files (mixed extensions, the needed one present and at least one other) + an empty folder."""
    rng = random.Random(f'p9-{split}-{index}')
    words = WORDS_TRAIN if split == 'train' else WORDS_TEST
    pool = EXTS['train' if split == 'train' else 'eval']
    n = rng.choice([4, 5, 6])
    names = rng.sample(words, n + 1)
    exts = [rng.choice(pool) for _ in range(n)]
    if ext != 'any':
        exts[0] = ext
        if all(e == ext for e in exts):
            exts[1] = rng.choice([e for e in pool if e != ext])
    ws = Workspace(Path(root))
    files = {}
    for i in range(n):
        p = f'{names[i]}.{exts[i]}'
        (ws.root / p).write_bytes(f'{names[i]} {rng.random():.6f}\n'.encode())
        files[p] = ws.attrs(p)['hash']
    (ws.root / names[n]).mkdir()
    return ws, files, names[n]


def truth_set(files, ext):
    return sorted(f for f in files if ext == 'any' or name_ext(f) == ext)


def judge(ws, files, folder, tool, ext, dest):
    sel = set(truth_set(files, ext))
    paths = list(files) + [folder] + ([f'{dest}/{f}' for f in sel] if dest else [])
    st = ws.observe(paths)
    ok = st[folder]['kind'] == 'dir'
    for f, h in files.items():
        if f not in sel:
            ok &= st[f]['kind'] == 'file' and st[f]['hash'] == h
            continue
        if tool in ('copy', 'move'):
            d = f'{dest}/{f}'
            ok &= st[d]['kind'] == 'file' and st[d]['hash'] == h
        if tool == 'copy':
            ok &= st[f]['kind'] == 'file' and st[f]['hash'] == h
        else:
            ok &= st[f]['kind'] == 'absent'
    return bool(ok)


def scene_view(rep, ws, use_concepts):
    """What ATANOR sees: each existing object's atoms and its first string-valued raw attribute."""
    objs = [o for o in ws.existing()]
    st = ws.observe(objs)
    return {o: (object_atoms(rep, st, o, use_concepts), raw_attrs('fs', st[o])['a2']) for o in objs}


# ---------------- acting ----------------
def act(rep, ws, interp, jpath, gid):
    """ATANOR's goal from its interpretation (its own learned effects), reached by its own planner."""
    if not interp.get('selected') or not interp.get('tool'):
        return {'acted': False}
    paths = list(interp['selected']) + ([f"{interp['dest']}/{o}" for o in interp['selected']] + [interp['dest']] if interp['dest'] else [])
    st = ws.observe(paths)
    goal = goal_from_interpretation(rep, st, interp, gid)
    if goal is None:
        return {'acted': False}
    goal.capabilities = {'destroy': True}            # the command is the user's permission
    j = Journal(jpath)
    rec = run_episode(ws, goal, ConceptModel(rep), j, gid)
    j.close()
    return {'acted': True, 'actions': rec['actions'], 'believes_done': rec['agent_believes_done']}


def _correct(interp, files, ext, tool, dest):
    t = interp['tool'] == tool
    s = sorted(interp['selected']) == truth_set(files, ext)
    d = (interp['dest'] or None) == (dest or None)
    return {'tool': t, 'set': s, 'dest': d, 'all': t and s and d}


def none_interp(lex, toks, view):
    tool = sorted(lex.tool_n, key=lambda t: (-lex.tool_n[t], t))[0]
    sel = sorted(o for o, (at, _) in view.items() if ('U', 0, 'a1', 0) in at)
    return {'tool': tool, 'selected': sel, 'dest': toks[-1] if lex._takes_dest(tool) else None}


# ---------------- training process (teacher on) ----------------
def train(out=OUT):
    from ..teach.p9_sentences import sentences
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rep = Representation.loads(R1_PATH.read_text(encoding='utf-8'))
    data = sentences()
    log = []
    lex = {'CONCEPT': Lexicon(), 'FLAT': Lexicon()}
    for i, item in enumerate(data):
        toks = tokens(item['sentence'])
        row = {'id': item['id']}
        for c, L in lex.items():
            ws, files, folder = scene(i, 'train', out / 'train_ws' / c / f's{i}', item['ext'])
            view = scene_view(rep, ws, c == 'CONCEPT')
            interp = L.interpret(toks, view)                     # ATANOR interprets and acts first
            a = act(rep, ws, interp, out / 'train_ws' / c / f'j{i}.sqlite', f'p9-train-{c}-{i}')
            row[c] = {**_correct(interp, files, item['ext'], item['tool'], item['dest']), 'success': judge(ws, files, folder, item['tool'], item['ext'], item['dest']), **a}
            L.update(toks, view, item['tool'], truth_set(files, item['ext']), item['dest'])   # then the teacher's answer
        log.append(row)
    for c, L in lex.items():
        (out / f'lexicon_{c}.json').write_text(json.dumps(L.to_json(), indent=1, sort_keys=True), encoding='utf-8')
    shas = {c: hashlib.sha256((out / f'lexicon_{c}.json').read_bytes()).hexdigest() for c in lex}
    norm = lambda s: ' '.join(tokens(s))
    (out / 'train_sentence_hashes.json').write_text(json.dumps(sorted(hashlib.sha256(norm(x['sentence']).encode()).hexdigest() for x in data)), encoding='utf-8')
    (out / 'freeze.json').write_text(json.dumps({'frozen_at': time.time(), 'frozen_at_iso': time.strftime('%Y-%m-%dT%H:%M:%S'), 'lexicon_sha': shas,
                                                 'r1_sha': hashlib.sha256(R1_PATH.read_bytes()).hexdigest()}, indent=1), encoding='utf-8')
    (out / 'train_log.json').write_text(json.dumps(log, indent=1), encoding='utf-8')
    return log


# ---------------- evaluation process (teacher and models off) ----------------
class _NoTeacher:
    attempts = []

    def find_spec(self, name, path=None, target=None):
        if name.startswith('atanor_os.teach'):
            _NoTeacher.attempts.append(name)
            raise ImportError('teacher is off during evaluation')
        return None


NET = []


def _net_hook(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo', 'urllib.Request'):
        NET.append([event, repr(args)[:200]])


def evaluate(which='immediate', out=OUT):
    out = Path(out)
    fz = json.loads((out / 'freeze.json').read_text(encoding='utf-8'))
    hours = (time.time() - fz['frozen_at']) / 3600
    if which == 'delayed' and hours < DELAY_HOURS:
        raise RuntimeError(f'delayed test refused: only {hours:.1f} h since the freeze (needs {DELAY_HOURS} h)')
    if any(m.startswith('atanor_os.teach') for m in sys.modules):
        raise RuntimeError('teacher module loaded in the evaluation process')
    sys.meta_path.insert(0, _NoTeacher())
    sys.addaudithook(_net_hook)
    path = SEALED / f'p9_{which}.json'
    if PKG.resolve() in path.resolve().parents:
        raise RuntimeError('sealed_inside_repo')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SEALED_SHA[which]:
        raise RuntimeError('sealed file hash differs from the published hash')
    for c in ('CONCEPT', 'FLAT'):
        if hashlib.sha256((out / f'lexicon_{c}.json').read_bytes()).hexdigest() != fz['lexicon_sha'][c]:
            raise RuntimeError(f'lexicon {c} changed since the freeze')
    items = json.loads(raw.decode('utf-8'))
    rep = Representation.loads(R1_PATH.read_text(encoding='utf-8'))
    lex = {c: Lexicon.from_json(json.loads((out / f'lexicon_{c}.json').read_text(encoding='utf-8'))) for c in ('CONCEPT', 'FLAT')}
    train_h = set(json.loads((out / 'train_sentence_hashes.json').read_text(encoding='utf-8')))
    rows, overlap = [], 0
    for i, it in enumerate(items):
        toks = tokens(it['sentence'])
        overlap += hashlib.sha256(' '.join(toks).encode()).hexdigest() in train_h
        row = {'id': it['id'], 'tool': it['tool'], 'ext': it['ext'], 'seen_ext': it['ext'] in SEEN_EXT}
        for c in CONDS:
            ws, files, folder = scene(i, f'eval-{which}', out / f'{which}_ws' / c / f's{i}', it['ext'])
            if c == 'ORACLE':
                interp = {'tool': it['tool'], 'selected': truth_set(files, it['ext']), 'dest': it['dest']}
            else:
                L = lex['CONCEPT' if c == 'NONE' else c]
                view = scene_view(rep, ws, c == 'CONCEPT')
                interp = none_interp(L, toks, view) if c == 'NONE' else L.interpret(toks, view)
            a = act(rep, ws, interp, out / f'{which}_ws' / c / f'j{i}.sqlite', f'p9-{which}-{c}-{i}')
            row[c] = {**_correct(interp, files, it['ext'], it['tool'], it['dest']),
                      'success': judge(ws, files, folder, it['tool'], it['ext'], it['dest']), **a,
                      'interp': {k: interp.get(k) for k in ('tool', 'selected', 'dest')}}
        rows.append(row)
    res = {'which': which, 'hours_since_freeze': round(hours, 2), 'n': len(items), 'exact_overlap_with_training': overlap,
           'teacher_import_attempts': list(_NoTeacher.attempts), 'network_events': NET[:20], 'network_event_count': len(NET),
           'summary': summarize(rows), 'rows': rows}
    (out / f'eval_{which}.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    return res


def summarize(rows):
    s = {}
    for c in CONDS:
        def rate(key, sub=lambda r: True):
            rs = [r for r in rows if sub(r)]
            return round(sum(r[c][key] for r in rs) / max(1, len(rs)), 3)
        s[c] = {'interpretation': rate('all'), 'tool': rate('tool'), 'set': rate('set'), 'dest': rate('dest'), 'action_success': rate('success'),
                'interpretation_seen_ext': rate('all', lambda r: r['seen_ext']), 'interpretation_unseen_ext': rate('all', lambda r: not r['seen_ext']),
                'by_tool': {t: rate('all', lambda r, t=t: r['tool'] == t) for t in ('copy', 'move', 'delete')}}
    return s


def verdict(res):
    s = res['summary']
    if res['teacher_import_attempts'] or res['network_event_count']:
        return {'verdict': 'INVALID'}
    c, f, n = s['CONCEPT'], s['FLAT'], s['NONE']
    linked = c['interpretation'] >= 0.60 and c['interpretation'] >= n['interpretation'] + 0.30 and c['action_success'] >= 0.60
    return {'verdict': 'LINKED' if linked else 'WEAK',
            'concept_contribution': round(c['interpretation'] - f['interpretation'], 3),
            'concept_contribution_claimed': c['interpretation'] - f['interpretation'] >= 0.10}
