import itertools
from packages.action_core.world import Frame, Action
from scripts.developmental_rooted_probe import rooted, value


def test_rooted_is_permutation_invariant():
    frame = Frame([1, 0, 1], [.2, 0., .7],
                  [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                  [[0, 1, 0], [0, 0, 0], [0, 1, 0]], ('n0', 'n1', 'n2'))
    action = Action('opaque', ('n2', 'n0'))
    address = (1, 2)
    key, nodes = rooted(frame, action, 'equal', address)
    for order in itertools.permutations(range(3)):
        inverse = {old: new for new, old in enumerate(order)}
        perm = Frame([frame.kinds[i] for i in order], [frame.sizes[i] for i in order],
                     [[frame.equal[i][j] for j in order] for i in order],
                     [[frame.parent[i][j] for j in order] for i in order], frame.handles)
        act = Action('opaque', tuple(f'n{inverse[i]}' for i in (2, 0)))
        addr = tuple(inverse[i] for i in address)
        new_key, new_nodes = rooted(perm, act, 'equal', addr)
        assert new_key == key
        for expr in [('keep',), ('constant', 1), ('copy', 0, 1)]:
            assert value(expr, frame, 'equal', address, nodes) == value(expr, perm, 'equal', addr, new_nodes)


def test_rooted_separates_argument_target_incidence():
    frame = Frame([1, 1], [.2, .2], [[1, 1], [1, 1]], [[0, 0], [0, 0]], ('n0', 'n1'))
    action = Action('opaque', ('n0',))
    assert rooted(frame, action, 'size', (0,))[0] != rooted(frame, action, 'size', (1,))[0]
