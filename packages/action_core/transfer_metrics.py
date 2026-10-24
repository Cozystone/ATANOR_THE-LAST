"""Fixed paired-case arithmetic for the one native-new-effect decision run.

Sampling units are task configurations, not steps or correlated bootstrap draws.
These intervals do not establish independent external judging or generic transfer.
"""
import math
import numpy as np

ARMS = ('warm', 'retrieval', 'cold_memory', 'warm_frozen')
FIELDS = {'case', 'arm', 'success', 'charged_steps', 'cpu_seconds'}


def summarize(rows, *, expected_cases=64, seed=58319, draws=4000):
    if (type(expected_cases) is not int or expected_cases < 1 or type(seed) is not int or seed < 0 or
            type(draws) is not int or draws < 1 or type(rows) is not list):
        raise ValueError('invalid paired bootstrap configuration')
    grouped = {}
    for row in rows:
        if type(row) is not dict or set(row) != FIELDS:
            raise ValueError('exact measurement fields required')
        if (type(row['case']) is not int or not 0 <= row['case'] < expected_cases or
                type(row['arm']) is not str or row['arm'] not in ARMS or
                type(row['success']) is not bool or type(row['charged_steps']) is not int or
                not 1 <= row['charged_steps'] <= 8 or
                (not row['success'] and row['charged_steps'] != 8)):
            raise ValueError('invalid case/arm/success/charged-action record')
        if (type(row['cpu_seconds']) not in (int, float) or
                not math.isfinite(row['cpu_seconds']) or row['cpu_seconds'] <= 0):
            raise ValueError('positive finite CPU measurement required')
        group = grouped.setdefault(row['case'], {})
        if row['arm'] in group:
            raise ValueError('duplicate case/arm')
        group[row['arm']] = row
    if (set(grouped) != set(range(expected_cases)) or
            any(set(group) != set(ARMS) for group in grouped.values())):
        raise ValueError('all expected four-arm pairs required')
    data = np.asarray([[[grouped[c][a]['success'], grouped[c][a]['charged_steps'],
                         grouped[c][a]['cpu_seconds']] for a in ARMS]
                       for c in range(expected_cases)], dtype=float)
    totals = {arm: {'cases': expected_cases, 'successes': int(data[:, i, 0].sum()),
                    'charged_steps': int(data[:, i, 1].sum()),
                    'cpu_seconds': math.fsum(data[:, i, 2])} for i, arm in enumerate(ARMS)}
    if not all(math.isfinite(v['cpu_seconds']) for v in totals.values()):
        raise ValueError('nonfinite CPU aggregate')
    indices = np.random.default_rng(seed).integers(0, expected_cases, size=(draws, expected_cases))
    sampled = data[indices].sum(axis=1)
    comparisons, gates = {}, {}
    for i, other in enumerate(ARMS[1:], 1):
        differences = data[:, 0, 0] - data[:, i, 0]
        result = {'success_difference': float(differences.mean()),
                  'success_difference_lcb05': float(np.quantile(differences[indices].mean(axis=1), .05))}
        for name, col, total_key in [('action', 1, 'charged_steps'), ('cpu', 2, 'cpu_seconds')]:
            result[name + '_ratio'] = totals['warm'][total_key] / totals[other][total_key]
            result[name + '_ratio_ucb95'] = float(np.quantile(sampled[:, 0, col] / sampled[:, i, col], .95))
        comparisons[other] = result
        gates[other + '_success_noninferiority'] = result['success_difference_lcb05'] >= -.05
        if other != 'warm_frozen':
            gates[other + '_action_20pct_point_10pct_bound'] = (
                result['action_ratio'] <= .80 and result['action_ratio_ucb95'] < .90)
            gates[other + '_target_cpu'] = result['cpu_ratio_ucb95'] <= 1.25
        else:
            gates['online_weight_revision_beyond_old_knowledge'] = (
                (result['success_difference'] >= .05 and result['success_difference_lcb05'] > 0) or
                (result['action_ratio'] <= .90 and result['action_ratio_ucb95'] < 1.0))
    if not all(math.isfinite(v) for row in comparisons.values() for v in row.values()):
        raise ValueError('nonfinite final statistic')
    regression = any(comparisons[a]['success_difference'] < -.05 or
                     comparisons[a]['action_ratio'] > 1.10 or comparisons[a]['cpu_ratio'] > 1.25
                     for a in ('retrieval', 'cold_memory'))
    verdict = ('ADAPTATION_LIFT_CONFIRMED' if all(gates.values()) else
               'REGRESSION' if regression else 'NO_ADAPTATION_LIFT')
    return {'verdict': verdict, 'cases': expected_cases, 'seed': seed, 'draws': draws,
            'bootstrap': 'paired case percentile, ratio of totals, linear quantile',
            'totals': totals, 'comparisons': comparisons, 'gates': gates}
