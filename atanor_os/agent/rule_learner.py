"""Relational precondition/effect induction from success/failure contrast (first hypothesis, charter §5).

Successes are split into type groups by the (kind, value) of each argument (charter §5 ③: narrow or
split condition candidates). Each group gets the most general conjunction consistent with ALL
observed failures: literals common to the group's successes, minus those whose removal admits no
failure, tried in a fixed order with object-type ('kind') literals last. A prediction succeeds when
any group's conjunction is satisfied, so disjunctive preconditions (e.g. "panel or compare") are
representable. Failures a group's full conjunction already admits are kept as counterexamples: the
representation or perception cannot separate them.
Effects = for each changed attribute, the first candidate in `lift.effect_candidates` order (constants,
then copies of another role's attributes) that predicts the outcome of EVERY success of the tool,
including successes where the attribute did not change; only attributes no single candidate explains
across the groups are chosen per group (a relation is preferred exactly when the value varies between
groups, a constant when it never did).

Learner version 4 (2026-10-24). v1: repr order, strict spec agreement. v2: type-last order and
prediction-consistent effects. v3: per-type groups (disjunctions such as "panel or compare").
v4: effect language widened from copies of hash/value to copies of any attribute (the view body's
compare inherits filter/sort from its source panel). On the filesystem body v4 replays 294 of the 300
recorded C test episodes exactly (p1-test-02, p1-test-03-contrast, p1-test-03-scarce, 5 seeds each); the 6
others (scarce seed 1, convert) complete equally but with 16 more actions, because the literal-dropping
order decides between two equally consistent generalizations there (see DECISIONS.md).
"""
from dataclasses import dataclass, field

from .lift import effect_candidates, lifted_pre

LEARNER_VERSION = 4


@dataclass
class OperatorModel:
    tool: str
    arity: int
    pre: object                 # single-group conjunction, or literals common to all groups; None when no success
    effects: list               # effects of the first group (compatibility; prediction uses match())
    support: int                # successes used
    failures: int
    counter: list               # ids of failures some group's conjunction cannot exclude
    status: str                 # no_success | hypothesis | supported | unseparable
    dropped: list = field(default_factory=list)
    groups: list = field(default_factory=list)   # [{'kinds', 'pre', 'effects', 'support'}]

    def match(self, sig):
        """Effects of the first type group whose conjunction is satisfied by `sig`, else None."""
        for g in self.groups:
            if g['pre'] <= sig:
                return g['effects']
        return None

    def to_json(self):
        lit = lambda l: [l[0], list(l[1]), l[2]]
        return {'tool': self.tool, 'pre': None if self.pre is None else sorted(map(lit, self.pre), key=repr),
                'effects': [[i, a, list(s)] for i, a, s in self.effects], 'support': self.support,
                'failures': self.failures, 'counter': self.counter, 'status': self.status,
                'dropped': sorted(map(lit, self.dropped), key=repr),
                'groups': [{'kinds': [list(k) for k in g['kinds']], 'pre': sorted(map(lit, g['pre']), key=repr),
                            'effects': [[i, a, list(s)] for i, a, s in g['effects']], 'support': g['support']}
                           for g in self.groups]}


def _order(lit):
    return (lit[0] == 'kind', repr(lit))


def _predicted(spec, e, i, attr):
    if spec[0] == 'const':
        return spec[1]
    if spec[0] == 'copy':
        src = e.pre.get(e.args[spec[1]])
        sa = spec[2] if len(spec) > 2 else attr
        return None if src is None else src.get(sa)
    return None


def _effects(succ):
    cands = {}
    for e in succ:
        for key, specs in effect_candidates(e.pre, e.post, e.args).items():
            cands.setdefault(key, []).extend(specs)
    tier = lambda s: 0 if s[0] == 'const' else (1 if len(s) == 2 else 2)
    effects = []
    for (i, attr), specs in sorted(cands.items()):
        chosen = ('unknown',)
        for cand in sorted(dict.fromkeys(specs), key=tier):          # stable: appearance order within a tier
            if all(e.pre.get(e.args[i]) is None or e.post.get(e.args[i]) is None
                   or _predicted(cand, e, i, attr) == e.post[e.args[i]].get(attr) for e in succ):
                chosen = cand
                break
        effects.append((i, attr, chosen))
    return effects


def _type_key(e, type_attrs):
    out = []
    for a in e.args:
        o = e.pre.get(a)
        out.append(tuple(None for _ in type_attrs) if o is None else tuple(o.get(t) for t in type_attrs))
    return tuple(out)


def learn_operator(tool, arity, exps, type_attrs=('kind',)):
    """type_attrs: the attributes that name an object's type, declared by the body spec (filesystem: kind;
    view: kind and the value object's name) — provided knowledge, listed in BOOTSTRAP_MANIFEST."""
    succ = [e for e in exps if e.succeeded and not e.blocked]
    fail = [e for e in exps if not e.succeeded and not e.blocked]
    if not succ:
        return OperatorModel(tool, arity, None, [], 0, len(fail), [], 'no_success')
    fsigs = [(e.id, lifted_pre(e.pre, e.args)) for e in fail]
    by_type = {}
    for e in succ:
        by_type.setdefault(_type_key(e, type_attrs), []).append(e)
    shared = {(i, a): spec for i, a, spec in _effects(succ) if spec != ('unknown',)}
    groups, dropped, counter = [], [], set()
    for key in sorted(by_type, key=repr):
        es = by_type[key]
        pre = set(frozenset.intersection(*(lifted_pre(e.pre, e.args) for e in es)))
        unexplained = {i for i, s in fsigs if pre <= s}
        for lit in sorted(pre, key=_order):
            trial = pre - {lit}
            if not any(trial <= s for i, s in fsigs if i not in unexplained):
                pre = trial
                dropped.append(lit)
        counter |= unexplained
        own = {(i, a): spec for i, a, spec in _effects(es)}
        effects = [(i, a, shared.get((i, a)) or own[(i, a)]) for i, a in sorted(set(own) | set(shared))]
        groups.append({'kinds': key, 'pre': frozenset(pre), 'effects': effects, 'support': len(es)})
    # identical conjunctions from different value groups collapse into one
    merged = []
    for g in groups:
        same = next((m for m in merged if m['pre'] == g['pre'] and m['effects'] == g['effects']), None)
        if same:
            same['support'] += g['support']
            same['kinds'] = same['kinds'] if same['kinds'] == g['kinds'] else tuple(
                tuple(x if x == y else '*' for x, y in zip(k1, k2)) for k1, k2 in zip(same['kinds'], g['kinds']))
        else:
            merged.append(dict(g))
    pre_common = merged[0]['pre'] if len(merged) == 1 else frozenset.intersection(*(g['pre'] for g in merged))
    status = 'unseparable' if counter else ('supported' if len(succ) >= 2 else 'hypothesis')
    return OperatorModel(tool, arity, pre_common, merged[0]['effects'], len(succ), len(fail), sorted(counter),
                         status, dropped, merged)
