import pytest
from packages.representation_r0.search import fit, majority


def experience():
    return [((10, 2), (10, 2)), ((11, 2), (12, 2)),
            ((13, 4), (13, 4)), ((15, 4), (14, 4))], [True, False, True, False]


def test_selects_relation_and_transfers_to_new_values():
    pairs, labels = experience()
    rule = fit(pairs, labels)
    assert rule.column == 0 and rule.operator == 'eq'
    assert rule.predict(((999, 3), (999, 3)))
    assert not rule.predict(((1000, 3), (999, 3)))


def test_channel_permutation_does_not_hardcode_identity_slot():
    pairs, labels = experience()
    pairs = [tuple(tuple(reversed(row)) for row in pair) for pair in pairs]
    rule = fit(pairs, labels)
    assert rule.column == 1
    assert rule.predict(((3, 999), (3, 999)))


def test_feature_removal_loses_discrimination():
    pairs, labels = experience()
    rule = fit(pairs, labels, excluded_columns=(0,))
    assert sum(rule.predict(x) == y for x, y in zip(pairs, labels)) == 2
    assert majority(labels) is False


@pytest.mark.parametrize('bad', [
    {'verified': True, 'same_object': True}, ((1, True), (2, 1)),
    ((1,), (2, 3)), ((1.0,), (2.0,)), ((1,),),
])
def test_caller_metadata_and_invalid_shapes_not_accepted(bad):
    pairs, labels = experience()
    with pytest.raises(ValueError):
        fit(pairs, labels).predict(bad)


def test_prediction_cannot_take_future_or_labels():
    pairs, labels = experience()
    with pytest.raises(TypeError):
        fit(pairs, labels).predict(pairs[0], label=True)


def test_width_mismatch_rejected():
    pairs, labels = experience()
    with pytest.raises(ValueError):
        fit(pairs, labels).predict(((1,), (1,)))
