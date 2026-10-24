"""ATANOR living core: one persistent mind in one persistent workspace.

Loop for every command: interpret (from the learned lexicon) -> if the user's intent is unclear, ask the user
(explain a word / point at the objects / demonstrate once) -> turn the intended change into a goal -> plan with
the world model learned from stored episodes -> if no plan, the gap is about the world: experiment in a lab copy
(ask for a demonstration only when the experiment budget is spent) -> act in the real workspace, every outcome
checks a prediction and is stored -> ask for confirmation -> learn the words from the confirmed interpretation.

What is provided (not learned): the body's tool names and arity, the observation adapter and atom families, the
contrast-induction algorithm, the planner, the path relations a change can be expressed in (o, D, D/name(o)),
the question formats, and two policies: intent gaps are asked (only the user knows the intent), world gaps are
experimented first. What is learned: every tool's preconditions and effects (from episodes), which changes words
ask for, which objects words pick out, where the destination name stands, which words carry nothing.
Never imports teach/ or eval/.
"""
import hashlib
import json
import random
import re
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path

from ..core.types import Experience, Goal, Literal
from ..world.raw_obs import raw_attrs
from .concepts import FAMILIES_ALL, apply_raw, atoms, induce
from .planner import plan

LAB_BUDGET = 60            # provided: lab actions per world gap before asking for a demonstration
BUDGET = {'actions': 40, 'predictions': 400000, 'nodes': 800, 'depth': 12, 'seconds': 120.0}


def tokens(sentence):
    return re.findall(r'[a-z0-9]+', sentence.lower())


def name_of(p):
    return p.rsplit('/', 1)[-1]


# ---------------------------------------------------------------- world model from episodes
class WorldModel:
    """Rules re-induced from every stored episode (nothing summarised away). Three-valued predictions:
    a success is only predicted when the argument kinds were seen succeeding AND the rule is backed by at least one
    excluded failure (an unchecked generalisation is not a fact); otherwise 'unknown' (a reason to experiment)."""
    name = 'LIFE'

    def __init__(self, episodes, body='fs', generalize=True, notice_change=True, retired=None):
        self.body, self.generalize = body, generalize
        eps = [e for e in episodes if not e.blocked]
        retired = retired or {}                    # tool -> number of episodes before a re-verified world change
        eps = [e for i, e in enumerate(eps) if i >= retired.get(e.tool, -1)]
        self.changes = []
        if notice_change:
            # the same situation and action gave a different result than before: the world changed for that tool;
            # its older episodes are set aside (kept in memory, not used) and the tool is relearned from newer ones
            last, cut = {}, {}
            for i, e in enumerate(eps):
                k = (e.tool, atoms(body, e.pre, e.args, FAMILIES_ALL))
                if k in last and last[k][1] != e.succeeded:
                    cut[e.tool] = i
                    self.changes.append({'tool': e.tool, 'at_episode': e.id, 'was': last[k][1], 'now': e.succeeded})
                last[k] = (i, e.succeeded)
            eps = [e for i, e in enumerate(eps) if i >= cut.get(e.tool, -1)]
        self.eps = eps
        self.rules = induce(body, self.eps, FAMILIES_ALL) if self.eps else {}
        self.exact = defaultdict(dict)
        self.kinds_ok = defaultdict(set)
        self.kinds_seen = defaultdict(set)
        for e in self.eps:
            at = atoms(body, e.pre, e.args, FAMILIES_ALL)
            self.exact[e.tool][at] = e
            k = self.kinds(e.pre, e.args)
            self.kinds_seen[e.tool].add(k)
            if e.succeeded:
                self.kinds_ok[e.tool].add(k)
        self._cache = {}
        self.unknown_asked = Counter()

    def kinds(self, state, args):
        return tuple((raw_attrs(self.body, state[a])['a0'], raw_attrs(self.body, state[a])['a1']) if a in state else None for a in args)

    def predict(self, state, tool, args, sig=None):
        if any(a not in state for a in args):
            return None, 'unknown'
        at = atoms(self.body, state, args, FAMILIES_ALL)
        key = (tool, at)
        if key not in self._cache:
            self._cache[key] = self._judge(state, tool, args, at)
        verdict, g = self._cache[key]
        if verdict == 'unknown':
            self.unknown_asked[tool] += 1
        if verdict in ('known', 'learned'):
            return apply_raw(self.body, state, args, g['eff']), verdict
        return None, verdict

    def _judge(self, state, tool, args, at):
        groups = sorted(self.rules.get(tool, []), key=lambda g: -g['support'])
        e = self.exact[tool].get(at)
        if e is not None:
            if not e.succeeded:
                return 'known_fail', None
            g = next((g for g in groups if all(tuple(a) in at for a in g['pre'])), None)
            return ('known', g) if g else ('unknown', None)
        if not self.generalize:
            return 'unknown', None
        g = next((g for g in groups if all(tuple(a) in at for a in g['pre'])), None)
        k = self.kinds(state, args)
        if g is None:
            fails = sum(1 for e in self.eps if e.tool == tool and not e.succeeded and self.kinds(e.pre, e.args) == k)
            return ('learned_fail', None) if k not in self.kinds_ok[tool] and fails >= 3 else ('unknown', None)
        backed = sum(g.get('ev', {}).values()) > 0
        if k in self.kinds_ok[tool] and backed:
            return 'learned', g
        return 'unknown', None

    def update(self, exp):
        pass


