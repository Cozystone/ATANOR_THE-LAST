"""D4 arithmetic only: paired life-cluster estimates, not native attestation.

The fixed protocol has 64 independent lives, four arms and four successive
goals per life. Only the last two goals enter target performance; all four goals
and one initial training cost enter CPU. Configurable counts/draws support unit
tests, not post-result protocol changes. A single checkpoint and known mechanics
do not establish AGI, new mechanics, multi-seed robustness or calibrated beliefs.

These estimates are conditional on the input costs and outcomes. The caller must
independently bind native replay, model/data/source identities and frozen-arm
integrity before accepting any computed verdict. Unused receipt metadata does
not authenticate this arithmetic.
"""
from __future__ import annotations

import math

import numpy as np


ARMS = ('relational', 'full_context', 'retrieval', 'frozen')


def _number(value, label, *, positive=False):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or (value <= 0 if positive else value < 0)):
        raise ValueError('invalid ' + label)
    return float(value)


def _validate(rows, trainingcosts, expected_lives):
    if type(expected_lives) is not int or expected_lives < 1:
        raise ValueError('expected_lives must be a positive integer')
    if type(rows) is not list or len(rows) != expected_lives * len(ARMS):
        raise ValueError('exactly one row per life and arm is required')
    if type(trainingcosts) is not dict or set(trainingcosts) != set(ARMS):
        raise ValueError('exact training-cost arms are required')
    training = np.array([_number(trainingcosts[a], a + ' training CPU') for a in ARMS])
    successes = np.zeros((expected_lives, len(ARMS), 4), dtype=np.int64)
    actual = np.zeros_like(successes)
    charged = np.zeros_like(successes)
    cpu = np.zeros((expected_lives, len(ARMS)), dtype=np.float64)
    seen = set()
    for row in rows:
        if type(row) is not dict:
            raise ValueError('life result must be a mapping')
        life, arm = row.get('life'), row.get('arm')
        if type(life) is not int or not 0 <= life < expected_lives or type(arm) is not str or arm not in ARMS:
            raise ValueError('invalid life/arm identity')
        if (life, arm) in seen:
            raise ValueError('duplicate life/arm')
        seen.add((life, arm))
        column = ARMS.index(arm)
        cpu[life, column] = _number(row.get('cpu_seconds'), 'whole-life CPU', positive=True)
        episodes = row.get('episodes')
        if type(episodes) is not list or len(episodes) != 4:
            raise ValueError('exactly four goals per life/arm are required')
        indexes = set()
        for episode in episodes:
            if type(episode) is not dict:
                raise ValueError('goal result must be a mapping')
            index = episode.get('index')
            if type(index) is not int or not 0 <= index < 4 or index in indexes:
                raise ValueError('invalid/duplicate goal index')
            indexes.add(index)
            if episode.get('phase') != ('learning' if index < 2 else 'evaluation'):
                raise ValueError('goal phase/index mismatch')
            result = episode.get('result')
            if type(result) is not dict or type(result.get('completed')) is not bool:
                raise ValueError('completion must be a strict Boolean')
            steps, cost = result.get('steps'), episode.get('charged_steps')
            if type(steps) is not int or not 0 <= steps <= 8 or type(cost) is not int:
                raise ValueError('invalid actual/charged steps')
            if cost != (steps if result['completed'] else 8):
                raise ValueError('failure must cost eight, success must cost actual steps')
            if 'cpu_seconds' in episode:
                _number(episode['cpu_seconds'], 'goal CPU')
            successes[life, column, index] = int(result['completed'])
            actual[life, column, index] = steps
            charged[life, column, index] = cost
    if seen != {(life, arm) for life in range(expected_lives) for arm in ARMS}:
        raise ValueError('missing life/arm')
    return successes, actual, charged, cpu, training


def _ratio(numerator, denominator, label):
    numerator, denominator = np.asarray(numerator), np.asarray(denominator)
    if not np.all(np.isfinite(numerator)) or not np.all(np.isfinite(denominator)):
        raise ValueError('nonfinite aggregate: ' + label)
    if np.any(denominator <= 0):
        raise ValueError('zero cost denominator: ' + label)
    result = numerator / denominator
    if not np.all(np.isfinite(result)):
        raise ValueError('nonfinite ratio: ' + label)
    return result


def _bound(samples, quantile):
    result = float(np.quantile(samples, quantile, method='linear'))
    if not math.isfinite(result):
        raise ValueError('nonfinite bootstrap bound')
    return result


