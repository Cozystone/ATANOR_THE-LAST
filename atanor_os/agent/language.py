"""P9: links English command words to ATANOR's own representation (frozen R1: raw atoms + concept atoms).

Word meanings are learned from feedback only: a word's meaning is the set of atoms every selected object had in
every training sentence containing it (minus atoms all candidates share). Tool identifiers are opaque: words are
never compared with tool names. Concepts are referred to by the sha256 of their definition, not by number.
Never imports teach/ or eval/.
"""
import hashlib
import json
import math
import re
from collections import Counter, defaultdict

from ..core.types import Goal, Literal
from .concepts import FAMILIES_ALL, apply_raw, atoms

MIN_WORD_COUNT = 2           # provided: a word seen once carries no meaning yet
VALUE_RULE_MIN = 0.8         # provided: reliability needed before an unseen token may name an attribute value
DEST_MIN = 0.5               # provided: a tool takes a destination if it had one in at least half of its sentences


def tokens(sentence):
    return re.findall(r'[a-z0-9]+', sentence.lower())


def concept_ids(rep):
    """number -> definition hash (12 hex)."""
    return {n: hashlib.sha256(json.dumps(sorted(map(list, d))).encode()).hexdigest()[:12] for n, d in rep.dictionary.items()}


def object_atoms(rep, state, obj, use_concepts=True):
    """Unary atoms of one object in ATANOR's representation; concept atoms renamed to their definition hash."""
    concepts = {n: [tuple(a) for a in d] for n, d in rep.dictionary.items()} if use_concepts else None
    ids = concept_ids(rep)
    out = set()
    for a in atoms(rep.body, state, (obj,), FAMILIES_ALL, concepts):
        if a[0] == 'E':
            continue
        out.add(('C', 0, ids[a[2]]) if a[0] == 'C' else a)
    return frozenset(out)


class Lexicon:
    def __init__(self):
        self.n = 0
        self.tool_n = Counter()
        self.word_tool = defaultdict(Counter)
        self.word_n = Counter()
        self.meaning = {}                    # word -> set of atoms (repr strings)
        self.marker = Counter()              # word right before the destination name
        self.prev_n = Counter()
        self.tool_dest = defaultdict(lambda: [0, 0])
        self.value_rule = [0, 0]             # [token named exactly the selected objects' value, opportunities]

    # ---------- learning from one teacher feedback ----------
    def update(self, toks, scene, tool, selected, dest):
        """scene: {obj: (atom frozenset, raw value of the first non-identity attribute that varies)}."""
        self.n += 1
        self.tool_n[tool] += 1
        d_idx = toks.index(dest) if dest in toks else None
        self.tool_dest[tool][0] += int(dest is not None)
        self.tool_dest[tool][1] += 1
        common = frozenset.intersection(*[a for a, _ in scene.values()]) if scene else frozenset()
        sel = [scene[o][0] for o in selected if o in scene]
        sel_inter = (frozenset.intersection(*sel) - common) if sel else frozenset()
        for i, w in enumerate(toks):
            if i == d_idx:
                continue
            if i + 1 < len(toks):
                self.prev_n[w] += 1
        if d_idx:
            self.marker[toks[d_idx - 1]] += 1
        for w in set(t for i, t in enumerate(toks) if i != d_idx):
            self.word_n[w] += 1
            self.word_tool[w][tool] += 1
            cur = {repr(a) for a in sel_inter}
            self.meaning[w] = cur if w not in self.meaning else (self.meaning[w] & cur)
        values = {v for _, v in scene.values()}
        for w in set(toks):
            if w in values:
                self.value_rule[1] += 1
                named = {o for o, (_, v) in scene.items() if v == w}
                self.value_rule[0] += int(named == set(selected))

    # ---------- interpretation ----------
    def interpret(self, toks, scene):
        tool = self._tool(toks)
        dest = self._dest(toks, scene) if tool and self._takes_dest(tool) else None
        cons = set()
        for i, w in enumerate(toks):
            if w == dest:
                continue
            if self.word_n[w] >= MIN_WORD_COUNT and self.meaning.get(w):
                cons |= self.meaning[w]
        hits, opp = self.value_rule
        if opp >= 5 and hits / opp >= VALUE_RULE_MIN:
            for w in toks:
                if w != dest and any(v == w for _, v in scene.values()):
                    cons |= {repr(a) for o, (at, v) in scene.items() if v == w for a in at if a[0] == 'U' and a[3] == w}
        selected = sorted(o for o, (at, _) in scene.items() if cons <= {repr(a) for a in at})
        return {'tool': tool, 'selected': selected, 'dest': dest, 'constraints': sorted(cons)}

    def _tool(self, toks):
        if not self.n:
            return None
        tools = sorted(self.tool_n)
        best, best_s = None, -math.inf
        for t in tools:
            s = math.log(self.tool_n[t] / self.n)
            for w in set(toks):
                if self.word_n[w]:
                    s += math.log((self.word_tool[w][t] + 0.5) / (self.word_n[w] + 0.5 * len(tools)))
            if s > best_s:
                best, best_s = t, s
        return best

    def _takes_dest(self, tool):
        w, n = self.tool_dest[tool]
        return n and w / n >= DEST_MIN

    def _dest(self, toks, scene):
        values = {v for _, v in scene.values()}
        best, best_s = None, 0.0
        for i, w in enumerate(toks):
            if i == 0 or w in values or (self.word_n[w] >= MIN_WORD_COUNT and self.meaning.get(w)):
                continue
            if self.word_n[w] >= MIN_WORD_COUNT:          # a known word without meaning (e.g. a function word)
                continue
            prev = toks[i - 1]
            s = self.marker[prev] / self.prev_n[prev] if self.prev_n[prev] else 0.0
            if s >= best_s and s > 0:
                best, best_s = w, s
        return best

    # ---------- persistence ----------
    def to_json(self):
        return {'n': self.n, 'tool_n': dict(self.tool_n), 'word_tool': {w: dict(c) for w, c in self.word_tool.items()},
                'word_n': dict(self.word_n), 'meaning': {w: sorted(m) for w, m in self.meaning.items()},
                'marker': dict(self.marker), 'prev_n': dict(self.prev_n), 'tool_dest': dict(self.tool_dest), 'value_rule': self.value_rule}

    @staticmethod
    def from_json(d):
        x = Lexicon()
        x.n, x.tool_n = d['n'], Counter(d['tool_n'])
        x.word_tool = defaultdict(Counter, {w: Counter(c) for w, c in d['word_tool'].items()})
        x.word_n, x.meaning = Counter(d['word_n']), {w: set(m) for w, m in d['meaning'].items()}
        x.marker, x.prev_n = Counter(d['marker']), Counter(d['prev_n'])
        x.tool_dest = defaultdict(lambda: [0, 0], {t: list(v) for t, v in d['tool_dest'].items()})
        x.value_rule = list(d['value_rule'])
        return x


