import copy
import json

import numpy as np
import pytest

from scripts.shared_world_metrics import ARMS, analyze


def fixture(lives=8, *, costs=None, cpus=None, successes=None):
    costs = costs or {'relational': 2, 'full_context': 4, 'retrieval': 4, 'frozen': 3}
    cpus = cpus or {'relational': 1., 'full_context': 2., 'retrieval': 2., 'frozen': 1.}
    successes = successes or {a: True for a in ARMS}
    rows = []
    for life in range(lives):
        for arm in ARMS:
            completed = successes[arm]
            rows.append({'life': life, 'arm': arm, 'cpu_seconds': cpus[arm], 'episodes': [
                {'index': index, 'phase': 'learning' if index < 2 else 'evaluation',
                 'result': {'completed': completed, 'steps': costs[arm]},
                 'charged_steps': costs[arm] if completed else 8}
                for index in range(4)]})
    return rows, {a: 0. for a in ARMS}


def test_known_counts_clear_online_and_utility_gain():
    rows, training = fixture()
    result = analyze(rows, training, expected_lives=8, bootstrap=200)
    assert result['status'] == 'CAPABILITY_GATE_GREEN'
    assert all(result['gates'].values())
    assert result['raw_totals']['relational']['all'] == {
        'goals': 32, 'successes': 32, 'success_rate': 1., 'actual_steps': 64, 'charged_steps': 64}
    assert result['raw_totals']['full_context']['evaluation']['charged_steps'] == 64
    assert result['comparisons']['full_context']['charged_ratio'] == .5
    assert result['comparisons']['full_context']['charged_ratio_ucb95'] == .5
    assert result['online_contribution']['frozen_minus_online_charged_per_goal_lcb05'] == 1.
    json.dumps(result, allow_nan=False)


def test_identical_online_and_frozen_is_partial_not_online_gain():
    rows, training = fixture(costs={'relational': 2, 'full_context': 4, 'retrieval': 4, 'frozen': 2})
    result = analyze(rows, training, expected_lives=8, bootstrap=200)
    assert result['status'] == 'PARTIAL_NO_ONLINE_LIFT'
    assert result['integrated_utility']
    assert not result['online_contribution']['confirmed']


def test_identical_arms_cannot_pass_twenty_percent_cost_improvement():
    rows, training = fixture(costs={a: 2 for a in ARMS}, cpus={a: 1. for a in ARMS})
    result = analyze(rows, training, expected_lives=8, bootstrap=200)
    assert result['status'] == 'NO_GO'
    assert result['comparisons']['full_context']['success_difference_lcb05'] == 0.
    assert result['comparisons']['full_context']['charged_ratio_ucb95'] == 1.


def test_training_cost_is_added_once_and_can_remove_cpu_gain():
    rows, training = fixture()
    training['relational'] = 10.
    result = analyze(rows, training, expected_lives=8, bootstrap=200)
    assert result['raw_totals']['relational']['total_cpu_seconds'] == 18.
    assert result['comparisons']['full_context']['total_cpu_ratio'] == 18 / 16
    assert result['comparisons']['full_context']['total_cpu_ratio_ucb95'] == 18 / 16
    assert result['status'] == 'NO_GO'


def test_paired_cluster_bootstrap_matches_independent_explicit_calculation():
    rows, training = fixture(lives=4)
    for row in rows:
        row['cpu_seconds'] *= row['life'] + 1
        for episode in row['episodes']:
            episode['result']['steps'] += row['life'] % 2
            episode['charged_steps'] = episode['result']['steps']
    training['relational'], training['full_context'] = 7., 3.
    result = analyze(rows, training, expected_lives=4, seed=92, bootstrap=50)
    rng = np.random.Generator(np.random.PCG64(92))
    samples = rng.integers(0, 4, size=(50, 4))
    cpu_ratios, action_ratios = [], []
    for indexes in samples:
        rel_cpu = sum(int(i) + 1 for i in indexes) + 7
        ctx_cpu = 2 * sum(int(i) + 1 for i in indexes) + 3
        cpu_ratios.append(rel_cpu / ctx_cpu)
        action_ratios.append(sum(2 + int(i) % 2 for i in indexes) / sum(4 + int(i) % 2 for i in indexes))
    primary = result['comparisons']['full_context']
    assert primary['total_cpu_ratio_ucb95'] == pytest.approx(np.quantile(cpu_ratios, .95, method='linear'))
    assert primary['charged_ratio_ucb95'] == pytest.approx(np.quantile(action_ratios, .95, method='linear'))


@pytest.mark.parametrize('change', ['duplicate', 'missing', 'nan_cpu', 'zero_cpu', 'bool_success',
    'bool_steps', 'negative_steps', 'excess_steps', 'wrong_charge', 'phase', 'duplicate_goal', 'missing_goal', 'bad_training'])
