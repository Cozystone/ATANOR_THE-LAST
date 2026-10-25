"""ATANOR living core: one persistent mind in one persistent workspace.

Loop for every command: interpret (from the learned lexicon) -> if the user's intent is unclear, ask the user
(explain a word / point at the objects / demonstrate once) -> turn the intended change into a goal -> plan with
the world model learned from stored episodes -> if no plan, the gap is about the world: experiment in a lab copy
(ask for a demonstration only when the experiment budget is spent) -> act in the real workspace, every outcome
checks a prediction and is stored -> ask for confirmation -> learn the words from the confirmed interpretation.

What is provided (not learned): the body's tool names and arity, the observation adapter and atom families, the
contrast-induction algorithm, the planner, the path relations a change can be expressed in (o, D, D/name(o)),
the question formats, the price of a question in lab actions, and one policy: intent gaps are asked (only the
person knows the intent), world gaps are experimented or asked by their recorded cost and success. What is learned: every tool's preconditions and effects (from episodes), which changes words
ask for, which objects words pick out, where the destination name stands, which words carry nothing.
Never imports teach/ or eval/.
"""
import hashlib
import json
import math
import random
import re
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path

from ..core.types import Experience, Goal, Literal
from ..world.raw_obs import KIND_ATTRS, names_of, raw_attrs
from .concepts import FAMILIES_ALL, apply_raw, atoms, induce
from .planner import plan

