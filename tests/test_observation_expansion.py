import tempfile
from pathlib import Path
import pytest
from packages.action_core.world import Sandbox
from packages.action_core.observation_scope import observe_ancestors


def test_selectable_native_observation_separates_alias_without_expanding_actions():
    with tempfile.TemporaryDirectory() as root:
        a = Sandbox(Path(root)/'a', ['source', 'container/dest'], {'source':b'x'})
        b = Sandbox(Path(root)/'b', ['source', 'container/dest'], {'source':b'x'})
        (b.root/'container').mkdir()  # fixture only, never a learned policy
        assert a.observe() == b.observe()
        actions = a.actions(); evidence = a.evidence()
        fa, added_a = observe_ancestors(a, ['n1'], max_new=1)
        fb, added_b = observe_ancestors(b, ['n1'], max_new=1)
        assert added_a == added_b == ('n2',)
        assert fa.kinds[-1] == 0 and fb.kinds[-1] == 2
        assert a.handles == ('n0','n1') and a.actions() == actions
        assert a.evidence() == evidence and not (a.root/'container').exists()
        # Looking at the unrelated handle reveals no extra node.
        untouched, added = observe_ancestors(a, ['n0'], max_new=0)
        assert not added and untouched == a.observe()


def test_scope_and_budget_denials_do_not_mutate_body():
    with tempfile.TemporaryDirectory() as root:
        body = Sandbox(Path(root)/'body', ['a/b/dest'], {})
        before = body.observe()
        for handles, budget in [(['n0'],1), (['../escape'],3), (['n0','n0'],3), (['n0'],True)]:
            with pytest.raises(ValueError):
                observe_ancestors(body, handles, max_new=budget)
        assert body.observe() == before
        assert not list(body.root.iterdir())
