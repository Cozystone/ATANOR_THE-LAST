"""Generic delayed-payoff tree: no filesystem action-effect knowledge."""
import unittest

from packages.action_core.model import Forecast
from packages.action_core.planner import Goal, choose
from packages.action_core.world import Action, Frame


class DelayedPayoff:
    def __init__(self):
        self.calls = []

    def predict(self, frame, actions, history=()):
        self.calls.append((frame.sizes[0], tuple(actions)))
        results = []
        for action in actions:
            # Sizes encode arbitrary test states, unrelated to real body effects.
            if frame.sizes[0] == 0.:
                probability, state = (.3, .1) if action.op == 'branch_a' else (.05, .2)
            elif frame.sizes[0] == .2:
                probability, state = .99, .3
            else:
                probability, state = .31, .3
            prediction = Forecast([[1. - probability, probability, 0.]], [state],
                                  [[probability]], [[0.]], ('n0',))
            results.append((prediction, 0.))
        return results


class SearchCoverageTests(unittest.TestCase):
    def setUp(self):
        self.frame = Frame([0], [0.], [[0.]], [[0.]], ('n0',))
        self.actions = [Action('branch_a', ('n0',)), Action('branch_b', ('n0',))]
        self.goal = Goal('generic-delayed-goal', (('n0', 1),))

    def test_root_coverage_keeps_delayed_payoff_branch_that_narrow_beam_loses(self):
        ordinary = DelayedPayoff()
        narrow_action, _, narrow_nodes = choose(ordinary, self.frame, self.goal, self.actions,
                                               horizon=2, width=1, limit=6, cover_root=False)
        covered = DelayedPayoff()
        action, first_prediction, nodes = choose(covered, self.frame, self.goal, self.actions,
                                                 horizon=2, width=1, limit=6, cover_root=True)
        self.assertEqual(narrow_action, self.actions[0])
        self.assertEqual(narrow_nodes, 4)
        self.assertEqual(action, self.actions[1])
        self.assertIn(action, self.actions)
        self.assertAlmostEqual(self.goal.probability(first_prediction), .05)
        self.assertEqual(nodes, len(self.actions) + len(self.actions) ** 2)
        self.assertEqual(sum(len(actions) for _, actions in covered.calls), nodes)
        self.assertEqual([state for state, _ in covered.calls], [0., .1, .2])

    def test_insufficient_full_coverage_budget_rejected_before_any_prediction(self):
        for limit in (1, 2, 5):
            with self.subTest(limit=limit):
                model = DelayedPayoff()
                with self.assertRaises(ValueError):
                    choose(model, self.frame, self.goal, self.actions,
                           horizon=2, width=1, limit=limit, cover_root=True)
                self.assertEqual(model.calls, [])

    def test_third_depth_does_not_overrun_budget_consumed_by_root_coverage(self):
        model = DelayedPayoff()
        action, _, nodes = choose(model, self.frame, self.goal, self.actions,
                                  horizon=3, width=1, limit=6, cover_root=True)
        self.assertEqual(action, self.actions[1])
        self.assertEqual(nodes, 6)
        self.assertEqual(sum(len(actions) for _, actions in model.calls), 6)
        self.assertEqual(len(model.calls), 3)

    def test_coverage_is_not_required_for_single_depth_search(self):
        model = DelayedPayoff()
        action, _, nodes = choose(model, self.frame, self.goal, self.actions,
                                  horizon=1, width=1, limit=2, cover_root=True)
        self.assertEqual(action, self.actions[0])
        self.assertEqual(nodes, 2)


if __name__ == '__main__':
    unittest.main()