def goal_from_interpretation(rep, state, interp, gid):
    """ATANOR's own goal: the effects of its top-support rule for the interpreted tool, applied to each selected
    object (and destination/name). No human tool -> goal mapping."""
    tool, dest = interp['tool'], interp['dest']
    rules = sorted(rep.rules.get(tool, []), key=lambda g: -g['support'])
    if not tool or not rules or not interp['selected']:
        return None
    eff = rules[0]['eff']
    arity = 1 + max([e[0] for e in eff] + [s[1] for _, _, s in eff if s[0] == 'copy'] + [0])
    if arity != (2 if dest else 1):
        return None                                  # the interpretation does not fit the tool's learned arity: no action
    # attribute values implied by the kind: constant across every currently observed object of that kind
    implied = {}
    for kind in {o.get('kind') for o in state.values()}:
        same = [o for o in state.values() if o.get('kind') == kind]
        if len(same) >= 2:
            implied[kind] = {k: same[0][k] for k in ('hash',) if all(o.get(k) == same[0].get(k) for o in same)}
    must, universe = [], set()
    for o in interp['selected']:
        args = (o, f"{dest}/{o.rsplit('/', 1)[-1]}") if dest else (o,)
        universe |= set(args)
        if any(a not in state for a in args):
            return None
        post = apply_raw(rep.body, state, args, eff)
        for a in args:
            for k in ('kind', 'hash'):
                v = post[a].get(k)
                if v not in (None, 'unknown') and v != state[a].get(k):
                    if k != 'kind' and implied.get(post[a].get('kind'), {}).get(k) == v:
                        continue                     # implied by the kind literal
                    must.append(Literal(k, (a,), v))
    if not must:
        return None
    return Goal(gid, must, [], {}, {'actions': 20, 'predictions': 400000, 'nodes': 600, 'depth': 12, 'seconds': 180.0},
                sorted(universe | ({dest} if dest else set())))
