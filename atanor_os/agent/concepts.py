"""P8: concepts ATANOR forms from its own experience (no human concept names, no completed vocabulary).

Atoms over anonymous raw observations (world/raw_obs.py), for an action's argument roles i, j:
  ('U', i, k, v)  role i has a_k = v                         (unary)
  ('E', i, j, k)  role i and role j have equal a_k            (equality)
  ('S', i, k, v)  an object related to role i by r0 has a_k = v   (depth-1 structural composition)
  ('N', i)        no object related to role i is observed
  ('C', i, n)     role i satisfies invented concept c_n
The generators are provided; WHICH combinations become concepts is learned:
  1. per tool, contrast-based induction (as in rule_learner v4) -> per type group the most general
     conjunction of atoms consistent with every observed failure, and effects over raw attributes;
  2. the parts of those conjunctions that concern one role recur across groups and tools; recurring
     parts become numbered concepts c_n (names are numbers only) and rules are rewritten with them;
  3. the representation (dictionary + rules) is serialized and pruned to a byte budget B by
     explained-experiences-per-byte;
  4. revision: from a stored representation and NEW experience only, rules are re-induced with the
     existing concepts available as atoms; concepts with identical definitions merge, unsupported
     rules are dropped, and the dictionary changes are recorded.
"""
import json
import math
from collections import Counter, defaultdict

from ..world.raw_obs import IDENTITY, KIND_ATTRS, neighbours, raw_attrs, recompute_derived, to_human


def _kinds(body):
    """The raw attributes that make up an argument's kind, as the adapter declares them (provided)."""
    return KIND_ATTRS.get(body, ('a0',))

FAMILIES_ALL = ('U', 'E', 'S', 'N')
FAMILIES_FLAT = ('U', 'E')


def _hashable(v):
    return v if isinstance(v, (str, int, float, type(None))) else json.dumps(v, sort_keys=True)


def atoms(body, state, args, families=FAMILIES_ALL, concepts=None):
    out = set()
    raws = [raw_attrs(body, state[a]) if a in state else None for a in args]
    ident = IDENTITY[body]
    for i, r in enumerate(raws):
        if r is None:
            continue
        if 'U' in families:
            for k, v in r.items():
                if k not in ident:
                    out.add(('U', i, k, _hashable(v)))
        if 'S' in families or 'N' in families:
            nb = neighbours(body, state, args[i])
            if not nb and 'N' in families:
                out.add(('N', i))
            if 'S' in families:
                for o in nb:
                    for k, v in raw_attrs(body, state[o]).items():
                        if k not in ident:
                            out.add(('S', i, k, _hashable(v)))
    if 'E' in families:
        for i in range(len(raws)):
            for j in range(i + 1, len(raws)):
                if raws[i] is None or raws[j] is None:
                    continue
                for k in raws[i]:
                    vi, vj = raws[i][k], raws[j].get(k)
                    if k in ident and (vi in (None, '-') or vj in (None, '-')):
                        continue
                    out.add(('E', i, j, k, vi == vj))
    if concepts:
        for n, definition in concepts.items():
            for i in range(len(args)):
                if all(_inst(a, i) in out for a in definition):
                    out.add(('C', i, n))
    return frozenset(out)


def _inst(norm_atom, i):
    """Concept atoms are stored with the role written as 'x'; instantiate for role i."""
    return tuple(i if x == 'x' else x for x in norm_atom)


def _role_of(atom):
    return atom[1] if atom[0] in ('U', 'S', 'N', 'C') else None


def _norm(atom):
    return tuple('x' if (idx == 1) else x for idx, x in enumerate(atom))


def _type_key(body, state, args):
    key = []
    for a in args:
        if a not in state:
            key.append(None)
            continue
        r = raw_attrs(body, state[a])
        ks = _kinds(body)
        kind = _hashable(r[ks[0]]) if len(ks) == 1 else tuple(_hashable(r[k]) for k in ks)
        key.append((kind, bool(neighbours(body, state, a))))   # the declared kind attributes + related object present
    return tuple(key)


