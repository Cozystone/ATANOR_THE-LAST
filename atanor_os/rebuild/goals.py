"""REBUILD_PLAN.md C: whether a change is what the person meant, apart from what the action does.

The person's answers to "this one too?" (yes / not the one I meant / meant, but leave it) are cases of one action
(tool + constant arguments) under one selection concept, keyed by the object's own start observation. The same
explanation averaging as the effect model predicts an answer for a new start; it answers only above tau. An answer is
never widened to another action or another concept; within one, it reaches another start only when the evidence says
the deciding attributes are the same.
"""
from .effects import ActionModel, BayesAction, Case, flat, model_digest


class Goals:
    def __init__(self, tau=0.99):
        self.models, self.tau = {}, tau

    def add(self, tool, consts, concept, start, answer, t):
        key = (tool, tuple(consts), concept)
        m = self.models.setdefault(key, ActionModel(key))
        m.add(Case(flat([start]), {('goal',): answer}, t, 'person'))
        m._bayes = None

    def digest(self):
        return model_digest(self.models)

    def predict(self, tool, consts, concept, start):
        m = self.models.get((tool, tuple(consts), concept))
        if m is None or not m.cases:
            return None
        x = flat([start])
        same = [c for c in m.cases if c.x == x]
        if same:
            return same[-1].y[('goal',)]                   # this very start was answered: the latest answer
        if getattr(m, '_bayes', None) is None or m._bayes_n != len(m.cases):
            m._bayes, m._bayes_n = BayesAction(m, self.tau), len(m.cases)
        p = m._bayes.predict_out(('goal',), x)
        return p['value'] if p['known'] else None
