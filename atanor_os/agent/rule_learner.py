"""Relational precondition/effect induction from success/failure contrast (first hypothesis, charter §5).

Precondition = literals common to all successes, minus those whose removal admits no observed
failure (deterministic order, most general consistent conjunction). Failures the full
conjunction already admits are kept as counterexamples: the representation or perception cannot
separate them. Effects = per-role consensus across successes; disagreement → ('unknown',).
"""
from dataclasses import dataclass, field

from .lift import EFFECT_ATTRS, lifted_effects, lifted_pre


@dataclass
class OperatorModel:
    tool: str
    arity: int
    pre: object                 # frozenset of lifted literals; None when no success has been seen
    effects: list               # [(role, attr, spec)]
    support: int                # successes used
    failures: int
    counter: list               # ids of failures the precondition cannot exclude
    status: str                 # no_success | hypothesis | supported | unseparable
    dropped: list = field(default_factory=list)

    def to_json(self):
        lit = lambda l: [l[0], list(l[1]), l[2]]
        return {'tool': self.tool, 'pre': None if self.pre is None else sorted(map(lit, self.pre), key=repr),
                'effects': [[i, a, list(s)] for i, a, s in self.effects], 'support': self.support,
                'failures': self.failures, 'counter': self.counter, 'status': self.status,
                'dropped': sorted(map(lit, self.dropped), key=repr)}


def learn_operator(tool, arity, exps):
    succ = [e for e in exps if e.succeeded and not e.blocked]
    fail = [e for e in exps if not e.succeeded and not e.blocked]
    if not succ:
        return OperatorModel(tool, arity, None, [], 0, len(fail), [], 'no_success')
    sigs = [lifted_pre(e.pre, e.args) for e in succ]
    fsigs = [(e.id, lifted_pre(e.pre, e.args)) for e in fail]
    pre = set(frozenset.intersection(*sigs))
    unexplained = {i for i, s in fsigs if pre <= s}
    dropped = []
    for lit in sorted(pre, key=repr):
        trial = pre - {lit}
        if not any(trial <= s for i, s in fsigs if i not in unexplained):
            pre = trial
            dropped.append(lit)
    per = {}
    for e in succ:
        eff = {(i, attr): spec for i, attr, spec in lifted_effects(e.pre, e.post, e.args)}
        for i in range(arity):
            for attr in EFFECT_ATTRS:
                per.setdefault((i, attr), []).append(eff.get((i, attr)))
    effects = []
    for (i, attr), specs in sorted(per.items()):
        if all(s is None for s in specs):
            continue
        effects.append((i, attr, specs[0] if all(s == specs[0] for s in specs) else ('unknown',)))
    counter = sorted(unexplained)
    status = 'unseparable' if counter else ('supported' if len(succ) >= 2 else 'hypothesis')
    return OperatorModel(tool, arity, frozenset(pre), effects, len(succ), len(fail), counter, status, dropped)