def _effects(body, exps):
    """Per (role, raw attr) the first candidate (const, or copy of another role's attr) that predicts every success."""
    changes = defaultdict(list)
    for e in exps:
        for i, a in enumerate(e.args):
            if a not in e.pre or a not in e.post:
                continue
            r0, r1 = raw_attrs(body, e.pre[a]), raw_attrs(body, e.post[a])
            for k in r0:
                if r0[k] == r1[k]:
                    continue
                cands = [('const', _hashable(r1[k]))] if k not in IDENTITY[body] else []
                for j, b in enumerate(e.args):
                    if j != i and b in e.pre:
                        rb = raw_attrs(body, e.pre[b])
                        cands += [('copy', j, kk) for kk in sorted(rb) if rb[kk] == r1[k] and r1[k] not in (None, '-')]
                if not cands:
                    cands = [('unknown',)]
                changes[(i, k)].extend(cands)
    out = []
    for (i, k), cands in sorted(changes.items()):
        chosen = ('unknown',)
        for c in dict.fromkeys(cands):
            if all(_pred_val(body, c, e, i, k) == raw_attrs(body, e.post[e.args[i]])[k] for e in exps
                   if e.args[i] in e.pre and e.args[i] in e.post):
                chosen = c
                break
        out.append([i, k, list(chosen)])
    return out


def _pred_val(body, spec, e, i, k):
    if spec[0] == 'const':
        return spec[1]
    if spec[0] == 'copy':
        src = e.pre.get(e.args[spec[1]])
        return None if src is None else raw_attrs(body, src).get(spec[2])
    return 'unknown'


def induce(body, exps, families=FAMILIES_ALL, concepts=None, extra_fails=None, atoms_of=None):
    """{tool: [group dicts]} by contrast-based induction over atoms (most general consistent conjunction per type group).
    extra_fails (P8b): {tool: [(atom set, weight)]} stored evidence re-entered as synthetic failures. Each kept atom gets
    an evidence count = weight of failures that only it excludes (group['ev'])."""
    extra_fails = extra_fails or {}
    by_tool = defaultdict(list)
    for e in exps:
        if not e.blocked:
            by_tool[e.tool].append(e)
    rules = {}
    for tool, es in sorted(by_tool.items()):
        succ = [e for e in es if e.succeeded]
        at = atoms_of or (lambda e: atoms(body, e.pre, e.args, families, concepts))
        fails = [(at(e), 1) for e in es if not e.succeeded] + list(extra_fails.get(tool, []))
        groups_raw = defaultdict(list)
        for e in succ:
            groups_raw[_type_key(body, e.pre, e.args)].append(e)
        groups = []
        for key in sorted(groups_raw, key=repr):
            g = groups_raw[key]
            pre = set(frozenset.intersection(*(at(e) for e in g)))
            unexplained = [s for s, w in fails if pre <= s]
            rest = [(s, w) for s, w in fails if not pre <= s]
            for a in sorted(pre, key=lambda a: (a[0] == 'U' and a[2] in _kinds(body), repr(a))):   # the kind atoms last
                if not any((pre - {a}) <= s for s, w in rest):
                    pre.discard(a)
            ev = {repr(a): sum(w for s, w in rest if (pre - {a}) <= s and a not in s) for a in pre}
            groups.append({'pre': sorted(pre, key=repr), 'eff': _effects(body, g), 'support': len(g), 'unexplained': len(unexplained), 'ev': ev})
        rules[tool] = groups
    return rules


def invent(rules, min_count=2, max_concepts=64):
    """Recurring one-role parts of rule conjunctions -> numbered concepts; rewrite rules with them."""
    parts = Counter()
    for tool, groups in rules.items():
        for g in groups:
            by_role = defaultdict(list)
            for a in g['pre']:
                a = tuple(a)
                if _role_of(a) is not None and a[0] != 'C':
                    by_role[a[1]].append(_norm(a))
            for role, ats in by_role.items():
                if len(ats) >= 2:
                    parts[frozenset(ats)] += 1
    common = [p for p, c in parts.most_common() if c >= min_count][:max_concepts]
    dictionary = {f'c{n}': sorted(p, key=repr) for n, p in enumerate(sorted(common, key=lambda p: (-parts[p], repr(sorted(p, key=repr)))))}
    return dictionary, rewrite(rules, dictionary)


