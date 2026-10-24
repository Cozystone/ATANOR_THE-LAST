"""P3 spec tests: view body semantics, its true model vs reality, renderer fidelity, Korean grammar."""
import pytest

from atanor_os.agent.loop import run_episode
from atanor_os.agent.models import DocModel, RuleModel
from atanor_os.agent.bootstrap import VIEW_DOCS
from atanor_os.core.journal import Journal
from atanor_os.eval.explore import explore
from atanor_os.eval.generator import layout, materialize
from atanor_os.eval.oracle import reachable, rule_agreement, semantic_check
from atanor_os.eval.view_tasks import ViewTrueModel, make_view_task, view_block, view_sem_block, view_true_pre
from atanor_os.lang.korean import parse
from atanor_os.ui.renderer import layout as ui_layout, render_once, validate
from atanor_os.world.view_world import TOOLS, ViewWorkspace


def _data(tmp_path):
    import random
    files, ddir, dfile = layout(random.Random(3), 'dev')
    return materialize(tmp_path / 'data', files, ddir, dfile)


@pytest.mark.view
def test_view_tool_semantics(tmp_path):
    ws = ViewWorkspace(tmp_path / 'v', _data(tmp_path))
    caps = {'close_panels': True}
    assert ws.execute('filter', ('p1', 'ext:txt'), caps)['ok'] is False      # panel absent
    assert ws.execute('open', ('ext:txt',), caps)['ok'] is False              # values are not panels
    assert ws.execute('open', ('p1',), caps)['ok'] is True
    assert ws.execute('open', ('p1',), caps)['ok'] is False
    assert ws.execute('filter', ('p1', 'key:size'), caps)['ok'] is False      # wrong value class
    assert ws.execute('filter', ('p1', 'ext:txt'), caps)['ok'] is True
    assert ws.execute('group', ('p1', 'grp:ext'), caps)['ok'] is False        # grouping needs filter=all
    assert ws.execute('filter', ('p1', 'ext:all'), caps)['ok'] is True
    assert ws.execute('group', ('p1', 'grp:ext'), caps)['ok'] is True
    assert ws.execute('compare', ('cmp', 'p1'), caps)['ok'] is True
    assert ws.execute('filter', ('cmp', 'ext:txt'), caps)['ok'] is False      # compare panels are not filtered
    assert ws.execute('sort', ('cmp', 'key:size'), caps)['ok'] is True
    r = ws.execute('close', ('cmp',), {'close_panels': False})
    assert r['blocked'] and not r['ok']
    st = ws.observe()
    assert st['p1'] == {'kind': 'panel', 'filter': 'all', 'sort': 'name', 'group': 'ext', 'value': '-'}
    assert st['ext:md'] == {'kind': 'ext', 'filter': '-', 'sort': '-', 'group': '-', 'value': 'md'}
    assert len(ws.actions(ws.universe())) == 2 * 15 + 4 * 15 * 14


@pytest.mark.view
def test_view_true_model_matches_reality(tmp_path):
    r = semantic_check(8, seed=5, root=tmp_path / 'sem', block=view_sem_block, model=ViewTrueModel(), pre_fn=view_true_pre)
    assert r['ok'], r


@pytest.mark.view
def test_view_tasks_reachable_and_oracle_solves(tmp_path):
    seen = set()
    for i in range(6):
        ws, goal, meta = make_view_task(i, 'test', tmp_path / f't{i}')
        seen.add(meta['template'])
        assert reachable(ws, goal, model=ViewTrueModel()) is not None, goal.id
        j = Journal(tmp_path / f'j{i}.sqlite')
        rec = run_episode(ws, goal, ViewTrueModel(), j, f'o{i}')
        assert goal.satisfied(ws.observe()) and not rec['keep_violated'], goal.id
        j.close()
    assert seen == {'focus', 'regroup', 'compare'}


def P(kind, f='all', s='name', g='none'):
    return {'kind': kind, 'filter': f, 'sort': s, 'group': g, 'value': '-'}


def V(kind, value):
    return {'kind': kind, 'filter': '-', 'sort': '-', 'group': '-', 'value': value}


