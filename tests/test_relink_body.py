import os
from pathlib import Path
import tempfile
import pytest
from packages.action_core.world import Sandbox, Action
from packages.action_core.relink_body import RelinkBody

SCHEMA = [{'id':'empty','arity':1},{'id':'unlink','arity':1},
          {'id':'copy','arity':2},{'id':'link','arity':2}]


def test_link_is_native_and_requires_absent_destination():
    with tempfile.TemporaryDirectory() as root:
        body=RelinkBody(Path(root)/'body',paths=['a','b','ref'],
                        initial={'a':b'abc','b':b'def','ref':b'safe'},
                        protected={'n2'},operations=SCHEMA)
        link=Action('link',('n0','n1'))
        assert not body.step(link)
        assert body._paths['n1'].read_bytes()==b'def'
        assert body.step(Action('unlink',('n1',)))
        assert body.step(link)
        assert os.path.samefile(body._paths['n0'],body._paths['n1'])
        assert body.step(Action('empty',('n1',)))
        assert body._paths['n0'].read_bytes()==b''
        assert body._paths['n2'].read_bytes()==b'safe'


@pytest.mark.parametrize('args',[('n2','n0'),('n0','n2')])
def test_caller_cannot_alias_protected_handle(args):
    with tempfile.TemporaryDirectory() as root:
        body=RelinkBody(Path(root)/'body',paths=['a','b','ref'],
                        initial={'a':b'abc','ref':b'safe'},protected={'n2'},operations=SCHEMA)
        with pytest.raises(ValueError):body.step(Action('link',args))
        assert body._paths['n2'].read_bytes()==b'safe'


def test_native_protected_alias_is_denied_even_with_other_handle():
    with tempfile.TemporaryDirectory() as root:
        body=RelinkBody(Path(root)/'body',paths=['a','b','ref'],
                        initial={'ref':b'safe'},protected={'n2'},operations=SCHEMA)
        # Adversarial test-owned native alias, not legitimate body action.
        os.link(body._paths['n2'],body._paths['n0'])
        with pytest.raises(ValueError):body.step(Action('link',('n0','n1')))
        assert not body._paths['n1'].exists()


def test_default_body_still_rejects_link():
    with tempfile.TemporaryDirectory() as root:
        with pytest.raises(ValueError):
            Sandbox(Path(root)/'body',paths=['a','b'],initial={'a':b'x'},operations=SCHEMA)