def rewrite(rules, dictionary):
    out = {}
    defs = sorted(((n, frozenset(tuple(a) for a in d)) for n, d in dictionary.items()), key=lambda x: -len(x[1]))
    for tool, groups in rules.items():
        ng = []
        for g in groups:
            pre = [tuple(a) for a in g['pre']]
            roles = sorted({_role_of(a) for a in pre if _role_of(a) is not None})
            new = [a for a in pre if _role_of(a) is None or a[0] == 'C']
            for r in roles:
                mine = {_norm(a) for a in pre if _role_of(a) == r and a[0] != 'C'}
                for n, d in defs:
                    if d <= mine:
                        new.append(('C', r, n))
                        mine -= d
                new += [_inst(a, r) for a in sorted(mine, key=repr)]
            ev = dict(g.get('ev', {}))
            for a in new:
                if a[0] == 'C':
                    members = [_inst(tuple(x), a[1]) for x in dictionary[a[2]]]
                    ev[repr(a)] = max([ev.get(repr(m), 0) for m in members] + [0])
            ng.append({**g, 'pre': sorted(set(new), key=repr), 'ev': {repr(a): ev.get(repr(a), 0) for a in set(new)}})
        out[tool] = ng
    return out


def concept_use(rules):
    use = defaultdict(set)
    for tool, groups in rules.items():
        for g in groups:
            for a in g['pre']:
                if a[0] == 'C':
                    use[a[2]].add(tool)
    return {n: sorted(t) for n, t in use.items()}


class Representation:
    """What survives a restart: dictionary + rules (+ the body name). Serialized compactly."""

    def __init__(self, body, dictionary, rules, families=FAMILIES_ALL, history=None):
        self.body, self.dictionary, self.rules, self.families = body, dictionary, rules, families
        self.history = history or []

    def to_json(self):
        return {'body': self.body, 'families': list(self.families), 'concepts': self.dictionary,
                'rules': {t: [self._group_json(g) for g in gs] for t, gs in self.rules.items()},
                'history': self.history}

    @staticmethod
    def _group_json(g):
        d = {'p': g['pre'], 'e': g['eff'], 's': g['support']}
        if g.get('ev'):
            d['v'] = [g['ev'].get(repr(tuple(a)), 0) for a in g['pre']]
        if g.get('held'):
            d['h'] = g['held']
        return d

    def dumps(self):
        return json.dumps(self.to_json(), separators=(',', ':'), sort_keys=True)

    @staticmethod
    def loads(s):
        d = json.loads(s)
        def grp(g):
            out = {'pre': [tuple(a) for a in g['p']], 'eff': g['e'], 'support': g['s']}
            if 'v' in g:
                out['ev'] = {repr(tuple(a)): c for a, c in zip(g['p'], g['v'])}
            if 'h' in g:
                out['held'] = g['h']
            return out
        rules = {t: [grp(g) for g in gs] for t, gs in d['rules'].items()}
        return Representation(d['body'], {n: [tuple(a) for a in v] for n, v in d['concepts'].items()}, rules, tuple(d['families']), d.get('history'))

    def size(self):
        return len(self.dumps().encode('utf-8'))

    def prune(self, budget):
        """Drop the rule group with the fewest explained experiences per byte until the budget holds; then unused concepts."""
        dropped = 0
        while self.size() > budget:
            cands = [(g['support'] / max(1, len(json.dumps(g['pre']))), t, i) for t, gs in self.rules.items() for i, g in enumerate(gs)]
            if not cands:
                break
            _, t, i = min(cands)
            self.rules[t].pop(i)
            dropped += 1
            used = set(concept_use(self.rules))
            self.dictionary = {n: d for n, d in self.dictionary.items() if n in used}
            # history may grow; keep only the most recent entries if needed
            while self.size() > budget and len(self.history) > 1:
                self.history.pop(0)
        return dropped


def build(body, exps, budget=None, families=FAMILIES_ALL, invent_concepts=True):
    rules = induce(body, exps, families)
    dictionary = {}
    if invent_concepts:
        dictionary, rules = invent(rules)
    rep = Representation(body, dictionary, rules, families, history=[{'step': 'build', 'experiences': len(exps), 'concepts': len(dictionary)}])
    if budget:
        rep.history[-1]['pruned_groups'] = rep.prune(budget)
    return rep


