"""P6 harness (evaluator side): tasks, judge, teacher-on training, teacher-off dev check, sealed evaluation.

Training (teacher on) and evaluation (teacher off) run in separate processes. The evaluation process
installs an import guard that refuses atanor_os.teach, blocks LLM hosts and localhost (no sLLM), and
checks that the teacher's call counter was never touched; any attempt is recorded and makes the run
INVALID. Web observations are archived per condition; only URLs, sha256 and short snippets go into
the committed results (page text stays in the local, git-ignored archive).
"""
import copy
import hashlib
import json
import random
import re
import string
import sys
import time
from pathlib import Path

from ..agent.autonomy import BUDGET, FORMS, Agent, norm
from ..agent.models import RuleModel
from ..agent.reader import Lexicon, NameReader
from ..core.journal import Journal
from ..core.types import Experience
from ..world.fs_world import Workspace
from ..world.web_world import WebSession
from .generator import WORDS_TEST, WORDS_TRAIN
from .web_truth import accepts, split

PKG = Path(__file__).resolve().parents[1]
FS_EXPERIENCE = PKG / 'results' / 'p1-test-03-contrast' / 'explore' / 'experiences_s1.jsonl'
LLM_HOSTS = ('api.anthropic.com', 'api.openai.com', 'generativelanguage.googleapis.com', 'localhost', '127.0.0.1', '::1')
STOP_REASONS = ('no_evidence', 'contradiction', 'single_source')
DEV_EXTS = 4


def load_snapshot():
    return json.loads((PKG / 'results' / 'p6-truth' / 'truth.json').read_text(encoding='utf-8'))


def fs_model():
    exps = [Experience.from_json(json.loads(l)) for l in FS_EXPERIENCE.read_text(encoding='utf-8').splitlines() if l.strip()]
    return RuleModel(exps)


def impossible_ext(rng, snapshot):
    while True:
        e = ''.join(rng.choice(string.ascii_lowercase) for _ in range(5))
        if e not in snapshot['formats']:
            return e


def make_task(index, split_name, root, snapshot, exts, sentences, seed, impossible=False):
    """sentences: {form: [sentence, ...]}. Three files with distinct extensions from `exts`; an impossible
    task replaces one of them by an extension no source can name. A decoy file in a subfolder must stay."""
    rng = random.Random(f'p6-{split_name}-{seed}-{index}')
    form = FORMS[index % 3]
    sentence = rng.choice(sentences[form])
    chosen = rng.sample(sorted(exts), 3)
    words = WORDS_TEST if split_name == 'eval' else WORDS_TRAIN
    names = rng.sample(words, 4)
    imp = None
    if impossible:
        chosen[2] = impossible_ext(rng, snapshot)
        imp = f'{names[2]}.{chosen[2]}'
    ws = Workspace(root)
    files = {}
    for n, e in zip(names, chosen):
        (ws.root / f'{n}.{e}').write_bytes(f'{n} {rng.random():.6f}\n'.encode())
        files[f'{n}.{e}'] = ws.attrs(f'{n}.{e}')['hash']
    (ws.root / 'keep').mkdir()
    (ws.root / 'keep' / f'{names[3]}.txt').write_bytes(b'do not touch\n')
    decoy = {'keep': 'dir', f'keep/{names[3]}.txt': ws.attrs(f'keep/{names[3]}.txt')['hash']}
    return ws, {'index': index, 'split': split_name, 'form': form, 'sentence': sentence, 'files': files, 'impossible_file': imp,
                'decoy': decoy, 'exts': chosen}


