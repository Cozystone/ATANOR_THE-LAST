import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from packages.action_core.fresh_eval import new_cases, decode, run
from packages.action_core.planner import Goal
from packages.action_core.world import Sandbox


class FreshHarnessTests(unittest.TestCase):
    def test_fixed_strata_and_native_unsolved_conditions_without_policy_execution(self):
        cases = new_cases(17)  # UNIT fixture seed, not the future cohort seed.
        self.assertEqual(len(cases), 64)
        self.assertEqual(cases, new_cases(17))
        with tempfile.TemporaryDirectory(prefix='atanor-fresh-fixture-') as tmp:
            for c in cases:
                body = Sandbox(Path(tmp) / str(c['case']), **decode(c['config']))
                self.assertFalse(Goal.from_dict(c['goal']).holds(body.evidence()))
                self.assertLessEqual(len(body.actions()) * (1 + len(body.actions())), 4096)
                self.assertTrue(4 <= len(body.handles) <= 7)
        for stratum in range(4):
            rows = [c for c in cases if c['stratum'] == stratum]
            self.assertEqual(len(rows), 16)
            self.assertEqual(sum(c['missing_parent'] for c in rows), 8)

    def test_wrong_out_of_band_digest_never_starts_attempt_or_worker(self):
        with tempfile.TemporaryDirectory(prefix='atanor-prereg-mismatch-') as tmp:
            (Path(tmp) / 'preregistration.json').write_text('{}', encoding='utf-8')
            with patch('packages.action_core.fresh_eval.Client') as worker:
                with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                    run(tmp, 'forged')
                worker.assert_not_called()
            self.assertFalse((Path(tmp) / 'attempt.lock').exists())


if __name__ == '__main__':
    unittest.main()
