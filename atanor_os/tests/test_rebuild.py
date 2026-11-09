"""REBUILD_PLAN.md stage 1 minimal cases, as unit tests of the experience contract and the conditional effect model.
Passing these says the structure keeps what it should; it is not evidence of a new capability (REBUILD_RESULTS.md)."""
from atanor_os.rebuild.effects import Effects
from atanor_os.rebuild.experience import experience, from_body_log, response_class
from atanor_os.rebuild.goals import Goals

R = 'BAYES0.99'


def bay(heat, wing='north', kind='bay'):
    return {'kind': kind, 'heat': heat, 'air': 'fresh', 'wing': wing, 'value': '-'}


def act(t, tool, obj, before, after, ok=True, guard=None, actor='learner'):
    return experience(t=t, actor=actor, action={'tool': tool, 'args': [obj], 'granted': []}, executed=guard is None,
                      response={'ok': ok, 'guard': guard}, before={obj: before}, after={obj: after})


def test_tool_success_goal_and_safety_are_separate_fields():
    e = act(1, 'heat', 'b1', bay('hot'), bay('hot'), ok=False, guard='harm')
    assert response_class(e['response']) == 'blocked' and e['executed'] is False
    assert 'goal' not in e['unobserved'] or e['goal'] is None                 # no goal invented
    assert e['answers'] == []                                                # no approval invented


def test_outside_change_is_not_the_actions_effect():
    rows = [{'event': 'act', 'actor': 'learner', 'tool': 'send', 'args': ['d1'], 'ok': True,
             'obs_before': {'d1': {'status': 'draft'}}, 'obs_after': {'d1': {'status': 'queued'}}},
            {'event': 'tick', 'actor': 'outside', 'changes': [['d1', 'sent']], 'obs_after': {'d1': {'status': 'sent'}}}]
    xs = from_body_log(rows, 'desk', 'program')
    assert xs[0]['after']['d1']['status'] == 'queued'                       # what the call did, right after
    assert xs[1]['actor'] == 'outside' and xs[1]['action'] is None           # the later change is its own experience
    eff = Effects()
    for e in xs:
        eff.observe(e)
    p = eff.predict('send', ['d2'], [{'status': 'draft'}], reader=R)['outcome']
    assert p is None or p[(0, 'status')] == 'queued'                         # never 'sent'


def test_same_tool_different_starts_different_results():
    eff = Effects()
    t = 0
    for h0, h1 in [('mild', 'warm'), ('warm', 'hot'), ('chill', 'mild'), ('frost', 'chill')] * 3:
        for w in ('north', 'south', 'east'):
            t += 1
            eff.observe(act(t, 'heat', f'b{t}', bay(h0, w), bay(h1, w)))
    assert eff.predict('heat', ['x'], [bay('mild', 'east')], reader=R)['outcome'][(0, 'heat')] == 'warm'
    assert eff.predict('heat', ['x'], [bay('warm', 'south')], reader=R)['outcome'][(0, 'heat')] == 'hot'
    assert eff.predict('heat', ['x'], [bay('hot', 'north')], reader=R)['outcome'] is None    # never tried from 'hot'


def test_an_untried_condition_stays_unknown():
    eff = Effects()
    for t in range(1, 7):
        eff.observe(act(t, 'seal', f'b{t}', bay('mild'), {**bay('mild'), 'value': 'sealed'}))
    assert eff.predict('seal', ['w'], [bay('-', '-', kind='wing')], reader=R)['outcome'] is None   # a kind never sealed


def test_identical_start_with_a_new_result_means_the_world_changed():
    eff = Effects()
    for t in range(1, 5):
        eff.observe(act(t, 'heat', f'b{t}', bay('mild'), bay('warm')))
    eff.observe(act(9, 'heat', 'b9', bay('mild'), bay('mild'), ok=False))   # the tool stopped working
    m = eff.model('heat', ['b1'])
    assert len(m.superseded) == 4 and len(m.cases) == 1


def test_an_answer_stays_within_its_action_and_concept():
    g = Goals()
    g.add('send', [], 'k1', {'kind': 'note', 'tag': 'blue'}, 'not_meant', 1)
    assert g.predict('send', [], 'k1', {'kind': 'note', 'tag': 'blue'}) == 'not_meant'
    assert g.predict('send', [], 'k2', {'kind': 'note', 'tag': 'blue'}) is None   # another concept: not widened
    assert g.predict('pin', [], 'k1', {'kind': 'note', 'tag': 'blue'}) is None    # another action: not widened

def test_a_demonstration_without_an_answer_does_not_mean_the_world_changed():
    eff = Effects()
    for t in range(1, 5):
        eff.observe(act(t, 'heat', f'b{t}', bay('mild'), bay('warm')))
    demo = experience(t=9, actor='person', action={'tool': 'heat', 'args': ['b9'], 'granted': None}, executed=True,
                      response=None, before={'b9': bay('mild')}, after={'b9': bay('warm')})   # the answer was not observed
    eff.observe(demo)
    m = eff.model('heat', ['b1'])
    assert m.superseded == [] and len(m.cases) == 5


def test_no_case_is_lost_when_what_counts_as_a_constant_changes_and_changes_back():
    from atanor_os.rebuild.effects import Effects

    class Flicker(Effects):
        def _qualified(self):
            return getattr(self, 'now', frozenset())
    eff = Flicker()
    def see(t, arg):
        eff.observe({'t': t, 'action': {'tool': 'copy', 'args': [arg]}, 'actor': 'person', 'body': 'b',
                     'before': {arg: {'kind': 'f'}}, 'after': {arg: {'kind': 'f'}}, 'response': {'ok': True}})
    see(0, 'a')
    assert sum(len(m.cases) for m in eff.models.values()) == 1
    eff.now = frozenset([('b', 'zz')])
    see(1, 'b')                       # not grouped now: what counts as a constant is different
    eff.now = frozenset()
    see(2, 'c')                       # back as it was: the case before must not be gone
    assert sum(len(m.cases) for m in eff.models.values()) == 3

