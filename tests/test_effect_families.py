from packages.action_core.world import Frame, Action
from packages.shared_world.contextual_rewrite import ContextualRewrite
from scripts.developmental_effect_families import EffectFamilies


def row(op, before, after):
    def frame(size): return Frame([1], [size], [[1]], [[0]], ('n0',)).to_dict()
    return dict(before=frame(before), after=frame(after), action=Action(op, ('n0',)).to_dict())


def test_structural_incremental_matches_every_batch_prefix():
    records = [row('a', 1., 0.), row('b', 1., 1.), row('a', 0., 1.)]
    learner = ContextualRewrite([])
    for i, record in enumerate(records):
        learner.learn([record])
        assert learner.rules == ContextualRewrite(records[:i+1]).rules


def test_disagreement_is_preserved_not_caller_selected():
    class Proposal:
        def __init__(self, value): self.value = value
        def predict(self, *args): return [('size', (0,), self.value)]
    learner = EffectFamilies([])
    learner.local, learner.structural = Proposal([0.]), Proposal([1.])
    assert learner.predict(None, None) == [('size', (0,), [0., 1.])]
    learner.local = Proposal([])
    assert learner.predict(None, None) == [('size', (0,), [1.])]