def test_counterfeit_or_missing_inputs_are_invalid(change):
    rows, training = fixture()
    if change == 'duplicate': rows[-1] = copy.deepcopy(rows[0])
    elif change == 'missing': rows.pop()
    elif change == 'nan_cpu': rows[0]['cpu_seconds'] = float('nan')
    elif change == 'zero_cpu': rows[0]['cpu_seconds'] = 0.
    elif change == 'bool_success': rows[0]['episodes'][0]['result']['completed'] = 1
    elif change == 'bool_steps': rows[0]['episodes'][0]['result']['steps'] = True
    elif change == 'negative_steps': rows[0]['episodes'][0]['result']['steps'] = -1
    elif change == 'excess_steps': rows[0]['episodes'][0]['result']['steps'] = 9
    elif change == 'wrong_charge': rows[0]['episodes'][0]['charged_steps'] = 0
    elif change == 'phase': rows[0]['episodes'][2]['phase'] = 'learning'
    elif change == 'duplicate_goal': rows[0]['episodes'][3]['index'] = 2
    elif change == 'missing_goal': rows[0]['episodes'].pop()
    else: training['frozen'] = float('inf')
    result = analyze(rows, training, expected_lives=8, bootstrap=20)
    assert result['status'] == 'INVALID'
    assert result['errors']


def test_failure_is_charged_full_budget_and_weak_baseline_cannot_validate():
    rows, training = fixture(successes={'relational': True, 'full_context': False,
                                       'retrieval': True, 'frozen': True})
    result = analyze(rows, training, expected_lives=8, bootstrap=100)
    assert result['raw_totals']['full_context']['evaluation']['charged_steps'] == 128
    assert result['status'] == 'NO_GO'
    assert not result['gates']['strong_baseline_success_at_least_50pct']


def test_zero_target_cost_denominator_is_invalid_not_silent_perfect_ratio():
    rows, training = fixture(costs={'relational': 2, 'full_context': 0, 'retrieval': 4, 'frozen': 3})
    result = analyze(rows, training, expected_lives=8, bootstrap=100)
    assert result['status'] == 'INVALID'
    assert 'zero cost denominator' in result['errors'][0]


def test_zero_actual_success_steps_are_legal_and_failures_cannot_hide_as_zero_charge():
    rows, training = fixture(costs={'relational': 0, 'full_context': 4, 'retrieval': 4, 'frozen': 3})
    assert analyze(rows, training, expected_lives=8, bootstrap=20)['status'] == 'CAPABILITY_GATE_GREEN'
    rows[0]['episodes'][0]['result']['completed'] = False
    assert analyze(rows, training, expected_lives=8, bootstrap=20)['status'] == 'INVALID'


def test_primary_comparator_is_not_switched_to_weak_retrieval_after_result():
    rows, training = fixture(costs={'relational': 3, 'full_context': 3, 'retrieval': 8, 'frozen': 4})
    result = analyze(rows, training, expected_lives=8, bootstrap=100)
    assert result['comparisons']['retrieval']['charged_ratio'] < .8
    assert result['status'] == 'NO_GO'
    assert result['primary_comparator'] == 'full_context'


def test_learning_goal_failures_are_reported_but_not_counted_as_target_goals():
    rows, training = fixture()
    for row in rows:
        for episode in row['episodes'][:2]:
            episode['result'].update(completed=False, steps=0)
            episode['charged_steps'] = 8
    result = analyze(rows, training, expected_lives=8, bootstrap=100)
    assert result['status'] == 'CAPABILITY_GATE_GREEN'
    counts = result['raw_totals']['relational']
    assert counts['all']['successes'] == 16
    assert counts['learning']['successes'] == 0
    assert counts['learning']['charged_steps'] == 128
    assert counts['evaluation']['successes'] == 16


def test_online_cost_gain_does_not_hide_success_regression_against_frozen():
    rows, training = fixture(costs={'relational': 1, 'full_context': 4, 'retrieval': 4, 'frozen': 3})
    for row in rows:
        if row['life'] == 0 and row['arm'] in ('relational', 'full_context'):
            row['episodes'][2]['result']['completed'] = False
            row['episodes'][2]['charged_steps'] = 8
    result = analyze(rows, training, expected_lives=8, seed=4, bootstrap=200)
    assert result['online_contribution']['frozen_minus_online_charged_per_goal'] > 0
    assert result['online_contribution']['success_difference_lcb05'] < -.05
    assert result['status'] == 'PARTIAL_NO_ONLINE_LIFT'


def test_default_protocol_requires_64_complete_life_clusters():
    rows, training = fixture(lives=64)
    result = analyze(rows, training, bootstrap=20)
    assert result['status'] == 'CAPABILITY_GATE_GREEN'
    assert result['method']['life_clusters'] == 64
    assert result['raw_totals']['relational']['evaluation']['goals'] == 128
    assert analyze(rows[:-4], training, bootstrap=20)['status'] == 'INVALID'
