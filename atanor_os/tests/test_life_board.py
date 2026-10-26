"""The same core on the third body (a task board): no board words in the core; the teacher judges on the board as it
is; a change shown and confirmed is reused on other cards and another tray with nobody to ask."""
from pathlib import Path

from atanor_os.agent.life import Mind
from atanor_os.teach.life_teacher import BoardTeacher
from atanor_os.world.board_world import BoardWorkspace


def _board(tmp_path, cards):
    ws = BoardWorkspace(tmp_path / 'board')
    ws.add_cards(cards)
    return ws


def _do(ws, tmp_path, teacher, task, tid, user=True):
    teacher.begin(task)
    m = Mind(ws, tmp_path / 'mind', tmp_path / 'lab', user=teacher if user else None)
    r = m.do(task['command'], tid)
    return r, teacher.judge(), m


def test_core_has_no_board_words():
    src = (Path(__file__).resolve().parents[1] / 'agent' / 'life.py').read_text(encoding='utf-8')
    for word in ("'card'", "'tray'", "'mark'", "'level'", "'urgent'", "'teal'", "'lodge'", "'stamp'"):
        assert word not in src, word


def test_teacher_judges_on_the_board_as_it_is(tmp_path):
    ws = _board(tmp_path, {'a1': {'mark': 'idea'}, 'a2': {'mark': 'chore'}})
    t = BoardTeacher(ws)
    t.begin({'command': 'x', 'tool': 'lodge', 'select': ['mark', 'idea'], 'second': 't2', 'phrases': {}})
    assert t.truth == ['a1'] and not t.judge()
    ws.execute('lodge', ('a1', 't2'), {})
    assert t.judge()
    ws.execute('lodge', ('a2', 't2'), {})
    assert not t.judge()                                       # another card changed too


import pytest


@pytest.mark.xfail(strict=True, reason='v24 core: a value token that names the second object also constrains the selection '
                   '(contradiction); the target for language learning v2')
def test_a_board_change_shown_once_is_reused_alone(tmp_path):
    ws = _board(tmp_path, {'a1': {'mark': 'idea'}, 'a2': {'mark': 'chore'}, 'a3': {'mark': 'idea'}})
    t = BoardTeacher(ws)
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Stash the idea cards in the teal tray.', 'tool': 'lodge', 'select': ['mark', 'idea'],
                                    'second': 't2', 'phrases': {'explain_map': {'the': '', 'in': '', 'tray': '', 'cards': ''}}}, 't1')
    assert ok, (r, dict(t.help))
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Stash the chore cards in the amber tray.', 'tool': 'lodge', 'select': ['mark', 'chore'],
                                    'second': 't1', 'phrases': {}}, 't1b')
    assert ok, (r, dict(t.help))
    ws.add_cards({'b1': {'mark': 'memo'}, 'b2': {'mark': 'memo'}})
    before = dict(t.help)
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Stash the memo cards in the plum tray.', 'tool': 'lodge', 'select': ['mark', 'memo'],
                                    'second': 't3', 'phrases': {}}, 't2', user=False)
    assert ok, (r, dict(m.counts))
    assert t.help == before
