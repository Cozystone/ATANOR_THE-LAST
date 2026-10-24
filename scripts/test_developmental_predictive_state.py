import copy
import json
import pytest
from scripts.developmental_predictive_state import PredictiveState, token


def corpus(model):
    for b, a, o in [('a', 'q', 'x'), ('a', 'q', 'x'), ('b', 'q', 'y'), ('b', 'q', 'y')]:
        model.learn(b, a, o, boundary=True)
    return model


def test_birth_requires_real_conflicting_futures_and_support():
    m = PredictiveState()
    m.learn('a', 'q', 'x', boundary=True)
    m.learn('b', 'q', 'y', boundary=True)
    assert not m.tests
    m.learn('a', 'q', 'x', boundary=True)
    m.learn('b', 'q', 'y', boundary=True)
    assert len(m.tests) == 1
    assert m.state('a') != m.state('b')
    assert m.predict('a', 'q') == 'x'
    assert m.predict('b', 'q') == 'y'
    assert m.predict('a', 'q', ablated=True) is None
    assert m.plan('a', ['q'], 'x')[0] == ['q']
    assert m.plan('a', ['q'], 'x', ablated=True)[0] is None


def test_same_anchor_mixed_outcomes_not_fake_hidden_state():
    m = PredictiveState()
    for result in ['x', 'y'] * 3:
        m.learn('a', 'q', result, boundary=True)
    assert not m.tests
    assert m.predict('a', 'q') is None


def test_unknown_not_zero_no_prediction_learning():
    m = corpus(PredictiveState())
    old = token(m.snapshot())
    assert m.predict('unseen', 'q') is None
    assert all(p is None for p in m.state('unseen'))
    m.plan('a', ['q'], 'x')
    assert old == token(m.snapshot())


def test_restart_and_forged_dimension_rejection():
    m = corpus(PredictiveState())
    restored = PredictiveState.restore(json.loads(token(m.snapshot())))
    assert restored.state('a') == m.state('a')
    assert restored.plan('a', ['q'], 'x') == m.plan('a', ['q'], 'x')
    bad = copy.deepcopy(m.snapshot())
    bad['tests'] = []
    with pytest.raises(ValueError):
        PredictiveState.restore(bad)


def test_no_future_window_across_reset_and_no_silent_forgetting():
    m = corpus(PredictiveState(max_records=4))
    assert all(len(actions) == 1 for _, actions in m.stats)
    with pytest.raises(RuntimeError):
        m.learn('a', 'q', 'x', boundary=True)
    n = PredictiveState()
    n.learn('a', 'q', 'x')
    with pytest.raises(ValueError):
        n.learn('b', 'q', 'y')


def test_noncontradictory_experience_does_not_grow_vocabulary():
    m = PredictiveState()
    for anchor in ['a', 'a', 'b', 'b', 'c', 'c']:
        m.learn(anchor, 'q', 'x', boundary=True)
    assert not m.tests
    assert m.predict('b', 'q') == 'x'
