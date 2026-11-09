import json

import pytest

from atanor_os.life.metabolism import DEFAULT_GENOME, GAIN, PRICES, Death, Metabolism


def test_prices_follow_the_record_kinds():
    m = Metabolism()
    assert m.price_of('PREDICTION', {}) == PRICES['PREDICTION']
    assert m.price_of('ACTION_INTENT', {'actor': 'learner'}) == PRICES['ACTION_INTENT']
    assert m.price_of('ACTION_INTENT', {'actor': 'learner-lab'}) == PRICES['LAB']
    assert m.price_of('OBSERVATION', {}) == 0 and m.price_of('HOST', {}) == 0 and m.price_of('INTEROCEPTION', {}) == 0
    assert m.price_of('TESTIMONY', {'question': 'recall'}) == 0
    assert m.price_of('TESTIMONY', {'question': 'this_one_too'}) == PRICES['QUESTION']
    assert m.price_of('TESTIMONY', {'question': 'demo'}) == 0 and m.price_of('TESTIMONY', {'question': 'point'}) == 0
    off = Metabolism(enabled=False)
    assert off.price_of('ACTION_INTENT', {}) == 0 and off.allow(5, True)
    off.charge('x', -1000)
    assert not off.dead


def test_death_is_once_and_at_zero():
    m = Metabolism(e0=1.0)
    m.charge('a', -0.6)
    assert not m.dead
    with pytest.raises(Death):
        m.charge('b', -0.6)
    assert m.dead


def test_replay_gives_the_balance_of_the_record():
    m = Metabolism(e0=50)
    rows = [{'kind': 'INTEROCEPTION', 'data': {'E': 41.5}}, {'kind': 'OBSERVATION', 'data': {}}, {'kind': 'INTEROCEPTION', 'data': {'E': 44.5}}]
    assert m.replay(rows) == 44.5 and not m.dead
    assert m.replay(rows + [{'kind': 'HOST', 'data': {'event': 'death'}}]) == 44.5 and m.dead


def test_the_one_rule_explores_when_safe_and_not_near_death():
    m = Metabolism({'E_low': 30, 'w_epi': 1.0})
    m.E = 80
    assert m.allow(PRICES['LAB'], unknown=True)          # far above the preferred floor: information is worth its price
    assert not m.allow(PRICES['LAB'], unknown=False)     # nothing to learn: no payment
    m.E = 0.5
    assert not m.allow(PRICES['LAB'], unknown=True)      # the price would nearly end the life: risk dwarfs the gain
    m.E = 25
    assert m.allow(PRICES['LAB'], unknown=True)          # a little below the floor: risk is small (0.045), still explores
    m.E = 0.3
    assert not m.allow(PRICES['LAB'], unknown=True)      # the price is the whole balance: infinite risk
    assert all(len(e) == 5 for e in m.evaluations)


def test_outcomes_feed_and_harm():
    m = Metabolism(e0=10)
    m.outcome('success')
    m.outcome('held')
    assert m.E == 10 + GAIN['success']
    m.outcome('wrong')
    assert m.E == 10 + GAIN['success'] + GAIN['wrong']
    assert set(DEFAULT_GENOME) == {'tau', 'lab_tests', 'per_action', 'E_low', 'E_high', 'w_epi', 'guide'}
    json.dumps(m.state())