def revise(rep, new_exps, budget=None):
    """From a stored representation and NEW experience only (the old log is not available)."""
    concepts = {n: d for n, d in rep.dictionary.items()}
    new_rules = induce(rep.body, new_exps, rep.families, concepts)
    merged = {}
    newset = defaultdict(list)
    for e in new_exps:
        if not e.blocked and not e.succeeded:
            newset[e.tool].append(atoms(rep.body, e.pre, e.args, rep.families, concepts))
    kept_old = dropped_old = 0
    for tool in sorted(set(rep.rules) | set(new_rules)):
        old = []
        for g in rep.rules.get(tool, []):
            pre = frozenset(tuple(a) for a in g['pre'])
            if any(pre <= s for s in newset.get(tool, [])):      # contradicted by a new failure
                dropped_old += 1
                continue
            old.append(g)
            kept_old += 1
        seen = {tuple(sorted(map(tuple, g['pre']))) for g in new_rules.get(tool, [])}
        merged[tool] = new_rules.get(tool, []) + [g for g in old if tuple(sorted(map(tuple, g['pre']))) not in seen]
    # expand concept atoms back to raw parts, re-invent over the union, record the dictionary change
    expanded = {t: [{**g, 'pre': _expand(g['pre'], concepts)} for g in gs] for t, gs in merged.items()}
    new_dict, new_rules2 = invent(expanded)
    old_defs = {frozenset(map(tuple, d)): n for n, d in rep.dictionary.items()}
    new_defs = {frozenset(map(tuple, d)): n for n, d in new_dict.items()}
    change = {'kept': sorted(old_defs[d] for d in old_defs if d in new_defs), 'removed': sorted(old_defs[d] for d in old_defs if d not in new_defs),
              'added': sorted(new_defs[d] for d in new_defs if d not in old_defs),
              'edited': sorted({old_defs[o] for o in old_defs for nd in new_defs if o not in new_defs and nd not in old_defs and (o & nd)}),
              'old_rules_kept': kept_old, 'old_rules_dropped': dropped_old}
    out = Representation(rep.body, new_dict, new_rules2, rep.families,
                         history=list(rep.history) + [{'step': 'revise', 'experiences': len(new_exps), 'concepts': len(new_dict), 'change': change}])
    if budget:
        out.history[-1]['pruned_groups'] = out.prune(budget)
    return out, change


def _expand(pre, concepts):
    out = []
    for a in pre:
        a = tuple(a)
        if a[0] == 'C' and a[2] in concepts:
            out += [_inst(tuple(x), a[1]) for x in concepts[a[2]]]
        else:
            out.append(a)
    return sorted(set(out), key=repr)


class ConceptModel:
    """predict(state, tool, args) from a Representation (the planner/judge interface)."""
    name = 'INTERNAL'

    def __init__(self, rep, name='INTERNAL'):
        self.rep, self.name = rep, name
        self.concepts = {n: [tuple(a) for a in d] for n, d in rep.dictionary.items()}
        self._cache = {}

    def predict(self, state, tool, args, sig=None):
        at = atoms(self.rep.body, state, args, self.rep.families, self.concepts)
        key = (tool, at)
        if key not in self._cache:                                   # the chosen rule depends only on the atoms
            self._cache[key] = next((g for g in sorted(self.rep.rules.get(tool, []), key=lambda g: -g['support'])
                                     if all(tuple(a) in at for a in g['pre'])), None)
        g = self._cache[key]
        if g is None:
            return None, 'learned_fail'
        return apply_raw(self.rep.body, state, args, g['eff']), 'learned'

    def update(self, exp):
        pass

    def describe(self):
        return {'condition': self.name, 'bytes': self.rep.size(), 'concepts': len(self.rep.dictionary)}


def apply_raw(body, state, args, effects):
    new = {p: dict(o) for p, o in state.items()}
    raws = {a: raw_attrs(body, state[a]) for a in args if a in state}
    for i, k, spec in effects:
        a = args[i]
        if a not in raws:
            continue
        if spec[0] == 'const':
            raws[a] = {**raws[a], k: spec[1]}
        elif spec[0] == 'copy':
            src = state.get(args[spec[1]])
            raws[a] = {**raws[a], k: raw_attrs(body, src).get(spec[2]) if src is not None else 'unknown'}
        else:
            raws[a] = {**raws[a], k: 'unknown'}
    for a, r in raws.items():
        new[a] = to_human(body, r, new[a])
    return recompute_derived(body, new)