def judge(ws, task, snapshot, result):
    """Independent re-observation of the real workspace."""
    st = ws.observe([])
    per, wrong = {}, 0
    for src, h in task['files'].items():
        ext = src.rsplit('.', 1)[1]
        base = src
        copies = [p for p, o in st.items() if o['kind'] == 'file' and o['hash'] == h and p != src]
        if src == task['impossible_file']:
            untouched = st.get(src, {}).get('kind') == 'file' and st[src]['hash'] == h and not copies
            reason = (result.get('files', {}).get(src) or {}).get('status')
            per[src] = 'correct_stop' if untouched and reason in STOP_REASONS else f'wrong:{reason}'
            continue
        if task['form'] == 'rename':
            good = [p for p in copies if '/' not in p and p.endswith('.' + ext) and accepts(snapshot, ext, p[:-(len(ext) + 1)])]
            ok = bool(good) and src not in st
        else:
            good = [p for p in copies if p.count('/') == 1 and p.split('/')[1] == base and accepts(snapshot, ext, p.split('/')[0])]
            ok = bool(good) and ((src not in st) if task['form'] == 'folder' else (st.get(src, {}).get('hash') == h))
        wrong += len([p for p in copies if p not in good])
        per[src] = 'ok' if ok else 'not_done'
    decoy_ok = st.get('keep', {}).get('kind') == 'dir' and all(st.get(p, {}).get('hash') == h for p, h in task['decoy'].items() if p != 'keep')
    possible = [s for s in task['files'] if s != task['impossible_file']]
    return {'per_file': per, 'wrong_placements': wrong, 'decoy_ok': decoy_ok,
            'completed': decoy_ok and wrong == 0 and all(per[s] == 'ok' for s in possible),
            'impossible_correct': None if task['impossible_file'] is None else per[task['impossible_file']] == 'correct_stop'}


class OracleAgent(Agent):
    """Diagnostic: names from the truth table, same interpretation-free acting (the gold form is given)."""

    def __init__(self, fs, snapshot, gold_form):
        super().__init__(fs, None, 'F')
        self.snapshot, self.gold = snapshot, gold_form

    def interpret(self, goal_text):
        return {'form': self.gold, 'margin': 99.0, 'scores': {}, 'unknown': []}

    def find_name(self, ext):
        f = self.snapshot['formats'].get(ext)
        return (f['label'], 'oracle') if f else (None, 'no_evidence')


# ---------------- state ----------------
def save_state(path, agent):
    lex, rd = agent.lex, agent.reader
    st = {'lexicon': {'c': {w: dict(d) for w, d in lex.c.items()}, 'n': dict(lex.n), 'vocab': sorted(lex.vocab),
                      'learned_from_pages': lex.learned_from_pages},
          'reader': {'w': dict(rd.w), 'util': {f'{s}|{f}': u for (s, f), u in rd.util.items()}, 'updates': rd.updates,
                     'examples': rd.examples, 'threshold': rd.threshold, 'host_util': dict(rd.host_util),
                     'spans': rd.spans.state(), 'pages': rd.pages.state()},
          'memory': agent.memory}
    Path(path).write_text(json.dumps(st, indent=1, ensure_ascii=False), encoding='utf-8')


def load_state(path):
    st = json.loads(Path(path).read_text(encoding='utf-8'))
    lex = Lexicon(FORMS)
    for w, d in st['lexicon']['c'].items():
        for f, v in d.items():
            lex.c[w][f] = v
    for f, v in st['lexicon']['n'].items():
        lex.n[f] = v
    lex.vocab = set(st['lexicon']['vocab'])
    lex.learned_from_pages = list(st['lexicon']['learned_from_pages'])
    rd = NameReader()
    for k, v in st['reader']['w'].items():
        rd.w[k] = v
    for k, u in st['reader']['util'].items():
        s, f = k.split('|', 1)
        rd.util[(s, f)] = list(u)
    rd.updates = st['reader']['updates']
    rd.threshold = st['reader'].get('threshold', 0.0)
    for h, u in st['reader'].get('host_util', {}).items():
        rd.host_util[h] = list(u)
    rd.spans.load(st['reader'].get('spans', {}))
    rd.pages.load(st['reader'].get('pages', {}))
    ex = st['reader'].get('examples') or {}
    rd.examples = {'rank': [(list(fs), list(g)) for fs, g in ex.get('rank', [])], 'trust': [tuple(x) for x in ex.get('trust', [])]}
    return lex, rd, st['memory']


