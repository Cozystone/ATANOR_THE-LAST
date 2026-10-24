"""Generic soft-cost tests; test actions encode no filesystem effect rules."""
import copy
import unittest
from unittest.mock import patch

from packages.action_core.model import Forecast
from packages.action_core.planner import Goal, choose
from packages.action_core.world import Action, Frame
from packages.action_core.worker import Client


class Predictor:
    def __init__(self, *, delayed=False):
        self.calls = []
        self.delayed = delayed

    def predict(self, frame, actions, history=()):
        self.calls.append(tuple(actions))
        forecasts = []
        for action in actions:
            if self.delayed:
                probability = (.99 if frame.sizes[0] == .1 else .96) if isinstance(frame, Forecast) else .1
            else:
                probability = .6 if action.op == 'option_a' else .55
            marker = .1 if action.op == 'option_a' else .2
            future = Forecast([[1-probability, probability, 0.]], [marker],
                              [[probability]], [[0.]], ('n0',))
            forecasts.append((future, 0.))
        return forecasts


class RevisitTests(unittest.TestCase):
    def setUp(self):
        self.frame = Frame([0], [0.], [[0.]], [[0.]], ('n0',))
        self.actions = [Action('option_a', ('n0',)), Action('option_b', ('n0',))]
        self.goal = Goal('goal', (('n0', 1),))
        self.history = [(copy.deepcopy(self.frame), self.actions[0])]

    def choose(self, model, **overrides):
        arguments = dict(horizon=1, width=1, limit=2, uncertainty_weight=0.)
        arguments.update(overrides)
        return choose(model, self.frame, self.goal, self.actions, self.history, **arguments)

    def test_default_and_explicit_zero_are_identical(self):
        implicit, explicit = Predictor(), Predictor()
        left, right = self.choose(implicit), self.choose(explicit, revisit_weight=0.)
        self.assertEqual(left, right)
        self.assertEqual(implicit.calls, explicit.calls)
        self.assertEqual(left[0], self.actions[0])
        self.assertEqual(left[2], 2)

    def test_observed_repeat_can_change_choice_without_prediction_override(self):
        before = copy.deepcopy(self.history)
        action, forecast, nodes = self.choose(Predictor(), revisit_weight=.1)
        self.assertEqual(action, self.actions[1])
        self.assertAlmostEqual(self.goal.probability(forecast), .55)
        self.assertEqual(nodes, 2)
        self.assertEqual(self.history, before)

    def test_full_observation_match_required_not_just_kinds(self):
        self.history = [(Frame([0], [.01], [[0.]], [[0.]], ('n0',)), self.actions[0])]
        action, _, _ = self.choose(Predictor(), revisit_weight=10.)
        self.assertEqual(action, self.actions[0])

    def test_forecast_history_is_not_an_observed_revisit(self):
        imagined = Forecast([[1., 0., 0.]], [0.], [[0.]], [[0.]], ('n0',))
        self.history = [(imagined, self.actions[0])]
        action, _, _ = self.choose(Predictor(), revisit_weight=10.)
        self.assertEqual(action, self.actions[0])
        # Imagined current state cannot confer observation authority either.
        action, _, _ = choose(Predictor(), imagined, self.goal, self.actions,
                              [(self.frame, self.actions[0])], horizon=1, limit=2, revisit_weight=10.)
        self.assertEqual(action, self.actions[0])

    def test_repeat_count_is_accumulated(self):
        once = self.choose(Predictor(), revisit_weight=.03)[0]
        self.history *= 2
        twice = self.choose(Predictor(), revisit_weight=.03)[0]
        self.assertEqual(once, self.actions[0])
        self.assertEqual(twice, self.actions[1])

    def test_deeper_optimism_cannot_erase_first_action_cost_or_ban_branches(self):
        plain, penalized = Predictor(delayed=True), Predictor(delayed=True)
        baseline = self.choose(plain, horizon=2, cover_root=True, limit=6)
        changed = self.choose(penalized, horizon=2, cover_root=True, limit=6, revisit_weight=.1)
        self.assertEqual(baseline[0], self.actions[0])
        self.assertEqual(changed[0], self.actions[1])
        self.assertEqual(baseline[2], 6)
        self.assertEqual(changed[2], 6)
        self.assertEqual(sum(map(len, penalized.calls)), 6)
        self.assertTrue(all(set(call) == set(self.actions) for call in penalized.calls))

    def test_soft_cost_never_excludes_the_only_legal_action(self):
        action, _, nodes = choose(Predictor(), self.frame, self.goal, [self.actions[0]],
                                  self.history, horizon=2, limit=2, revisit_weight=100.)
        self.assertEqual(action, self.actions[0])
        self.assertEqual(nodes, 2)

    def test_invalid_weights_rejected_before_model_or_process(self):
        for value in (-.1, float('nan'), float('inf'), -float('inf'), None, '0.1', True):
            with self.subTest(value=value):
                model = Predictor()
                with self.assertRaises(ValueError):
                    self.choose(model, revisit_weight=value)
                self.assertEqual(model.calls, [])
                with patch('packages.action_core.worker.subprocess.Popen') as spawn:
                    with self.assertRaises(ValueError):
                        Client(revisit_weight=value)
                    spawn.assert_not_called()

    def test_client_forwards_opt_in_weight_and_defaults_off(self):
        for value in (None, .1):
            with self.subTest(value=value), patch('packages.action_core.worker.subprocess.Popen'), \
                    patch.object(Client, '_request', return_value=True) as request:
                client = Client(**({} if value is None else {'revisit_weight': value}))
                try:
                    expected = 0. if value is None else value
                    action = Action('mkdir', ('n0',))
                    forecast = Forecast([[.4, .6, 0.]], [.1], [[.6]], [[0.]], ('n0',))
                    request.return_value = {'action': action.to_dict(), 'forecast': forecast.to_dict(), 'nodes': 1}
                    client.choose(self.frame, self.goal, [action], self.history)
                    self.assertEqual(client.budget['revisit_weight'], expected)
                    self.assertEqual(request.call_args.kwargs['budget']['revisit_weight'], expected)
                finally:
                    client.close()


if __name__ == '__main__':
    unittest.main()
