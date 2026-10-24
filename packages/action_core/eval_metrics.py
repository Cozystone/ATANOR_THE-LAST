"""Fixed paired-case bootstrap for narrow local utility, never an AGI verdict.

Cases are the sampling clusters: all four arms share each sampled case index.
Percentile limits use NumPy's linear quantile interpolation, not a population
guarantee. Finite cases, bootstrap Monte Carlo error, reused DEV cases, correlated
generator families, or adaptive tuning can limit inference. This arithmetic does
not certify fresh data, genuine observations, external judging, or causal
attribution. Those requirements belong to the separately fixed run protocol.
"""
from __future__ import annotations

import math
import numpy as np


ARMS = ('neural', 'retrieval', 'cold', 'frozen')
FIELDS = {'case', 'arm', 'success', 'charged_steps', 'cpu_seconds'}


def summarize(rows, *, seed=44113, draws=4000):
    """Require complete four-arm pairs; never drop missing or invalid observations."""
    if (type(seed) is not int or seed < 0 or type(draws) is not int or draws < 1 or
            type(rows) not in (list, tuple) or not rows):
        raise ValueError('nonempty rows, nonnegative integer seed and positive integer draws required')
    grouped = {}
    for row in rows:
        if type(row) is not dict or set(row) != FIELDS:
            raise ValueError('row fields must exactly match the measurement schema')
        if type(row['case']) is not int or type(row['arm']) is not str or row['arm'] not in ARMS:
            raise ValueError('invalid case or arm')
        if type(row['success']) is not bool:
            raise ValueError('success must be a boolean, not a score or caller status')
        if type(row['charged_steps']) is not int or not 1 <= row['charged_steps'] <= 8:
            raise ValueError('charged steps must be an integer in 1..8')
        cpu = row['cpu_seconds']
        if type(cpu) not in (int, float) or not math.isfinite(cpu) or cpu <= 0:
            raise ValueError('CPU seconds must be finite and positive')
        arms = grouped.setdefault(row['case'], {})
        if row['arm'] in arms:
            raise ValueError('duplicate case/arm')
        arms[row['arm']] = row
    if any(set(arms) != set(ARMS) for arms in grouped.values()):
        raise ValueError('every case must contain exactly one row for all four arms')
    cases = sorted(grouped)
    n = len(cases)
    data = np.asarray([[[grouped[c][a]['success'], grouped[c][a]['charged_steps'],
                         grouped[c][a]['cpu_seconds']] for a in ARMS] for c in cases], dtype=float)
    totals = {}
    for index, arm in enumerate(ARMS):
        try:
            cpu_total = math.fsum(data[:, index, 2])
        except OverflowError as error:
            raise ValueError('CPU aggregate exceeds finite numeric range') from error
        totals[arm] = {'cases': n, 'successes': int(data[:, index, 0].sum()),
                       'charged_steps': int(data[:, index, 1].sum()), 'cpu_seconds': cpu_total}
    means = data.mean(axis=0)
    points = {'neural_success_rate': float(means[0, 0])}
    for index, other in enumerate(ARMS[1:], 1):
        points[f'success_diff_neural_{other}'] = float((data[:, 0, 0] - data[:, index, 0]).mean())
    points['cpu_ratio_neural_retrieval'] = totals['neural']['cpu_seconds'] / totals['retrieval']['cpu_seconds']
    points['action_ratio_neural_retrieval'] = totals['neural']['charged_steps'] / totals['retrieval']['charged_steps']
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, n, size=(draws, n))
    sampled = data[indices].mean(axis=1)  # Same indices for every arm and every metric.
    bounds = {}
    for index, other in enumerate(ARMS[1:], 1):
        # Difference per pair first avoids cancellation around exact gate values
        # such as 19/20 - 20/20, without introducing a post-hoc tolerance.
        differences = (data[:, 0, 0] - data[:, index, 0])[indices].mean(axis=1)
        bounds[f'success_diff_neural_{other}_lcb05'] = float(np.quantile(differences, .05, method='linear'))
    for field, column in (('cpu', 2), ('action', 1)):
        ratios = sampled[:, 0, column] / sampled[:, 1, column]
        bounds[f'{field}_ratio_neural_retrieval_ucb95'] = float(np.quantile(ratios, .95, method='linear'))
    if not all(math.isfinite(x) for x in (*points.values(), *bounds.values())):
        raise ValueError('nonfinite aggregate metric')
    gates = {
        'neural_success_rate_at_least_0_80': points['neural_success_rate'] >= .80,
        'retrieval_success_lcb_at_least_minus_0_05': bounds['success_diff_neural_retrieval_lcb05'] >= -.05,
        'cold_success_lcb_at_least_0_20': bounds['success_diff_neural_cold_lcb05'] >= .20,
        'cpu_ratio_ucb_at_most_0_50': bounds['cpu_ratio_neural_retrieval_ucb95'] <= .50,
        'action_ratio_ucb_at_most_1_25': bounds['action_ratio_neural_retrieval_ucb95'] <= 1.25,
    }
    return {'cases': n, 'case_ids': cases, 'seed': seed, 'draws': draws,
            'bootstrap': 'paired case percentile; linear quantile; LCB=.05/UCB=.95',
            'totals': totals, 'points': points, 'bounds': bounds, 'primary_gates': gates,
            'verdict': 'LOCAL_UTILITY_CONFIRMED' if all(gates.values()) else 'NOT_CONFIRMED',
            'online_revision_support': bounds['success_diff_neural_frozen_lcb05'] > 0.}
