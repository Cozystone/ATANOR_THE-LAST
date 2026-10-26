"""DESK_EVAL2_PROTOCOL.md learner changes: capabilities come from whoever gives the command (a refusal is neither done
work nor counter-evidence), and an effect that comes in two steps is learned from observation, so the same command
later does not redo work already on its way. Also: the round-2 outcome rule keeps judge-accepted partial results apart."""
from atanor_os.agent.grounding import Grounder
from atanor_os.eval.desk_eval2 import outcome
from atanor_os.teach.tutor import DeskSpec, Tutor, symbols
from atanor_os.world.desk_world import DeskWorkspace


def _desk(tmp_path, seed=3):
    ws = DeskWorkspace(tmp_path / 'desk', seed=seed)
    tags = ['red', 'blue', 'none', 'green']
    ws.add_items({f'd{i}': {'kind': 'draft', 'tag': tags[i]} for i in range(4)} | {f'm{i}': {'kind': 'message', 'tag': tags[i]} for i in range(4)})
    return ws


def _teach(ws, tmp_path, sel, act):
    tut = Tutor(ws, DeskSpec, 1)
    tut.start(sel, act)
    g = Grounder(ws, tmp_path / 'mind', person=tut)
    sc, ac = g.learn_selection('L'), g.learn_action('L')
    g.apply(sc['content'], ac['content'], 'L')
    sym = symbols(1)
    g.bind(sym[0], sc['content']['concept'], 'L')
    g.bind(sym[1], ac['content']['action'], 'L')
    return sym[1], sym[0]


def test_the_learner_does_not_grant_itself_capabilities(tmp_path):
    ws = _desk(tmp_path)
    words = _teach(ws, tmp_path, {'kind': 'message'}, {'tool': 'purge'})
    ws.add_items({'m9': {'kind': 'message'}})
    res = Grounder(ws, tmp_path / 'mind', person=None).obey(list(words))       # nobody grants anything
    assert res['refused'] == ['m9'] and not res['ok'] and 'm9' in ws.existing()
    effect = [c for c in Grounder(ws, tmp_path / 'mind').mem.claims.claims('effect')][0]
    assert effect['status'] == 'active' and not effect['counter']            # not a counter-example
    res = Grounder(ws, tmp_path / 'mind', person=None, caps={'destroy_items': True}).obey(list(words))
    assert res['ok'] and ws.kind('m9') == 'absent'


def test_a_later_outcome_is_learned_and_not_redone(tmp_path):
    ws = _desk(tmp_path)
    words = _teach(ws, tmp_path, {'kind': 'draft'}, {'tool': 'send'})
    ws.add_items({f'n{i}': {'kind': 'draft', 'tag': ['blue', 'green', 'none'][i]} for i in range(3)})
    g = Grounder(ws, tmp_path / 'mind', person=None)
    assert g.obey(list(words))['ok']
    ws.tick()                                              # queued drafts are now sent or failed
    n0 = sum(1 for _ in open(ws.root / 'world_log.jsonl', encoding='utf-8'))
    res = Grounder(ws, tmp_path / 'mind', person=None).obey(list(words))
    again = open(ws.root / 'world_log.jsonl', encoding='utf-8').read().splitlines()[n0:]
    assert res['ok'] and not res['acted'] and not any('"tool": "send"' in l for l in again)
    effect = [c for c in Grounder(ws, tmp_path / 'mind').mem.claims.claims('effect')][0]
    assert effect['content'].get('later')


def test_partial_is_kept_apart_from_wrong(tmp_path):
    ws = _desk(tmp_path)
    spec = DeskSpec
    t = Tutor(ws, spec, 1)
    act = {'tool': 'read'}
    s = ws._read()
    s['items']['m0']['locked'] = True
    ws._write(s)
    t.start({'kind': 'message'}, act)
    for o in ('m1', 'm2', 'm3'):
        ws.execute('read', (o,), {})
    assert outcome(spec, act, t, {'ok': False, 'acted': ['m1', 'm2', 'm3'], 'failed': ['m0']}) == 'partial'
    assert outcome(spec, act, t, {'ok': True, 'acted': ['m1', 'm2', 'm3'], 'failed': []}) == 'success'