@pytest.mark.view
def test_view_rules_from_controlled_contrasts():
    from atanor_os.agent.rule_learner import learn_operator
    from atanor_os.core.types import Experience
    base = {'p1': P('panel'), 'p2': P('absent', '-', '-', '-'), 'ext:txt': V('ext', 'txt'), 'ext:csv': V('ext', 'csv'),
            'key:size': V('key', 'size'), 'grp:ext': V('grp', 'ext')}
    X = lambda i, tool, args, pre, post, ok: Experience(f'v{i}', tool, args, pre, post, ok)
    pre2 = {**base, 'p1': P('panel', 'txt')}
    exps = [X(1, 'filter', ('p1', 'ext:txt'), base, pre2, True),
            X(2, 'filter', ('p1', 'ext:csv'), pre2, {**pre2, 'p1': P('panel', 'csv')}, True),
            X(3, 'filter', ('p1', 'ext:txt'), pre2, pre2, True),          # same value: success without change
            X(4, 'filter', ('p2', 'ext:txt'), base, base, False),          # absent panel
            X(5, 'filter', ('p1', 'key:size'), base, base, False)]         # wrong value class
    op = learn_operator('filter', 2, exps)
    assert op.pre == frozenset({('kind', (0,), 'panel'), ('kind', (1,), 'ext')}), op.to_json()
    assert op.effects == [(0, 'filter', ('copy', 1, 'value'))], op.to_json()
    g1 = {**base, 'p1': P('panel', 'all')}
    g2 = {**base, 'p1': P('panel', 'csv')}
    g3 = {**base, 'cmp': P('compare', 'all')}
    exps_g = [X(6, 'group', ('p1', 'grp:ext'), g1, {**g1, 'p1': P('panel', 'all', 'name', 'ext')}, True),
              X(7, 'group', ('p1', 'grp:ext'), {**g1, 'p1': P('panel', 'all', 'size')},
                {**g1, 'p1': P('panel', 'all', 'size', 'ext')}, True),
              X(8, 'group', ('p1', 'grp:ext'), g2, g2, False),             # filtered list cannot be grouped
              X(9, 'group', ('p2', 'grp:ext'), g1, g1, False),             # absent panel
              X(10, 'group', ('cmp', 'grp:ext'), g3, g3, False)]           # compare panel (filter all) cannot be grouped
    opg = learn_operator('group', 2, exps_g, type_attrs=('kind', 'value'))
    assert ('filter', (0,), 'all') in opg.pre and ('kind', (0,), 'panel') in opg.pre, opg.to_json()
    c1 = {**base, 'p1': P('panel', 'txt', 'size'), 'cmp': P('absent', '-', '-', '-')}
    c2 = {**base, 'p1': P('panel', 'csv', 'name'), 'cmp': P('absent', '-', '-', '-')}
    c3 = {**c1, 'p2': P('panel')}
    exps_c = [X(11, 'compare', ('cmp', 'p1'), c1, {**c1, 'cmp': P('compare', 'txt', 'size')}, True),
              X(12, 'compare', ('cmp', 'p1'), c2, {**c2, 'cmp': P('compare', 'csv', 'name')}, True),
              X(13, 'compare', ('cmp', 'p2'), c1, c1, False),           # source panel absent
              X(14, 'compare', ('p2', 'p1'), c3, c3, False)]            # target already open
    opc = learn_operator('compare', 2, exps_c)
    assert opc.pre == frozenset({('kind', (0,), 'absent'), ('kind', (1,), 'panel')}), opc.to_json()
    assert (0, 'filter', ('copy', 1)) in opc.effects and (0, 'sort', ('copy', 1)) in opc.effects, opc.to_json()   # same-attribute copy
    assert (0, 'kind', ('const', 'compare')) in opc.effects and (0, 'group', ('const', 'none')) in opc.effects, opc.to_json()


