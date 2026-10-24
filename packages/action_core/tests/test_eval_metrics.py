import copy
import unittest

import numpy as np

from packages.action_core.eval_metrics import ARMS, summarize


def rows_for(n=12, *, identical=False, neural_cpu=.1, frozen_success=False):
    rows = []
    for case in range(n):
        for arm in ARMS:
            success = True if identical or arm in ('neural', 'retrieval') else frozen_success if arm == 'frozen' else False
            cpu = 1. if identical or arm != 'neural' else neural_cpu
            rows.append({'case': case, 'arm': arm, 'success': success,
                         'charged_steps': 2 if identical else 1 if arm == 'neural' else 2,
                         'cpu_seconds': cpu})
    return rows


class MetricsTests(unittest.TestCase):
    def test_identical_arms_have_exact_zero_differences_and_unit_ratios(self):
        result = summarize(rows_for(identical=True))
        self.assertEqual(result['cases'], 12)
        for other in ARMS[1:]:
            self.assertEqual(result['bounds'][f'success_diff_neural_{other}_lcb05'], 0.)
        self.assertEqual(result['bounds']['cpu_ratio_neural_retrieval_ucb95'], 1.)
        self.assertEqual(result['bounds']['action_ratio_neural_retrieval_ucb95'], 1.)
        self.assertEqual(result['verdict'], 'NOT_CONFIRMED')
        self.assertFalse(result['online_revision_support'])

    def test_clear_positive_satisfies_every_fixed_primary_gate(self):
        result = summarize(rows_for())
        self.assertEqual(result['verdict'], 'LOCAL_UTILITY_CONFIRMED')
        self.assertTrue(all(result['primary_gates'].values()))
        self.assertTrue(result['online_revision_support'])
        self.assertEqual(result['totals']['neural']['successes'], 12)
        self.assertEqual(result['totals']['neural']['charged_steps'], 12)
        self.assertAlmostEqual(result['points']['cpu_ratio_neural_retrieval'], .1)
        self.assertEqual(result['bounds']['success_diff_neural_cold_lcb05'], 1.)

    def test_cpu_regression_blocks_primary_but_frozen_test_is_separate(self):
        result = summarize(rows_for(neural_cpu=.8))
        self.assertEqual(result['verdict'], 'NOT_CONFIRMED')
        self.assertFalse(result['primary_gates']['cpu_ratio_ucb_at_most_0_50'])
        result = summarize(rows_for(frozen_success=True))
        self.assertEqual(result['verdict'], 'LOCAL_UTILITY_CONFIRMED')
        self.assertFalse(result['online_revision_support'])

    def test_bootstrap_pairing_ratio_of_totals_and_row_order_invariance(self):
        rows = rows_for(5)
        for row in rows:
            case = row['case']
            row['success'] = case % 2 == 0  # Shared heterogeneity: paired differences stay zero.
            row['cpu_seconds'] = (case + 1) if row['arm'] == 'neural' else (case + 1) ** 2
        result = summarize(rows, seed=23, draws=81)
        self.assertEqual(result, summarize(list(reversed(rows)), seed=23, draws=81))
        self.assertEqual(result['bounds']['success_diff_neural_retrieval_lcb05'], 0.)
        self.assertAlmostEqual(result['points']['cpu_ratio_neural_retrieval'], 15 / 55)
        indices = np.random.default_rng(23).integers(0, 5, size=(81, 5))
        cpu_n = np.arange(1., 6.)
        cpu_r = cpu_n ** 2
        expected = np.quantile(cpu_n[indices].mean(1) / cpu_r[indices].mean(1), .95, method='linear')
        self.assertEqual(result['bounds']['cpu_ratio_neural_retrieval_ucb95'], expected)

    def test_missing_duplicate_unknown_and_extra_rows_rejected(self):
        rows = rows_for()
        for invalid in (rows[:-1], rows + [rows[0]], []):
            with self.assertRaises(ValueError):
                summarize(invalid)

    def test_success_difference_uses_paired_counts_without_boundary_cancellation(self):
        rows = rows_for(20, identical=True)
        rows[0]['success'] = False
        result = summarize(rows, seed=41, draws=73)
        self.assertEqual(result['points']['success_diff_neural_retrieval'], -.05)
        delta = np.array([-1.] + [0.] * 19)
        indices = np.random.default_rng(41).integers(0, 20, size=(73, 20))
        expected = np.quantile(delta[indices].mean(axis=1), .05, method='linear')
        self.assertEqual(result['bounds']['success_diff_neural_retrieval_lcb05'], expected)
        for key, value in [('arm', 'other'), ('success', 1), ('case', True),
                           ('charged_steps', 0), ('charged_steps', 9), ('charged_steps', True),
                           ('verified', True)]:
            invalid = copy.deepcopy(rows)
            invalid[0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                summarize(invalid)

    def test_nonfinite_nonpositive_cpu_and_invalid_bootstrap_settings_rejected(self):
        for cpu in (float('nan'), float('inf'), -float('inf'), 0., -1., True):
            rows = rows_for()
            rows[0]['cpu_seconds'] = cpu
            with self.subTest(cpu=cpu), self.assertRaises(ValueError):
                summarize(rows)
        for options in ({'draws': 0}, {'draws': True}, {'seed': -1}, {'seed': True}):
            with self.assertRaises(ValueError):
                summarize(rows_for(), **options)


if __name__ == '__main__':
    unittest.main()