class CaseModel:
    """Nearest-case retrieval over raw atom sets (Jaccard), majority outcome of the k nearest of the same tool."""
    name = 'CASE'

    def __init__(self, body, exps, k=5):
        self.body, self.k = body, k
        self._cache = {}
        self.cases = defaultdict(list)
        for e in exps:
            if not e.blocked:
                self.cases[e.tool].append((atoms(body, e.pre, e.args), e))

    def predict(self, state, tool, args, sig=None):
        at = atoms(self.body, state, args)
        key = (tool, at)
        if key not in self._cache:                                   # the retrieved neighbours depend only on the atoms
            cs = self.cases.get(tool, [])
            scored = sorted(cs, key=lambda c: -len(at & c[0]) / max(1, len(at | c[0])))[:self.k] if cs else []
            ok = bool(scored) and sum(c[1].succeeded for c in scored) * 2 > len(scored)
            self._cache[key] = _effects(self.body, [next(c[1] for c in scored if c[1].succeeded)]) if ok else None
        eff = self._cache[key]
        if eff is None:
            return None, 'retrieved_fail'
        return apply_raw(self.body, state, args, eff), 'retrieved'

    def update(self, exp):
        pass

    def describe(self):
        return {'condition': self.name, 'cases': sum(len(v) for v in self.cases.values())}


# ---------------- P8b: evidence-preserving revision ----------------
UNCERTAIN_BELOW = 2          # provided: a condition backed by fewer stored counter-examples is uncertain, not a fact


def uncertain_atoms(group):
    return sorted(a for a in map(tuple, group['pre']) if group.get('ev', {}).get(repr(a), 0) < UNCERTAIN_BELOW)


def _synthetic(rep):
    """Stored evidence -> synthetic failures: for condition a of a rule with conjunction P, a failure in which
    everything in P but a held (weight = its evidence count)."""
    out = defaultdict(list)
    for tool, groups in rep.rules.items():
        for gi, g in enumerate(groups):
            pre = set(map(tuple, g['pre']))
            for a in pre:
                w = g.get('ev', {}).get(repr(a), 0)
                if w > 0:
                    out[tool].append({'group': gi, 'atom': a, 'set': frozenset(pre - {a}), 'w': w})
    return out


def revise_b(rep, new_exps, budget=None, verifier=None):
    """P8b revision. Stored evidence enters as synthetic failures, so a condition is not dropped merely because
    the new experience did not test it. A new success that satisfies everything but a stored condition
    conflicts with that condition's evidence; ATANOR then re-verifies (a small experiment through `verifier`,
    in the current world), revises (retires the evidence), or holds (keeps it, marks the condition uncertain)."""
    concepts = {n: [tuple(a) for a in d] for n, d in rep.dictionary.items()}
    synth = _synthetic(rep)
    succ_atoms = defaultdict(list)
    for e in new_exps:
        if not e.blocked and e.succeeded:
            succ_atoms[e.tool].append(atoms(rep.body, e.pre, e.args, rep.families, concepts))
    decisions, retired, uncertain = [], set(), set()
    for tool, items in synth.items():
        others = [(gi, frozenset(map(tuple, g['pre']))) for gi, g in enumerate(rep.rules.get(tool, []))]
        for it in items:
            # a conflict = a new success that meets everything but this condition and that no other rule of the tool explains
            hits = [s for s in succ_atoms.get(tool, []) if it['set'] <= s and it['atom'] not in s
                    and not any(gi != it['group'] and pre <= s for gi, pre in others)]
            if not hits:
                continue                                     # no conflict: the stored evidence stands
            d = {'tool': tool, 'atom': list(it['atom']), 'evidence': it['w'], 'conflicting_successes': len(hits)}
            # re-verification re-creates the conflicting situation: the stored conjunction minus the condition,
            # with the argument kinds (the declared kind attributes) the new success had
            like = frozenset(a for a in hits[0] if a[0] == 'U' and a[2] in _kinds(rep.body))
            outcome = verifier(rep.body, tool, it['set'] | like, it['atom'], concepts) if verifier else None
            if outcome is True:
                d['decision'], d['why'] = 'revise', 're-verified: the action succeeds now without this condition'
                retired.add((tool, it['group'], it['atom']))
            elif outcome is False:
                d['decision'], d['why'] = 'keep', 're-verified: the action still fails without this condition'
            elif it['w'] < UNCERTAIN_BELOW:
                d['decision'], d['why'] = 'revise', 'stored evidence is weak and new evidence contradicts it'
                retired.add((tool, it['group'], it['atom']))
            else:
                d['decision'], d['why'] = 'hold', 'could not re-verify; keep the evidence, condition marked uncertain'
                uncertain.add((tool, it['atom']))
            d['verified'] = outcome
            decisions.append(d)
    extra = {t: [(it['set'], it['w']) for it in items if (t, it['group'], it['atom']) not in retired] for t, items in synth.items()}
    new_rules = induce(rep.body, new_exps, rep.families, concepts, extra)
    merged = {}
    new_fail_atoms = defaultdict(list)
    for e in new_exps:
        if not e.blocked and not e.succeeded:
            new_fail_atoms[e.tool].append(atoms(rep.body, e.pre, e.args, rep.families, concepts))
    kept_old = dropped_old = 0
    for tool in sorted(set(rep.rules) | set(new_rules)):
        new_g = new_rules.get(tool, [])
        new_keys = {_key_of(g, _kinds(rep.body)) for g in new_g}
        old = []
        for g in rep.rules.get(tool, []):
            pre = frozenset(map(tuple, g['pre']))
            if any(pre <= s for s in new_fail_atoms.get(tool, [])) or any((tool, gi, a) in retired for gi, gg in enumerate(rep.rules[tool]) if gg is g for a in pre):
                dropped_old += 1                             # contradicted by a new failure, or relies on retired evidence
                continue
            if _key_of(g, _kinds(rep.body)) in new_keys:
                continue
            old.append(g)
            kept_old += 1
        merged[tool] = new_g + old
    expanded = {t: [{**g, 'pre': _expand(g['pre'], concepts), 'ev': _expand_ev(g, concepts)} for g in gs] for t, gs in merged.items()}
    new_dict, new_rules2 = invent(expanded)
    for t, gs in new_rules2.items():                         # carry the hold decisions as uncertainty marks
        for g in gs:
            g['held'] = sorted(repr(a) for a in map(tuple, g['pre']) if (t, a) in uncertain)
    old_defs = {frozenset(map(tuple, d)): n for n, d in rep.dictionary.items()}
    new_defs = {frozenset(map(tuple, d)): n for n, d in new_dict.items()}
    change = {'kept': sorted(old_defs[d] for d in old_defs if d in new_defs), 'removed': sorted(old_defs[d] for d in old_defs if d not in new_defs),
              'added': sorted(new_defs[d] for d in new_defs if d not in old_defs), 'old_rules_kept': kept_old, 'old_rules_dropped': dropped_old,
              'decisions': decisions, 'counts': dict(Counter(d['decision'] for d in decisions)),
              'experiments': sum(1 for d in decisions if d['verified'] is not None)}
    out = Representation(rep.body, new_dict, new_rules2, rep.families,
                         history=list(rep.history) + [{'step': 'revise_b', 'experiences': len(new_exps), 'concepts': len(new_dict),
                                                       'counts': change['counts'], 'experiments': change['experiments']}])
    if budget:
        out.history[-1]['pruned'] = out.prune_b(budget)
    return out, change


