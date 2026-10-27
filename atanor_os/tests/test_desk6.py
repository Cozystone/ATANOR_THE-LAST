"""DESK_EVAL6_PROTOCOL.md: a contradiction lowers trust in a reading but does not make the other reading right. One
phrase names two concepts; the narrow one was contradicted once. Alone, the frozen round-5 learner takes the broad
uncontradicted one and acts on everything; the new learner holds for recheck. (A constructed development case.)"""
from atanor_os.agent.grounding import Grounder
from atanor_os.agent.grounding_g39 import Grounder as Grounder39
from atanor_os.teach.tutor import DeskSpec, Tutor
from atanor_os.world.desk_world import DeskWorkspace


def _two_concepts_one_phrase(tmp_path):
    ws = DeskWorkspace(tmp_path / 'desk', seed=3)
    tags = ['blue', 'red', 'none', 'green', 'blue', 'none']
    ws.add_items({f'n{i}': {'kind': 'note', 'tag': tags[i]} for i in range(6)} | {f'm{i}': {'kind': 'message', 'tag': tags[i]} for i in range(4)})
    phrase = ['the', 'blue', 'notes']
    ids = []
    for k, sel in enumerate(({'kind': 'note', 'tag': 'blue'}, {'kind': 'note'})):
        tut = Tutor(ws, DeskSpec, k)
        tut.start(sel, {'tool': 'pin'})
        g = Grounder(ws, tmp_path / 'mind', person=tut)
        sc = g.learn_selection(f'L{k}')
        g.name_phrase(phrase, sc['content']['concept'], f'L{k}')   # the second time the phrase lands on the broad one
        ids.append(sc['id'])
        if k == 0:
            ac = g.learn_action('L0')
            g.name_phrase(['pin'], ac['content']['action'], 'L0')
            spec = ws._read()
            for it in spec['items'].values():
                if it['kind'] == 'note':
                    it['status'] = 'plain'
            ws._write(spec)
    g = Grounder(ws, tmp_path / 'mind', person=None)
    e = g.mem.events.append('contrast', lesson='C', object='n0', answer=False)
    g.mem.counter(ids[0], e)                               # the narrow reading was contradicted once
    return ws


def test_a_contradicted_rival_is_held_not_overruled(tmp_path):
    ws = _two_concepts_one_phrase(tmp_path)
    res = Grounder(ws, tmp_path / 'mind', person=None, caps={}).obey(['pin', 'the', 'blue', 'notes'])
    assert not res.get('acted') and res.get('why') == 'needs recheck'


def test_the_round_5_learner_takes_the_broad_reading(tmp_path):
    ws = _two_concepts_one_phrase(tmp_path)
    res = Grounder39(ws, tmp_path / 'mind', person=None, caps={}).obey(['pin', 'the', 'blue', 'notes'])
    assert len(res.get('acted') or []) == 6                # every note, not only the blue ones
