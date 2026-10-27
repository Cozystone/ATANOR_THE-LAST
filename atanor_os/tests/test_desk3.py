"""DESK_EVAL3_PROTOCOL.md: an unheard word standing where another known phrase of the same kind has its deciding word
keeps the reading undecided, even when a broader phrase was said whole (a constructed development case; the
development seed's desk phrases have no such pair). The frozen round-2 learner shows the flaw."""
from atanor_os.agent.grounding import Grounder
from atanor_os.agent.grounding_g36 import Grounder as Grounder36
from atanor_os.teach.tutor import DeskSpec, Tutor
from atanor_os.world.desk_world import DeskWorkspace


def _taught(tmp_path):
    ws = DeskWorkspace(tmp_path / 'desk', seed=3)
    tags = ['blue', 'red', 'none', 'green', 'blue', 'none']
    ws.add_items({f'n{i}': {'kind': 'note', 'tag': tags[i]} for i in range(6)} | {f'm{i}': {'kind': 'message', 'tag': tags[i]} for i in range(4)})
    lessons = [({'kind': 'note'}, ['the', 'notes']), ({'kind': 'note', 'tag': 'blue'}, ['the', 'blue', 'notes']),
               ({'kind': 'message'}, ['the', 'messages'])]
    for k, (sel, phrase) in enumerate(lessons):
        tut = Tutor(ws, DeskSpec, k)
        tut.start(sel, {'tool': 'pin'})
        g = Grounder(ws, tmp_path / 'mind', person=tut)
        sc = g.learn_selection(f'L{k}')
        g.name_phrase(phrase, sc['content']['concept'], f'L{k}')
        if k == 0:
            ac = g.learn_action('L0')
            g.name_phrase(['pin'], ac['content']['action'], 'L0')
            ws_state = ws._read()                            # the lesson's pin is undone: the commands below start fresh
            for it in ws_state['items'].values():
                it['status'] = 'plain' if it['kind'] == 'note' else it['status']
            ws._write(ws_state)
    ws.add_items({'n8': {'kind': 'note', 'tag': 'blue'}, 'n9': {'kind': 'note', 'tag': 'red'}})
    return ws


def test_an_unknown_modifier_is_not_dropped(tmp_path):
    ws = _taught(tmp_path)
    res = Grounder(ws, tmp_path / 'mind', person=None, caps={}).obey(['pin', 'the', 'cerulean', 'notes'])
    assert not res.get('acted') and res.get('why') == 'unknown word in place of a deciding word'
    res = Grounder(ws, tmp_path / 'mind', person=None, caps={}, cases=False).obey(['pin', 'the', 'notes', 'now'])   # a filler
    # elsewhere (generalizing alone: GEN3_F off; with it the notes never seen pinned are left, test_gen3_f.py)
    assert res['ok'] and res['acted']


def test_the_round_2_learner_drops_it(tmp_path):
    ws = _taught(tmp_path)
    res = Grounder36(ws, tmp_path / 'mind', person=None, caps={}).obey(['pin', 'the', 'cerulean', 'notes'])
    assert res.get('acted')                                # all notes, the red one too