# ---------------- training (teacher on) ----------------
def train(out, epochs=3, seed=1, n_extra=60, reading_epochs=2):
    from ..teach import teacher                                    # training process only
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    snap = load_snapshot()
    pools = split(snap)
    rng = random.Random(f'p6-train-{seed}')
    teach_exts = sorted(pools['train'])
    rng.shuffle(teach_exts)
    dev_exts, teach_exts = sorted(teach_exts[:DEV_EXTS]), sorted(teach_exts[DEV_EXTS:])
    extra = json.loads((PKG / 'results' / 'p6-truth' / 'train_extra.json').read_text(encoding='utf-8'))['formats']
    teacher.EXTRA.update(extra)
    teach_exts = teach_exts + sorted(extra)[:n_extra]
    assert not set(teach_exts) & set(pools['eval']) and not set(dev_exts) & set(teach_exts)
    web = WebSession(out / 'web', min_interval=1.0)
    agent = Agent(fs_model(), web, 'F')
    log = {'dev_exts': dev_exts, 'teach_exts': teach_exts, 'lexicon_epochs': [], 'reading_epochs': []}
    opened_by_ext = {}
    sents = list(teacher.TRAIN_SENTENCES)
    for ep in range(epochs):
        rng.shuffle(sents)
        right = 0
        for s, _ in sents:
            pred = agent.lex.interpret(s)['form']                   # ATANOR answers first
            ok, gold = teacher.feedback_form(s, pred)
            right += ok
            agent.lex.learn(s, gold)
        log['lexicon_epochs'].append({'epoch': ep, 'accuracy_before_feedback': right / len(sents)})
    for ep in range(reading_epochs):
        rows = []
        for ext in teach_exts:
            agent.memory.pop(ext, None)
            agent.failed.pop(ext, None)
            agent.trace = []
            name, how = agent.find_name(ext)                       # ATANOR's own searching and choosing
            pages = [t for t in agent.trace if t['action'] == 'open' and t.get('ok')]
            opened_by_ext.setdefault(ext, [])
            opened_by_ext[ext] += [t['url'] for t in pages if t['url'] not in opened_by_ext[ext]]
            for t in pages:                                        # teacher feedback on every page it chose to open
                p = web.open(t['url'])
                agent.reader.record_host(t['url'], bool(t.get('best')) and teacher.feedback_name(snap, ext, t['best']['name']))
                if p.get('ok'):
                    agent.reader.train(p['text'], ext, t['url'].rstrip('/').rsplit('/', 1)[-1].replace('_', ' '),
                                       lambda n, e=ext: teacher.feedback_name(snap, e, n), refit=False)
            if len(rows) % 6 == 5 or ext == teach_exts[-1]:
                agent.reader.fit()                                 # refit periodically (cost grows with examples)
            for t in agent.trace:
                if t['action'] == 'search':
                    form = next((f for f in ('{ext} file format', '.{ext} file extension', '{EXT} format', '{ext}')
                                 if f.format(ext=ext, EXT=ext.upper()) == t['query']), None)
                    if form:
                        hit = any(p.get('best') and teacher.feedback_name(snap, ext, p['best']['name']) for p in pages)
                        agent.reader.record_query(t['service'], form, hit)
            correct = name is not None and teacher.feedback_name(snap, ext, name)
            if not correct:
                agent.memory[ext] = {'name': teacher.correct_name(snap, ext), 'source': 'teacher', 'evidence': []}
            rows.append({'ext': ext, 'adopted': name, 'how': how, 'correct': correct, 'pages': len(pages),
                         'searches': sum(t['action'] == 'search' for t in agent.trace)})
        log['reading_epochs'].append({'epoch': ep, 'adopted_correct': sum(r['correct'] for r in rows), 'n': len(rows),
                                      'adopted_wrong': sum(r['adopted'] is not None and not r['correct'] for r in rows), 'rows': rows})
    agent.reader.fit()
    per_ext = []                                                   # calibration data: pages ATANOR chose, final weights
    for ext, urls in opened_by_ext.items():
        rows_c = []
        for u in urls:
            p = web.open(u)
            if p.get('ok'):
                b = agent.reader.best(p['text'], ext, u.rstrip('/').rsplit('/', 1)[-1].replace('_', ' '))
                if b:
                    rows_c.append((u, b['name'], b['score'], teacher.feedback_name(snap, ext, b['name'])))
        per_ext.append((ext, rows_c))
    log['calibration'] = agent.reader.calibrate(per_ext)
    log['teacher_calls'] = teacher.CALLS['n']
    (out / 'dev_sentences.json').write_text(json.dumps(teacher.DEV_SENTENCES, indent=1), encoding='utf-8')
    (out / 'train_sentences.json').write_text(json.dumps(teacher.TRAIN_SENTENCES, indent=1), encoding='utf-8')
    log['web'] = web.stats()
    save_state(out / 'state.json', agent)
    (out / 'train_log.json').write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding='utf-8')
    return log


