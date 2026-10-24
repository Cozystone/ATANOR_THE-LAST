from pathlib import Path
import tempfile
import unittest

from packages.action_core.episode import Episode
from packages.action_core.planner import Goal
from packages.action_core.tests.test_episode import FakeClient
from packages.action_core.world import Action, Sandbox


class AttachTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='atanor-attach-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.config = {'paths': ['ref', 'folder', 'folder/out'],
                       'initial': {'ref': b'original'}, 'protected': {'n0'}}
        self.body = Sandbox(self.base / 'body', **self.config)
        self.goal = Goal('copy', equal=(('n0', 'n2'),))

    def test_attach_preserves_existing_and_missing_state(self):
        self.body.step(Action('mkdir', ('n1',)))
        original = self.body.evidence()
        attached = Sandbox.attach(self.body.root, self.config['paths'], {'n0'})
        self.assertEqual(attached.evidence(), original)
        self.assertFalse((self.body.root / 'folder/out').exists())
        with self.assertRaises(ValueError):
            attached.step(Action('empty', ('n0',)))
        self.assertEqual(attached.evidence(), original)

    def test_attach_rejects_missing_root_bad_paths_and_unknown_protection(self):
        for root, paths, protected in [
                (self.base / 'absent', ['file'], set()),
                (Path(tempfile.gettempdir()), ['file'], set()),
                (self.body.root, ['../escape'], set()),
                (self.body.root, ['ref', 'REF'], set()),
                (self.body.root, ['ref'], {'n9'})]:
            with self.subTest(root=root, paths=paths), self.assertRaises(ValueError):
                Sandbox.attach(root, paths, protected)
        self.assertFalse((self.base / 'absent').exists())

    def test_new_client_and_new_body_resume_without_reinitialization(self):
        path = self.base / 'episode.sqlite'
        first = FakeClient([Action('mkdir', ('n1',))])
        ep = Episode(path, self.body, self.goal, first, config=self.config, budget=2)
        ep.step()
        ep.close()
        second = FakeClient([Action('copy', ('n0', 'n2'))])
        attached = Sandbox.attach(self.body.root, self.config['paths'], {'n0'})
        resumed = Episode(path, attached, self.goal, second, config=self.config, budget=2)
        self.assertEqual(second.revision, 1)
        result = resumed.run()
        resumed.close()
        self.assertTrue(result['completed'])
        self.assertEqual(result['steps'], 2)
        self.assertEqual(second.calls, 1)

    def test_native_change_between_processes_does_not_get_trusted(self):
        path = self.base / 'episode.sqlite'
        ep = Episode(path, self.body, self.goal, FakeClient([]), config=self.config, budget=2)
        ep.close()
        (self.body.root / 'ref').write_bytes(b'external-change')
        second = FakeClient([Action('mkdir', ('n1',))])
        attached = Sandbox.attach(self.body.root, self.config['paths'], {'n0'})
        resumed = Episode(path, attached, self.goal, second, config=self.config, budget=2)
        result = resumed.run()
        resumed.close()
        self.assertEqual(result['reason'], 'observation_mismatch')
        self.assertEqual(second.calls, 0)
        self.assertFalse((self.body.root / 'folder').exists())


if __name__ == '__main__':
    unittest.main()
