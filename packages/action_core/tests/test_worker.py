from pathlib import Path
import tempfile
import unittest

from packages.action_core.planner import Goal
from packages.action_core.worker import Client
from packages.action_core.retrieval import Retrieval
from packages.action_core.world import Action, Sandbox


class WorkerTests(unittest.TestCase):
    def test_retrieval_roundtrip_uses_same_worker_and_checkpoint_boundary(self):
        with tempfile.TemporaryDirectory(prefix='atanor-retrieval-worker-') as tmp:
            body = Sandbox(Path(tmp) / 'body', ['a', 'b'], {'a': b'actual'}, {'n0'})
            model = Retrieval()
            before = body.observe()
            action = Action('copy', ('n0', 'n1'))
            body.step(action)
            model.learn('observed', before, action, body.observe(), [])
            with Client(limit=32) as client:
                client.restore(model.snapshot())
                checkpoint = client.snapshot()
                self.assertEqual(checkpoint['algorithm'], 'retrieval')
                self.assertEqual(checkpoint, model.snapshot())
                chosen, forecast, count = client.choose(before, Goal('equal', equal=(('n0', 'n1'),)), body.actions())
                self.assertIn(chosen, body.actions())
                self.assertGreater(count, 0)

    def test_roundtrip_forecast_learning_and_reopen(self):
        with tempfile.TemporaryDirectory(prefix='atanor-worker-') as tmp:
            body = Sandbox(Path(tmp) / 'body', ['ref', 'p', 'p/out'], {'ref': b'hello'}, {'n0'})
            before, goal = body.observe(), Goal('target', (('n2', 1),), (('n0', 'n2'),))
            with Client(seed=7, updates=1, limit=32) as first:
                a, f, used = first.choose(before, goal, body.actions())
                self.assertIn(a, body.actions())
                self.assertLessEqual(used, 32)
                body.step(a)
                self.assertTrue(first.learn('one', before, a, body.observe(), []))
                self.assertFalse(first.learn('one', before, a, body.observe(), []))
                snapshot = first.snapshot()
                expected = first.choose(body.observe(), goal, body.actions(), [(before, a)])
            with Client(seed=999, updates=1, limit=32) as second:
                second.restore(snapshot)
                actual = second.choose(body.observe(), goal, body.actions(), [(before, a)])
                self.assertEqual(actual[0], expected[0])
                self.assertEqual(actual[1].to_dict(), expected[1].to_dict())
                self.assertEqual(actual[2], expected[2])

    def test_extra_authority_action_is_not_accepted(self):
        with Client(updates=1) as worker:
            with self.assertRaises(ValueError):
                worker._request('learn', event_id='forgery', before={}, after={}, history=[],
                                action={'op': 'mkdir', 'args': ['n0'], 'verified': True})


if __name__ == '__main__':
    unittest.main()