@pytest.mark.view
@pytest.mark.learning
def test_same_learner_induces_view_rules_from_exploration(tmp_path):
    exps = explore(2, 300, tmp_path / 'x', policy='contrast-kind', block=view_block)
    m = RuleModel(exps, spec={'tools': TOOLS, 'docs': VIEW_DOCS, 'type_attrs': ('kind', 'value')})
    op = m.ops['filter']
    assert op is not None and op.pre is not None and op.support >= 2, None if op is None else op.to_json()
    assert ('kind', (0,), 'panel') in op.pre, op.to_json()
    assert (0, 'filter', ('copy', 1, 'value')) in op.effects, op.to_json()
    opg = m.ops['group']                        # the rare tool: kind-level novelty must find its first successes
    assert opg is not None and opg.support >= 2 and ('kind', (0,), 'panel') in opg.pre, None if opg is None else opg.to_json()
    opc = m.ops['compare']
    assert (0, 'filter', ('copy', 1)) in opc.effects, opc.to_json()


@pytest.mark.view
def test_renderer_draws_exactly_the_layout(tmp_path):
    data = _data(tmp_path)
    spec = {'p1': {'kind': 'panel', 'filter': 'all', 'sort': 'name', 'group': 'ext'},
            'cmp': {'kind': 'compare', 'filter': 'txt', 'sort': 'size', 'group': 'none'}}
    validate(spec)
    with pytest.raises(ValueError):
        validate({'p9': spec['p1']})
    with pytest.raises(ValueError):
        validate({'p1': {**spec['p1'], 'filter': 'exe'}})
    lay = ui_layout(spec, data)
    assert lay['p1']['items'][0].startswith('[') and any(x.startswith('L ') for x in lay['cmp']['items'])
    try:
        w = render_once(spec, data)
    except Exception as e:                                        # no display available
        pytest.skip(f'tkinter unavailable: {e}')
    for p in sorted(spec):
        assert list(w['lists'][p].get(0, 'end')) == lay[p]['items']
        btn, action = w['buttons'][p]
        assert action == ('close', (p,))
        btn.invoke()
    assert w['requested'] == [('close', ('cmp',)), ('close', ('p1',))]
    w['root'].destroy()


def _lits(ls):
    return {(l.pred, l.args, l.value) for l in ls}


@pytest.mark.view
def test_korean_grammar():
    r = parse('p3를 열어, p3에서 md만 보여줘 그리고 p3를 크기순으로 정렬')
    assert r['goal'] is not None and r['unsupported'] == [] and r['ask'] is None
    assert _lits(r['literals']) >= {('kind', ('p3',), 'panel'), ('filter', ('p3',), 'md'), ('sort', ('p3',), 'size')}
    r2 = parse('이것을 확장자별로 묶어')
    assert r2['goal'] is None and r2['ask']                        # deixis without a selection asks
    r3 = parse('이것을 확장자별로 묶어', selection='p1')
    assert {('group', ('p1',), 'ext'), ('filter', ('p1',), 'all')} <= _lits(r3['literals'])
    r4 = parse('p1을 예쁘게 꾸며줘')
    assert r4['goal'] is None and r4['unsupported'] == ['p1을 예쁘게 꾸며줘']
    state = {'p1': {'kind': 'panel'}, 'p2': {'kind': 'panel'}, 'ext:txt': {'kind': 'ext'}}
    r5 = parse('cmp를 p1과 비교', state=state)
    assert ('kind', ('p2',), 'panel') in _lits(r5['goal'].keep) and r5['goal'].capabilities == {'close_panels': False}


@pytest.mark.view
def test_rule_agreement_grades_truth_and_docs(tmp_path):
    r = rule_agreement(ViewTrueModel(), k=5, seed=3, root=tmp_path / 'a', block=view_sem_block, pre_fn=view_true_pre)
    assert r['filled'] and r['n_exact'] == r['n_tools'] == 6, r
    d = rule_agreement(DocModel(spec={'tools': TOOLS, 'docs': VIEW_DOCS, 'type_attrs': ('kind', 'value')}), k=5, seed=3, root=tmp_path / 'd',
                       block=view_sem_block, pre_fn=view_true_pre)
    assert d['n_exact'] < 6 and sum(v['fp'] for v in d['per_tool'].values()) > 0, d      # docs are optimistic