class Optimistic:
    """The same knowledge, but an unchecked generalisation is assumed to hold (used only to choose lab experiments)."""
    name = 'OPTIMISTIC'

    def __init__(self, model):
        self.m = model

    def predict(self, state, tool, args, sig=None):
        post, st = self.m.predict(state, tool, args)
        if st != 'unknown' or any(a not in state for a in args):
            return post, st
        at = atoms(self.m.body, state, args, FAMILIES_ALL)
        g = next((g for g in sorted(self.m.rules.get(tool, []), key=lambda g: -g['support']) if all(tuple(a) in at for a in g['pre'])), None)
        return (apply_raw(self.m.body, state, args, g['eff']), 'optimistic') if g else (None, 'unknown')

    def update(self, exp):
        pass


# ---------------------------------------------------------------- lexicon: words <-> intended change, objects, destination
class Lexicon:
    def __init__(self, mode='general'):
        self.mode = mode                        # 'general' or 'case' (exact sentence-shape retrieval only)
        self.word_n = Counter()
        self.pattern_of = defaultdict(Counter)  # word -> pid counts (from confirmed / demonstrated uses)
        self.meaning = {}                       # word -> set(repr(atom)) intersected over selections
        self.neutral = set()                    # words the user explained as carrying nothing
        self.marker = Counter()
        self.prev_n = Counter()
        self.value_rule = [0, 0]
        self.cases = {}                         # 'case' mode: sentence shape -> (pid, constraints)
        self.confirmed = Counter()              # word -> confirmed uses (the result was what the person wanted)

    # -- learning from one confirmed or taught interpretation
    def learn(self, toks, view, pid, selected, dest):
        d_idx = toks.index(dest) if dest in toks else None
        if d_idx:
            self.marker[toks[d_idx - 1]] += 1
        for i, w in enumerate(toks):
            if i != d_idx and i + 1 < len(toks):
                self.prev_n[w] += 1
        sel = [view[o][0] for o in selected if o in view]
        common = frozenset.intersection(*[a for a, _ in view.values()]) if view else frozenset()
        inter = (frozenset.intersection(*sel) - common) if sel else frozenset()
        cur = {repr(a) for a in inter}
        values = {v for _, v in view.values()}
        for w in set(t for i, t in enumerate(toks) if i != d_idx):
            self.word_n[w] += 1
            if pid is not None:
                self.pattern_of[w][pid] += 1
            if w not in self.neutral:
                self.meaning[w] = cur if w not in self.meaning else (self.meaning[w] & cur)
        for w in set(toks):
            if w in values:
                self.value_rule[1] += 1
                self.value_rule[0] += int(bool(selected) and set(selected) <= {o for o, (_, v) in view.items() if v == w})
        self.cases[self._shape(toks, view, dest)] = (pid, sorted(cur))

    def learn_word(self, word, pids=None, meaning=None, neutral=False):
        self.word_n[word] += 1
        if neutral:
            self.neutral.add(word)
            self.meaning.pop(word, None)
            return
        for p in pids or []:
            self.pattern_of[word][p] += 1
        if meaning is not None:
            self.meaning[word] = set(meaning)

    def _shape(self, toks, view, dest):
        values = {v for _, v in view.values()}
        return ' '.join('<D>' if t == dest else ('<V>' if t in values else t) for t in toks)

    # -- interpretation (with what is still unknown)
    def interpret(self, toks, view, takes_dest):
        values = {v for _, v in view.values()}
        dest = self._dest(toks, values)
        unknown = [t for t in toks if self.word_n[t] == 0 and t != dest and t not in values]
        if self.mode == 'case':
            c = self.cases.get(self._shape(toks, view, dest))
            if c is None:
                return {'pid': None, 'dest': dest, 'selected': [], 'unknown': unknown or ['<shape>'], 'contradiction': False}
            pid, cons = c[0], set(c[1])
            vals = [t for t in toks if t in values]
            cons = {a for a in cons if not a.startswith("('U', 0, 'a2'")} | {repr(a) for o, (at, v) in view.items() if v in vals for a in at if a[0] == 'U' and a[2] == 'a2'}
            sel = sorted(o for o, (at, _) in view.items() if cons <= {repr(a) for a in at})
            return {'pid': pid, 'dest': dest, 'selected': sel, 'unknown': [], 'contradiction': False}
        votes = Counter()
        for t in toks:
            pc = self.pattern_of.get(t)
            if t in values or t == dest:
                continue                                    # a word that names objects does not name the change
            if pc and len(pc) == 1 and t not in self.neutral:
                votes[next(iter(pc))] += 1
        pid = votes.most_common(1)[0][0] if votes else None
        ambiguous = len(votes) > 1                          # words in one sentence point to different changes
        cons = set()
        for t in toks:
            if t != dest and t not in self.neutral and self.word_n[t] and self.meaning.get(t):
                cons |= self.meaning[t]
        hits, opp = self.value_rule
        if opp >= 2 and hits / opp >= 0.8:
            for t in toks:
                if t != dest and t in values:
                    cons = {a for a in cons if not a.startswith("('U', 0, 'a2'")}
                    cons |= {repr(a) for o, (at, v) in view.items() if v == t for a in at if a[0] == 'U' and a[2] == 'a2'}
        a2 = {a for a in cons if a.startswith("('U', 0, 'a2'")}
        contradiction = len(a2) > 1
        sel = [] if contradiction else sorted(o for o, (at, _) in view.items() if cons <= {repr(a) for a in at})
        return {'pid': pid, 'dest': dest, 'selected': sel, 'unknown': unknown, 'contradiction': contradiction, 'ambiguous': ambiguous}

    def _dest(self, toks, values):
        best, best_s = None, 0.0
        for i in range(1, len(toks)):
            w, prev = toks[i], toks[i - 1]
            if w in values or (self.word_n[w] and (self.pattern_of.get(w) or self.meaning.get(w) or w in self.neutral)):
                continue
            s = self.marker[prev] / self.prev_n[prev] if self.prev_n[prev] else 0.0
            if s > best_s:
                best, best_s = w, s
        return best

    def to_json(self):
        return {'mode': self.mode, 'word_n': dict(self.word_n), 'pattern_of': {w: dict(c) for w, c in self.pattern_of.items()},
                'meaning': {w: sorted(m) for w, m in self.meaning.items()}, 'neutral': sorted(self.neutral),
                'marker': dict(self.marker), 'prev_n': dict(self.prev_n), 'value_rule': self.value_rule,
                'cases': {k: [v[0], v[1]] for k, v in self.cases.items()}, 'confirmed': dict(self.confirmed)}

    @staticmethod
    def from_json(d):
        x = Lexicon(d.get('mode', 'general'))
        x.word_n = Counter(d['word_n'])
        x.pattern_of = defaultdict(Counter, {w: Counter(c) for w, c in d['pattern_of'].items()})
        x.meaning = {w: set(m) for w, m in d['meaning'].items()}
        x.neutral = set(d['neutral'])
        x.marker, x.prev_n, x.value_rule = Counter(d['marker']), Counter(d['prev_n']), list(d['value_rule'])
        x.cases = {k: (v[0], v[1]) for k, v in d['cases'].items()}
        x.confirmed = Counter(d.get('confirmed', {}))
        return x