LAB_COST = 1 / 20          # provided preference: one question to the person costs as much as 20 lab actions
DECISIVE = 0.75            # provided: a unit is decisive about the change when it mostly goes with one change
HELP_COST = {'explain': 1, 'check': 1, 'point': 1, 'demonstrate': 2, 'demonstrate_goal': 3}
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

    def __init__(self, episodes, body='fs', generalize=True, notice_change=True, retired=None, cache=None):
        """cache (kept by the mind across rebuilds): atoms per episode id, and induced rules per tool keyed by the
        exact list of episodes they came from, so only a tool with new experience is re-induced."""
        self.body, self.generalize = body, generalize
        cache = cache if cache is not None else {'atoms': {}, 'rules': {}}
        A = cache['atoms']

        def at_of(e):
            if e.id not in A:
                A[e.id] = atoms(body, e.pre, e.args, FAMILIES_ALL)
            return A[e.id]
        self.at_of = at_of
        eps = [e for e in episodes if not e.blocked]
        retired = retired or {}                    # tool -> number of episodes before a re-verified world change
        eps = [e for i, e in enumerate(eps) if i >= retired.get(e.tool, -1)]
        self.changes = []
        if notice_change:
            # the same situation and action gave a different result than before: the world changed for that tool;
            # its older episodes are set aside (kept in memory, not used) and the tool is relearned from newer ones
            last, cut = {}, {}
            for i, e in enumerate(eps):
                k = (e.tool, at_of(e))
                if k in last and last[k][1] != e.succeeded:
                    cut[e.tool] = i
                    self.changes.append({'tool': e.tool, 'at_episode': e.id, 'was': last[k][1], 'now': e.succeeded})
                last[k] = (i, e.succeeded)
            eps = [e for i, e in enumerate(eps) if i >= cut.get(e.tool, -1)]
        self.eps = eps
        self.rules = {}
        by_tool = defaultdict(list)
        for e in self.eps:
            by_tool[e.tool].append(e)
        for tool, es in by_tool.items():
            key = (tool, len(es), es[0].id, es[-1].id)
            if key not in cache['rules']:
                cache['rules'][key] = induce(body, es, FAMILIES_ALL, atoms_of=at_of).get(tool, [])
            self.rules[tool] = cache['rules'][key]
        self.exact = defaultdict(dict)
        self.kinds_ok = defaultdict(set)
        self.kinds_seen = defaultdict(set)
        self.fail_kinds = Counter()
        for e in self.eps:
            at = at_of(e)
            self.exact[e.tool][at] = e
            k = self.kinds(e.pre, e.args)
            self.kinds_seen[e.tool].add(k)
            if not e.succeeded:
                self.fail_kinds[(e.tool, k)] += 1
            if e.succeeded:
                self.kinds_ok[e.tool].add(k)
        self._cache = {}
        self.unknown_asked = Counter()

    def kinds(self, state, args):
        ks = KIND_ATTRS[self.body]
        return tuple(tuple(raw_attrs(self.body, state[a])[k] for k in ks) if a in state else None for a in args)

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
            fails = self.fail_kinds[(tool, k)]
            return ('learned_fail', None) if k not in self.kinds_ok[tool] and fails >= 3 else ('unknown', None)
        backed = sum(g.get('ev', {}).values()) > 0 or (g.get('unexplained', 0) == 0 and g['support'] >= 3)
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
        self.kind_keys = set()                  # the body's kind attributes (given by the body, not learned)
        self.changed_keys = {}                  # change id -> attributes it rewrites on its object (from its pattern)
        self.word_n = Counter()
        self.pattern_of = defaultdict(Counter)  # word -> pid counts (from confirmed / demonstrated uses)
        self.meaning = {}                       # word -> set(repr(atom)) shared by most of its recent uses
        self.uses = {}                          # word -> list of per-use common-atom sets (repr strings), last 24
        self.disc_uses = {}                     # word -> per use, the value atoms that told the selected objects apart
        self.neutral = set()                    # words the user explained as carrying nothing
        self.marker = Counter()
        self.prev_n = Counter()
        self.value_rule = [0, 0]
        self.cases = {}                         # 'case' mode: sentence shape -> (pid, constraints)
        self.confirmed = Counter()              # word -> confirmed uses (the result was what the person wanted)
        self.pointed = Counter()                # word -> uses in which the person pointed at the objects
        self.dmeaning = {}                      # word -> atoms most second objects it was used with had in common
        self.duses = {}                         # word -> per-use atoms of the second object (last 24)
        self.d_n = Counter()                    # word -> confirmed uses with a second object
        self.d_disc = defaultdict(Counter)      # word -> atoms that told its second object apart, per use
        self.value_atoms = {}                   # value -> the atom (repr) that carried it, from every view seen
        self.defined = Counter()                # word -> explanations by the person
        self.join = Counter()                   # word -> confirmed uses where it stood between alternatives that were all selected
        self.join_n = Counter()                 # word -> confirmed uses where it stood between alternatives

    # -- learning from one confirmed or taught interpretation
    def note_values(self, view):
        for o, (at, vs) in view.items():
            for a in at:
                if a[0] == 'U' and a[3] in vs:
                    self.value_atoms[a[3]] = repr(a)

    def _derive(self, word):
        """The meaning is what at least three quarters of the word's remembered uses share."""
        us = self.uses.get(word, [])
        if not us:
            return
        need = max(1, -(-3 * len(us) // 4))
        counts = Counter(a for u in us for a in u)
        self.meaning[word] = {a for a, c in counts.items() if c >= need}

    def _add_use(self, word, atoms_repr, times=1, disc=None):
        us = self.uses.setdefault(word, [])
        ds = self.disc_uses.setdefault(word, [])
        for _ in range(times):
            us.append(set(atoms_repr))
            ds.append({a for a in atoms_repr if self.valued(a)} if disc is None else set(disc))
        del us[:-24]
        del ds[:-24]
        self._derive(word)

    def _discriminating(self, atoms_repr, objs, view, pid=None):
        """Of these atoms, the value atoms that some other object of the same kind lacked (they told objects apart),
        leaving out attributes the change itself rewrites on its object."""
        rewritten = self.changed_keys.get(pid, set())
        atoms_repr = {a for a in atoms_repr if not (a.startswith("('U'") and a.split(',')[2].strip(" '") in rewritten)}
        objs = [o for o in objs if o in view]
        if not objs:
            return set()
        kinds = {a for a in {repr(x) for x in view[objs[0]][0]} if a.startswith("('U'") and a.split(',')[2].strip(" '") in self.kind_keys}
        peers = [{repr(x) for x in at} for o, (at, _) in view.items() if o not in objs and kinds <= {repr(x) for x in at}]
        return {a for a in atoms_repr if self.valued(a) and any(a not in pa for pa in peers)}

    def _absent_like(self, atoms, objs, view):
        """No object like these (same kind, sharing what they all share outside these atoms' attributes) carries the atoms."""
        insel = [{repr(x) for x in view[o][0]} for o in objs if o in view]
        keys = {a.split(',')[2] for a in atoms}
        shared = {x for x in set.intersection(*insel) if x.split(',')[2:3] not in [[k] for k in keys]} if insel else set()
        return not any(shared <= {repr(x) for x in at} and atoms & {repr(x) for x in at} for at, _ in view.values())

    def naming_atoms(self, word):
        """Value atoms of the word's meaning that told its objects apart in at least half of its remembered uses."""
        m = self.meaning.get(word, ())
        ds = self.disc_uses.get(word)
        if not ds:
            return {a for a in m if self.valued(a)}
        c = Counter(a for d in ds for a in d)
        return {a for a in m if self.valued(a) and 2 * c[a] >= len(ds)}

    def _alternatives(self, toks, view, dest):
        """Value-naming atoms brought by the tokens, by attribute: {key: {atom: first token index}}, only for
        attributes with more than one alternative."""
        values = set().union(*[vs for _, vs in view.values()]) if view else set()
        by_key = defaultdict(dict)
        for i, t in enumerate(toks):
            if t == dest or t in view:
                continue
            if t in values:
                got = {repr(a) for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
            elif self.strong(t) and self.meaning.get(t):
                got = self.naming_atoms(t)
            else:
                continue
            for a in got:
                by_key[a.split(',')[2]].setdefault(a, i)
        return {k: v for k, v in by_key.items() if len(v) > 1}

    def value_history(self, word):
        """The value a word has kept naming: of its remembered uses that carried a value (at least 4), three quarters
        carried the same one, and that value was in at least half of all its uses (a function word co-occurs with
        whatever is selected, so its values spread)."""
        us = self.uses.get(word, [])
        vals = [set(d) for d in self.disc_uses.get(word, [])] or [{a for a in u if self.valued(a)} for u in us]
        valued = [v for v in vals if v]
        if len(valued) < 4:
            return set()
        c = Counter(a for v in valued for a in v)
        return {a for a, n in c.items() if 4 * n >= 3 * len(valued) and 2 * n >= len(us)}

    def joined(self, word):
        return self.join[word] >= 2 and self.join[word] / max(1, self.join_n[word]) >= 0.8

    def _between(self, toks, alts):
        idx = sorted(alts.values())
        bringers = set(idx)
        return {toks[i] for i in range(idx[0] + 1, idx[-1]) if i not in bringers}

    def learn(self, toks, view, pid, selected, dest):
        self.note_values(view)
        parts = {}                                          # alternative atom -> the selected objects carrying it
        alts = self._alternatives(toks, view, dest)
        insel0 = [{repr(x) for x in view[o][0]} for o in selected if o in view]
        def absent(key, a):                                 # nothing like the selected objects carries this alternative
            shared = {x for x in set.intersection(*insel0) if x.split(',')[2:3] != [key]} if insel0 else set()
            return not any(shared <= {repr(x) for x in at} and a in {repr(x) for x in at} for at, _ in view.values())
        bringers = {i for k, am in alts.items() for a, i in am.items() if absent(k, a)}
        alt_atoms = {a for am in alts.values() for a in am}
        insel = [{repr(x) for x in view[o][0]} for o in selected if o in view]
        akey = next(iter(alts)) if len(alts) == 1 else None
        shared = {a for a in set.intersection(*insel) if a.split(',')[2:3] != [akey]} if insel and akey else set()
        carried = lambda a: any(shared <= {repr(x) for x in at} and a in {repr(x) for x in at} for at, _ in view.values())
        if len(alts) == 1 and insel and all(carried(a) for a in alts[akey]):     # each alternative has objects like the selected ones
            (key, am), = alts.items()
            parts = {a: [o for o in selected if o in view and a in {repr(x) for x in view[o][0]}] for a in am}
            union = all(parts.values()) and set().union(*map(set, parts.values())) == {o for o in selected if o in view}
            for w in self._between(toks, am):
                self.join_n[w] += 1
                self.join[w] += int(union)
            if not union:
                parts = {}
            else:
                parts = {i: parts[a] for a, i in am.items()}     # token index -> its own objects
        d_idx = toks.index(dest) if dest in toks else None
        if d_idx:
            self.marker[toks[d_idx - 1]] += 1
        for i, w in enumerate(toks):
            if i != d_idx and i + 1 < len(toks):
                self.prev_n[w] += 1
        sel = [view[o][0] for o in selected if o in view]
        # what all selected objects had in common (atoms every object shares are kept: they may tell objects apart later)
        inter = frozenset.intersection(*sel) if sel else frozenset()
        cur = {repr(a) for a in inter}
        values = set().union(*[vs for _, vs in view.values()]) if view else set()
        for w in set(t for i, t in enumerate(toks) if i != d_idx):
            self.word_n[w] += 1
            if pid is not None:
                self.pattern_of[w][pid] += 1
            if w not in self.neutral:
                own = [parts[i] for i, t in enumerate(toks) if t == w and i in parts]
                if not own and any(t == w and i in bringers for i, t in enumerate(toks)):
                    continue                                # its own part of the selection cannot be told apart: no evidence
                va = self.naming_atoms(w) if w not in values and self.strong(w) else set()
                if not own and va and selected:
                    sel_in = [o for o in selected if o in view]
                    mine = [o for o in sel_in if va & {repr(a) for a in view[o][0]}]
                    if not mine:
                        if self._absent_like(va, sel_in, view):
                            continue                        # nothing it names is here today: this use says nothing about it
                    elif len(mine) < len(sel_in):
                        own = [mine]                        # a mixed selection: the word learns from the part it names
                if own:                                     # a value word in a union learns from its own part
                    sub = [view[o][0] for o in own[0] if o in view]
                    part = {repr(a) for a in frozenset.intersection(*sub)} if sub else cur
                    self._add_use(w, part, disc=self._discriminating(part, own[0], view, pid))
                else:
                    self._add_use(w, cur, disc=self._discriminating(cur, selected, view, pid))
        for pair in self.pairs(toks, dest, values):
            if pid is not None:
                self.pattern_of[pair][pid] += 1
        if dest in view:                                    # the second object exists: words may describe it
            dcur = {repr(a) for a in view[dest][0]}
            for w in set(toks):
                if w in self.neutral or w in view or w == dest:
                    continue
                for a in self._discriminating(dcur, [dest], view):
                    self.d_disc[w][a] += 1
                us = self.duses.setdefault(w, [])
                us.append(set(dcur))
                del us[:-24]
                self.d_n[w] += 1
                need = max(1, -(-3 * len(us) // 4))
                cnt = Counter(a for u in us for a in u)
                self.dmeaning[w] = {a for a, c in cnt.items() if c >= need}
        named_vals = {w for w in toks if w in values and w != dest}
        any_carrier = {o for o, (at, vs) in view.items() if vs & named_vals or alt_atoms & {repr(a) for a in at}}
        unread = any(t not in values and t != dest and t not in view and t not in self.neutral and not self.strong(t) for t in toks)
        for i, w in enumerate(toks):
            if w in values and w not in toks[:i]:
                carriers = {o for o, (_, vs) in view.items() if w in vs}
                own = parts.get(i)
                sel_in = {o for o in selected if o in view}
                hit = bool(sel_in) and (set(own) <= carriers if own else sel_in <= any_carrier and bool(sel_in & carriers))
                if not hit and (unread or not sel_in <= any_carrier):
                    continue                                # part of the selection is named by nothing read: no evidence either way
                self.value_rule[1] += 1
                self.value_rule[0] += int(hit)
        self.cases[self._shape(toks, view, dest)] = (pid, sorted(cur))

    @staticmethod
    def pairs(toks, dest=None, values=()):
        """Adjacent word pairs that name neither the destination nor an observed value."""
        return [f'{a} {b}' for a, b in zip(toks, toks[1:]) if dest not in (a, b) and a not in values and b not in values]

    def _share(self, unit, pids):
        pc = self.pattern_of.get(unit)
        if not pc:
            return None, 0.0
        n = sum(pc.values())
        top, c = pc.most_common(1)[0]
        if n < 3 or self.names_value(unit) or self.names_second(unit):
            return top, 0.0                                 # too little evidence, or an object word: not decisive
        return top, (c + 0.1) / (n + 0.1 * len(pids))

    def valued(self, a):
        """An atom that names a value: an attribute value that is neither a kind attribute of the body nor empty."""
        if not a.startswith("('U'"):
            return False
        parts = a.split(',')
        return parts[2].strip(" '") not in self.kind_keys and parts[3].strip(" )'") not in ('0', '1', '-')

    def names_second(self, word):
        """A strong word whose second-object meaning told that object apart from others of its kind in half its uses."""
        n = self.d_n[word]
        return self.strong(word) and n >= 3 and any(2 * self.d_disc[word][a] >= n for a in self.dmeaning.get(word, ()))

    def names_value(self, word):
        """A strong word whose meaning contains a value-bearing atom names objects, not a change."""
        return self.strong(word) and bool(self.naming_atoms(word))

    def strong(self, unit):
        return self.confirmed[unit] + self.pointed[unit] + 3 * self.defined[unit] >= 3

    def learn_word(self, word, pids=None, meaning=None, neutral=False):
        self.word_n[word] += 1
        self.defined[word] += 1
        if neutral:
            self.neutral.add(word)
            self.meaning.pop(word, None)
            self.uses.pop(word, None)
            self.disc_uses.pop(word, None)
            return
        for p in pids or []:
            self.pattern_of[word][p] += 5                    # the person defined it: strong evidence, not one co-occurrence
            self.confirmed[f'{word}|{p}'] += 1               # stated by the person counts like a confirmed use
        if meaning is not None:
            def specific(m):
                return any(self.valued(a) for a in m)
            old_m = self.meaning.get(word)
            if old_m is not None and specific(old_m) and not specific(meaning):
                pass                                         # the explanation names no value: keep the more specific meaning
            else:
                self.uses[word] = []                         # the person's definition supersedes what co-occurrence suggested
                self.disc_uses[word] = []
                self._add_use(word, set(meaning), times=3)   # and weighs three uses: later uses can still heal it

    def _shape(self, toks, view, dest):
        values = set().union(*[vs for _, vs in view.values()]) if view else set()
        return ' '.join('<D>' if t == dest else ('<V>' if t in values else t) for t in toks)

    # -- interpretation (with what is still unknown)
    def interpret(self, toks, view, takes_dest, join_unknown=False):
        values = set().union(*[vs for _, vs in view.values()]) if view else set()
        dest = self._dest(toks, values | set(view))
        unknown = [t for t in toks if self.word_n[t] == 0 and t != dest and t not in values and t not in view]
        if self.mode == 'case':
            c = self.cases.get(self._shape(toks, view, dest))
            if c is None:
                return {'pid': None, 'dest': dest, 'selected': [], 'unknown': unknown or ['<shape>'], 'contradiction': False}
            pid, cons = c[0], set(c[1])
            vals = [t for t in toks if t in values]
            named = {repr(a) for o, (at, vs) in view.items() if vs & set(vals) for a in at if a[0] == 'U' and a[3] in vals}
            keys = {a.split(',')[2] for a in named}
            cons = {a for a in cons if not (a.startswith("('U'") and a.split(',')[2] in keys)} | named
            sel = sorted(o for o, (at, _) in view.items() if cons <= {repr(a) for a in at})
            return {'pid': pid, 'dest': dest, 'selected': sel, 'unknown': [], 'contradiction': False}
        pids = sorted({q for c in self.pattern_of.values() for q in c})
        logp = {q: 0.0 for q in pids}
        informative, decisive = 0, 0.0
        units, i = [], 0
        while i < len(toks):
            pair = f'{toks[i]} {toks[i + 1]}' if i + 1 < len(toks) else None
            top, share = self._share(pair, pids) if pair else (None, 0.0)
            if pair and share >= DECISIVE and dest not in (toks[i], toks[i + 1]) and toks[i] not in values and toks[i + 1] not in values and toks[i] not in view and toks[i + 1] not in view                     and not self.names_value(toks[i]) and not self.names_value(toks[i + 1]):
                units.append(pair)                          # the pair speaks for both words
                i += 2
                continue
            units.append(toks[i])
            i += 1
        for t in units:
            pc = self.pattern_of.get(t)
            if t in values or t in view or t == dest or not pc or t in self.neutral:
                continue
            informative += 1
            n = sum(pc.values())
            probs = [(pc[q] + 0.1) / (n + 0.1 * len(pids)) for q in pids]
            ent = -sum(x * math.log(x) for x in probs) / math.log(len(pids)) if len(pids) > 1 else 0.0
            weight = 1.0 - ent                              # a word used with every change says little about which one
            decisive = max(decisive, weight)
            for q, x in zip(pids, probs):
                logp[q] += weight * math.log(x)
        pid, ambiguous = None, False
        if informative and pids:
            pid = max(logp, key=logp.get)
            tops = set()
            for t in units:
                if t in values or t in view or t == dest or t in self.neutral:
                    continue
                top, share = self._share(t, pids)
                if top is not None and share >= DECISIVE:   # a decisive unit: mostly used with one change
                    tops.add(top)
            ambiguous = len(tops) > 1 or (len(tops) == 1 and pid not in tops)   # decisive units disagree
            for t in units:                                 # a decisive unit confirmed only with another change: conflict
                pc = self.pattern_of.get(t)
                if t in values or t in view or t == dest or not pc or t in self.neutral:
                    continue
                top, n = pc.most_common(1)[0]
                if top != pid and n / sum(pc.values()) >= 0.9 and self.confirmed.get(f'{t}|{top}', 0) and not self.confirmed.get(f'{t}|{pid}', 0):
                    ambiguous = True
        def value_atoms_of(t):
            if t in values:
                return {repr(a) for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
            if self.names_value(t):
                return self.naming_atoms(t)
            return set()
        for t in set(toks):
            if t in values or t in view or t == dest or t in self.neutral or not self.names_value(t):
                continue
            pc = self.pattern_of.get(t)
            n = sum(pc.values()) if pc else 0
            if n < 3 or (pc.most_common(1)[0][1] + 0.1) / (n + 0.1 * len(pids)) < DECISIVE:
                continue
            others = set().union(*[value_atoms_of(u) for u in set(toks) if u != t and u != dest]) if len(toks) > 1 else set()
            if value_atoms_of(t) - others:
                ambiguous = True                            # change word or object word? the reading depends on it
        change_words = {w for u in units if self._share(u, pids)[1] >= DECISIVE and u not in values for w in u.split(' ')}
        weak_change = not any(self.strong(u) for u in units if self._share(u, pids)[1] >= DECISIVE and u not in values and u not in self.neutral)
        cons, weak_selection, support = set(), False, any(t in values and t != dest for t in toks)
        literal = support or any(t in view and t != dest for t in toks)
        for t in toks:
            if t == dest or t in values or t in view or t in self.neutral or t in change_words or self.word_n[t] == 0:
                continue
            if self.strong(t):
                if self.meaning.get(t):
                    cons |= self.meaning[t]
                    support = True
                    literal = literal or self.names_value(t)
            else:
                weak_selection = True                       # an object word with little evidence: ask or hold
        hits, opp = self.value_rule
        if opp >= 2 and hits / opp >= 0.8:
            named = {repr(a) for t in toks if t != dest and t in values
                     for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
            keys = {a.split(',')[2] for a in named}
            by_object_words = {a for t in toks if t != dest and t not in values and t not in self.neutral and self.names_value(t)
                               for a in self.naming_atoms(t)}
            cons = {a for a in cons if not (a.startswith("('U'") and a.split(',')[2] in keys) or a in by_object_words} | named
        by_key = defaultdict(set)
        for a in cons:
            if a.startswith("('U'"):
                by_key[a.split(',')[2]].add(a)
        contradiction = any(len(v) > 1 for v in by_key.values())
        union_sel = None
        if contradiction:
            alts = self._alternatives(toks, view, dest)
            between = self._between(toks, next(iter(alts.values()))) if len(alts) == 1 else set()
            by_analogy = join_unknown and any(self.joined(w) for w in self.join) and any(self.word_n[w] == 0 for w in between)
            if len(alts) == 1 and (any(self.joined(w) for w in between) or by_analogy):
                key = next(iter(alts))
                base = {a for a in cons if not (a.startswith("('U'") and a.split(',')[2] == key)}
                union_sel = sorted(o for o, (at, _) in view.items()
                                   if base <= {repr(a) for a in at} and any(x in {repr(a) for a in at} for x in alts[key]))
                contradiction = False                       # a learned joining word: the alternatives are all wanted
        value_named = any(self.valued(a) for a in cons)
        ignores_named = False
        if ids_named := [t for t in toks if t in view and t != dest]:
            pass                                                # objects named by their ids: nothing to drop
        else:
            used = set(cons) | ({x for am in self._alternatives(toks, view, dest).values() for x in am} if union_sel is not None else set())
            for t in set(toks):
                if t == dest or t in self.neutral:
                    continue
                if t in values:
                    va = {repr(a) for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
                else:
                    pc = self.pattern_of.get(t)
                    n = sum(pc.values()) if pc else 0
                    names_change = n >= 3 and (pc.most_common(1)[0][1] + 0.1) / (n + 0.1 * len(pids)) >= DECISIVE
                    va = self.value_history(t) if self.strong(t) and len(self.uses.get(t, [])) >= 3 and not names_change else set()
                if not va:
                    continue
                present = any(va & {repr(a) for a in at} for at, _ in view.values())
                if present and not va & used:
                    ignores_named = True                    # a word that names values restricts nothing in this reading
        if ignores_named:
            weak_selection = True                               # values were named but nothing in the reading uses them
        if not value_named and not literal:
            weak_selection = True                               # 'everything' with no value named: ask or hold
        ids = [t for t in toks if t in view and t != dest]
        if ids:
            sel, support = sorted(set(ids)), True                # tokens that are objects' own ids name them directly
        else:
            sel = [] if contradiction else union_sel if union_sel is not None else sorted(o for o, (at, _) in view.items() if cons <= {repr(a) for a in at})
        return {'pid': pid, 'dest': dest, 'selected': sel, 'unknown': unknown, 'contradiction': contradiction, 'ambiguous': ambiguous,
                'decisive': decisive, 'weak_change': weak_change, 'weak_selection': weak_selection, 'support': support and not ignores_named,
                'literal': literal}

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
                'uses': {w: [sorted(u) for u in us] for w, us in self.uses.items()},
                'disc_uses': {w: [sorted(u) for u in us] for w, us in self.disc_uses.items()},
                'marker': dict(self.marker), 'prev_n': dict(self.prev_n), 'value_rule': self.value_rule,
                'cases': {k: [v[0], v[1]] for k, v in self.cases.items()}, 'confirmed': dict(self.confirmed),
                'pointed': dict(self.pointed), 'defined': dict(self.defined), 'dmeaning': {w: sorted(m) for w, m in self.dmeaning.items()},
                'value_atoms': dict(self.value_atoms), 'join': dict(self.join), 'join_n': dict(self.join_n), 'duses': {w: [sorted(u) for u in us] for w, us in self.duses.items()},
                'd_n': dict(self.d_n), 'd_disc': {w: dict(c) for w, c in self.d_disc.items()}}

    @staticmethod
    def from_json(d):
        x = Lexicon(d.get('mode', 'general'))
        x.word_n = Counter(d['word_n'])
        x.pattern_of = defaultdict(Counter, {w: Counter(c) for w, c in d['pattern_of'].items()})
        x.meaning = {w: set(m) for w, m in d['meaning'].items()}
        x.uses = {w: [set(u) for u in us] for w, us in d.get('uses', {}).items()}
        x.disc_uses = {w: [set(u) for u in us] for w, us in d.get('disc_uses', {}).items()}
        x.neutral = set(d['neutral'])
        x.marker, x.prev_n, x.value_rule = Counter(d['marker']), Counter(d['prev_n']), list(d['value_rule'])
        x.cases = {k: (v[0], v[1]) for k, v in d['cases'].items()}
        x.confirmed = Counter(d.get('confirmed', {}))
        x.pointed, x.defined = Counter(d.get('pointed', {})), Counter(d.get('defined', {}))
        x.dmeaning = {w: set(m) for w, m in d.get('dmeaning', {}).items()}
        x.value_atoms = dict(d.get('value_atoms', {}))
        x.duses = {w: [set(u) for u in us] for w, us in d.get('duses', {}).items()}
        x.d_n = Counter(d.get('d_n', {}))
        x.d_disc = defaultdict(Counter, {w: Counter(c) for w, c in d.get('d_disc', {}).items()})
        x.join, x.join_n = Counter(d.get('join', {})), Counter(d.get('join_n', {}))
        return x


# ---------------------------------------------------------------- the mind
class Mind:
    def __init__(self, home, mind_dir, lab_root, user=None, generalize=True, lexicon_mode='general', seed=0, fixed=False, notice_change=True):
        """home: the body (a workspace); user: the channel to the person (ask_* / confirm), or None."""
        self.home, self.dir, self.lab_root, self.user = home, Path(mind_dir), Path(lab_root), user
        self.body = getattr(home, 'BODY', 'fs')
        self.caps = {c: True for c in set(getattr(home, 'CAPABILITY', {}).values())}   # the person's command grants the body's capabilities
        self.dir.mkdir(parents=True, exist_ok=True)
        self.generalize, self.fixed, self.notice_change = generalize, fixed, notice_change
        self.rng = random.Random(seed)
        self.episodes = self._load_episodes()
        lp = self.dir / 'lexicon.json'
        self.lex = Lexicon.from_json(json.loads(lp.read_text(encoding='utf-8'))) if lp.exists() else Lexicon(lexicon_mode)
        self.lex.kind_keys = set(KIND_ATTRS.get(self.body, ()))
        pp = self.dir / 'patterns.json'
        self.patterns = json.loads(pp.read_text(encoding='utf-8')) if pp.exists() else {}
        mp2 = self.dir / 'pattern_meta.json'
        self.pattern_meta = json.loads(mp2.read_text(encoding='utf-8')) if mp2.exists() else {}
        rp = self.dir / 'procedures.json'
        self.procedures = json.loads(rp.read_text(encoding='utf-8')) if rp.exists() else {}
        cp = self.dir / 'changes.json'
        self.world_changes = json.loads(cp.read_text(encoding='utf-8')) if cp.exists() else []
        mp = self.dir / 'methods.json'
        self.methods = json.loads(mp.read_text(encoding='utf-8')) if mp.exists() else {}
        self.methods.setdefault('explain', [0, 0])
        self.methods.setdefault('check', [0, 0])
        self.methods.setdefault('experiment', [0, 0, 0])      # resolved, attempts, lab actions spent when resolved
        self._model = None
        self._cache = {'atoms': {}, 'rules': {}}
        self._merge_patterns()
        self.lex.changed_keys = {pid: self._changed_keys(pid) for pid in self.patterns}
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
        (self.dir / 'pattern_meta.json').write_text(json.dumps(self.pattern_meta, indent=1), encoding='utf-8')

    def log(self, **kw):
        with open(self.dir / 'log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'t': round(time.time(), 3), 'task': getattr(self, 'task_id', None), **kw}, default=str) + '\n')

    @property
    def model(self):
        if self._model is None:
            retired = {c['tool']: c['before'] for c in self.world_changes} if self.notice_change else {}
            self._model = WorldModel(self.episodes, body=self.body, generalize=self.generalize, notice_change=self.notice_change,
                                     retired=retired, cache=self._cache)
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
        return {o: (frozenset(a for a in atoms(self.body, st, (o,), FAMILIES_ALL) if a[0] != 'E'), names_of(self.body, st[o])) for o in objs}

    # ---- unfinished goals (kept across restarts until a person has heard them)
    def pending_goals(self):
        p = self.dir / 'pending.json'
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else []

    def _set_pending(self, goals):
        (self.dir / 'pending.json').write_text(json.dumps(goals, indent=1), encoding='utf-8')

    def resume(self, goal):
        """With a person present: bring up one unfinished goal. Returns None if it is no longer wanted."""
        self._set_pending([g for g in self.pending_goals() if g['id'] != goal['id']])
        if self.user is None:
            raise ValueError('an unfinished goal is only resumed with the person')
        wanted = self.user.still_wanted(goal['command'])
        self.counts['recall'] += 1
        self.log(event='recall', goal=goal['id'], wanted=wanted)
        if not wanted:
            return None
        return self.do(goal['command'], goal['id'] + '/r')

    # ---- one command, start to finish (resumable)
    def do(self, command, task_id):
        r = self._do(command, task_id)
        why = r.get('reason') or ('not achieved' if r.get('achieved') is False else None)
        if why in ('not understood', 'no goal', 'not achieved') and self.user is None and not task_id.endswith('/r'):
            goals = [g for g in self.pending_goals() if g['id'] != task_id]
            self._set_pending(goals + [{'id': task_id, 'command': command, 'why': why}])
            self.log(event='unfinished', goal=task_id, why=why)
        return r

    def _do(self, command, task_id):
        self.task_id = task_id
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
        if confirmed:                                           # only a confirmed use teaches what the words mean
            self.lex.learn(toks, view_from_json(interp['view_at_start']), interp['pid'], interp['selected'], interp['dest'])
            self._note_d_naming(interp['pid'], toks, interp['dest'], view_from_json(interp['view_at_start']))
        if confirmed:
            for w in set(toks) | set(self.lex.pairs(toks, interp['dest'])):
                self.lex.confirmed[w] += 1
                self.lex.confirmed[f"{w}|{interp['pid']}"] += 1    # confirmed together with this change
        elif confirmed is False and self.user is not None:
            self.counts['corrections'] += 1
            self.log(event='wrong', task=task_id, interp={k: interp[k] for k in ('pid', 'selected', 'dest')})
            tt = self._taught = None
            if self._teach_from_demo(toks, command, interp_hint=interp):    # the counter-example corrects the words
                tt = self._taught if self._taught and self._taught['pid'] in self.patterns else None
            if tt is not None:
                again = {**interp, 'pid': tt['pid'], 'selected': tt['selected'], 'dest': tt['dest'], 'view_at_start': interp['view_at_start']}
                g2 = self._goal(again)
                if g2 is not None:                                   # try once more with what was just shown, and ask again
                    self.counts['retry_after_correction'] += 1
                    done = self._achieve(g2, task_id)
                    confirmed = self.user.confirm(command)
                    self.counts['confirm'] += 1
                    self.log(event='retry_after_correction', achieved=done, confirmed=confirmed)
                    if confirmed:
                        interp = again
                        self.lex.learn(toks, view_from_json(interp['view_at_start']), interp['pid'], interp['selected'], interp['dest'])
                        for w in set(toks) | set(self.lex.pairs(toks, interp['dest'])):
                            self.lex.confirmed[w] += 1
                            self.lex.confirmed[f"{w}|{interp['pid']}"] += 1
        self.save()
        t.update(status='done', ok=bool(confirmed if confirmed is not None else done))
        self._task(t)
        return {'ok': t['ok'], 'achieved': done, 'confirmed': confirmed}

    # ---- understanding the command (intent gaps are asked; nothing else knows the intent)
    def _understand(self, toks, command):
        view = self.view()
        asked_words, checked, rejected = set(), set(), set()
        pointed, accepted = None, None
        key = lambda r: (r['pid'], tuple(r['selected']), r['dest'])
        for _ in range(8):
            taught = self._from_taught(command, view)
            if taught is not None:
                return taught                                 # the person showed what this command means: do that
            if self.fixed:                                    # fixed human procedure: always ask to be shown
                self._teach_from_demo(toks, command)
                break
            r = self._resolve_dest(self.lex.interpret(toks, view, True), toks, view)
            if pointed is not None and r['pid'] in self.patterns:
                r = {**r, 'selected': [o for o in pointed['objects'] if o in view], 'dest': pointed['dest'] or r['dest'],
                     'contradiction': False, 'weak_selection': False, 'support': True}
            if r['unknown'] and self.user is not None:
                if not self.patterns or '<shape>' in r['unknown']:
                    self._teach_from_demo(toks, command)          # nothing known yet to explain it with: be shown
                    continue
                if r['contradiction'] and 'join_tried' not in checked:
                    checked.add('join_tried')                     # an unheard word where joining words stand: offer that reading
                    rj = self._resolve_dest(self.lex.interpret(toks, view, True, join_unknown=True), toks, view)
                    if not rj['contradiction'] and rj['selected'] and rj['pid'] in self.patterns:
                        ok = self.user.check(self._proposal(rj))
                        self.counts['check'] += 1
                        self.counts['join_by_analogy'] += 1
                        self.methods['check'][0] += int(ok)
                        self.methods['check'][1] += 1
                        self.log(event='ask_check', why='unheard word read as joining', unknown=r['unknown'], ok=ok)
                        if ok:
                            return self._result(rj, view)
                rate = lambda m: (self.methods[m][0] + 1) / (self.methods[m][1] + 2)
                word = next((w for w in r['unknown'] if w not in asked_words), None) if len(asked_words) < 2 else None
                can_check = self._complete(r) and key(r) not in checked
                if can_check and (word is None or rate('check') >= rate('explain')):
                    checked.add(key(r))
                    ok = self.user.check(self._proposal(r))
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
            if r['pid'] is None or r['pid'] not in self.patterns or (key(r) in rejected and self.user is not None):
                if self.user is None:
                    why = 'unknown' if r['unknown'] else 'no_change'
                    self.counts[f'refused_{why}'] += 1
                    self.log(event=f'refuse_{why}', words=r['unknown'])
                    return None
                if self._teach_from_demo(toks, command):          # nothing better than the rejected reading: be shown
                    break
                continue
            needs_dest = self._needs_dest(r['pid'])
            weak = r.get('weak_change') or r.get('weak_selection') or r.get('dest_by_meaning')
            if r['pid'] in self.patterns and self._irreversible(r['pid']) and not r.get('literal') and pointed is None:
                if self.user is None:
                    self.counts['refused_weak'] += 1
                    self.log(event='refuse_weak', why='irreversible without literal naming')
                    return None
                ans = self.user.point(command)
                self.counts['point'] += 1
                self.log(event='ask_point', why='irreversible without literal naming')
                self._learn_pointing(toks, view, ans)
                pointed = ans
                continue
            if self.user is None and ((weak and self._irreversible(r['pid'])) or not r.get('support')):
                self.counts['refused_weak'] += 1
                self.log(event='refuse_weak', why='irreversible' if r.get('support') else 'no selection support')
                return None
            if self.user is not None and (r.get('weak_selection') or not r.get('support') or r.get('dest_by_meaning')) and pointed is None:
                ans = self.user.point(command)
                self.counts['point'] += 1
                self.log(event='ask_point', why='weak selection')
                self._learn_pointing(toks, view, ans)
                pointed = ans
                continue
            if self.user is not None and r.get('weak_change') and key(r) not in checked and not r['unknown']:
                checked.add(key(r))
                rr = {**r, 'selected': [o for o in pointed['objects'] if o in view], 'dest': pointed['dest'] or r['dest']} if pointed else r
                ok = self.user.check(self._proposal(rr))
                self.counts['check'] += 1
                self.methods['check'][0] += int(ok)
                self.methods['check'][1] += 1
                self.log(event='ask_check', why='weak change', ok=ok)
                if not ok:
                    rejected.add(key(r))
                    self._teach_from_demo(toks, command)
                    return self._from_taught(command, view)
                accepted = r['pid']
            if r['contradiction'] or not r['selected'] or (needs_dest and not r['dest']):
                if self.user is None:
                    self.counts['refused_incomplete'] += 1
                    self.log(event='refuse_incomplete', why='contradiction' if r['contradiction'] else ('nothing selected' if not r['selected'] else 'no second object'))
                    return None
                ans = self.user.point(command)
                self.counts['point'] += 1
                self.log(event='ask_point', why='contradiction' if r['contradiction'] else ('nothing selected' if not r['selected'] else 'no destination'))
                if needs_dest and not ans['dest']:
                    self._teach_from_demo(toks, command)          # no destination meant: the change itself was misread
                    continue
                self._learn_pointing(toks, view, ans)
                pointed = ans
                continue
            break
        taught = self._from_taught(command, view)
        if taught is not None:
            return taught                                     # the person showed what this command means
        r = self._resolve_dest(self.lex.interpret(toks, view, True), toks, view)
        if pointed is not None and r['pid'] in self.patterns:
            r = {**r, 'selected': [o for o in pointed['objects'] if o in view], 'dest': pointed['dest'] or r['dest'],
                 'contradiction': False, 'weak_selection': False}
        if not self._complete(r) or key(r) in rejected:
            if self.user is None:
                self.counts['refused_incomplete'] += 1
                self.log(event='refuse_incomplete', why='rejected' if key(r) in rejected else 'weak or incomplete reading',
                         dest_by_meaning=bool(r.get('dest_by_meaning')))
            return None                                       # never act on an interpretation the person rejected
        if r['unknown'] and self.user is None:
            self.counts['refused_unknown'] += 1
            self.log(event='refuse_unknown', words=r['unknown'])
            return None                                       # a reading that leans on unknown words is a guess: hold
        if r.get('ambiguous') and key(r) not in checked:
            if self.user is None:
                self.counts['refused_ambiguous'] += 1
                self.log(event='refuse_ambiguous', command=command)
                return None
            ok = self.user.check(self._proposal(r))
            self.counts['check'] += 1
            self.methods['check'][0] += int(ok)
            self.methods['check'][1] += 1
            self.log(event='ask_check', why='ambiguous', ok=ok)
            checked.add(key(r))
            if not ok:
                self._teach_from_demo(toks, command)
                return self._from_taught(command, view)
        if self._irreversible(r['pid']) and key(r) not in checked:
            values = {v for _, v in view.values()}
            unproven = [t for t in toks if t != r['dest'] and t not in values and t not in self.lex.neutral
                        and not self.lex.confirmed[f"{t}|{r['pid']}"]]      # never confirmed with this irreversible change
            if unproven:
                if self.user is None:
                    self.counts['refused_irreversible'] += 1
                    self.log(event='refuse_irreversible', words=unproven)
                    return None
                ok = self.user.check(self._proposal(r))
                self.counts['check'] += 1
                self.methods['check'][0] += int(ok)
                self.methods['check'][1] += 1
                self.log(event='ask_check', why='irreversible', unproven=unproven, ok=ok)
                if not ok:
                    self._teach_from_demo(toks, command)
                    return self._from_taught(command, view)
        return self._result(r, view)

    def _irreversible(self, pid):
        """From its own learned change: an object's content disappears and is not left anywhere else."""
        pat = self.patterns.get(pid, [])
        gone = any(it[0] == 'o' and it[1] == 'kind' and it[2] == 'absent' for it in pat)
        kept = any(it[0] != 'o' and isinstance(it[2], str) and it[2].startswith('=o.') and it[1] != 'kind' and it[3:] != ['keep'] for it in pat)
        return gone and not kept

    def _from_taught(self, command, view):
        t = getattr(self, '_taught', None)
        if not t or t['command'] != command or t['pid'] not in self.patterns:
            return None
        sel = [o for o in t['selected'] if o in view]
        if not sel:
            return None
        return self._result({'pid': t['pid'], 'selected': sel, 'dest': t['dest']}, view)

    def _note_d_naming(self, pid, toks, dest, view):
        """Remember how this use named the change's second object: by its id, by a value it carries, or by meaning."""
        if not dest or pid not in self.patterns:
            return
        how = 'token' if dest in toks else ('value' if dest in view and set(view[dest][1]) & set(toks) else 'meaning')
        named = self.pattern_meta.setdefault(pid, {}).setdefault('D_named', {})
        named[how] = named.get(how, 0) + 1

    def _resolve_dest(self, r, toks, view):
        """A change whose second object has been named by a value it carries or by word meaning: find it among the
        unselected objects."""
        meta = self.pattern_meta.get(r['pid'] or '', {})
        named = dict(meta.get('D_named', {}))
        if meta.get('D_by'):
            named[meta['D_by']] = named.get(meta['D_by'], 0) + 1
        elif meta:
            named['meaning'] = named.get('meaning', 0) + 1           # the first demonstration named it neither way
        if r.get('dest') or not (named.get('value') or named.get('meaning')):
            return r
        kind_ok = lambda at: any(a[0] == 'U' and a[2] == 'a0' and a[3] == meta.get('D_kind') for a in at)
        cands = [o for o, (at, vs) in view.items() if o not in r['selected'] and vs & set(toks) and kind_ok(at)]
        if len(cands) == 1:
            return {**r, 'dest': cands[0]}
        pids = sorted({q for c in self.lex.pattern_of.values() for q in c})
        change_words = {w for t in toks for w in t.split(' ') if self.lex._share(t, pids)[1] >= DECISIVE}
        cons, by = set(), []
        for t in toks:
            if t not in view and t not in self.lex.neutral and t not in change_words and self.lex.strong(t) and self.lex.dmeaning.get(t):
                cons |= self.lex.dmeaning[t]
                by.append(t)
        if cons:
            cands = [o for o, (at, vs) in view.items() if o not in r['selected'] and kind_ok(at) and cons <= {repr(a) for a in at}]
            if len(cands) == 1:
                guess = any(self.lex.d_n[t] < 3 for t in by)       # too few uses naming a second object: a guess, ask or hold
                return {**r, 'dest': cands[0], 'dest_by_meaning': guess}
        return r

    def _needs_dest(self, pid):
        """A change needs a second object when an entry is about it or copies a value from it."""
        return any(it[0] != 'o' or (isinstance(it[2], str) and it[2].startswith('=D.')) for it in self.patterns.get(pid, []))

    def _remembered_kind(self, p):
        """The kind an object last had when it was present: in the home now, or in memory."""
        k = self.home.kind(p) if hasattr(self.home, 'kind') else None
        if k and k != 'absent':
            return k
        for e in reversed(self.episodes):
            for st in (e.post, e.pre):
                ob = st.get(p)
                if ob and ob.get('kind') not in (None, 'absent'):
                    return ob['kind']
        return None

    def _proposal(self, r):
        """What is shown to the person: the change, the objects, and the destination only if the change has one."""
        needs_dest = self._needs_dest(r['pid'])
        return {'change': self.patterns[r['pid']], 'objects': r['selected'], 'dest': r['dest'] if needs_dest else None}

    def _complete(self, r):
        if r['pid'] is None or r['pid'] not in self.patterns or not r['selected'] or r['contradiction']:
            return False
        if self.user is None:
            weak = r.get('weak_change') or r.get('weak_selection') or r.get('dest_by_meaning')
            if (weak and self._irreversible(r['pid'])) or not r.get('support', True) or r.get('dest_by_meaning'):
                return False                                  # nobody to ask: no irreversible, unsupported or meaning-guessed reading
            if self._irreversible(r['pid']) and not r.get('literal', True):
                return False
        return bool(r['dest']) or not self._needs_dest(r['pid'])

    def _result(self, r, view):
        needs_dest = self._needs_dest(r['pid'])
        return {'pid': r['pid'], 'selected': r['selected'], 'dest': r['dest'] if needs_dest else None,
                'view_at_start': {o: ([repr(a) for a in at], sorted(v)) for o, (at, v) in view.items()}}

    def _learn_pointing(self, toks, view, ans):
        """The person pointed at the objects: the words learn what those objects share; no change is attributed."""
        self.lex.learn(toks, view, None, ans['objects'], ans['dest'])
        values = {v for _, v in view.values()}
        for w in set(toks):
            if w != ans['dest'] and w not in values:
                self.lex.pointed[w] += 1

    def _learn_explanation(self, word, answer, view):
        if answer == '':
            self.lex.learn_word(word, neutral=True)            # the person says the word carries nothing
            return True
        if not answer:
            return False
        ptoks = tokens(answer)
        r = self.lex.interpret(ptoks, view, True)
        known_pid = r['pid'] if (r['pid'] in self.patterns and not r.get('ambiguous') and r.get('decisive', 0) >= 0.3) else None
        cons = set()
        values = {v for _, v in view.values()}
        for t in ptoks:
            if t not in self.lex.neutral and self.lex.meaning.get(t):
                cons |= self.lex.meaning[t]
        self.lex.note_values(view)
        for t in ptoks:                                       # a word of the explanation that names a value (seen now or before)
            atom = self.lex.value_atoms.get(t)
            if t in values:
                named = {repr(a) for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
            elif atom:
                named = {atom}
            else:
                continue
            keys = {a.split(',')[2] for a in named}
            cons = {a for a in cons if not (a.startswith("('U'") and a.split(',')[2] in keys)} | named
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
        seen = {p: k for p in objs for k in [self._remembered_kind(p)] if k}
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
        if dest:
            d_by = 'token' if dest in toks else ('value' if names_of(self.body, before.get(dest, {})) & set(toks) else None)
            self.pattern_meta[pid] = {'D_by': d_by, 'D_kind': before.get(dest, {}).get('kind')}
        self._taught = {'command': command, 'pid': pid, 'selected': sorted(objs), 'dest': dest}
        rel = {o: 'o', dest: 'D', f'{dest}/{name_of(o)}': 'D/o'} if dest else {o: 'o'}
        if all(a in rel for _, args in steps for a in args):
            self.procedures[pid] = [[tool, [rel[a] for a in args]] for tool, args in steps]   # the shown steps, relationally
        self.lex.learn(toks, self.view(), pid, objs, dest)
        self.log(event='demonstration', pid=pid, pattern=pattern, steps=steps)
        self.save()
        self._merge_patterns()
        self.lex.changed_keys = {q: self._changed_keys(q) for q in self.patterns}
        return True

    def _canonical(self, pattern):
        """A change without the entries that are now known to follow from the kind (learned implication)."""
        kind_of = {it[0]: it[2] for it in pattern if it[1] == 'kind'}
        return sorted(it for it in pattern if it[1] == 'kind' or not self._implied(kind_of.get(it[0]), it[1], it[2]))

    def _changed_keys(self, pid):
        """Raw attributes that this change rewrites on its object (read from its pattern through the body's mapping)."""
        preds = {it[1] for it in self.patterns.get(pid, []) if it[0] == 'o' and it[1] != 'kind' and not (len(it) > 3 and it[3] == 'keep')}
        keys = set()
        for pr in preds:
            base = {q: 'x0' for q in preds | {pr}}
            r0, r1 = raw_attrs(self.body, base), raw_attrs(self.body, {**base, pr: 'x1'})
            keys |= {k for k in r0 if r0[k] != r1[k]}
        return keys

    def _merge_patterns(self):
        """Changes that turn out to be the same once more is known get one identity; their word statistics and
        procedures are combined (so one intent is not split across ids learned at different times)."""
        if not self.patterns:
            return
        canon = {}
        for pid, pat in self.patterns.items():
            c = self._canonical(pat)
            canon.setdefault(json.dumps(c), []).append(pid)
        alias = {}
        for c, pids in canon.items():
            keep = sorted(pids)[0]
            self.patterns[keep] = json.loads(c)
            for q in pids:
                if q != keep:
                    alias[q] = keep
        if not alias:
            return
        for q, keep in alias.items():
            self.patterns.pop(q, None)
            if q in self.pattern_meta and keep not in self.pattern_meta:
                self.pattern_meta[keep] = self.pattern_meta[q]
            self.pattern_meta.pop(q, None)
            if q in self.procedures and keep not in self.procedures:
                self.procedures[keep] = self.procedures[q]
            self.procedures.pop(q, None)
        for w, c in self.lex.pattern_of.items():
            for q, keep in alias.items():
                if q in c:
                    c[keep] += c.pop(q)
        self.lex.cases = {k: (alias.get(v[0], v[0]), v[1]) for k, v in self.lex.cases.items()}
        for key in [k for k in self.lex.confirmed if '|' in k]:         # confirmations follow the merged identity
            w, q = key.split('|', 1)
            if q in alias:
                self.lex.confirmed[f'{w}|{alias[q]}'] += self.lex.confirmed.pop(key)
        self.log(event='merged_changes', alias=alias)
        self.save()

    def _implied(self, kind, attr, value):
        """From everything observed: objects of this kind always had this value of attr (>= 2 observations)."""
        seen = 0
        home = self.home.observe(self.home.existing())
        for e in [None] + self.episodes:
            for st in ((home,) if e is None else (e.pre, e.post)):
                for ob in st.values():
                    if ob.get('kind') == kind:
                        if ob.get(attr) != value:
                            return False
                        seen += 1
        return seen >= 2

    def _paths(self, o, dest):
        return [o] + ([dest, f'{dest}/{name_of(o)}'] if dest else [])

    def _pattern(self, before, after, o, dest):
        rels = {o: 'o'}
        if dest:
            rels.update({dest: 'D', f'{dest}/{name_of(o)}': 'D/o'})
        attrs = sorted({k for st in (before, after) for ob in st.values() for k in ob})
        changed = [p for p in sorted(set(before) | set(after)) if any(before.get(p, {}).get(k) != after.get(p, {}).get(k) for k in attrs)]
        if any(p not in rels for p in changed):
            return None
        needed = set(changed) | {q for q in rels if any(c.startswith(q + '/') for c in changed)}
        roles = [(rels[q], q) for q in rels if q in before]

        def encode(k, value):
            """A value that equals an attribute of a role before the change is a copy; the same attribute is preferred."""
            if value in ('-', None):
                return value
            for rel, q in roles:
                if before[q].get(k) == value:
                    return f'={rel}.{k}'
            for rel, q in sorted(roles, key=lambda x: (x[0] != 'D', x[0])):   # the pointed second object first
                for k2, v2 in before[q].items():
                    if v2 == value and k2 != 'kind':
                        return f'={rel}.{k2}'
            return value
        pat = []
        for p in sorted(needed):
            b, a = before.get(p, {}), after.get(p, {})
            for k in attrs:
                if k == 'kind' or b.get(k) != a.get(k):
                    if k != 'kind' and self._implied(a.get('kind'), k, a.get(k)):
                        continue                               # learned: every object of this kind seen so far had this value
                    pat.append([rels[p], k, a.get('kind') if k == 'kind' else encode(k, a.get(k))])
        if pat and o not in changed and before.get(o, {}).get('kind') not in ('absent', None):
            for k in attrs:                                    # what the shown change left as it was
                if k == 'kind' or not self._implied(before[o]['kind'], k, before[o].get(k)):
                    pat.append(['o', k, before[o]['kind'] if k == 'kind' else encode(k, before[o].get(k)), 'keep'])
        return pat or None

    def _goal(self, interp):
        pat = self.patterns.get(interp['pid'])
        if not pat:
            return None
        st = self.home.observe(list(interp['selected']) + ([interp['dest']] if interp['dest'] else []))
        must, keep, universe = [], [], set()
        for o in interp['selected']:
            path = {'o': o, 'D': interp['dest'], 'D/o': f"{interp['dest']}/{name_of(o)}" if interp['dest'] else None}
            for item in pat:
                rel, k, v = item[:3]
                if path[rel] is None:
                    return None
                if isinstance(v, str) and v.startswith('=') and '.' in v:
                    r2, k2 = v[1:].split('.', 1)
                    if path[r2] is None or path[r2] not in st:
                        return None
                    val = st[path[r2]].get(k2)
                else:
                    val = v
                (keep if item[3:] == ['keep'] else must).append(Literal(k, (path[rel],), val))
                universe.add(path[rel])
        universe |= set(interp['selected'])
        if interp['dest'] and self._needs_dest(interp['pid']):
            universe.add(interp['dest'])                      # the second object belongs to the goal even if only its value is copied
        g = Goal('life:' + interp['pid'], must, keep, dict(self.caps), dict(BUDGET), sorted(universe))
        g.selected, g.dest = list(interp['selected']), interp['dest']
        return g

    # ---- acting: plan with the learned world model; a world gap goes to the lab
    def _focus(self, goal):
        """The objects a goal is about, with their ancestors, and every object carrying a value the goal names."""
        out = set()
        for p in goal.universe:
            parts = p.split('/')
            out |= {'/'.join(parts[:i]) for i in range(1, len(parts) + 1)}
        wanted = {str(l.value) for l in goal.must}
        objs = self.home.existing()
        st = self.home.observe(objs)
        out |= {o for o in objs if names_of(self.body, st[o]) & wanted}
        return sorted(out)

    def _plannable(self, goal):
        """A cheap check used while experimenting: is there a plan within a small search budget?"""
        small = Goal(goal.id, goal.must, goal.keep, goal.capabilities, {**goal.budget, 'predictions': 20000, 'nodes': 120}, goal.universe)
        p, _ = self._plan(self.home, small)
        return bool(p)

    def _plan(self, ws, goal, avoid=frozenset()):
        """Plan over the goal's own objects; if the search budget (not knowledge) stops it, plan for one object's part
        of the goal at a time (a sub-goal) and report it."""
        state = ws.observe(goal.universe)
        cap = getattr(ws, 'CAPABILITY', {})
        if not getattr(self, '_subgoals_only', False):
            p, pst = plan(state, goal, self.model, ws.actions(self._focus(goal)), avoid, cap)
            if p or (pst['stop'] == 'exhausted' and not pst.get('depth_hits')):
                return p, pst                                # found, or truly no path with what is known
            self._subgoals_only = True                       # the whole goal is too long or wide to search: object by object from here
        self.counts['subgoals'] += 1
        for l in goal.must:
            if not l.holds(state):
                names = {a.rsplit('/', 1)[-1] for a in l.args}
                group = [m for m in goal.must if set(m.args) & set(l.args) or {a.rsplit('/', 1)[-1] for a in m.args} & names]
                paths = {a for m in group for a in m.args} | {q for q in goal.universe if q.rsplit('/', 1)[-1] in names}
                sub = Goal(goal.id + '-sub', group, goal.keep, goal.capabilities, goal.budget, sorted(paths))
                return plan(state, sub, self.model, ws.actions(self._focus(sub)), avoid, cap)
        return p, pst

    def _achieve(self, goal, task_id):
        ws = self.home
        avoid = set()
        self._subgoals_only = False
        limit = BUDGET['actions'] + 3 * len(getattr(goal, 'selected', []) or [])
        for step in range(limit):
            state = ws.observe(goal.universe)
            if goal.satisfied(state):
                return True
            p, pst = self._plan(ws, goal, avoid)
            if not p and (pst['stop'] != 'exhausted' or pst.get('depth_hits')) and not self._relevant_tools(goal):
                self.log(event='no_known_effect', task=task_id, stop=pst['stop'])
                pst = {**pst, 'stop': 'exhausted', 'depth_hits': 0}   # no known tool makes this change: a gap, not a budget stop
            if not p and (pst['stop'] != 'exhausted' or pst.get('depth_hits')):
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
            surprise = (predicted is None) == ok or (ok and any(predicted[a].get(k) not in ('unknown', post[a].get(k)) for a in args for k in predicted[a]))
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
        state = self.home.observe(goal.universe)
        for l in goal.must:
            cur = state.get(l.args[0], {})
            now, then = raw_attrs(self.body, cur), raw_attrs(self.body, {**cur, l.pred: l.value})
            for k in then:
                if then[k] != now.get(k):
                    want.add((k, then[k]))
                    want.add((k, 'copy'))
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
        lab = self.home.lab_from_state(self.lab_root, e.pre)
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
        res = ws.execute(tool, tuple(args), caps or self.caps)
        post = ws.observe(universe)
        exp = Experience(f'{source}-{len(self.episodes)}', tool, tuple(args), pre, post, res['ok'], res['blocked'], res['ms'], False, source)
        self._store(exp)
        return res['ok'], post

    def _lab(self, objs, dest, seen=None):
        """A fresh lab: the world's own copy of the relevant objects, as the world is now."""
        return self.home.lab_copy(self.lab_root, [o for o in objs if o is not None], seen)

    def _experiment(self, goal):
        """Experiments in a lab copy of the goal's objects until the real goal becomes plannable or the budget ends."""
        objs = [p for p in goal.universe if self.home.kind(p) != 'absent']
        lab = self._lab(objs, None)
        universe = sorted(set(goal.universe) | {'probe', 'probe/inner'})
        relevant = self._relevant_tools(goal)
        tried, resets = Counter(), 0
        ex = self.methods['experiment']
        p_ok = (ex[0] + 1) / (ex[1] + 2)
        avg = ex[2] / ex[0] if ex[0] else 10
        ask = HELP_COST['demonstrate_goal']
        expected = avg * LAB_COST / p_ok
        self.log(event='method_choice', experiment_cost=round(expected, 2), ask_cost=ask, user=self.user is not None)
        if self.user is not None and expected > 1.5 * ask:
            budget = 0                                         # experiments have been too costly here: ask to be shown
        else:
            budget = int(ask / LAB_COST) * (1 if self.user is not None else 3)
        ex[1] += 1
        spent0 = self.counts['lab_actions']
        proc = self.procedures.get(goal.id.split(':', 1)[-1])
        if proc and getattr(goal, 'selected', None):
            # analogy: replay the procedure that worked before, on one of the new objects, as an experiment
            o, d = goal.selected[0], goal.dest
            path = {'o': o, 'D': d, 'D/o': f'{d}/{name_of(o)}' if d else None}
            substituted, new_proc = False, []
            for tool, rels in proc:
                if any(path[r] is None for r in rels):
                    new_proc = None
                    break
                args = tuple(path[r] for r in rels)
                ok, _ = self._try(lab, tool, args, 'lab')
                self.counts['lab_actions'] += 1
                self.counts['lab_analogy'] += 1
                step = [tool, list(rels)]
                if not ok:                                     # the known step fails: a tool that never worked may do it now
                    worked = {e.tool for e in self.episodes if e.succeeded}
                    for alt in sorted(t for t, ar in lab.tools().items() if t not in worked and ar == len(args)):
                        for order in ([list(rels), list(rels)[::-1]] if len(args) > 1 else [list(rels)]):
                            ok, _ = self._try(lab, alt, tuple(path[r] for r in order), 'lab')
                            self.counts['lab_actions'] += 1
                            self.counts['lab_substitute'] += 1
                            if ok:
                                substituted, step = True, [alt, order]
                                break
                        if ok:
                            break
                new_proc.append(step)
            if substituted and new_proc:
                self.procedures[goal.id.split(':', 1)[-1]] = new_proc      # the procedure that works now
                self.save()
            if self._plannable(goal):
                self.log(event='experiment_resolved', how='substitute' if substituted else 'analogy', lab_actions=self.counts['lab_actions'] - spent0)
                ex[0] += 1
                ex[2] += self.counts['lab_actions'] - spent0
                return True
            lab = self._lab(objs, None)
        for i in range(budget):
            state = lab.observe(universe)
            # first choice: carry out the plan that would work if the unchecked generalisations held
            labgoal = Goal(goal.id, goal.must, goal.keep, goal.capabilities, {**goal.budget, 'predictions': 20000, 'nodes': 120}, goal.universe)
            op, _ = plan(lab.observe(goal.universe), labgoal, Optimistic(self.model), lab.actions(self._focus(goal)), set(), getattr(lab, 'CAPABILITY', {}))
            if op:
                tool, args = op[0]
                self._try(lab, tool, tuple(args), 'lab')
                self.counts['lab_actions'] += 1
                self.counts['lab_optimistic'] += 1
                if self._plannable(goal):
                    self.log(event='experiment_resolved', lab_actions=i + 1)
                    ex[0] += 1
                    ex[2] += self.counts['lab_actions'] - spent0
                    return True
                if labgoal.satisfied(lab.observe(goal.universe)):
                    lab = self._lab(objs, None)                # done in the lab but still not trusted: try again from the start
                continue
            cand = []
            for tool, args in lab.actions(sorted(state)):
                pred, status = self.model.predict(state, tool, args)
                if status != 'unknown':
                    continue
                sig = (tool, self.model.kinds(state, args), tuple(atoms(self.body, state, args, FAMILIES_ALL)) if not self.generalize else None)
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
            if self._plannable(goal):
                self.log(event='experiment_resolved', lab_actions=i + 1)
                ex[0] += 1
                ex[2] += self.counts['lab_actions'] - spent0
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
        if p:
            return True
        # what was shown worked, but a generalisation without counter-examples is not yet trusted: test it
        user, self.user = self.user, None
        try:
            ok = self._experiment(goal)
        finally:
            self.user = user
        self.log(event='after_demonstration_experiments', resolved=ok)
        return ok


def view_from_json(d):
    import ast
    return {o: (frozenset(ast.literal_eval(a) for a in at), frozenset(v) if isinstance(v, list) else v) for o, (at, v) in d.items()}
