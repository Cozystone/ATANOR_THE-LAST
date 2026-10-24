"""One learner's competing effect languages; no task/operation-name router.

Both families see ALL the same observations. Empty support means a family cannot
propose, not a true prediction of no change. Keep the union of surviving proposals
so disagreement cannot manufacture a singleton. No calibrated confidence, new
language invention, authority, or automatic production registration is claimed.
"""
from scripts.developmental_conditional_eval import Model
from packages.shared_world.contextual_rewrite import ContextualRewrite


class EffectFamilies:
    def __init__(self, records):
        self.local = Model(records)
        self.structural = ContextualRewrite(records)

    def learn(self, records):
        records = list(records)
        self.local.learn(records)
        self.structural.learn(records)

    def predict(self, frame, action, conditional=True):
        cells = {}
        for family in (self.local, self.structural):
            for field, address, possible in family.predict(frame, action, conditional):
                cells.setdefault((field, tuple(address)), set()).update(possible)
        return [(field, address, sorted(values)) for (field, address), values in cells.items()]
