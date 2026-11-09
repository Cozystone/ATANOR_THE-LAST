"""The generated world family: deterministic by seed, every effect in the grammar, no real body's words, a precondition that
fails leaves the state as it was."""
import random

from atanor_os.memory.worlds import World, generate


def test_worlds_are_deterministic_and_within_the_grammar():
    a, b = World(11), World(11)
    assert a.attrs == b.attrs and a.tools.keys() == b.tools.keys()
    for p in a.tools.values():
        assert p['nargs'] in (1, 2)
        for (i, attr), op in p['ops'].items():
            assert i < p['nargs'] and attr in a.attrs and op[0] in ('set', 'copy', 'blank', 'step', 'map')
            if op[0] == 'copy':
                assert op[1] == 1 - i and p['nargs'] == 2


def test_a_failed_precondition_changes_nothing():
    found = False
    for seed in range(60):
        w = World(seed)
        for tool, p in w.tools.items():
            if p['pre'] is None:
                continue
            rng = random.Random(seed)
            for _ in range(30):
                before = [w.state(rng) for _ in range(p['nargs'])]
                after, ok = w.apply(tool, before)
                if not ok:
                    assert after == before
                    found = True
    assert found


def test_no_real_body_word_is_in_the_family():
    real = {'bolt', 'vat', 'hue', 'fibre', 'dye', 'dip', 'peg', 'bay', 'heat', 'wing', 'tray', 'card', 'inbox', 'shelve', 'hash', 'move'}
    sc = generate(40, 5, seed=3)
    words = {w for s in sc for _, k, v in s.toks for w in (k, v)} | {s.tool for s in sc}
    assert not (words & real)
    assert any(s.resp == 1 for s in sc) and any(t != p for s in sc for p, t in enumerate(s.tg))
