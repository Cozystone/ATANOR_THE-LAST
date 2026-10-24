import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from packages.action_core.episode import canonical
from packages.action_core.planner import Goal
from packages.action_core.transfer_dev import ARMS, PLAN
from packages.action_core.transfer_eval import DEADLINE_UNIX, advance_episode, check_deadline, decode, new_cases, prepare, run
from packages.action_core.world import Action, Sandbox


class TransferHarnessTests(unittest.TestCase):
    def test_fixed_deadline_stops_before_next_actual_step(self):
        check_deadline(DEADLINE_UNIX - .001)
        with self.assertRaises(TimeoutError):
            check_deadline(DEADLINE_UNIX)
        class EpisodeStub:
            state = {'stop': None}
            calls = 0
            def step(self):
                self.calls += 1
        episode = EpisodeStub()
        with patch('packages.action_core.transfer_eval.time.time', side_effect=[DEADLINE_UNIX - 1, DEADLINE_UNIX]):
            with self.assertRaises(TimeoutError):
                advance_episode(episode)
        self.assertEqual(episode.calls, 1)

    def test_fixed_test_seed_configs_roundtrip_and_counterbalanced_schedule(self):
        # Exposed test input, NOT the final sampled seed/configurations.
        data = new_cases(123)
        self.assertEqual(data, json.loads(canonical(data)))
        self.assertEqual(data, new_cases(123))
        self.assertEqual([sum(r['stratum'] == s for r in data['cases']) for s in range(4)], [16] * 4)
        self.assertEqual(sorted(row['case'] for row in data['schedule']), list(range(64)))
        self.assertNotEqual([row['case'] for row in data['schedule']], list(range(64)))
        for arm in ARMS:
            for position in range(4):
                self.assertEqual(sum(row['arms'][position] == arm for row in data['schedule']), 16)

    def test_all_initial_native_schemas_fit_unchanged_budget_without_state_pruning(self):
        with tempfile.TemporaryDirectory(prefix='atanor-transfer-harness-test-') as tmp:
            for row in new_cases(123)['cases']:
                config = decode(row['config'])
                body = Sandbox(Path(tmp) / str(row['case']), **config)
                actions = body.actions()
                self.assertEqual(len(actions), 2 * row['objects'] * (row['objects'] - 1))
                self.assertLessEqual(len(actions) * (1 + len(actions)), PLAN['limit'])
                goal = Goal.from_dict(row['goal'])
                self.assertFalse(goal.holds(body.evidence()))
                source = next(h for h, kind in goal.kinds if kind == 0)
                target = next(h for h, kind in goal.kinds if kind == 1)
                for action in [Action('rename', (source, target)), Action('copy', (source, target)),
                               Action('unlink', (source,))]:
                    self.assertIn(action, actions)
                # No action outcome, predicted success or learning is sampled here.

    def test_wrong_independent_digest_does_not_spawn_or_consume_attempt(self):
        with tempfile.TemporaryDirectory(prefix='atanor-transfer-binding-test-') as tmp:
            folder = Path(tmp)
            (folder / 'preregistration.json').write_text('{}', encoding='utf-8')
            (folder / 'receipt.json').write_text('{}', encoding='utf-8')
            with patch('packages.action_core.transfer_eval.Client', side_effect=AssertionError('no worker')):
                with self.assertRaises(ValueError):
                    run(folder, '0' * 64)
                with self.assertRaises(ValueError):
                    prepare(folder, '0' * 64, folder / 'output')
            self.assertFalse((folder / 'attempt.lock').exists())
            self.assertFalse((folder / 'output').exists())
