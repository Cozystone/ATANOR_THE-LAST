import copy
import unittest

from packages.action_core.transfer_metrics import ARMS, summarize


def fixture():
    return [{'case': case, 'arm': arm, 'success': True,
             'charged_steps': 2 if arm == 'warm' else 6,
             'cpu_seconds': 1. if arm == 'warm' else 2.}
            for case in range(64) for arm in ARMS]


class TransferMetricTests(unittest.TestCase):
    def test_known_positive_counts_and_bounds(self):
        result = summarize(fixture())
        self.assertEqual(result['verdict'], 'ADAPTATION_LIFT_CONFIRMED')
        self.assertTrue(all(result['gates'].values()))
        self.assertEqual(result['totals']['warm']['charged_steps'], 128)
        for comparison in result['comparisons'].values():
            self.assertEqual(comparison['success_difference'], 0.)
            self.assertEqual(comparison['action_ratio_ucb95'], 1 / 3)
            self.assertEqual(comparison['cpu_ratio_ucb95'], .5)

    def test_old_knowledge_only_cannot_pass_online_ablation(self):
        rows = fixture()
        for row in rows:
            if row['arm'] == 'warm_frozen':
                row['charged_steps'] = 2
        result = summarize(rows)
        self.assertEqual(result['verdict'], 'NO_ADAPTATION_LIFT')
        self.assertFalse(result['gates']['online_weight_revision_beyond_old_knowledge'])

    def test_success_regression_and_cpu_are_not_hidden_by_action_gain(self):
        for reason in ('success', 'cpu'):
            rows = fixture()
            for row in rows:
                if row['arm'] == 'warm':
                    if reason == 'success' and row['case'] < 8:
                        row['success'], row['charged_steps'] = False, 8
                    elif reason == 'cpu':
                        row['cpu_seconds'] = 3.
            result = summarize(rows)
            self.assertEqual(result['verdict'], 'REGRESSION')

    def test_paired_permutation_and_heterogeneous_direct_counts(self):
        rows = fixture()
        for row in rows:
            if row['case'] % 2 and row['arm'] == 'warm':
                row['charged_steps'] = 4
        one = summarize(rows)
        self.assertEqual(one, summarize(list(reversed(rows))))
        self.assertEqual(one['comparisons']['retrieval']['action_ratio'], .5)

    def test_missing_duplicate_forged_status_and_failure_undercharge_rejected(self):
        rows = fixture()
        for bad in [rows[:-1], rows + [rows[0]]]:
            with self.assertRaises(ValueError):
                summarize(bad)
        for field, value in [('success', 1), ('cpu_seconds', float('nan')),
                             ('verified', True), ('charged_steps', 0)]:
            bad = copy.deepcopy(rows)
            bad[0][field] = value
            with self.assertRaises(ValueError):
                summarize(bad)
        bad = copy.deepcopy(rows)
        bad[0]['success'] = False
        with self.assertRaises(ValueError):
            summarize(bad)

