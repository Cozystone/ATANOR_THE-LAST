"""Condition models behind one interface: predict(state, tool, args) -> (post_state | None, status).

A docs only · B exact-signature retrieval · C induced rules (then B, then docs) · D council of three C's.
status ends with 'documented' when the prediction rests on documentation alone.
"""
from ..world.fs_world import TOOLS
from .bootstrap import DOCS
from .lift import apply_effects, lifted_effects, lifted_pre
from .rule_learner import learn_operator


class DocModel:
    """A: documented effects only; every syntactically valid action is assumed to succeed."""
    name = 'A'

    def __init__(self, experiences=()):
        pass

    def predict(self, state, tool, args, sig=None):
        return apply_effects(state, args, DOCS[tool]['effects']), 'documented'

    def update(self, exp):
        pass

    def describe(self):
        return {'condition': self.name}


class RetrievalModel(DocModel):
    """B: exact lifted-signature retrieval of past outcomes (majority); docs when nothing matches."""
    name = 'B'

    def __init__(self, experiences=()):
        self.index = {}
        for e in experiences:
            self._index(e)

    def _index(self, exp):
        if exp.blocked:
            return
        key = (exp.tool, lifted_pre(exp.pre, exp.args))
        eff = lifted_effects(exp.pre, exp.post, exp.args) if exp.succeeded else []
        self.index.setdefault(key, []).append((exp.succeeded, eff))

    def update(self, exp):
        self._index(exp)

    def retrieve(self, state, tool, args, sig=None):
        hits = self.index.get((tool, lifted_pre(state, args) if sig is None else sig))
        if not hits:
            return None
        ok = sum(h[0] for h in hits) * 2 > len(hits)
        return (True, next(h[1] for h in hits if h[0])) if ok else (False, [])

    def predict(self, state, tool, args, sig=None):
        hit = self.retrieve(state, tool, args, sig)
        if hit is None:
            return super().predict(state, tool, args, sig)
        ok, eff = hit
        return (apply_effects(state, args, eff), 'retrieved') if ok else (None, 'retrieved_fail')

    def describe(self):
        return {'condition': self.name, 'signatures': len(self.index)}


class RuleModel(RetrievalModel):
    """C: induced operator rules first, then B's retrieval, then docs."""
    name = 'C'

    def __init__(self, experiences=()):
        super().__init__(experiences)
        self.experiences = [e for e in experiences if not e.blocked]
        self.ops = {}
        self.relearn()

    def relearn(self, tools=None):
        for t in (tools or TOOLS):
            exps = [e for e in self.experiences if e.tool == t]
            self.ops[t] = learn_operator(t, TOOLS[t], exps) if exps else None

    def update(self, exp):
        super().update(exp)
        if not exp.blocked:
            self.experiences.append(exp)
            self.relearn([exp.tool])

    def predict(self, state, tool, args, sig=None):
        sig = lifted_pre(state, args) if sig is None else sig
        op = self.ops.get(tool)
        if op is not None and op.pre is not None:
            if op.pre <= sig:
                return apply_effects(state, args, op.effects), 'learned'
            return None, 'learned_fail'
        return super().predict(state, tool, args, sig)

    def describe(self):
        return {'condition': self.name, 'signatures': len(self.index),
                'operators': {t: (op.to_json() if op else None) for t, op in self.ops.items()}}


class CouncilModel(DocModel):
    """D (MAGI-style council): three RuleModels, each holding a disjoint third of the same experience log.

    v2 vote rule (after review): only members with evidence vote (a member whose answer rests on
    documentation alone abstains). Majority of the voters decides; a tie is a failure. When nobody
    has evidence, the council falls back to documentation like A. Effects come from the most
    informed agreeing voter (learned > retrieved). Same total experience as C; ~2-3x prediction cost.
    """
    name = 'D'
    RANK = {'learned': 0, 'retrieved': 1, 'documented': 2}

    def __init__(self, experiences=()):
        exps = [e for e in experiences if not e.blocked]
        self.members = [RuleModel(exps[i::3]) for i in range(3)]
        self.votes = self.disagreements = self.no_evidence = self.updates = 0

    def reset_stats(self):
        self.votes = self.disagreements = self.no_evidence = 0

    def stats(self):
        return {'votes': self.votes, 'disagreements': self.disagreements, 'no_evidence': self.no_evidence}

    def predict(self, state, tool, args, sig=None):
        sig = lifted_pre(state, args) if sig is None else sig        # computed once, shared by the members
        outs = [m.predict(state, tool, args, sig) for m in self.members]
        self.votes += 1
        voters = [o for o in outs if not o[1].endswith('documented')]
        if not voters:
            self.no_evidence += 1
            return outs[0][0], 'council_documented'
        oks = [o[0] is not None for o in voters]
        if any(oks) and not all(oks):
            self.disagreements += 1
        if sum(oks) * 2 <= len(oks):
            return None, 'council_fail'
        best = min((o for o in voters if o[0] is not None), key=lambda o: self.RANK[o[1]])
        return best[0], 'council_' + best[1]

    def update(self, exp):
        self.members[self.updates % 3].update(exp)     # keeps the members' experience disjoint
        self.updates += 1

    def describe(self):
        return {'condition': self.name, 'members': [m.describe() for m in self.members]}
