import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

from packages.action_core.model import DIM, Forecast, Learner, features, balanced_loss
from packages.action_core.planner import Goal, choose
from packages.action_core.world import Action, Frame, Sandbox


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='atanor-model-')
        self.addCleanup(self.temp.cleanup)
        self.body = Sandbox(Path(self.temp.name) / 'body', ['ref', 'p', 'p/out', 'extra'],
                            {'ref': b'actual bytes'}, protected={'n0'})
        self.model = Learner(seed=31, updates=1)
        self.frame = self.body.observe()

    def test_features_include_parent_context_and_no_names(self):
        x = features(self.frame, Action('copy', ('n0', 'n2')))
        self.assertEqual(x.shape, (4, DIM))
        self.assertEqual(x[2, 7], 1)  # absent direct parent kind
        self.body.step(Action('mkdir', ('n1',)))
        y = features(self.body.observe(), Action('copy', ('n0', 'n2')))
        self.assertEqual(y[2, 9], 1)  # directory parent, not a success precondition bit

    def test_change_balance_uses_actual_outcome_strata(self):
        losses = torch.tensor([10., 0., 0., 0.])
        self.assertEqual(balanced_loss(losses, torch.tensor([True, False, False, False])).item(), 5.)
        self.assertEqual(balanced_loss(losses, torch.zeros(4, dtype=torch.bool)).item(), 2.5)
        model = Learner(seed=2, updates=1, change_balanced=True)
        action = Action('mkdir', ('n1',))
        self.body.step(action)
        model.learn('change', self.frame, action, self.body.observe(), [])
        restored = Learner.restore(json.loads(json.dumps(model.snapshot())))
        self.assertTrue(restored.change_balanced)
        self.assertEqual(model.snapshot(), restored.snapshot())

    def test_latest_no_change_is_used_within_unchanged_update_budget(self):
        model = Learner(seed=2, updates=3, change_balanced=True, latest_update=True)
        action = Action('mkdir', ('n1',))
        self.body.step(action)
        after = self.body.observe()
        model.learn('changed', self.frame, action, after, [])
        model.learn('counterexample', after, action, after, [(self.frame, action)])
        self.assertIs(model._sample_update(0, [model.replay[0]]), model.replay[-1])
        self.assertEqual(model.updates, 3)
        restored = Learner.restore(json.loads(json.dumps(model.snapshot())))
        self.assertTrue(restored.latest_update)
        self.assertEqual(model.snapshot(), restored.snapshot())

    def test_forecast_is_not_evidence_or_learning_input(self):
        predicted, variance = self.model.predict(self.frame, self.body.actions()[:1])[0]
        self.assertIs(type(predicted), Forecast)
        self.assertGreaterEqual(variance, 0)
        with self.assertRaises(ValueError):
            Frame.from_dict(predicted.to_dict())
        with self.assertRaises(ValueError):
            self.model.learn('forged', self.frame, self.body.actions()[0], predicted, [])
        with self.assertRaises(ValueError):
            Forecast.from_dict({**predicted.to_dict(), 'verified': True})
        self.assertEqual(self.model.revision, 0)

    def test_prediction_nonmutating_variable_count_and_restore(self):
        actions = self.body.actions()
        initial = json.dumps(self.model.snapshot(), sort_keys=True)
        one = self.model.predict(self.frame, actions)
        self.assertEqual(initial, json.dumps(self.model.snapshot(), sort_keys=True))
        restored = Learner.restore(json.loads(initial))
        two = restored.predict(self.frame, actions)
        self.assertEqual([(f.to_dict(), u) for f, u in one], [(f.to_dict(), u) for f, u in two])
        other = Sandbox(Path(self.temp.name) / 'other', ['a', 'b'], {'a': b'x'})
        self.assertEqual(len(self.model.predict(other.observe(), other.actions())[0][0].kinds), 2)

    def test_actual_learning_is_idempotent_and_restore_preserves_next_update(self):
        action = Action('mkdir', ('n1',))
        self.body.step(action)
        after = self.body.observe()
        self.assertTrue(self.model.learn('real-1', self.frame, action, after, []))
        self.assertFalse(self.model.learn('real-1', self.frame, action, after, []))
        restored = Learner.restore(json.loads(json.dumps(self.model.snapshot())))
        for m in (self.model, restored):
            m.learn('real-2', after, action, after, [(self.frame, action)])
        self.assertEqual(self.model.snapshot(), restored.snapshot())

    def test_planning_budget_and_independent_native_goal(self):
        goal = Goal('copy-goal', (('n2', 1),), (('n0', 'n2'),))
        chosen, predicted, used = choose(self.model, self.frame, goal, self.body.actions(), limit=25)
        self.assertIn(chosen, self.body.actions())
        self.assertLessEqual(used, 25)
        self.assertFalse(goal.holds(self.body.evidence()))
        self.body.step(Action('mkdir', ('n1',)))
        self.body.step(Action('empty', ('n2',)))
        self.assertFalse(goal.holds(self.body.evidence()))
        self.body.step(Action('copy', ('n0', 'n2')))
        self.assertTrue(goal.holds(self.body.evidence()))


if __name__ == '__main__':
    unittest.main()
