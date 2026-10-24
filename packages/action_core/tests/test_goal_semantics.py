from pathlib import Path
import tempfile
import unittest

from packages.action_core.model import Forecast
from packages.action_core.planner import Goal
from packages.action_core.world import Sandbox


def forecast(kinds, equal):
    n = len(kinds)
    return Forecast(kinds, [0.] * n, equal, [[0.] * n for _ in range(n)],
                    tuple(f'n{i}' for i in range(n)))


class GoalSemanticsTests(unittest.TestCase):
    def test_impossible_one_hot_equality_does_not_score_success(self):
        goal = Goal('g', (('n1', 1),), (('n0', 'n1'),))
        for impossible_source in ([1., 0., 0.], [0., 0., 1.]):
            prediction = forecast([impossible_source, [0., 1., 0.]], [[1., 1.], [1., 1.]])
            self.assertEqual(goal.probability(prediction), 0.)
        equality_only = Goal('eq', equal=(('n0', 'n1'),))
        prediction = forecast([[0., 1., 0.], [1., 0., 0.]], [[1., 1.], [1., 1.]])
        self.assertEqual(equality_only.probability(prediction), 0.)

    def test_valid_one_hot_and_native_receipts_agree(self):
        with tempfile.TemporaryDirectory(prefix='atanor_goal_semantics_') as temp:
            body = Sandbox(Path(temp) / 'body', ['a', 'b', 'different', 'directory', 'absent'],
                           {'a': b'same', 'b': b'same', 'different': b'other', 'directory': None})
            observed, native = body.observe(), body.evidence()
            for left in body.handles:
                for right in body.handles:
                    goal = Goal('eq', equal=((left, right),))
                    self.assertEqual(goal.probability(observed), float(goal.holds(native)))
            for handle in body.handles:
                for kind in (0, 1, 2):
                    goal = Goal('kind', ((handle, kind),))
                    self.assertEqual(goal.probability(observed), float(goal.holds(native)))

    def test_duplicate_explicit_implicit_and_reversed_literals_count_once(self):
        prediction = forecast([[.2, .8, 0.], [.5, .5, 0.]], [[.8, .6], [.6, .5]])
        unique = Goal('g', (('n1', 1),), (('n0', 'n1'),))
        repeated = Goal('g', (('n0', 1), ('n1', 1), ('n1', 1)),
                        (('n0', 'n1'), ('n1', 'n0'), ('n0', 'n1')))
        self.assertAlmostEqual(unique.probability(prediction), .8 * .5 * .6)
        self.assertAlmostEqual(unique.probability(prediction), repeated.probability(prediction))
        restored = Goal.from_dict(repeated.to_dict())
        self.assertEqual(restored, repeated)
        reflexive = Goal('self', equal=(('n0', 'n0'), ('n0', 'n0')))
        self.assertAlmostEqual(reflexive.probability(prediction), .8)

    def test_soft_score_bounds_do_not_claim_joint_calibration(self):
        for source in (0., .1, .8, 1.):
            for target in (0., .3, 1.):
                for equal in (0., .6, 1.):
                    prediction = forecast([[1-source, source, 0.], [1-target, target, 0.]],
                                          [[source, equal], [equal, target]])
                    score = Goal('g', equal=(('n0', 'n1'),)).probability(prediction)
                    self.assertGreaterEqual(score, 0.)
                    self.assertLessEqual(score, min(source, target, equal) + 1e-12)

    def test_contradictions_malformed_goals_and_fake_native_metadata_rejected(self):
        for kinds, equal in [((('n0', 0), ('n0', 1)), ()),
                             ((('n0', 2),), (('n0', 'n1'),)),
                             ((('n0', True),), ()), ((('n0', 1),), ('ab',))]:
            with self.assertRaises(ValueError):
                Goal('g', kinds, equal)
        with self.assertRaises(ValueError):
            Goal.from_dict({'id': 'g', 'kinds': [['n0', 1]], 'equal': [], 'verified': True})
        goal = Goal('g', equal=(('n0', 'n1'),))
        self.assertFalse(goal.holds({'n0': {'kind': 1, 'sha256': 'x' * 64},
                                     'n1': {'kind': 1, 'sha256': 'x' * 64}}))
        self.assertFalse(goal.holds({'n0': {'kind': True, 'sha256': 'a' * 64},
                                     'n1': {'kind': 1, 'sha256': 'a' * 64}}))
        self.assertFalse(goal.holds({}))


if __name__ == '__main__':
    unittest.main()