def analyze(rows, trainingcosts, *, seed=91377, bootstrap=4000, expected_lives=64):
    """Return a JSON-compatible arithmetic verdict; malformed input => INVALID.

    ``rows`` uses experiment.run_life's result shape. ``trainingcosts`` maps
    each arm to its one-time total preprocessing/fit CPU, including the declared
    common-cost allocation. Training is added ONCE to every bootstrap replicate,
    not multiplied by the number or multiplicity of sampled life clusters.

    One primary comparator is registered: full_context. Retrieval is descriptive
    secondary; it cannot replace a disappointing primary comparator post hoc.
    Online contribution is separately frozen-minus-online target charged cost
    LCB > 0 AND online-minus-frozen success LCB >= -0.05.
    """
    try:
        if type(seed) is not int or seed < 0:
            raise ValueError('seed must be a nonnegative integer')
        if type(bootstrap) is not int or bootstrap < 1:
            raise ValueError('bootstrap must be a positive integer')
        successes, actual, charged, cpu, training = _validate(rows, trainingcosts, expected_lives)
        target_success = successes[:, :, 2:].sum(axis=2)
        target_cost = charged[:, :, 2:].sum(axis=2)
        success_rate = target_success.mean(axis=0) / 2
        cost_total = target_cost.sum(axis=0)
        total_cpu = cpu.sum(axis=0) + training
        if not np.all(np.isfinite(total_cpu)):
            raise ValueError('nonfinite total CPU')

        rng = np.random.Generator(np.random.PCG64(seed))
        sampled = rng.integers(0, expected_lives, size=(bootstrap, expected_lives))
        boot_success = target_success[sampled].mean(axis=1) / 2
        boot_cost = target_cost[sampled].sum(axis=1)
        boot_cpu = cpu[sampled].sum(axis=1) + training[None, :]
        comparisons = {}
        for arm in ('full_context', 'retrieval'):
            j = ARMS.index(arm)
            comparisons[arm] = {
                'success_difference': float(success_rate[0] - success_rate[j]),
                'success_difference_lcb05': _bound(boot_success[:, 0] - boot_success[:, j], .05),
                'charged_ratio': float(_ratio(cost_total[0], cost_total[j], arm + ' point actions')),
                'charged_ratio_ucb95': _bound(_ratio(boot_cost[:, 0], boot_cost[:, j], arm + ' bootstrap actions'), .95),
                'total_cpu_ratio': float(_ratio(total_cpu[0], total_cpu[j], arm + ' point CPU')),
                'total_cpu_ratio_ucb95': _bound(_ratio(boot_cpu[:, 0], boot_cpu[:, j], arm + ' bootstrap CPU'), .95),
            }
        online = {
            'success_difference': float(success_rate[0] - success_rate[3]),
            'success_difference_lcb05': _bound(boot_success[:, 0] - boot_success[:, 3], .05),
            'frozen_minus_online_charged_per_goal': float((cost_total[3] - cost_total[0]) / (2 * expected_lives)),
            'frozen_minus_online_charged_per_goal_lcb05': _bound(
                (boot_cost[:, 3] - boot_cost[:, 0]) / (2 * expected_lives), .05),
        }
        online['confirmed'] = (online['success_difference_lcb05'] >= -.05
            and online['frozen_minus_online_charged_per_goal_lcb05'] > 0)
        primary = comparisons['full_context']
        gates = {
            'strong_baseline_success_at_least_50pct': bool(success_rate[1] >= .50),
            'target_success_at_least_75pct': bool(success_rate[0] >= .75),
            'success_difference_lcb_at_least_minus_5pp': primary['success_difference_lcb05'] >= -.05,
            'charged_ratio_point_at_most_080': primary['charged_ratio'] <= .80,
            'charged_ratio_ucb_at_most_090': primary['charged_ratio_ucb95'] <= .90,
            'cpu_ratio_point_at_most_100': primary['total_cpu_ratio'] <= 1.,
            'cpu_ratio_ucb_at_most_110': primary['total_cpu_ratio_ucb95'] <= 1.10,
        }
        utility = all(gates.values())
        status = ('CAPABILITY_GATE_GREEN' if online['confirmed'] else 'PARTIAL_NO_ONLINE_LIFT') if utility else 'NO_GO'
        totals = {}
        for j, arm in enumerate(ARMS):
            totals[arm] = {}
            for name, indexes in (('all', slice(0, 4)), ('learning', slice(0, 2)), ('evaluation', slice(2, 4))):
                observed = successes[:, j, indexes]
                totals[arm][name] = {
                    'goals': int(observed.size), 'successes': int(observed.sum()),
                    'success_rate': float(observed.mean()),
                    'actual_steps': int(actual[:, j, indexes].sum()),
                    'charged_steps': int(charged[:, j, indexes].sum()),
                }
            totals[arm].update(life_cpu_seconds=float(cpu[:, j].sum()),
                               training_cpu_seconds=float(training[j]), total_cpu_seconds=float(total_cpu[j]))
        return {'status': status, 'errors': [], 'integrated_utility': utility,
            'primary_comparator': 'full_context', 'gates': gates, 'raw_totals': totals,
            'comparisons': comparisons, 'online_contribution': online,
            'method': {'life_clusters': expected_lives, 'goals_per_life': 4, 'evaluation_goal_indexes': [2, 3],
                       'seed': seed, 'bootstrap': bootstrap, 'rng': 'PCG64', 'quantile': 'linear',
                       'training_cost': 'one fixed per-arm additive cost in point and every replicate'},
            'scope': 'Arithmetic only; native/source/checkpoint hard gates must independently pass. Known mechanics, one checkpoint.'}
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return {'status': 'INVALID', 'errors': [str(exc) or type(exc).__name__],
                'integrated_utility': False, 'scope': 'No native evidence or capability is authenticated by this module.'}
