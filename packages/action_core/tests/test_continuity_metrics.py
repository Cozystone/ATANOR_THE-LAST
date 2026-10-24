"""Synthetic arithmetic and strict-input tests; no capability experiments."""
import copy
import json
import unittest

import numpy as np

from packages.action_core.continuity_metrics import summarize


def fixture():
    rows = [{'life': life, 'arm': arm, 'index': index, 'success': True, 'charged_steps': 1}
            for life in range(16) for arm in ('carry', 'reset') for index in range(8)]
    cpu = [{'life': life, 'arm': arm, 'cpu_seconds': 10.}
           for life in range(16) for arm in ('carry', 'reset')]
    return rows, cpu


class ContinuityMetricsTests(unittest.TestCase):
    def test_known_identical_counts_and_no_lift(self):
        result = summarize(*fixture())
        self.assertEqual(result['verdict'], 'NO_LIFT')
        self.assertEqual(result['points'], {'target_success_delta': 0., 'target_action_ratio': 1., 'total_cpu_ratio': 1.})
        self.assertEqual(result['bounds'], {'target_success_delta_lcb05': 0., 'target_action_ratio_ucb95': 1., 'total_cpu_ratio_ucb95': 1.})
        for arm in ('carry', 'reset'):
            self.assertEqual(result['totals'][arm]['all'], {'episodes': 128, 'successes': 128, 'charged_steps': 128})
            self.assertEqual(result['totals'][arm]['first_half']['episodes'], 64)
            self.assertEqual(result['totals'][arm]['target']['episodes'], 64)
            self.assertEqual(result['totals'][arm]['cpu_seconds'], 160.)

    def test_clear_lift_uses_latter_half_despite_opposite_first_half(self):
        rows, cpu = fixture()
        for row in rows:
            if row['arm'] == 'reset' and row['index'] == 7:
                row.update(success=False, charged_steps=8)
            if row['arm'] == 'carry' and row['index'] < 4:
                row.update(success=False, charged_steps=8)
        result = summarize(rows, cpu)
        self.assertEqual(result['verdict'], 'CONTINUITY_LIFT')
        self.assertEqual(result['points']['target_success_delta'], .25)
        self.assertEqual(result['bounds']['target_success_delta_lcb05'], .25)
        self.assertEqual(result['totals']['carry']['first_half']['successes'], 0)
        self.assertEqual(result['totals']['carry']['target']['successes'], 64)
        self.assertAlmostEqual(result['points']['target_action_ratio'], 4/11)

    def test_first_half_only_improvement_does_not_establish_target_lift(self):
        rows, cpu = fixture()
        for row in rows:
            if row['arm'] == 'reset' and row['index'] < 4:
                row['success'] = False
        self.assertEqual(summarize(rows, cpu)['verdict'], 'NO_LIFT')

    def test_point_gain_alone_cannot_pass_zero_lower_bound(self):
        rows, cpu = fixture()
        for row in rows:
            if row['index'] >= 4:
                row['success'] = row['arm'] == 'carry' and row['life'] == 0
        result = summarize(rows, cpu)
        self.assertEqual(result['points']['target_success_delta'], 1/16)
        self.assertEqual(result['bounds']['target_success_delta_lcb05'], 0.)
        self.assertEqual(result['verdict'], 'NO_LIFT')

    def test_bootstrap_samples_lives_not_individual_correlated_episodes(self):
        rows, cpu = fixture()
        for row in rows:
            if row['index'] >= 4:
                row['success'] = row['arm'] == 'carry' and row['life'] < 8
        result = summarize(rows, cpu, seed=17, draws=137)
        sampled_lives = np.random.default_rng(17).integers(0, 16, size=(137, 16))
        expected = float(np.quantile((sampled_lives < 8).mean(axis=1), .05, method='linear'))
        self.assertEqual(result['bounds']['target_success_delta_lcb05'], expected)
        self.assertEqual(result['points']['target_success_delta'], .5)
        shuffled = copy.deepcopy(rows)
        shuffled.reverse()
        self.assertEqual(summarize(shuffled, list(reversed(cpu)), seed=17, draws=137), result)

    def test_each_point_regression_condition(self):
        for condition in ('success', 'actions', 'cpu'):
            with self.subTest(condition=condition):
                rows, cpu = fixture()
                for row in rows:
                    if row['arm'] == 'carry' and row['index'] >= 4:
                        if condition == 'success' and row['index'] == 7:
                            row['success'] = False
                        elif condition == 'actions':
                            row['charged_steps'] = 2
                if condition == 'cpu':
                    for row in cpu:
                        if row['arm'] == 'carry':
                            row['cpu_seconds'] = 16.
                self.assertEqual(summarize(rows, cpu)['verdict'], 'REGRESSION')

    def test_regression_thresholds_are_strict(self):
        rows, cpu = fixture()
        for row in rows:
            if row['arm'] == 'carry' and row['index'] == 7:
                row['charged_steps'] = 2  # total ratio exactly 5/4, not above.
        for row in cpu:
            if row['arm'] == 'carry':
                row['cpu_seconds'] = 15.  # exactly 1.50, not above.
        result = summarize(rows, cpu)
        self.assertEqual(result['verdict'], 'NO_LIFT')
        self.assertFalse(any(result['regression_gates'].values()))

    def test_duplicate_missing_and_extra_observations_rejected(self):
        rows, cpu = fixture()
        for bad_rows, bad_cpu in ((rows[:-1], cpu), (rows + [rows[0]], cpu),
                                  (rows, cpu[:-1]), (rows, cpu + [cpu[0]])):
            with self.subTest(counts=(len(bad_rows), len(bad_cpu))), self.assertRaises(ValueError):
                summarize(bad_rows, bad_cpu)

    def test_counterfeit_types_fields_and_nonfinite_costs_rejected(self):
        replacements = [('success', 1), ('life', True), ('life', 16), ('index', True),
                        ('index', 8), ('charged_steps', True), ('charged_steps', 0),
                        ('charged_steps', 9), ('charged_steps', 1.), ('arm', 'frozen'), ('verified', True)]
        for key, value in replacements:
            rows, cpu = fixture()
            rows[0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                summarize(rows, cpu)
        for value in (True, -.1, '10', None, float('nan'), float('inf')):
            rows, cpu = fixture()
            cpu[0]['cpu_seconds'] = value
            with self.subTest(cpu=value), self.assertRaises(ValueError):
                summarize(rows, cpu)
        for key, value in (('seed', True), ('seed', -1), ('draws', 0), ('draws', 1.5)):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                summarize(*fixture(), **{key: value})

    def test_zero_timer_samples_are_allowed_but_unidentifiable_ratio_is_not(self):
        rows, cpu = fixture()
        cpu[0]['cpu_seconds'] = 0.
        self.assertEqual(summarize(rows, cpu)['points']['total_cpu_ratio'], 15/16)
        for row in cpu:
            if row['arm'] == 'reset':
                row['cpu_seconds'] = 0.
        with self.assertRaises(ValueError):
            summarize(rows, cpu)

    def test_bootstrap_zero_denominator_is_json_safe_and_cannot_pass_lift(self):
        rows, cpu = fixture()
        for row in cpu:
            if row['arm'] == 'reset':
                row['cpu_seconds'] = 1. if row['life'] == 0 else 0.
        result = summarize(rows, cpu)
        self.assertEqual(result['cpu_upper_bound_status'], 'UNBOUNDED')
        self.assertIsNone(result['bounds']['total_cpu_ratio_ucb95'])
        self.assertFalse(result['lift_gates']['total_cpu_ratio_ucb_at_most_1_25'])
        self.assertGreater(result['cpu_bootstrap_zero_denominator_samples'], 0)
        json.dumps(result, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
