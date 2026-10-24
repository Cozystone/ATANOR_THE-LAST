from packages.shared_world.conditional_tree_support import fit_tree


def test_two_separable_branches_survive_aliased_region():
    rows = [((0,0), {'a'}), ((0,0), {'b'}), ((1,0), {'a'}), ((0,1), {'b'})]
    model = fit_tree(rows)
    assert not model.query((0,0))
    assert model.query((1,0)) == {'a'}
    assert model.query((0,1)) == {'b'}
    assert model.query((1,1)) == {'a','b'}


def test_depth_bound_and_unanimous_leaf():
    assert not fit_tree([((0,), {'a'}), ((1,), {'b'})], depth=0).query((0,))
    assert fit_tree([((0,), {'a'}), ((1,), {'a'})]).query((2,)) == {'a'}