def _key_of(g, kinds=('a0',)):
    return tuple(sorted(repr(tuple(a)) for a in g['pre'] if tuple(a)[0] == 'U' and tuple(a)[2] in kinds))


def _expand_ev(g, concepts):
    ev = {}
    for a in map(tuple, g['pre']):
        c = g.get('ev', {}).get(repr(a), 0)
        if a[0] == 'C' and a[2] in concepts:
            for x in concepts[a[2]]:
                m = _inst(tuple(x), a[1])
                ev[repr(m)] = max(ev.get(repr(m), 0), c)
        else:
            ev[repr(a)] = max(ev.get(repr(a), 0), c)
    return ev


def _prune_b(self, budget):
    """ATANOR chooses what to keep under the budget: first the least valuable evidence entries
    (count x rule support), then rule groups by explained experiences per byte, then unused concepts."""
    dropped = {'evidence': 0, 'groups': 0}
    while self.size() > budget:
        evs = [(g.get('ev', {}).get(k, 0) * g['support'], t, i, k) for t, gs in self.rules.items() for i, g in enumerate(gs)
               for k in g.get('ev', {}) if g['ev'][k] > 0]
        if evs:
            _, t, i, k = min(evs)
            self.rules[t][i]['ev'][k] = 0                    # the condition stays; its evidence is forgotten (now uncertain)
            dropped['evidence'] += 1
            continue
        dropped['groups'] += self.prune(budget)
        break
    return dropped


Representation.prune_b = _prune_b


class ConceptModelB(ConceptModel):
    """Same predictions; statuses tell whether the chosen rule leans on an uncertain or held condition."""

    def predict(self, state, tool, args, sig=None):
        post, st = super().predict(state, tool, args, sig)
        if st == 'learned':
            at = atoms(self.rep.body, state, args, self.rep.families, self.concepts)
            g = self._cache.get((tool, at))
            if g is not None and (uncertain_atoms(g) or g.get('held')):
                st = 'learned_uncertain'
        return post, st