# ---------------- teacher-off runs ----------------
class _NoTeacher:
    """Import guard: any import of atanor_os.teach in this process is refused and recorded."""
    attempts = []

    def find_spec(self, name, path=None, target=None):
        if name.startswith('atanor_os.teach'):
            _NoTeacher.attempts.append(name)
            raise ImportError('teacher is off during evaluation')
        return None


def teacher_off():
    if any(m.startswith('atanor_os.teach') for m in sys.modules):
        raise RuntimeError('teacher module already loaded in the evaluation process')
    sys.meta_path.insert(0, _NoTeacher())


def run_condition(cond, tasks_spec, state_path, out, snapshot, sentences, split_name, seed, perception_factory=None):
    """cond: F, S, M, N, ORACLE, or F_LM / S_LM (P7: same agent with the language model as its reading tool)."""
    out = Path(out)
    lex, rd, mem = load_state(state_path)
    fs = fs_model()
    base = cond[:-3] if cond.endswith('_LM') else cond
    web = WebSession(out / 'web', min_interval=1.0, blocked_hosts=LLM_HOSTS) if base in ('F', 'S') else None
    memory = {} if base == 'N' else copy.deepcopy(mem)
    perception = perception_factory(out) if cond.endswith('_LM') else None
    agent = None if cond == 'ORACLE' else Agent(fs, web, base, memory, lex, rd, perception=perception)
    rows = []
    for spec in tasks_spec:
        ws, task = make_task(spec['index'], split_name, out / 'ws' / f't{spec["index"]}', snapshot, spec['exts'], sentences, seed,
                             spec['impossible'])
        j = Journal(out / f'journal_t{spec["index"]}.sqlite')
        a = OracleAgent(fs, snapshot, task['form']) if cond == 'ORACLE' else agent
        a.trace, a.t0 = [], time.time()
        t0 = time.time()
        res = a.run(task['sentence'], ws, j)
        j.close()
        verdict = judge(ws, task, snapshot, res)
        rows.append({'cond': cond, **{k: task[k] for k in ('index', 'form', 'sentence', 'exts', 'impossible_file')},
                     'interpreted_form': res['form'], 'form_correct': res['form'] == task['form'], 'result': res,
                     'judge': verdict, 'seconds': time.time() - t0,
                     'info_actions': sum(t['action'] in ('search', 'open', 'follow') for t in a.trace),
                     'trace': [{k: v for k, v in t.items() if k != 'text'} for t in a.trace]})
    stats = web.stats() if web else {'requests': 0}
    blocked = 0
    if web and (out / 'web' / 'fetch_log.jsonl').exists():
        blocked = sum('blocked_host' in l for l in (out / 'web' / 'fetch_log.jsonl').read_text(encoding='utf-8').splitlines())
    return rows, {'web': stats, 'llm_or_local_host_attempts': blocked, 'model_calls': None if agent is None or agent.perception is None else agent.perception.calls,
                  'memory_after': None if agent is None else {e: v['name'] for e, v in agent.memory.items()},
                  'self_learned_words': [] if agent is None else agent.lex.learned_from_pages}


def summarize(rows_by_cond):
    s = {}
    for c, rows in rows_by_cond.items():
        poss = [r for r in rows if r['impossible_file'] is None]
        imp = [r for r in rows if r['impossible_file'] is not None]
        s[c] = {'possible_tasks': len(poss), 'completion': sum(r['judge']['completed'] for r in poss) / max(1, len(poss)),
                'impossible_tasks': len(imp), 'correct_stops': sum(bool(r['judge']['impossible_correct']) for r in imp),
                'wrong_placements_per_task': sum(r['judge']['wrong_placements'] for r in rows) / max(1, len(rows)),
                'form_accuracy': sum(r['form_correct'] for r in rows) / max(1, len(rows)),
                'info_actions_per_task': sum(r['info_actions'] for r in rows) / max(1, len(rows)),
                'seconds_per_task': sum(r['seconds'] for r in rows) / max(1, len(rows)),
                'file_status': _count(st['status'] for r in rows for st in r['result'].get('files', {}).values()),
                'goal_unclear': sum(r['result'].get('stopped') == 'goal_unclear' for r in rows)}
    return s


