from packages.shared_world.conditional_support import fit
from packages.shared_world.partial_conditional_support import fit_partial


def test_conflict_is_unknown_but_explainable_branch_survives():
    rows = [((0,), {'a'}), ((0,), {'b'}), ((1,), {'c'})]
    assert not fit(rows).query((1,))
    model = fit_partial(rows)
    assert not model.query((0,))
    assert model.query((1,)) == {'c'}


def test_existing_complete_fit_unchanged():
    rows = [((0,), {'a'}), ((1,), {'b'})]
    assert fit_partial(rows) == fit(rows)


def test_conflict_without_separating_feature_cannot_be_resolved():
    assert not fit_partial([((0,), {'a'}), ((0,), {'b'})]).query((0,))
