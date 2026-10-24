import pytest
from scripts.plastic_law_world import LawWorld, native
from scripts.developmental_plastic_eval import frame


@pytest.mark.parametrize('law', ['null', 'cascade'])
def test_identical_sensors_but_real_conflicting_native_outcome(law):
    a=LawWorld(123,n=5,prefill=2)
    b=LawWorld(123,n=5,prefill=2,law=law)
    try:
        assert frame(a)==frame(b)
        original=list(a.config())
        assert a.con.execute('PRAGMA foreign_keys').fetchone()[0]==1
        assert b.con.execute('PRAGMA foreign_keys').fetchone()[0]==1
        assert not a.do('delete',0)
        assert b.do('delete',0)
        assert list(a.config())==original
        expected=[0]+[(1 if law=='null' else 0) if x==2 else x for x in original[1:]]
        assert list(b.config())==expected
        assert not b.con.execute('PRAGMA foreign_key_check').fetchall()
        assert set(frame(b))=={'kinds','scalars','edges'}
    finally:
        a.dispose(); b.dispose()


def test_unchanged_restrict_body_matches_original_and_no_operator_override():
    a=native.FKWorld(45,n=4,prefill=2); b=LawWorld(45,n=4,prefill=2)
    try:
        assert LawWorld.do is native.FKWorld.do
        for op,i in [('delete',0),('unlink',1),('delete',2),('insert',2),('link',2)]:
            assert frame(a)==frame(b)
            assert a.do(op,i)==b.do(op,i)
            assert frame(a)==frame(b)
    finally:
        a.dispose();b.dispose()
