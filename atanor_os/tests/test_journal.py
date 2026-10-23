from atanor_os.core.journal import Journal


def test_unresolved_actions_are_listed(tmp_path):
    j = Journal(tmp_path / 'j.sqlite')
    j.intent('e:0', 'e', 0, 'mkdir', ('d',), {'ok': True})
    j.intent('e:1', 'e', 1, 'mkdir', ('x',), {'ok': True})
    j.mark('e:0', 'executed', True)
    j.mark('e:0', 'verified', True)
    assert [r[0] for r in j.unresolved()] == ['e:1']
    assert j.counts() == {'intended': 1, 'verified': 1}
    j.close()