def _count(xs):
    out = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


def paired(rows_a, rows_b):
    kb = {r['index']: r for r in rows_b}
    pairs = [(r, kb[r['index']]) for r in rows_a if r['impossible_file'] is None and r['index'] in kb]
    d = [int(x['judge']['completed']) - int(y['judge']['completed']) for x, y in pairs]
    return {'pairs': len(pairs), 'mean_pp': 100 * sum(d) / max(1, len(d)), 'pos': sum(v > 0 for v in d), 'neg': sum(v < 0 for v in d)}


def dev(state_path, out, n_tasks=6, seed=1, conditions=('ORACLE', 'N', 'S', 'F')):
    """Teacher-off check on held-out training extensions and held-out training sentences."""
    teacher_off()
    snap = load_snapshot()
    out = Path(out)
    tl = json.loads((Path(state_path).parent / 'train_log.json').read_text(encoding='utf-8'))
    dev_sents = json.loads((Path(state_path).parent / 'dev_sentences.json').read_text(encoding='utf-8'))
    sentences = {f: [s for s, g in dev_sents if g == f] for f in FORMS}
    exts = tl['dev_exts'] + tl['teach_exts'][:2]
    specs = [{'index': i, 'exts': exts, 'impossible': i >= n_tasks - 1} for i in range(n_tasks)]
    rows, extra = {}, {}
    for c in conditions:
        rows[c], extra[c] = run_condition(c, specs, state_path, out / c, snap, sentences, 'dev', seed)
    res = {'summary': summarize(rows), 'F_vs_N': paired(rows['F'], rows['N']) if 'F' in rows and 'N' in rows else None,
           'extra': extra, 'teacher_import_attempts': _NoTeacher.attempts}
    (out / 'dev_result.json').write_text(json.dumps({'result': res, 'rows': rows}, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
    return res


# ---------------- sealed evaluation (teacher off) ----------------
def _nwords(s):
    return ' '.join(re.findall(r'[a-z]+', s.lower()))


def evaluate(state_path, sealed_path, commit_hash, out, conditions=('ORACLE', 'N', 'M', 'S', 'F'), n_possible=30, n_impossible=6,
             protocol=None):
    teacher_off()
    if Path(sealed_path).resolve().is_relative_to(PKG.resolve()):
        raise RuntimeError('sealed_inside_repo: keep sealed originals outside the repository; publish only their hash before the run')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    snap = load_snapshot()
    pools = split(snap)
    sealed_bytes = Path(sealed_path).read_bytes()
    sealed = json.loads(sealed_bytes)['sentences']
    sentences = {f: [x['sentence'] for x in sealed if x['form'] == f] for f in FORMS}
    trained = json.loads((Path(state_path).parent / 'train_sentences.json').read_text(encoding='utf-8'))
    trained += json.loads((Path(state_path).parent / 'dev_sentences.json').read_text(encoding='utf-8'))
    overlap = sorted({_nwords(s) for s, _ in trained} & {_nwords(x['sentence']) for x in sealed})
    tl = json.loads((Path(state_path).parent / 'train_log.json').read_text(encoding='utf-8'))
    ext_overlap = sorted(set(pools['eval']) & (set(tl['teach_exts']) | set(tl['dev_exts'])))
    seed = int(hashlib.sha256(commit_hash.encode()).hexdigest(), 16) % (2 ** 31)
    specs = [{'index': i, 'exts': pools['eval'], 'impossible': i >= n_possible} for i in range(n_possible + n_impossible)]
    rows, extra = {}, {}
    for c in conditions:
        rows[c], extra[c] = run_condition(c, specs, state_path, out / c, snap, sentences, 'eval', seed)
    summ = summarize(rows)
    checks = {'teacher_import_attempts': list(_NoTeacher.attempts),
              'teacher_module_loaded': any(m.startswith('atanor_os.teach') for m in sys.modules),
              'llm_or_local_host_attempts': {c: e['llm_or_local_host_attempts'] for c, e in extra.items()},
              'sentence_overlap_with_training': overlap, 'extension_overlap_with_training': ext_overlap,
              'sealed_sha256': hashlib.sha256(sealed_bytes).hexdigest(), 'commit_hash': commit_hash, 'seed': seed,
              'oracle_completion': summ.get('ORACLE', {}).get('completion')}
    res = {'summary': summ, 'F_vs_N': paired(rows['F'], rows['N']), 'F_vs_S': paired(rows['F'], rows['S']),
           'F_vs_M': paired(rows['F'], rows['M']), 'checks': checks, 'secondary': secondary(rows, out), 'extra': extra}
    res['verdict'] = verdict(res, protocol or {})
    (out / 'p6_result.json').write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
    (out / 'p6_rows.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
    return res


def secondary(rows, out):
    """Trigger validity, evidence validity, conflict handling, from the traces and the local web archive."""
    import gzip
    s = {}
    for c, rs in rows.items():
        if c == 'ORACLE':
            continue
        invalid_triggers, info, evid_ok, evid_n = 0, 0, 0, 0
        conflicts = {'adopted_despite_disagreement': 0, 'stopped_contradiction': 0, 'stopped_single_source': 0}
        known, adopted = set(), {}
        for r in rs:
            for t in r['trace']:
                if t['action'] in ('search', 'open', 'follow') and t.get('ext'):
                    info += 1
                    invalid_triggers += int(t['ext'] in known and t['action'] == 'search')
                if t['action'] in ('recall', 'compare'):
                    known.add(t.get('ext'))
                if t['action'] == 'compare':
                    adopted[t['ext']] = (t['name'], t['sources'])
                    conflicts['adopted_despite_disagreement'] += int(bool(t.get('disagreeing')))
                if t['action'] == 'stop_fact':
                    conflicts['stopped_contradiction'] += int(t.get('reason') == 'contradiction')
                    conflicts['stopped_single_source'] += int(t.get('reason') == 'single_source')
        arch = out / c / 'web' / 'pages'
        sha_of = {}
        for r in rs:
            for t in r['trace']:
                if t['action'] == 'open' and t.get('ok') and t.get('sha256'):
                    sha_of[t['url']] = t['sha256']
        for ext, (name, sources) in adopted.items():
            for u in sources:
                p = arch / f"{sha_of.get(u, '')}.json.gz"
                if u in sha_of and p.exists():
                    text = json.loads(gzip.decompress(p.read_bytes()))['text'].lower()
                    evid_n += 1
                    evid_ok += int(name.lower() in text and ext.lower() in text)
        s[c] = {'information_actions': info, 'searches_for_already_known_fact': invalid_triggers, 'conflicts': conflicts,
                'evidence_pages_checked': evid_n, 'evidence_pages_with_name_and_extension': evid_ok}
    return s


def verdict(res, protocol):
    ck, sm = res['checks'], res['summary']
    invalid = (ck['teacher_import_attempts'] or ck['teacher_module_loaded'] or any(ck['llm_or_local_host_attempts'].values())
               or ck['sentence_overlap_with_training'] or ck['extension_overlap_with_training'] or (ck['oracle_completion'] or 0) < 1.0)
    if invalid:
        return 'INVALID'
    F, d = sm['F'], res['F_vs_N']['mean_pp']
    gain = (d >= protocol.get('min_gain_pp', 30) and F['completion'] >= protocol.get('min_completion', 0.5)
            and F['correct_stops'] >= protocol.get('min_correct_stops_frac', 2 / 3) * F['impossible_tasks']
            and F['wrong_placements_per_task'] <= protocol.get('max_wrong_per_task', 0.5))
    if gain:
        return 'GAIN'
    if d <= 0 or F['completion'] < protocol.get('no_gain_completion', 0.2):
        return 'NO_GAIN'
    return 'INCONCLUSIVE'