# ---------------------------------------------------------------- the mind
class Mind:
    def __init__(self, home, mind_dir, lab_root, user=None, generalize=True, lexicon_mode='general', seed=0, fixed=False, notice_change=True):
        """home: the body (a workspace); user: the channel to the person (ask_* / confirm), or None."""
        self.home, self.dir, self.lab_root, self.user = home, Path(mind_dir), Path(lab_root), user
        self.dir.mkdir(parents=True, exist_ok=True)
        self.generalize, self.fixed, self.notice_change = generalize, fixed, notice_change
        self.rng = random.Random(seed)
        self.episodes = self._load_episodes()
        lp = self.dir / 'lexicon.json'
        self.lex = Lexicon.from_json(json.loads(lp.read_text(encoding='utf-8'))) if lp.exists() else Lexicon(lexicon_mode)
        pp = self.dir / 'patterns.json'
        self.patterns = json.loads(pp.read_text(encoding='utf-8')) if pp.exists() else {}
        rp = self.dir / 'procedures.json'
        self.procedures = json.loads(rp.read_text(encoding='utf-8')) if rp.exists() else {}
        cp = self.dir / 'changes.json'
        self.world_changes = json.loads(cp.read_text(encoding='utf-8')) if cp.exists() else []
        mp = self.dir / 'methods.json'
        self.methods = json.loads(mp.read_text(encoding='utf-8')) if mp.exists() else {'explain': [0, 0], 'check': [0, 0]}
        self._model = None
        self._noticed = []
        self.counts = Counter()

    # ---- memory
    def _load_episodes(self):
        p = self.dir / 'episodes.jsonl'
        if not p.exists():
            return []
        return [Experience.from_json(json.loads(l)) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]

    def _store(self, exp):
        self.episodes.append(exp)
        with open(self.dir / 'episodes.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(exp.to_json()) + '\n')
        self._model = None

    def save(self):
        (self.dir / 'lexicon.json').write_text(json.dumps(self.lex.to_json(), indent=1, sort_keys=True), encoding='utf-8')
        (self.dir / 'patterns.json').write_text(json.dumps(self.patterns, indent=1, sort_keys=True), encoding='utf-8')
        (self.dir / 'methods.json').write_text(json.dumps(self.methods), encoding='utf-8')
        (self.dir / 'changes.json').write_text(json.dumps(self.world_changes, indent=1), encoding='utf-8')
        (self.dir / 'procedures.json').write_text(json.dumps(self.procedures, indent=1), encoding='utf-8')

    def log(self, **kw):
        with open(self.dir / 'log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'t': round(time.time(), 3), **kw}, default=str) + '\n')

    @property
    def model(self):
        if self._model is None:
            retired = {c['tool']: c['before'] for c in self.world_changes} if self.notice_change else {}
            self._model = WorldModel(self.episodes, generalize=self.generalize, notice_change=self.notice_change, retired=retired)
            for c in self._model.changes:
                if c not in self._noticed:
                    self._noticed.append(c)
                    self.log(event='world_change', **c)
        return self._model

    def _task(self, d=None):
        p = self.dir / 'task.json'
        if d is None:
            return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
        p.write_text(json.dumps(d, indent=1), encoding='utf-8')

    # ---- what ATANOR sees of its home
    def view(self, ws=None):
        ws = ws or self.home
        objs = ws.existing()
        st = ws.observe(objs)
        return {o: (frozenset(a for a in atoms('fs', st, (o,), FAMILIES_ALL) if a[0] != 'E'), raw_attrs('fs', st[o])['a2']) for o in objs}

    # ---- one command, start to finish (resumable)
    def do(self, command, task_id):
        t = self._task()
        if t and t.get('status') == 'in_progress' and t['id'] == task_id:
            self.counts['resumed'] += 1
            self.log(event='resume', task=task_id, stage=t['stage'])
        else:
            t = {'id': task_id, 'command': command, 'status': 'in_progress', 'stage': 'interpret'}
            self._task(t)
        toks = tokens(command)
        if t['stage'] == 'interpret':
            interp = self._understand(toks, command)
            if interp is None:
                t.update(status='gave_up', stage='interpret')
                self._task(t)
                return {'ok': False, 'reason': 'not understood'}
            t.update(stage='act', interp=interp)
            self._task(t)
        interp = t['interp']
        goal = self._goal(interp)
        if goal is None:
            t.update(status='gave_up', stage='goal')
            self._task(t)
            return {'ok': False, 'reason': 'no goal'}
        done = self._achieve(goal, task_id)
        t.update(stage='confirm', achieved=done)
        self._task(t)
        confirmed = None
        if self.user is not None:
            confirmed = self.user.confirm(command)
            self.counts['confirm'] += 1
        if confirmed or (confirmed is None and done):
            self.lex.learn(toks, view_from_json(interp['view_at_start']), interp['pid'], interp['selected'], interp['dest'])
        if confirmed:
            for w in set(toks):
                self.lex.confirmed[w] += 1
        elif confirmed is False and self.user is not None:
            self.counts['corrections'] += 1
            self.log(event='wrong', task=task_id, interp={k: interp[k] for k in ('pid', 'selected', 'dest')})
            self._teach_from_demo(toks, command, interp_hint=interp)     # the counter-example corrects the words
        self.save()
        t.update(status='done', ok=bool(confirmed if confirmed is not None else done))
        self._task(t)
        return {'ok': t['ok'], 'achieved': done, 'confirmed': confirmed}

    # ---- understanding the command (intent gaps are asked; nothing else knows the intent)
    def _understand(self, toks, command):
        view = self.view()
        asked_words, checked, rejected = set(), set(), set()
        key = lambda r: (r['pid'], tuple(r['selected']), r['dest'])
        for _ in range(8):
            if self.fixed:                                    # fixed human procedure: always ask to be shown
                self._teach_from_demo(toks, command)
                break
            r = self.lex.interpret(toks, view, True)
            if r['unknown'] and self.user is not None:
                if not self.patterns or '<shape>' in r['unknown']:
                    self._teach_from_demo(toks, command)          # nothing known yet to explain it with: be shown
                    continue
                rate = lambda m: (self.methods[m][0] + 1) / (self.methods[m][1] + 2)
                word = next((w for w in r['unknown'] if w not in asked_words), None) if len(asked_words) < 2 else None
                can_check = self._complete(r) and key(r) not in checked
                if can_check and (word is None or rate('check') >= rate('explain')):
                    checked.add(key(r))
                    ok = self.user.check({'change': self.patterns[r['pid']], 'objects': r['selected'], 'dest': r['dest']})
                    self.counts['check'] += 1
                    self.methods['check'][0] += int(ok)
                    self.methods['check'][1] += 1
                    self.log(event='ask_check', unknown=r['unknown'], ok=ok)
                    if ok:
                        return self._result(r, view)              # the unknown words are learned from this confirmed use
                    rejected.add(key(r))
                    continue
                if word is not None:
                    asked_words.add(word)
                    ans = self.user.explain(word)
                    self.counts['explain'] += 1
                    learned = self._learn_explanation(word, ans, view)
                    self.methods['explain'][0] += int(learned)
                    self.methods['explain'][1] += 1
                    self.log(event='ask_explain', word=word, answer=ans, learned=learned)
                    continue
                self._teach_from_demo(toks, command)
                continue
            if r['pid'] is None or r['pid'] not in self.patterns:
                if self.user is None:
                    return None
                self._teach_from_demo(toks, command)
                continue
            needs_dest = any(it[0] != 'o' for it in self.patterns[r['pid']])
            if r['contradiction'] or not r['selected'] or (needs_dest and not r['dest']):
                if self.user is None:
                    return None
                ans = self.user.point(command)
                self.counts['point'] += 1
                self.log(event='ask_point', why='contradiction' if r['contradiction'] else ('nothing selected' if not r['selected'] else 'no destination'))
                self.lex.learn(toks, view, r['pid'], ans['objects'], ans['dest'])
                continue
            break
        r = self.lex.interpret(toks, view, True)
        if not self._complete(r) or key(r) in rejected:
            return None                                       # never act on an interpretation the person rejected
        if r.get('ambiguous') and key(r) not in checked:
            if self.user is None:
                self.counts['refused_ambiguous'] += 1
                self.log(event='refuse_ambiguous', command=command)
                return None
            ok = self.user.check({'change': self.patterns[r['pid']], 'objects': r['selected'], 'dest': r['dest']})
            self.counts['check'] += 1
            self.methods['check'][0] += int(ok)
            self.methods['check'][1] += 1
            self.log(event='ask_check', why='ambiguous', ok=ok)
            checked.add(key(r))
            if not ok:
                old = key(r)
                self._teach_from_demo(toks, command)
                r = self.lex.interpret(toks, view, True)
                if not self._complete(r) or key(r) == old:
                    return None
                return self._result(r, view)
        if self._irreversible(r['pid']) and key(r) not in checked:
            values = {v for _, v in view.values()}
            unproven = [t for t in toks if t != r['dest'] and t not in values and not self.lex.confirmed[t]]
            if unproven:
                if self.user is None:
                    self.counts['refused_irreversible'] += 1
                    self.log(event='refuse_irreversible', words=unproven)
                    return None
                ok = self.user.check({'change': self.patterns[r['pid']], 'objects': r['selected'], 'dest': r['dest']})
                self.counts['check'] += 1
                self.methods['check'][0] += int(ok)
                self.methods['check'][1] += 1
                self.log(event='ask_check', why='irreversible', unproven=unproven, ok=ok)
                if not ok:
                    old = key(r)
                    self._teach_from_demo(toks, command)
                    r = self.lex.interpret(toks, view, True)
                    if not self._complete(r) or key(r) == old:
                        return None                           # still the rejected reading: do not act
                    return self._result(r, view)
        return self._result(r, view)

    def _irreversible(self, pid):
        """From its own learned change: an object's content disappears and is not left anywhere else."""
        pat = self.patterns.get(pid, [])
        gone = any(it[0] == 'o' and it[1] == 'kind' and it[2] == 'absent' for it in pat)
        kept = any(it[1] == 'hash' and it[2] == '=o' and it[3:] != ['keep'] for it in pat)
        return gone and not kept

    def _complete(self, r):
        if r['pid'] is None or r['pid'] not in self.patterns or not r['selected'] or r['contradiction']:
            return False
        return bool(r['dest']) or not any(it[0] != 'o' for it in self.patterns[r['pid']])

    def _result(self, r, view):
        needs_dest = any(it[0] != 'o' for it in self.patterns[r['pid']])
        return {'pid': r['pid'], 'selected': r['selected'], 'dest': r['dest'] if needs_dest else None,
                'view_at_start': {o: ([repr(a) for a in at], v) for o, (at, v) in view.items()}}

    def _learn_explanation(self, word, answer, view):
        if answer == '':
            self.lex.learn_word(word, neutral=True)            # the person says the word carries nothing
            return True
        if not answer:
            return False
        ptoks = tokens(answer)
        r = self.lex.interpret(ptoks, view, True)
        pids = {next(iter(self.lex.pattern_of[t])) for t in ptoks if len(self.lex.pattern_of.get(t, {})) == 1 and t not in self.lex.neutral}
        known_pid = next(iter(pids)) if len(pids) == 1 and next(iter(pids)) in self.patterns else None
        cons = set()
        for t in ptoks:
            if t not in self.lex.neutral and self.lex.meaning.get(t):
                cons |= self.lex.meaning[t]
        if known_pid is None and not cons and not r['unknown']:
            self.lex.learn_word(word, neutral=True)            # explained, but carries no change and no objects
            return True
        if known_pid is None and not cons:
            return False
        self.lex.learn_word(word, pids=[known_pid] if known_pid else None, meaning=cons if cons else None)
        return True

    def _teach_from_demo(self, toks, command, interp_hint=None):
        """Ask the user to show the change once on one object, in the lab; ATANOR does the shown steps itself there."""
        if self.user is None:
            return False
        ans = self.user.point(command)
        self.counts['point'] += 1
        objs, dest = ans['objects'], ans['dest']
        if not objs:
            return False
        o = objs[0]
        seen = {p: 'file' for p in objs}
        lab = self._lab([o] + ([dest] if dest else []), dest, seen)
        before = lab.observe(self._paths(o, dest))
        steps = self.user.demonstrate(command, o, dest)
        self.counts['demonstrate'] += 1
        for tool, args in steps:
            self._try(lab, tool, tuple(args), 'demo')
        after = lab.observe(self._paths(o, dest))
        pattern = self._pattern(before, after, o, dest)
        if pattern is None:
            return False
        pattern = sorted(pattern)
        pid = hashlib.sha256(json.dumps(pattern).encode()).hexdigest()[:10]
        self.patterns[pid] = pattern
        rel = {o: 'o', dest: 'D', f'{dest}/{name_of(o)}': 'D/o'} if dest else {o: 'o'}
        if all(a in rel for _, args in steps for a in args):
            self.procedures[pid] = [[tool, [rel[a] for a in args]] for tool, args in steps]   # the shown steps, relationally
        self.lex.learn(toks, self.view(), pid, objs, dest)
        self.log(event='demonstration', pid=pid, pattern=pattern, steps=steps)
        self.save()
        return True

    def _paths(self, o, dest):
        return [o] + ([dest, f'{dest}/{name_of(o)}'] if dest else [])

    def _pattern(self, before, after, o, dest):
        rels = {o: 'o'}
        if dest:
            rels.update({dest: 'D', f'{dest}/{name_of(o)}': 'D/o'})
        pat = []
        for p in sorted(set(before) | set(after)):
            b, a = before.get(p, {}), after.get(p, {})
            for k in ('kind', 'hash'):
                if b.get(k) != a.get(k):
                    if k == 'hash' and a.get('kind') != 'file':
                        continue                               # provided: only files have content
                    if p not in rels:
                        return None
                    v = '=o' if k == 'hash' and a.get(k) == before[o].get('hash') and a.get(k) != '-' else a.get(k)
                    pat.append([rels[p], k, v])
        if pat and before.get(o, {}).get('kind') == after.get(o, {}).get('kind') == 'file':
            pat += [['o', 'kind', 'file', 'keep'], ['o', 'hash', '=o', 'keep']]     # what the shown change left as it was
        return pat or None

    def _goal(self, interp):
        pat = self.patterns.get(interp['pid'])
        if not pat:
            return None
        st = self.home.observe(interp['selected'])
        must, keep, universe = [], [], set()
        for o in interp['selected']:
            path = {'o': o, 'D': interp['dest'], 'D/o': f"{interp['dest']}/{name_of(o)}" if interp['dest'] else None}
            for item in pat:
                rel, k, v = item[:3]
                if path[rel] is None:
                    return None
                val = st[o]['hash'] if v == '=o' else v
                (keep if item[3:] == ['keep'] else must).append(Literal(k, (path[rel],), val))
                universe.add(path[rel])
        universe |= set(interp['selected'])
        g = Goal('life:' + interp['pid'], must, keep, {'destroy': True}, dict(BUDGET), sorted(universe))
        g.selected, g.dest = list(interp['selected']), interp['dest']
        return g

    # ---- acting: plan with the learned world model; a world gap goes to the lab
    def _focus(self, goal):
        """The objects a goal is about, with their ancestors: actions are considered over these only."""
        out = set()
        for p in goal.universe:
            parts = p.split('/')
            out |= {'/'.join(parts[:i]) for i in range(1, len(parts) + 1)}
        return sorted(out)

    def _plan(self, ws, goal, avoid=frozenset()):
        """Plan over the goal's own objects; if the search budget (not knowledge) stops it, plan for one object's part
        of the goal at a time (a sub-goal) and report it."""
        state = ws.observe(goal.universe)
        cap = getattr(ws, 'CAPABILITY', {})
        p, pst = plan(state, goal, self.model, ws.actions(self._focus(goal)), avoid, cap)
        if p or pst['stop'] == 'exhausted':
            return p, pst
        self.counts['subgoals'] += 1
        for l in goal.must:
            if not l.holds(state):
                group = [m for m in goal.must if set(m.args) & set(l.args) or m.args[0].rsplit('/', 1)[-1] == l.args[0].rsplit('/', 1)[-1]]
                sub = Goal(goal.id + '-sub', group, goal.keep, goal.capabilities, goal.budget, sorted({a for m in group for a in m.args}))
                return plan(state, sub, self.model, ws.actions(self._focus(sub)), avoid, cap)
        return p, pst

    def _achieve(self, goal, task_id):
        ws = self.home
        avoid = set()
        for step in range(BUDGET['actions']):
            state = ws.observe(goal.universe)
            if goal.satisfied(state):
                return True
            p, pst = self._plan(ws, goal, avoid)
            if not p and pst['stop'] != 'exhausted':
                self.counts['plan_budget_stops'] += 1
                self.log(event='plan_budget', task=task_id, stop=pst['stop'])
                return False
            if not p:
                self.counts['world_gaps'] += 1
                if not self._experiment(goal):
                    self.log(event='stuck', task=task_id)
                    return False
                avoid = set()
                continue
            if self._needs_rehearsal(p) and not self._rehearse(goal, p):
                avoid = set()
                continue                                         # the rehearsal taught something: plan again
            tool, args = p[0]
            predicted, status = self.model.predict(state, tool, args)
            ok, post = self._try(ws, tool, args, 'home', goal.capabilities)
            self.counts['home_actions'] += 1
            surprise = (predicted is None) == ok or (ok and any(predicted[a].get(k) not in ('unknown', post[a].get(k)) for a in args for k in ('kind', 'hash')))
            if surprise:
                self.counts['surprises'] += 1
                self.log(event='surprise', task=task_id, action=[tool, list(args)], predicted_ok=predicted is not None, ok=ok)
                if predicted is not None and not ok and self.notice_change:
                    self._reverify(tool)
            if not ok:
                avoid.add((tool, tuple(args)))
        return goal.satisfied(ws.observe(goal.universe))

    def _relevant_tools(self, goal):
        """Tools whose learned effects make the kind of change the goal asks for (in raw attributes)."""
        want = set()
        for l in goal.must:
            if l.pred == 'kind':
                want |= {('a0', 0)} if l.value == 'absent' else ({('a0', 1), ('a1', 1)} if l.value == 'dir' else {('a0', 1)})
            elif l.pred == 'hash':
                want.add(('a3', 'copy'))
        out = set()
        for tool, groups in self.model.rules.items():
            for g in groups:
                for i, k, spec in g['eff']:
                    if (k, spec[1] if spec[0] == 'const' else spec[0]) in want:
                        out.add(tool)
        return out

    def _needs_rehearsal(self, p):
        """A plan relying on a tool with little evidence (fewer than 3 successes since its last world change) is
        tried in the lab first."""
        succ = Counter(e.tool for e in self.model.eps if e.succeeded)
        return any(succ[t] < 3 for t, _ in p)

    def _rehearse(self, goal, p):
        objs = [q for q in goal.universe if self.home.kind(q) != 'absent']
        lab = self._lab(objs, None)
        for tool, args in p:
            ok, _ = self._try(lab, tool, tuple(args), 'rehearsal')
            self.counts['rehearsal_actions'] += 1
            if not ok:
                break
        done = goal.satisfied(lab.observe(goal.universe))
        self.counts['rehearsals'] += 1
        self.log(event='rehearsal', ok=done, steps=len(p))
        if not done:
            self.counts['rehearsals_failed'] += 1
        return done

    def _reverify(self, tool):
        """A confident prediction failed. Rebuild in the lab the most recent situation where this tool worked and
        try it again there: if it fails now, the world changed for this tool and its older experience is set aside."""
        past = [i for i, e in enumerate(self.episodes) if e.tool == tool and e.succeeded and not e.blocked]
        if not past:
            return
        e = self.episodes[past[-1]]
        if self.lab_root.exists():
            shutil.rmtree(self.lab_root)
        lab = type(self.home)(self.lab_root)
        lab.drift = getattr(self.home, 'drift', frozenset())
        for path in sorted(e.pre, key=lambda q: q.count('/')):
            k = e.pre[path].get('kind')
            target = lab.path(path)
            if k == 'dir':
                target.mkdir(parents=True, exist_ok=True)
            elif k == 'file':
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'placeholder' + bytes([10]))
        before = len(self.episodes)
        ok, _ = self._try(lab, tool, tuple(e.args), 'reverify')
        self.counts['reverifications'] += 1
        self.log(event='reverify', tool=tool, replayed=e.id, ok=ok)
        if not ok:
            self.world_changes.append({'tool': tool, 'before': before, 'evidence': e.id})
            self.counts['world_changes'] += 1
            self.log(event='world_change', tool=tool, set_aside_before=before)
            self._model = None
            self.save()

    def _try(self, ws, tool, args, source, caps=None):
        universe = ws.universe(list(args))
        pre = ws.observe(universe)
        res = ws.execute(tool, tuple(args), caps or {'destroy': True})
        post = ws.observe(universe)
        exp = Experience(f'{source}-{len(self.episodes)}', tool, tuple(args), pre, post, res['ok'], res['blocked'], res['ms'], False, source)
        self._store(exp)
        return res['ok'], post

    def _lab(self, objs, dest, seen=None):
        """A fresh lab mirroring the relevant objects of home (same relative paths, kinds and contents); an object no
        longer in home but seen earlier (seen: {path: kind}) is recreated with placeholder content."""
        if self.lab_root.exists():
            shutil.rmtree(self.lab_root)
        lab = type(self.home)(self.lab_root)
        lab.drift = getattr(self.home, 'drift', frozenset())     # the lab is a copy of the world as it is now
        for o in objs:
            if o is None:
                continue
            src = self.home.path(o)
            dst = lab.path(o)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file():
                shutil.copyfile(src, dst)
            elif src.is_dir():
                dst.mkdir(exist_ok=True)
            elif seen and seen.get(o) == 'file':
                dst.write_bytes(b'placeholder' + bytes([10]))
            elif seen and seen.get(o) == 'dir':
                dst.mkdir(exist_ok=True)
        return lab

    def _experiment(self, goal):
        """Experiments in a lab copy of the goal's objects until the real goal becomes plannable or the budget ends."""
        objs = [p for p in goal.universe if self.home.kind(p) != 'absent']
        lab = self._lab(objs, None)
        universe = sorted(set(goal.universe) | {'probe', 'probe/inner'})
        relevant = self._relevant_tools(goal)
        tried, resets = Counter(), 0
        proc = self.procedures.get(goal.id.split(':', 1)[-1])
        if proc and getattr(goal, 'selected', None):
            # analogy: replay the procedure that worked before, on one of the new objects, as an experiment
            o, d = goal.selected[0], goal.dest
            path = {'o': o, 'D': d, 'D/o': f'{d}/{name_of(o)}' if d else None}
            for tool, rels in proc:
                if any(path[r] is None for r in rels):
                    break
                self._try(lab, tool, tuple(path[r] for r in rels), 'lab')
                self.counts['lab_actions'] += 1
                self.counts['lab_analogy'] += 1
            p, _ = self._plan(self.home, goal)
            if p:
                self.log(event='experiment_resolved', how='analogy', lab_actions=len(proc))
                return True
            lab = self._lab(objs, None)
        for i in range(LAB_BUDGET):
            state = lab.observe(universe)
            # first choice: carry out the plan that would work if the unchecked generalisations held
            labgoal = Goal(goal.id, goal.must, goal.keep, goal.capabilities, goal.budget, goal.universe)
            op, _ = plan(lab.observe(goal.universe), labgoal, Optimistic(self.model), lab.actions(self._focus(goal)), set(), getattr(lab, 'CAPABILITY', {}))
            if op:
                tool, args = op[0]
                self._try(lab, tool, tuple(args), 'lab')
                self.counts['lab_actions'] += 1
                self.counts['lab_optimistic'] += 1
                p, _ = self._plan(self.home, goal)
                if p:
                    self.log(event='experiment_resolved', lab_actions=i + 1)
                    return True
                if labgoal.satisfied(lab.observe(goal.universe)):
                    lab = self._lab(objs, None)                # done in the lab but still not trusted: try again from the start
                continue
            cand = []
            for tool, args in lab.actions(sorted(state)):
                pred, status = self.model.predict(state, tool, args)
                if status != 'unknown':
                    continue
                sig = (tool, self.model.kinds(state, args), tuple(atoms('fs', state, args, FAMILIES_ALL)) if not self.generalize else None)
                cand.append((0 if tool in relevant else 1, tried[sig], self.rng.random(), tool, args, sig))
            if not cand:
                if resets >= 2:
                    break
                resets += 1
                lab = self._lab(objs, None)                    # nothing unknown left here: start from the original again
                continue
            _, _, _, tool, args, sig = min(cand)
            tried[sig] += 1
            self._try(lab, tool, args, 'lab')
            self.counts['lab_actions'] += 1
            p, _ = self._plan(self.home, goal)
            if p:
                self.log(event='experiment_resolved', lab_actions=i + 1)
                return True
        self.log(event='experiment_budget_spent')
        if self.user is None:
            return False
        steps = self.user.demonstrate_goal(goal)                  # last resort: be shown how, in the lab
        self.counts['demonstrate_how'] += 1
        lab = self._lab(objs, None)
        for tool, args in steps:
            self._try(lab, tool, tuple(args), 'demo')
        p, _ = self._plan(self.home, goal)
        return bool(p)


def view_from_json(d):
    import ast
    return {o: (frozenset(ast.literal_eval(a) for a in at), v) for o, (at, v) in d.items()}
