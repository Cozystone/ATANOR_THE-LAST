"""Fixed paired life-sequence bootstrap for narrow carry-versus-reset evidence.

The 64 latter-half episodes per arm are not 64 independent learning runs: there
are 16 clusters, one checkpoint, and known mechanics. All eight episodes and
their CPU costs remain paired inside each sampled life sequence. Percentile
bootstrap with 16 clusters has limited precision and no population guarantee.
These counts do not authenticate native observations, freshness, or timing; the
separately fixed supervisor protocol must establish those properties.
"""
from __future__ import annotations

import math
import numpy as np


ARMS = ('carry', 'reset')
ROW_FIELDS = {'life', 'arm', 'index', 'success', 'charged_steps'}
CPU_FIELDS = {'life', 'arm', 'cpu_seconds'}


def _identity(row):
    if (type(row['life']) is not int or not 0 <= row['life'] < 16 or
            type(row['arm']) is not str or row['arm'] not in ARMS):
        raise ValueError('life must be an integer in 0..15 and arm carry/reset')
    return row['life'], row['arm']


def summarize(rows, life_summaries, *, seed=771031, draws=4000):
    """Require exactly 16 paired lives, eight episodes per arm, plus total CPU.

    Individual CPU observations may be zero at timer resolution. Reset total
    CPU must be positive for a point ratio. A bootstrap zero denominator is
    treated conservatively as unbounded, never 0/0=1. If the upper percentile
    is unbounded it is represented as null plus cpu_upper_bound_status, which
    fails the lift gate rather than emitting invalid JSON infinity.
    """
    if (type(rows) not in (list, tuple) or type(life_summaries) not in (list, tuple) or
            type(seed) is not int or seed < 0 or type(draws) is not int or draws < 1):
        raise ValueError('rows/summaries, nonnegative integer seed and positive draws required')
    episodes, cpu = {}, {}
    for row in rows:
        if type(row) is not dict or set(row) != ROW_FIELDS:
            raise ValueError('episode row must exactly match the schema')
        pair = _identity(row)
        if type(row['index']) is not int or not 0 <= row['index'] < 8:
            raise ValueError('episode index must be an integer in 0..7')
        if type(row['success']) is not bool:
            raise ValueError('success must be a strict boolean')
        if type(row['charged_steps']) is not int or not 1 <= row['charged_steps'] <= 8:
            raise ValueError('charged steps must be an integer in 1..8')
        key = (*pair, row['index'])
        if key in episodes:
            raise ValueError('duplicate life/arm/episode')
        episodes[key] = row
    for row in life_summaries:
        if type(row) is not dict or set(row) != CPU_FIELDS:
            raise ValueError('life CPU summary must exactly match the schema')
        pair = _identity(row)
        value = row['cpu_seconds']
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('life CPU must be finite and nonnegative')
        if pair in cpu:
            raise ValueError('duplicate life/arm CPU summary')
        cpu[pair] = float(value)
    expected_pairs = {(life, arm) for life in range(16) for arm in ARMS}
    expected_rows = {(*pair, index) for pair in expected_pairs for index in range(8)}
    if set(episodes) != expected_rows or set(cpu) != expected_pairs:
        raise ValueError('all 16 paired lives, eight episodes each, and CPU summaries are required')

    totals = {}
    for arm in ARMS:
        totals[arm] = {}
        for label, indices in (('all', range(8)), ('first_half', range(4)), ('target', range(4, 8))):
            selected = [episodes[life, arm, index] for life in range(16) for index in indices]
            totals[arm][label] = {'episodes': len(selected),
                'successes': sum(row['success'] for row in selected),
                'charged_steps': sum(row['charged_steps'] for row in selected)}
        try:
            totals[arm]['cpu_seconds'] = math.fsum(cpu[life, arm] for life in range(16))
        except OverflowError as error:
            raise ValueError('CPU total exceeds finite range') from error
    if totals['reset']['cpu_seconds'] <= 0:
        raise ValueError('zero reset total CPU: ratio is not identifiable')
    points = {
        'target_success_delta': (totals['carry']['target']['successes'] - totals['reset']['target']['successes']) / 64,
        'target_action_ratio': totals['carry']['target']['charged_steps'] / totals['reset']['target']['charged_steps'],
        'total_cpu_ratio': totals['carry']['cpu_seconds'] / totals['reset']['cpu_seconds'],
    }
    # Data hold per-life latter-half totals and whole-life CPU, not per-episode
    # pseudo-independent samples. All metrics and both arms reuse these indices.
    data = np.asarray([[[sum(episodes[life, arm, i]['success'] for i in range(4, 8)),
                          sum(episodes[life, arm, i]['charged_steps'] for i in range(4, 8)),
                          cpu[life, arm]] for arm in ARMS] for life in range(16)], dtype=float)
    indices = np.random.default_rng(seed).integers(0, 16, size=(draws, 16))
    delta_samples = ((data[:, 0, 0] - data[:, 1, 0]) / 4)[indices].mean(axis=1)
    # CPU scaling is common to both arms, so it leaves ratios unchanged while
    # avoiding overflow when an otherwise valid resample repeats a large value.
    data[:, :, 2] /= max(cpu.values())
    sampled = data[indices].sum(axis=1)
    action_ratios = sampled[:, 0, 1] / sampled[:, 1, 1]
    zero_denominator = sampled[:, 1, 2] == 0
    cpu_ratios = np.full(draws, np.inf)
    np.divide(sampled[:, 0, 2], sampled[:, 1, 2], out=cpu_ratios, where=~zero_denominator)
    ordered_cpu = np.sort(cpu_ratios)
    position = .95 * (draws - 1)
    hi = math.ceil(position)
    # NumPy interpolation of inf-inf produces NaN. The extended upper bound is
    # unbounded whenever either contributing positive-weight endpoint is inf.
    upper_unbounded = not math.isfinite(float(ordered_cpu[hi]))
    cpu_upper = None if upper_unbounded else float(np.quantile(cpu_ratios, .95, method='linear'))
    bounds = {
        'target_success_delta_lcb05': float(np.quantile(delta_samples, .05, method='linear')),
        'target_action_ratio_ucb95': float(np.quantile(action_ratios, .95, method='linear')),
        'total_cpu_ratio_ucb95': cpu_upper,
    }
    if not all(math.isfinite(value) for value in (*points.values(), *(v for v in bounds.values() if v is not None))):
        raise ValueError('nonfinite aggregate metric')
    lift_gates = {
        'target_success_delta_at_least_0_05': points['target_success_delta'] >= .05,
        'target_success_lcb_positive': bounds['target_success_delta_lcb05'] > 0,
        'target_action_ratio_ucb_at_most_1_10': bounds['target_action_ratio_ucb95'] <= 1.10,
        'total_cpu_ratio_ucb_at_most_1_25': cpu_upper is not None and cpu_upper <= 1.25,
    }
    regression_gates = {
        'target_success_delta_below_minus_0_05': points['target_success_delta'] < -.05,
        'target_action_ratio_above_1_25': points['target_action_ratio'] > 1.25,
        'total_cpu_ratio_above_1_50': points['total_cpu_ratio'] > 1.50,
    }
    verdict = 'REGRESSION' if any(regression_gates.values()) else 'CONTINUITY_LIFT' if all(lift_gates.values()) else 'NO_LIFT'
    return {'life_sequences': 16, 'episodes_per_life': 8, 'target_indices': [4, 5, 6, 7],
        'seed': seed, 'draws': draws, 'bootstrap': 'paired life-cluster percentile; linear quantile; LCB=.05/UCB=.95',
        'totals': totals, 'points': points, 'bounds': bounds, 'lift_gates': lift_gates,
        'regression_gates': regression_gates, 'verdict': verdict,
        'cpu_bootstrap_zero_denominator_samples': int(zero_denominator.sum()),
        'cpu_upper_bound_status': 'UNBOUNDED' if upper_unbounded else 'FINITE',
        'limitations': ['16 life clusters, not 64 independent target learning runs',
                        'known mechanics and one starting checkpoint',
                        'metrics do not authenticate freshness, actual observations or CPU measurement']}
