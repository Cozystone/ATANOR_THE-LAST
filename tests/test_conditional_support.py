import pytest
from packages.shared_world.conditional_support import fit


def test_conflicting_effects_learn_conditions_without_supplied_threshold():
    examples = [((7.,), {'alpha'}), ((11.,), {'beta'})]
    model = fit(examples)
    assert model.query((7.,)) == {'alpha'}
    assert model.query((11.,)) == {'beta'}
    # Unseen region: competing consistent predicates must not be collapsed.
    assert model.query((9.,)) == {'alpha', 'beta'}
    assert examples == [((7.,), {'alpha'}), ((11.,), {'beta'})]


def test_unresolvable_same_context_stays_unknown():
    model = fit([((2.,), {'a'}), ((2.,), {'b'})])
    assert model.query((2.,)) == frozenset()


def test_training_order_invariance_and_retention():
    rows = [((7.,), {'a'}), ((11.,), {'b'}), ((13.,), {'b'})]
    forward, reverse = fit(rows), fit(list(reversed(rows)))
    assert forward == reverse
    for features, symbols in rows:
        assert forward.query(features) == symbols


def test_common_effect_does_not_invent_a_split():
    model = fit([((1.,), {'keep', 'x'}), ((3.,), {'keep', 'y'})])
    assert model.query((2.,)) == {'keep'}
    assert not model.alternatives


def test_invalid_features_rejected():
    with pytest.raises(ValueError):
        fit([((float('nan'),), {'a'})])
    with pytest.raises(ValueError):
        fit([((1.,), {'a'}), ((1., 2.), {'a'})])
